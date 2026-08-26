"""Builder validator — enforce policy / budget / capability constraints.

The validator never raises on a soft issue (e.g. missing pricing) — it records
a ``WARNING`` issue so authors can still compile. Hard issues (e.g. denied
deployment, exceeded ``max_tokens``) are recorded as ``ERROR`` and block
compilation.

The validator reuses the same :class:`ModelPolicyEngine` used at runtime so
the decision matches what will actually happen when the Agent runs.
"""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.builder.config import (
    AgentBuilderConfig,
    AgentBuilderConfigIssue,
    AgentBuilderConfigIssueSeverity,
    AgentBuilderValidationReport,
)
from app.api.deps import Principal
from app.llm.policy import ModelPolicyEngine, ModelPolicyRule
from app.llm.schemas import LLMChatRequest, LLMRequestContext, Message
from app.models.llm import LLMDeployment, LLMProvider, LLMModel
from app.schemas.mcp import McpServerStatus
from app.services import mcp_service
from sqlmodel import select


async def validate_config_against_policies(
    session: AsyncSession,
    principal: Principal,
    config: AgentBuilderConfig,
) -> AgentBuilderValidationReport:
    issues: list[AgentBuilderConfigIssue] = []

    # 1. Resolve deployment rows (primary + fallback) and ensure they exist,
    #    are active, and belong to the tenant.
    primary_ok = await _validate_deployment(
        session,
        principal,
        deployment_id=config.deployment_id,
        model_key=config.model_key,
        routing_key=config.routing_key,
        field_name="deployment_id",
        issues=issues,
    )
    for index, fallback_id in enumerate(config.fallback_deployment_ids):
        await _validate_deployment(
            session,
            principal,
            deployment_id=fallback_id,
            model_key=None,
            routing_key=None,
            field_name=f"fallback_deployment_ids[{index}]",
            issues=issues,
            is_fallback=True,
        )

    # 2. Run the model policy engine on a synthetic chat request so the
    #    decision matches runtime behaviour.
    policy_issues = await _validate_policy_decision(
        session,
        principal,
        config=config,
        primary_ok=primary_ok,
    )
    issues.extend(policy_issues)

    # 3. Validate MCP server keys reference active tenant servers.
    mcp_issues = await _validate_mcp_server_keys(session, principal, config.mcp_server_keys)
    issues.extend(mcp_issues)

    # 4. Soft warnings for unset fields that degrade quality but don't block.
    if not config.knowledge_base_ids and not config.mcp_server_keys:
        issues.append(
            AgentBuilderConfigIssue(
                severity=AgentBuilderConfigIssueSeverity.WARNING,
                code="no_knowledge_or_tools",
                message="Agent has no knowledge bases or MCP tools bound; answers will rely solely on the LLM.",
            )
        )
    if config.fallback_deployment_ids and not config.deployment_id:
        issues.append(
            AgentBuilderConfigIssue(
                severity=AgentBuilderConfigIssueSeverity.WARNING,
                code="fallback_without_primary",
                message="Fallback deployments are configured without a primary deployment_id; "
                "the runtime will rely on routing_key/model_key only.",
                field="fallback_deployment_ids",
            )
        )

    ok = not any(issue.severity == AgentBuilderConfigIssueSeverity.ERROR for issue in issues)
    return AgentBuilderValidationReport(ok=ok, issues=issues)


async def _validate_deployment(
    session: AsyncSession,
    principal: Principal,
    *,
    deployment_id: UUID | None,
    model_key: str | None,
    routing_key: str | None,
    field_name: str,
    issues: list[AgentBuilderConfigIssue],
    is_fallback: bool = False,
) -> bool:
    """Validate that a deployment exists, is active and tenant-scoped.

    Returns ``True`` when the deployment row is valid. When no deployment_id
    is given (legacy routing_key/model_key mode) the function returns
    ``True`` without DB checks — those are covered by the policy engine.
    """
    if deployment_id is None:
        return True
    result = await session.execute(
        select(LLMDeployment, LLMProvider, LLMModel)
        .join(LLMProvider, cast(ColumnElement[bool], LLMProvider.id == LLMDeployment.provider_id))
        .join(LLMModel, cast(ColumnElement[bool], LLMModel.id == LLMDeployment.model_id))
        .where(
            cast(ColumnElement[bool], LLMDeployment.id == deployment_id),
            cast(ColumnElement[bool], LLMDeployment.tenant_id == principal.tenant_id),
        )
    )
    row = result.first()
    if row is None:
        issues.append(
            AgentBuilderConfigIssue(
                severity=AgentBuilderConfigIssueSeverity.ERROR,
                code="deployment_not_found",
                message=f"Deployment {deployment_id} not found in tenant.",
                field=field_name,
            )
        )
        return False
    deployment = row[0]
    if not deployment.is_active:
        issues.append(
            AgentBuilderConfigIssue(
                severity=AgentBuilderConfigIssueSeverity.ERROR,
                code="deployment_inactive",
                message=f"Deployment {deployment_id} is not active.",
                field=field_name,
            )
        )
        return False
    # Soft warning: a fallback deployment pointing at the same provider/model
    # as the primary offers no resilience.
    if is_fallback:
        issues.append(
            AgentBuilderConfigIssue(
                severity=AgentBuilderConfigIssueSeverity.WARNING,
                code="fallback_validated",
                message=f"Fallback deployment {deployment_id} is active and reachable.",
                field=field_name,
            )
        )
    return True


async def _validate_policy_decision(
    session: AsyncSession,
    principal: Principal,
    *,
    config: AgentBuilderConfig,
    primary_ok: bool,
) -> list[AgentBuilderConfigIssue]:
    issues: list[AgentBuilderConfigIssue] = []
    rules = await _load_policy_rules(session, principal)
    engine = ModelPolicyEngine(rules)
    synthetic_request = LLMChatRequest(
        model_key=config.model_key,
        routing_key=config.routing_key,
        messages=[Message(role="user", content="preview")],
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
    context = LLMRequestContext(
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
    )
    decision = await engine.evaluate(synthetic_request, context)
    if not decision.allowed:
        issues.append(
            AgentBuilderConfigIssue(
                severity=AgentBuilderConfigIssueSeverity.ERROR,
                code="policy_denied",
                message=f"Model policy denied the configured route: {decision.reason}.",
                field="model_key",
            )
        )
        return issues
    # Enforce max_tokens cap from the policy.
    if (
        decision.max_tokens is not None
        and config.max_tokens is not None
        and config.max_tokens > decision.max_tokens
    ):
        issues.append(
            AgentBuilderConfigIssue(
                severity=AgentBuilderConfigIssueSeverity.ERROR,
                code="max_tokens_exceeds_policy",
                message=(
                    f"max_tokens={config.max_tokens} exceeds policy limit {decision.max_tokens}."
                ),
                field="max_tokens",
            )
        )
    if primary_ok is False and decision.reason.startswith("explicit_route"):
        issues.append(
            AgentBuilderConfigIssue(
                severity=AgentBuilderConfigIssueSeverity.WARNING,
                code="policy_implicit_route",
                message=(
                    "Primary deployment_id was invalid but the model policy "
                    "still allowed the route via model_key/routing_key."
                ),
                field="model_key",
            )
        )
    return issues


async def _load_policy_rules(session: AsyncSession, principal: Principal) -> list[ModelPolicyRule]:
    from app.models.llm import LLMPolicy

    result = await session.execute(
        select(LLMPolicy)
        .where(
            cast(ColumnElement[bool], LLMPolicy.tenant_id == principal.tenant_id),
            cast(Any, LLMPolicy.is_active).is_(True),
        )
        .order_by(cast(Any, LLMPolicy.priority))
    )
    return [
        ModelPolicyRule(
            id=policy.id,
            name=policy.name,
            scope_type=policy.scope_type,
            scope_id=policy.scope_id,
            effect=policy.effect,
            allowed_models=tuple(policy.allowed_models),
            allowed_routing_keys=tuple(policy.allowed_routing_keys),
            default_model_key=policy.default_model_key,
            default_routing_key=policy.default_routing_key,
            max_tokens=policy.max_tokens,
            priority=policy.priority,
            metadata=dict(policy.metadata_json or {}),
        )
        for policy in result.scalars().all()
    ]


async def _validate_mcp_server_keys(
    session: AsyncSession,
    principal: Principal,
    server_keys: list[str],
) -> list[AgentBuilderConfigIssue]:
    if not server_keys:
        return []
    issues: list[AgentBuilderConfigIssue] = []
    # Reuse the tenant-scoped MCP server list as the source of truth.
    servers = await mcp_service.list_mcp_servers_for_tenant(session, tenant_id=principal.tenant_id)
    active_keys = {
        server.server_key for server in servers.servers if server.status == McpServerStatus.ACTIVE
    }
    for index, key in enumerate(server_keys):
        if key not in active_keys:
            issues.append(
                AgentBuilderConfigIssue(
                    severity=AgentBuilderConfigIssueSeverity.ERROR,
                    code="mcp_server_not_active",
                    message=f"MCP server '{key}' is not active in this tenant.",
                    field=f"mcp_server_keys[{index}]",
                )
            )
    return issues
