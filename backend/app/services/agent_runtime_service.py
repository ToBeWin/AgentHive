from collections.abc import AsyncIterator
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, TypedDict, cast
from uuid import UUID
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.agents.registry import agent_registry
from app.agents import runtime_diagnostics
from app.api.deps import Principal, is_tenant_admin
from app.core.config import is_development_environment
from app.models.agent_module import AgentInstance, AgentModule, TenantAgentModule
from app.models.base import utc_now
from app.models.channel import ChannelConfig
from app.models.knowledge import KnowledgeBase
from app.models.llm import LLMDeployment, LLMModel, LLMProvider
from app.models.org import Department
from app.models.user import User, UserDepartment
from app.schemas.agents import (
    AgentCatalogEntry,
    AgentCatalogResponse,
    AgentGovernanceTargetItem,
    AgentGovernanceTargetsResponse,
    AgentInstanceCreateRequest,
    AgentInstanceListResponse,
    AgentInstanceResponse,
    AgentInstanceUpdateRequest,
    AgentRunRequest,
    AgentRunResponse,
    WorkbenchAgentKnowledgeBaseSummary,
    WorkbenchAgentInstanceListResponse,
    WorkbenchAgentInstanceResponse,
)
from app.schemas.knowledge import RetrievalTestRequest, RetrievalTestResponse
from app.schemas.license import AgentModuleState, LicenseStatus
from app.schemas.llm import LLMUsageResponse
from app.services.knowledge_service import (
    _can_access_base,
    _get_accessible_base_db,
    run_retrieval_test,
)
from app.services.license_service import ensure_license_capacity, get_license_status_for_tenant
from app.services.audit_service import record_audit_event

MAX_KNOWLEDGE_CONTEXT_SOURCE_CHARS = runtime_diagnostics.MAX_KNOWLEDGE_CONTEXT_SOURCE_CHARS
KNOWLEDGE_CONFIDENCE_HIGH_THRESHOLD = runtime_diagnostics.KNOWLEDGE_CONFIDENCE_HIGH_THRESHOLD
KNOWLEDGE_CONFIDENCE_MEDIUM_THRESHOLD = runtime_diagnostics.KNOWLEDGE_CONFIDENCE_MEDIUM_THRESHOLD
KNOWLEDGE_GUARDRAIL_DEFAULT_MODE = runtime_diagnostics.KNOWLEDGE_GUARDRAIL_DEFAULT_MODE
RUNNABLE_AGENT_INSTANCE_STATUSES = {"active"}
KNOWLEDGE_GUARDRAIL_REQUIRED_KEYWORDS = runtime_diagnostics.KNOWLEDGE_GUARDRAIL_REQUIRED_KEYWORDS


@dataclass(frozen=True)
class AgentRunAuthorization:
    license_gate: str
    licensed: bool | None
    installed: bool | None
    enabled: bool | None
    reason: str


async def list_agent_catalog(
    session: AsyncSession | None = None,
    principal: Principal | None = None,
) -> AgentCatalogResponse:
    module_states = await _catalog_module_states(session, principal)
    return AgentCatalogResponse(
        agents=[
            AgentCatalogEntry(
                **agent.catalog_entry(),
                **cast(
                    dict[str, Any],
                    module_states.get(agent.definition.required_module, _unknown_module_state()),
                ),
            )
            for agent in agent_registry.list_agents()
        ]
    )


async def list_agent_instances(
    session: AsyncSession,
    principal: Principal,
) -> AgentInstanceListResponse:
    try:
        result = await session.execute(
            select(AgentInstance)
            .where(AgentInstance.tenant_id == principal.tenant_id)
            .order_by(cast(Any, AgentInstance.created_at).desc())
        )
    except (OSError, SQLAlchemyError):
        await session.rollback()
        return AgentInstanceListResponse(agents=[])
    department_ids = await _principal_department_ids(session, principal)
    visible_instances = [
        row
        for row in result.scalars().all()
        if _can_read_agent_instance(row, principal, department_ids)
    ]
    model_index = await _active_model_deployment_index(session, principal)
    return AgentInstanceListResponse(
        agents=[_agent_instance_response(row, model_index=model_index) for row in visible_instances]
    )


async def list_workbench_agent_instances(
    session: AsyncSession,
    principal: Principal,
) -> WorkbenchAgentInstanceListResponse:
    try:
        result = await session.execute(
            select(AgentInstance)
            .where(
                AgentInstance.tenant_id == principal.tenant_id,
                AgentInstance.status == "active",
            )
            .order_by(
                cast(Any, AgentInstance.updated_at).desc(), cast(Any, AgentInstance.name).asc()
            )
        )
    except (OSError, SQLAlchemyError):
        await session.rollback()
        return WorkbenchAgentInstanceListResponse(agents=[])
    department_ids = await _principal_department_ids(session, principal)
    visible_instances = [
        row
        for row in result.scalars().all()
        if _can_read_agent_instance(row, principal, department_ids)
    ]
    visible_bases_by_id = await _visible_bound_knowledge_bases_by_id(
        session,
        principal,
        visible_instances,
        department_ids,
    )
    model_index = await _active_model_deployment_index(session, principal)
    return WorkbenchAgentInstanceListResponse(
        agents=[
            _workbench_agent_instance_response(
                row,
                knowledge_bases=[
                    visible_bases_by_id[knowledge_base_id]
                    for knowledge_base_id in _knowledge_base_uuids_from_config(row.config)
                    if knowledge_base_id in visible_bases_by_id
                ],
                model_index=model_index,
            )
            for row in visible_instances
        ]
    )


async def list_agent_governance_targets(
    session: AsyncSession,
    principal: Principal,
) -> AgentGovernanceTargetsResponse:
    try:
        department_ids = await _principal_department_ids(session, principal)
        departments_result = await session.execute(
            select(Department)
            .where(Department.tenant_id == principal.tenant_id)
            .order_by(cast(Any, Department.sort_order).asc(), cast(Any, Department.name).asc())
        )
        users_result = await session.execute(
            select(User)
            .where(
                User.tenant_id == principal.tenant_id,
                cast(Any, User.deleted_at).is_(None),
                cast(Any, User.is_active).is_(True),
            )
            .order_by(cast(Any, User.full_name).asc(), cast(Any, User.email).asc())
        )
        knowledge_result = await session.execute(
            select(KnowledgeBase)
            .where(
                KnowledgeBase.tenant_id == principal.tenant_id,
                cast(Any, KnowledgeBase.deleted_at).is_(None),
                KnowledgeBase.status == "active",
            )
            .order_by(cast(Any, KnowledgeBase.updated_at).desc())
        )
        deployments_result = await session.execute(
            select(LLMDeployment)
            .where(
                LLMDeployment.tenant_id == principal.tenant_id,
                cast(Any, LLMDeployment.is_active).is_(True),
            )
            .order_by(
                cast(Any, LLMDeployment.priority).asc(), cast(Any, LLMDeployment.routing_key).asc()
            )
        )
    except (OSError, SQLAlchemyError):
        await session.rollback()
        return AgentGovernanceTargetsResponse()

    tenant_admin = is_tenant_admin(principal)
    departments = [
        AgentGovernanceTargetItem(
            id=row.id,
            label=row.name,
            description=row.description,
            metadata={
                "parent_id": str(row.parent_id) if row.parent_id else None,
                "sort_order": row.sort_order,
            },
        )
        for row in departments_result.scalars().all()
        if tenant_admin or row.id in department_ids
    ]
    users = [
        AgentGovernanceTargetItem(
            id=row.id,
            label=f"{row.full_name} ({row.email})" if row.full_name else row.email,
            description=row.username,
            metadata={"email": row.email, "username": row.username},
        )
        for row in users_result.scalars().all()
        if tenant_admin or row.id == principal.user_id
    ]
    knowledge_bases = [
        AgentGovernanceTargetItem(
            id=row.id,
            label=f"{row.name} · {row.rag_engine}",
            description=row.description,
            metadata={
                "name": row.name,
                "rag_engine": row.rag_engine,
                "visibility": row.visibility,
                "document_count": row.document_count,
                "status": row.status,
            },
        )
        for row in knowledge_result.scalars().all()
        if _can_access_base(row, principal, department_ids)
    ]
    model_deployments = [
        AgentGovernanceTargetItem(
            id=row.id,
            label=f"{row.routing_key} · {row.deployment_name}",
            description=None,
            metadata={
                "routing_key": row.routing_key,
                "deployment_name": row.deployment_name,
                "model_id": str(row.model_id),
                "provider_id": str(row.provider_id),
                "priority": row.priority,
            },
        )
        for row in deployments_result.scalars().all()
    ]
    return AgentGovernanceTargetsResponse(
        departments=departments,
        users=users,
        knowledge_bases=knowledge_bases,
        model_deployments=model_deployments,
    )


async def create_agent_instance(
    session: AsyncSession,
    principal: Principal,
    payload: AgentInstanceCreateRequest,
    *,
    request_id: str | None = None,
) -> AgentInstanceResponse:
    agent = agent_registry.get(payload.agent_key)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown agent: {payload.agent_key}",
        )
    authorization = await _authorize_agent_run(
        session,
        principal,
        required_module=agent.definition.required_module,
    )
    await ensure_license_capacity(
        session,
        tenant_id=principal.tenant_id,
        resource="agents",
    )
    await _validate_agent_instance_knowledge_config(session, principal, payload.config)
    department_id = await _normalize_agent_instance_department(
        session, principal, payload.visibility, payload.department_id
    )
    owner_user_id = _normalize_agent_instance_owner(principal, payload.owner_user_id)
    slug = payload.slug or _slugify(payload.name)
    await _ensure_agent_slug_available(session, principal.tenant_id, slug)
    now = utc_now()
    instance = AgentInstance(
        tenant_id=principal.tenant_id,
        name=payload.name,
        slug=slug,
        agent_key=payload.agent_key,
        module_key=agent.definition.required_module,
        description=payload.description,
        status="active" if authorization.enabled else "draft",
        visibility=payload.visibility,
        department_id=department_id,
        owner_user_id=owner_user_id,
        model_routing_key=payload.model_routing_key,
        model_key=payload.model_key,
        system_prompt=payload.system_prompt,
        config=dict(payload.config),
        metadata_json=dict(payload.metadata),
        created_by=principal.user_id,
        created_at=now,
        updated_at=now,
    )
    session.add(instance)
    await session.flush()
    await record_audit_event(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        request_id=request_id,
        action="agent.instance.create",
        resource_type="agent_instance",
        resource_id=instance.id,
        details={
            "agent_key": instance.agent_key,
            "module_key": instance.module_key,
            **_agent_license_gate_audit_details(authorization),
            "slug": instance.slug,
            "status": instance.status,
            "visibility": instance.visibility,
        },
    )
    await session.commit()
    await session.refresh(instance)
    return _agent_instance_response(instance)


async def update_agent_instance(
    session: AsyncSession,
    principal: Principal,
    agent_id: UUID,
    payload: AgentInstanceUpdateRequest,
    *,
    request_id: str | None = None,
) -> AgentInstanceResponse:
    instance = await _get_agent_instance(session, principal, agent_id, require_write=True)
    next_visibility = payload.visibility if payload.visibility is not None else instance.visibility
    next_department_id = (
        payload.department_id if payload.department_id is not None else instance.department_id
    )
    next_status = payload.status if payload.status is not None else instance.status
    authorization: AgentRunAuthorization | None = None
    if next_status == "active":
        authorization = await _authorize_agent_run(
            session,
            principal,
            required_module=instance.module_key,
        )
    next_department_id = await _normalize_agent_instance_department(
        session,
        principal,
        next_visibility,
        next_department_id,
    )
    if payload.name is not None:
        instance.name = payload.name
    if payload.description is not None:
        instance.description = payload.description
    if payload.status is not None:
        instance.status = payload.status
    if payload.visibility is not None:
        instance.visibility = payload.visibility
    instance.department_id = next_department_id
    if payload.owner_user_id is not None:
        if not is_tenant_admin(principal) and payload.owner_user_id != principal.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot assign an Agent instance owner outside the current user scope.",
            )
        instance.owner_user_id = payload.owner_user_id
    if payload.model_routing_key is not None:
        instance.model_routing_key = payload.model_routing_key
    if payload.model_key is not None:
        instance.model_key = payload.model_key
    if payload.system_prompt is not None:
        instance.system_prompt = payload.system_prompt
    if payload.config is not None:
        await _validate_agent_instance_knowledge_config(session, principal, payload.config)
        instance.config = dict(payload.config)
    if payload.metadata is not None:
        instance.metadata_json = dict(payload.metadata)
    instance.updated_at = utc_now()
    await record_audit_event(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        request_id=request_id,
        action="agent.instance.update",
        resource_type="agent_instance",
        resource_id=instance.id,
        details={
            "status": instance.status,
            "visibility": instance.visibility,
            **_agent_license_gate_audit_details(authorization),
        },
    )
    await session.commit()
    await session.refresh(instance)
    return _agent_instance_response(instance)


async def get_agent_instance(
    session: AsyncSession,
    principal: Principal,
    agent_id: UUID,
) -> AgentInstanceResponse:
    return _agent_instance_response(
        await _get_agent_instance(session, principal, agent_id, require_write=False)
    )


async def run_agent(
    session: AsyncSession,
    agent_key: str,
    payload: AgentRunRequest,
    principal: Principal,
    *,
    request_id: str | None = None,
) -> AgentRunResponse:
    agent = agent_registry.get(agent_key)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown agent: {agent_key}",
        )
    authorization = await _authorize_agent_run(
        session,
        principal,
        required_module=agent.definition.required_module,
    )
    payload = await _canonicalize_agent_governance_context(session, payload, principal)
    payload = await _apply_agent_instance_defaults(
        session,
        payload,
        principal,
        agent_key=agent_key,
        required_module=agent.definition.required_module,
    )
    payload = await _canonicalize_agent_governance_context(session, payload, principal)
    greeting_response = _customer_service_greeting_response(
        agent_key=agent_key,
        payload=payload,
        request_id=request_id,
        required_module=agent.definition.required_module,
    )
    if greeting_response is not None:
        knowledge_sources: list[dict[str, object]] = []
        knowledge_diagnostics: dict[str, object] = {
            "enabled": False,
            "reason": "greeting_intent",
            "guardrail": {
                "mode": "off",
                "triggered": False,
                "skipped_model_call": True,
                "reason": "greeting_intent",
            },
        }
        response = greeting_response
    else:
        (
            enriched_payload,
            knowledge_sources,
            knowledge_diagnostics,
        ) = await _enrich_with_knowledge_context(
            session,
            payload,
            principal,
            agent_key=agent_key,
            request_id=request_id,
        )
        guardrail = _knowledge_guardrail_decision(enriched_payload, knowledge_diagnostics)
        knowledge_diagnostics = {
            **knowledge_diagnostics,
            "guardrail": guardrail,
        }
        if guardrail["triggered"]:
            response = _knowledge_guardrail_response(
                agent_key=agent_key,
                payload=enriched_payload,
                request_id=request_id,
                required_module=agent.definition.required_module,
                knowledge_diagnostics=knowledge_diagnostics,
            )
        else:
            enriched_payload = await _enrich_with_mcp_tools(
                session,
                enriched_payload,
                principal,
            )
            response = await agent.run(
                enriched_payload,
                principal,
                request_id=request_id,
                session=session,
            )
    merged_sources = _dedupe_sources([*response.sources, *knowledge_sources])
    final_metadata = {
        **response.metadata,
        "license_gate": authorization.license_gate,
        "license_gate_reason": authorization.reason,
        "licensed": authorization.licensed,
        "installed": authorization.installed,
        "enabled": authorization.enabled,
        "agent_instance": _agent_instance_diagnostics_from_context(payload.context),
        "knowledge": knowledge_diagnostics,
        "mcp": payload.context.get("mcp") if isinstance(payload.context, dict) else None,
    }
    final_response = response.model_copy(
        update={
            "sources": merged_sources,
            "metadata": final_metadata,
        }
    )
    final_response.metadata["runtime_summary"] = _agent_run_runtime_summary(final_response)
    _augment_runtime_summary_with_mcp(final_response)
    await _record_agent_run_audit(
        session,
        principal=principal,
        agent_key=agent_key,
        payload=payload,
        response=final_response,
        authorization=authorization,
        request_id=request_id or final_response.request_id,
    )
    return final_response


async def run_agent_stream(
    session: AsyncSession,
    agent_key: str,
    payload: AgentRunRequest,
    principal: Principal,
    *,
    request_id: str | None = None,
) -> AsyncIterator[dict[str, object]]:
    """Streaming variant of :func:`run_agent`.

    Reuses the same authorization, governance, knowledge enrichment, and
    guardrail pipeline. Yields ``{"type": "delta", "content": "..."}`` events
    as the LLM emits content, then a single
    ``{"type": "done", "response": AgentRunResponse}`` event with the full
    response (metadata merged identically to ``run_agent``).

    Agents that do not implement ``run_stream`` fall back to ``run`` and emit
    a single delta containing the complete answer.
    """
    agent = agent_registry.get(agent_key)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown agent: {agent_key}",
        )
    authorization = await _authorize_agent_run(
        session,
        principal,
        required_module=agent.definition.required_module,
    )
    payload = await _canonicalize_agent_governance_context(session, payload, principal)
    payload = await _apply_agent_instance_defaults(
        session,
        payload,
        principal,
        agent_key=agent_key,
        required_module=agent.definition.required_module,
    )
    payload = await _canonicalize_agent_governance_context(session, payload, principal)

    greeting_response = _customer_service_greeting_response(
        agent_key=agent_key,
        payload=payload,
        request_id=request_id,
        required_module=agent.definition.required_module,
    )

    if greeting_response is not None:
        knowledge_sources: list[dict[str, object]] = []
        knowledge_diagnostics: dict[str, object] = {
            "enabled": False,
            "reason": "greeting_intent",
            "guardrail": {
                "mode": "off",
                "triggered": False,
                "skipped_model_call": True,
                "reason": "greeting_intent",
            },
        }
        yield {"type": "delta", "content": greeting_response.answer}
        final_response = _merge_agent_stream_metadata(
            greeting_response,
            payload=payload,
            authorization=authorization,
            knowledge_sources=knowledge_sources,
            knowledge_diagnostics=knowledge_diagnostics,
        )
        await _record_agent_run_audit(
            session,
            principal=principal,
            agent_key=agent_key,
            payload=payload,
            response=final_response,
            authorization=authorization,
            request_id=request_id or final_response.request_id,
        )
        yield {"type": "done", "response": final_response}
        return

    (
        enriched_payload,
        knowledge_sources,
        knowledge_diagnostics,
    ) = await _enrich_with_knowledge_context(
        session,
        payload,
        principal,
        agent_key=agent_key,
        request_id=request_id,
    )
    guardrail = _knowledge_guardrail_decision(enriched_payload, knowledge_diagnostics)
    knowledge_diagnostics = {
        **knowledge_diagnostics,
        "guardrail": guardrail,
    }

    if guardrail["triggered"]:
        guardrail_response = _knowledge_guardrail_response(
            agent_key=agent_key,
            payload=enriched_payload,
            request_id=request_id,
            required_module=agent.definition.required_module,
            knowledge_diagnostics=knowledge_diagnostics,
        )
        yield {"type": "delta", "content": guardrail_response.answer}
        final_response = _merge_agent_stream_metadata(
            guardrail_response,
            payload=enriched_payload,
            authorization=authorization,
            knowledge_sources=knowledge_sources,
            knowledge_diagnostics=knowledge_diagnostics,
        )
        await _record_agent_run_audit(
            session,
            principal=principal,
            agent_key=agent_key,
            payload=enriched_payload,
            response=final_response,
            authorization=authorization,
            request_id=request_id or final_response.request_id,
        )
        yield {"type": "done", "response": final_response}
        return

    enriched_payload = await _enrich_with_mcp_tools(
        session,
        enriched_payload,
        principal,
    )

    if hasattr(agent, "run_stream"):
        async for event in agent.run_stream(
            enriched_payload,
            principal,
            request_id=request_id,
            session=session,
        ):
            if event.get("type") == "delta":
                yield event
            elif event.get("type") == "done":
                base_response = event.get("response")
                if base_response is None:
                    continue
                final_response = _merge_agent_stream_metadata(
                    base_response,
                    payload=enriched_payload,
                    authorization=authorization,
                    knowledge_sources=knowledge_sources,
                    knowledge_diagnostics=knowledge_diagnostics,
                )
                await _record_agent_run_audit(
                    session,
                    principal=principal,
                    agent_key=agent_key,
                    payload=enriched_payload,
                    response=final_response,
                    authorization=authorization,
                    request_id=request_id or final_response.request_id,
                )
                yield {"type": "done", "response": final_response}
        return

    # Fallback: agent has no run_stream; run non-streaming and emit a single delta.
    response = await agent.run(
        enriched_payload,
        principal,
        request_id=request_id,
        session=session,
    )
    yield {"type": "delta", "content": response.answer}
    final_response = _merge_agent_stream_metadata(
        response,
        payload=enriched_payload,
        authorization=authorization,
        knowledge_sources=knowledge_sources,
        knowledge_diagnostics=knowledge_diagnostics,
    )
    await _record_agent_run_audit(
        session,
        principal=principal,
        agent_key=agent_key,
        payload=enriched_payload,
        response=final_response,
        authorization=authorization,
        request_id=request_id or final_response.request_id,
    )
    yield {"type": "done", "response": final_response}


def _merge_agent_stream_metadata(
    response: AgentRunResponse,
    *,
    payload: AgentRunRequest,
    authorization: AgentRunAuthorization,
    knowledge_sources: list[dict[str, object]],
    knowledge_diagnostics: dict[str, object],
) -> AgentRunResponse:
    """Apply the same metadata enrichment ``run_agent`` applies to its result."""
    merged_sources = _dedupe_sources([*response.sources, *knowledge_sources])
    final_metadata = {
        **response.metadata,
        "license_gate": authorization.license_gate,
        "license_gate_reason": authorization.reason,
        "licensed": authorization.licensed,
        "installed": authorization.installed,
        "enabled": authorization.enabled,
        "agent_instance": _agent_instance_diagnostics_from_context(payload.context),
        "knowledge": knowledge_diagnostics,
        "mcp": payload.context.get("mcp") if isinstance(payload.context, dict) else None,
    }
    final_response = response.model_copy(
        update={
            "sources": merged_sources,
            "metadata": final_metadata,
        }
    )
    final_response.metadata["runtime_summary"] = _agent_run_runtime_summary(final_response)
    _augment_runtime_summary_with_mcp(final_response)
    return final_response


async def _apply_agent_instance_defaults(
    session: AsyncSession,
    payload: AgentRunRequest,
    principal: Principal,
    *,
    agent_key: str,
    required_module: str,
) -> AgentRunRequest:
    raw_agent_id = payload.context.get("agent_id")
    if raw_agent_id in (None, ""):
        return payload
    try:
        agent_id = UUID(str(raw_agent_id))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="agent_id must be a UUID.",
        ) from exc

    instance = await _get_agent_instance(session, principal, agent_id, require_write=False)
    if instance.agent_key != agent_key:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Agent instance does not match the requested official Agent.",
        )
    if instance.module_key != required_module:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Agent instance module does not match the requested official Agent module.",
        )
    _ensure_agent_instance_runnable(instance)
    await _ensure_agent_instance_ready_for_runtime(session, principal, instance)
    department_id = _context_uuid(payload.context.get("department_id"), field_name="department_id")
    if instance.department_id is not None:
        if department_id is not None and department_id != instance.department_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Agent run department_id does not match the selected Agent instance.",
            )
        department_id = instance.department_id

    merged_context = {
        **instance.config,
        **payload.context,
        "agent_id": str(instance.id),
        "module_key": instance.module_key,
        "agent_instance_slug": instance.slug,
        "agent_instance_name": instance.name,
        "visibility": instance.visibility,
    }
    if department_id is not None:
        merged_context["department_id"] = str(department_id)
    return payload.model_copy(
        update={
            "context": merged_context,
            "model_key": payload.model_key or instance.model_key,
            "routing_key": payload.routing_key or instance.model_routing_key,
        }
    )


async def _canonicalize_agent_governance_context(
    session: AsyncSession,
    payload: AgentRunRequest,
    principal: Principal,
) -> AgentRunRequest:
    context = dict(payload.context)
    channel_id = _context_uuid(context.get("channel_id"), field_name="channel_id")
    if channel_id is not None:
        channel = await _get_channel_config(session, principal, channel_id)
        if channel.agent_id is not None:
            agent_id = _context_uuid(context.get("agent_id"), field_name="agent_id")
            if agent_id is not None and agent_id != channel.agent_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Agent run agent_id does not match the selected channel.",
                )
            context["agent_id"] = str(channel.agent_id)
        context["channel_id"] = str(channel.id)

    department_id = _context_uuid(context.get("department_id"), field_name="department_id")
    if department_id is not None:
        await _assert_department_access(session, principal, department_id)
        context["department_id"] = str(department_id)

    return payload.model_copy(update={"context": context})


async def _get_channel_config(
    session: AsyncSession,
    principal: Principal,
    channel_id: UUID,
) -> ChannelConfig:
    result = await session.execute(
        select(ChannelConfig).where(
            ChannelConfig.tenant_id == principal.tenant_id,
            ChannelConfig.id == channel_id,
        )
    )
    channel = result.scalar_one_or_none()
    if channel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found.",
        )
    return channel


async def _assert_department_access(
    session: AsyncSession,
    principal: Principal,
    department_id: UUID,
) -> None:
    result = await session.execute(
        select(Department.id).where(
            Department.tenant_id == principal.tenant_id,
            Department.id == department_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found.",
        )
    if is_tenant_admin(principal):
        return
    membership = await session.execute(
        select(UserDepartment.department_id)
        .join(Department, cast(ColumnElement[bool], Department.id == UserDepartment.department_id))
        .where(
            UserDepartment.user_id == principal.user_id,
            UserDepartment.department_id == department_id,
            Department.tenant_id == principal.tenant_id,
        )
    )
    if membership.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Department access denied.",
        )


def _context_uuid(value: object, *, field_name: str) -> UUID | None:
    if value in (None, ""):
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{field_name} must be a UUID.",
        ) from exc


async def _enrich_with_mcp_tools(
    session: AsyncSession,
    payload: AgentRunRequest,
    principal: Principal,
) -> AgentRunRequest:
    """Mount active MCP servers' tools into the run context.

    Minimal runtime interface: resolve MCP endpoints configured for the
    tenant (filtered by payload.mcp_server_keys when provided), discover
    tools per server, and inject a ``mcp`` summary into ``payload.context``
    so agent implementations can call tools via the MCP client.

    Failures are surfaced as diagnostics rather than aborting the run so a
    misbehaving MCP server cannot take the whole agent offline.
    """
    # Avoid heavy import at module import time to keep startup cost low.
    from app.services.mcp_service import get_active_mcp_endpoints_for_tenant
    from app.mcp.client import McpClientError, list_tools as mcp_list_tools

    server_keys = payload.mcp_server_keys
    endpoints = get_active_mcp_endpoints_for_tenant(
        principal.tenant_id,
        server_keys=server_keys,
    )
    mounted: list[dict[str, object]] = []
    total_tools = 0
    for endpoint in endpoints:
        tool_names: list[str] = []
        error: str | None = None
        try:
            tools = await mcp_list_tools(endpoint)
            tool_names = [tool.name for tool in tools]
            total_tools += len(tool_names)
        except McpClientError as exc:
            error = str(exc)
        except Exception as exc:  # defensive: never let MCP break the run
            error = f"{type(exc).__name__}: {exc}"
        mounted.append(
            {
                "server_id": endpoint.server_id,
                "server_key": endpoint.server_key,
                "endpoint_url": endpoint.endpoint_url,
                "transport": endpoint.transport,
                "tool_count": len(tool_names),
                "tool_names": tool_names,
                "error": error,
            }
        )
    new_context = {**payload.context, "mcp": {"mounted": mounted, "total_tools": total_tools}}
    return payload.model_copy(update={"context": new_context})


async def _enrich_with_knowledge_context(
    session: AsyncSession,
    payload: AgentRunRequest,
    principal: Principal,
    *,
    agent_key: str | None = None,
    request_id: str | None = None,
) -> tuple[AgentRunRequest, list[dict[str, object]], dict[str, object]]:
    knowledge_base_ids = _knowledge_base_ids_from_context(payload.context)
    if not knowledge_base_ids:
        return payload, [], {"enabled": False, "reason": "no_knowledge_base_context"}

    top_k = _context_int(payload.context.get("knowledge_top_k"), default=5, minimum=1, maximum=10)
    sources: list[dict[str, object]] = []
    per_base: list[dict[str, object]] = []
    for knowledge_base_id in knowledge_base_ids:
        result = await _retrieve_for_agent_run(
            session,
            payload=payload,
            principal=principal,
            knowledge_base_id=knowledge_base_id,
            retrieval_payload=RetrievalTestRequest(
                query=payload.input,
                top_k=top_k,
                include_raw_chunks=True,
            ),
            agent_key=agent_key,
            request_id=request_id,
        )
        for item in result.results:
            knowledge_base_name = result.diagnostics.get("knowledge_base_name")
            sources.append(
                {
                    "rank": len(sources) + 1,
                    "knowledge_base_id": str(knowledge_base_id),
                    "knowledge_base_name": knowledge_base_name,
                    "chunk_id": item.chunk_id,
                    "document_id": str(item.document_id) if item.document_id else None,
                    "source_name": item.source_name,
                    "score": item.score,
                    "text": item.text,
                    "metadata": item.metadata,
                }
            )
        per_base.append(
            {
                "knowledge_base_id": str(knowledge_base_id),
                "knowledge_base_name": result.diagnostics.get("knowledge_base_name"),
                "knowledge_base_visibility": result.diagnostics.get("knowledge_base_visibility"),
                "engine": result.engine.value,
                "source_count": len(result.results),
                "elapsed_ms": result.elapsed_ms,
            }
        )

    enriched_context = {
        **payload.context,
        "knowledge_context": _format_knowledge_context(sources),
        "knowledge_sources": sources,
    }
    return (
        payload.model_copy(update={"context": enriched_context}),
        sources,
        {
            "enabled": True,
            "knowledge_base_ids": [str(item) for item in knowledge_base_ids],
            "source_count": len(sources),
            "top_k": top_k,
            "per_base": per_base,
            "reason": "sources_found" if sources else "no_matching_sources",
            **_knowledge_confidence_diagnostics(sources),
        },
    )


async def _retrieve_for_agent_run(
    session: AsyncSession,
    *,
    payload: AgentRunRequest,
    principal: Principal,
    knowledge_base_id: UUID,
    retrieval_payload: RetrievalTestRequest,
    agent_key: str | None,
    request_id: str | None,
) -> RetrievalTestResponse:
    result = await run_retrieval_test(
        session,
        knowledge_base_id,
        retrieval_payload,
        principal,
    )
    await _record_knowledge_retrieve_audit(
        session,
        principal=principal,
        payload=payload,
        knowledge_base_id=knowledge_base_id,
        retrieval_payload=retrieval_payload,
        result=result,
        agent_key=agent_key,
        request_id=request_id,
    )
    return result


async def _record_knowledge_retrieve_audit(
    session: AsyncSession,
    *,
    principal: Principal,
    payload: AgentRunRequest,
    knowledge_base_id: UUID,
    retrieval_payload: RetrievalTestRequest,
    result: RetrievalTestResponse,
    agent_key: str | None,
    request_id: str | None,
) -> None:
    scores = [_coerce_score(item.score) for item in result.results]
    numeric_scores = [score for score in scores if score is not None]
    await record_audit_event(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        action="knowledge.retrieve",
        resource_type="knowledge_base",
        resource_id=knowledge_base_id,
        request_id=request_id,
        details={
            "agent_key": agent_key,
            "agent_id": payload.context.get("agent_id"),
            "conversation_id": payload.context.get("conversation_id"),
            "channel_id": payload.context.get("channel_id"),
            "source": payload.context.get("source"),
            "query_preview": payload.input[:160],
            "query_length": len(payload.input),
            "top_k": retrieval_payload.top_k,
            "source_count": len(result.results),
            "max_score": round(max(numeric_scores), 6) if numeric_scores else None,
            "engine": result.engine.value,
            "elapsed_ms": result.elapsed_ms,
            "knowledge_base_name": result.diagnostics.get("knowledge_base_name"),
            "knowledge_base_visibility": result.diagnostics.get("knowledge_base_visibility"),
            "document_ids": [str(item.document_id) for item in result.results if item.document_id],
        },
    )


def _knowledge_confidence_diagnostics(sources: list[dict[str, object]]) -> dict[str, object]:
    return runtime_diagnostics.knowledge_confidence_diagnostics(sources)


def _knowledge_guardrail_decision(
    payload: AgentRunRequest,
    knowledge_diagnostics: dict[str, object],
) -> dict[str, object]:
    return runtime_diagnostics.knowledge_guardrail_decision(
        context=payload.context,
        input_value=payload.input,
        knowledge_diagnostics=knowledge_diagnostics,
    )


def _knowledge_guardrail_mode(context: dict[str, object]) -> str:
    return runtime_diagnostics.knowledge_guardrail_mode(context)


def _input_requires_strict_knowledge(value: str) -> bool:
    return runtime_diagnostics.input_requires_strict_knowledge(value)


def _knowledge_guardrail_response(
    *,
    agent_key: str,
    payload: AgentRunRequest,
    request_id: str | None,
    required_module: str,
    knowledge_diagnostics: dict[str, object],
) -> AgentRunResponse:
    return AgentRunResponse(
        answer=_knowledge_guardrail_answer(payload, knowledge_diagnostics),
        usage=LLMUsageResponse(
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            cost_usd=Decimal("0"),
        ),
        model_key=payload.model_key or payload.routing_key or "knowledge-guardrail",
        request_id=request_id or f"agent-guardrail-{uuid4()}",
        sources=[],
        metadata={
            "agent_key": agent_key,
            "required_module": required_module,
            "knowledge_guardrail": knowledge_diagnostics["guardrail"],
            "runtime_evidence": _local_runtime_evidence(
                execution="knowledge_guardrail",
                agent_key=agent_key,
                required_module=required_module,
                model_key=payload.model_key or payload.routing_key or "knowledge-guardrail",
                request_id=request_id,
                reason=str(
                    cast(Any, knowledge_diagnostics["guardrail"]).get("reason")
                    or "knowledge_guardrail"
                ),
                local_response="knowledge_guardrail",
            ),
        },
    )


def _customer_service_greeting_response(
    *,
    agent_key: str,
    payload: AgentRunRequest,
    request_id: str | None,
    required_module: str,
) -> AgentRunResponse | None:
    if agent_key != "customer_service" or not _is_greeting_intent(payload.input):
        return None
    return AgentRunResponse(
        answer=(
            "你好，我是电商客服助手。你可以把客户问题、订单状态、商品信息或售后诉求发给我，"
            "我会帮你起草可发送给客户的回复，也可以协助查询 SOP、整理升级处理摘要。"
        ),
        usage=LLMUsageResponse(
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            cost_usd=Decimal("0"),
        ),
        model_key=payload.model_key or payload.routing_key or "agenthive-local-response",
        request_id=request_id or f"agent-greeting-{uuid4()}",
        sources=[],
        metadata={
            "agent_key": agent_key,
            "required_module": required_module,
            "local_response": "greeting_intent",
            "runtime_evidence": _local_runtime_evidence(
                execution="local_response",
                agent_key=agent_key,
                required_module=required_module,
                model_key=payload.model_key or payload.routing_key or "agenthive-local-response",
                request_id=request_id,
                reason="greeting_intent",
                local_response="greeting_intent",
            ),
        },
    )


def _local_runtime_evidence(
    *,
    execution: str,
    agent_key: str,
    required_module: str,
    model_key: str,
    request_id: str | None,
    reason: str,
    local_response: str,
) -> dict[str, object]:
    return {
        "execution": execution,
        "llm_gateway_called": False,
        "agent_key": agent_key,
        "required_module": required_module,
        "model_key": model_key,
        "provider_key": "agenthive-local",
        "request_id": request_id,
        "finish_reason": local_response,
        "reason": reason,
        "local_response": local_response,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cost_usd": "0",
        "fallback_attempt_count": 0,
        "route_attempts": [],
        "mock_adapter": False,
    }


def _augment_runtime_summary_with_mcp(response: AgentRunResponse) -> None:
    """Attach MCP mount diagnostics to the runtime summary in-place."""
    mcp_context = response.metadata.get("mcp") if isinstance(response.metadata, dict) else None
    if not isinstance(mcp_context, dict):
        return
    mounted_raw = mcp_context.get("mounted")
    mounted: list[Any] = mounted_raw if isinstance(mounted_raw, list) else []
    summary = response.metadata.get("runtime_summary")
    if not isinstance(summary, dict):
        return
    summary["mcp_server_count"] = len(mounted)
    summary["mcp_tool_count"] = mcp_context.get("total_tools", 0)
    summary["mcp_errors"] = [
        m.get("server_key") for m in mounted if isinstance(m, dict) and m.get("error")
    ]


def _agent_run_runtime_summary(response: AgentRunResponse) -> dict[str, object]:
    metadata = response.metadata if isinstance(response.metadata, dict) else {}
    return runtime_diagnostics.agent_run_runtime_summary(
        metadata=metadata,
        model_key=response.model_key,
        request_id=response.request_id,
        total_tokens=response.usage.total_tokens,
        source_count=len(response.sources),
    )


def _agent_runtime_adapter_mode(*, execution: str, gateway_called: bool, mock_adapter: bool) -> str:
    return runtime_diagnostics.agent_runtime_adapter_mode(
        execution=execution,
        gateway_called=gateway_called,
        mock_adapter=mock_adapter,
    )


def _agent_runtime_status(adapter_mode: str) -> str:
    return runtime_diagnostics.agent_runtime_status(adapter_mode)


def _runtime_route_attempts(value: object) -> list[dict[str, object]]:
    return runtime_diagnostics.runtime_route_attempts(value)


def _is_greeting_intent(value: str) -> bool:
    return runtime_diagnostics.is_greeting_intent(value)


def _knowledge_guardrail_answer(
    payload: AgentRunRequest,
    knowledge_diagnostics: dict[str, object],
) -> str:
    del payload
    return runtime_diagnostics.knowledge_guardrail_answer(knowledge_diagnostics)


def _knowledge_base_names_from_diagnostics(knowledge_diagnostics: dict[str, object]) -> str:
    return runtime_diagnostics.knowledge_base_names_from_diagnostics(knowledge_diagnostics)


def _coerce_score(value: object) -> float | None:
    return runtime_diagnostics.coerce_score(value)


def _agent_instance_diagnostics_from_context(context: dict[str, object]) -> dict[str, object]:
    return runtime_diagnostics.agent_instance_diagnostics_from_context(context)


async def _record_agent_run_audit(
    session: AsyncSession,
    *,
    principal: Principal,
    agent_key: str,
    payload: AgentRunRequest,
    response: AgentRunResponse,
    authorization: AgentRunAuthorization,
    request_id: str | None,
) -> None:
    agent_instance = response.metadata.get("agent_instance")
    agent_instance_details = agent_instance if isinstance(agent_instance, dict) else {}
    await record_audit_event(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        action="agent.run",
        resource_type="agent_instance" if agent_instance_details.get("enabled") else "agent",
        resource_id=_optional_context_uuid(agent_instance_details.get("agent_id")),
        request_id=request_id,
        details=_agent_run_audit_details(
            agent_key=agent_key,
            payload=payload,
            response=response,
            authorization=authorization,
        ),
    )


def _agent_run_audit_details(
    *,
    agent_key: str,
    payload: AgentRunRequest,
    response: AgentRunResponse,
    authorization: AgentRunAuthorization,
) -> dict[str, object]:
    knowledge = response.metadata.get("knowledge")
    agent_instance = response.metadata.get("agent_instance")
    runtime_summary = response.metadata.get("runtime_summary")
    if not isinstance(runtime_summary, dict):
        runtime_summary = _agent_run_runtime_summary(response)
    return {
        "agent_key": agent_key,
        "model_key": response.model_key,
        "routing_key": payload.routing_key,
        "requested_model_key": payload.model_key,
        "max_tokens": payload.max_tokens,
        "context_keys": sorted(payload.context.keys()),
        "source": payload.context.get("source"),
        "department_id": payload.context.get("department_id"),
        "channel_id": payload.context.get("channel_id"),
        "conversation_id": payload.context.get("conversation_id"),
        "license_gate": authorization.license_gate,
        "license_gate_reason": authorization.reason,
        "required_module": response.metadata.get("required_module"),
        "agent_instance": agent_instance if isinstance(agent_instance, dict) else {},
        "knowledge": knowledge if isinstance(knowledge, dict) else {},
        "runtime_summary": runtime_summary if isinstance(runtime_summary, dict) else {},
        "source_count": len(response.sources),
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "total_tokens": response.usage.total_tokens,
            "cost_usd": str(response.usage.cost_usd),
        },
    }


def _agent_license_gate_audit_details(
    authorization: AgentRunAuthorization | None,
) -> dict[str, object]:
    if authorization is None:
        return {"license_gate": "not_checked"}
    return {
        "license_gate": authorization.license_gate,
        "license_gate_reason": authorization.reason,
        "licensed": authorization.licensed,
        "installed": authorization.installed,
        "enabled": authorization.enabled,
    }


def _optional_context_uuid(value: object) -> UUID | None:
    if value in (None, ""):
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _knowledge_base_ids_from_context(context: dict[str, object]) -> list[UUID]:
    raw_ids: list[object] = []
    if context.get("knowledge_base_id"):
        raw_ids.append(context["knowledge_base_id"])
    raw_ids_value = context.get("knowledge_base_ids")
    if isinstance(raw_ids_value, list):
        raw_ids.extend(raw_ids_value)

    result: list[UUID] = []
    for raw_id in raw_ids:
        try:
            value = UUID(str(raw_id))
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="knowledge_base_id must be a UUID.",
            ) from exc
        if value not in result:
            result.append(value)
    return result[:5]


async def _validate_agent_instance_knowledge_config(
    session: AsyncSession,
    principal: Principal,
    config: dict[str, object],
) -> None:
    knowledge_base_ids = _knowledge_base_ids_from_context(config)
    for knowledge_base_id in knowledge_base_ids:
        await _get_accessible_base_db(
            session,
            knowledge_base_id,
            principal,
            require_write=False,
        )


def _context_int(value: object, *, default: int, minimum: int, maximum: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(str(value))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="knowledge_top_k must be an integer.",
        ) from exc
    return min(max(parsed, minimum), maximum)


def _format_knowledge_context(sources: list[dict[str, object]]) -> str:
    return runtime_diagnostics.format_knowledge_context(sources)


def _truncate_knowledge_source_text(text: str) -> str:
    return runtime_diagnostics.truncate_knowledge_source_text(text)


def _dedupe_sources(sources: list[dict[str, object]]) -> list[dict[str, object]]:
    return runtime_diagnostics.dedupe_sources(sources)


async def _catalog_module_states(
    session: AsyncSession | None,
    principal: Principal | None,
) -> dict[str, dict[str, bool | str | None]]:
    if session is None or principal is None:
        return {}
    try:
        license_status = await get_license_status_for_tenant(session, tenant_id=principal.tenant_id)
        tenant_states = await _tenant_module_states(session, principal.tenant_id)
        result = await session.execute(
            select(AgentModule).where(cast(Any, AgentModule.is_active).is_(True))
        )
        states: dict[str, dict[str, bool | str | None]] = {}
        for module in result.scalars().all():
            licensed = (
                license_status.status == LicenseStatus.ACTIVE
                and module.module_key in license_status.allowed_modules
            )
            tenant_module = tenant_states.get(module.id)
            state = (
                AgentModuleState(tenant_module.state)
                if tenant_module
                else AgentModuleState.NOT_INSTALLED
            )
            states[module.module_key] = {
                "licensed": licensed,
                "installed": state
                in {
                    AgentModuleState.INSTALLED,
                    AgentModuleState.ENABLED,
                    AgentModuleState.DISABLED,
                },
                "enabled": state == AgentModuleState.ENABLED,
                "license_gate": "enforced",
            }
        return states
    except (OSError, SQLAlchemyError):
        if is_development_environment():
            return {
                agent.definition.required_module: {
                    "licensed": None,
                    "installed": None,
                    "enabled": None,
                    "license_gate": "development_fallback",
                }
                for agent in agent_registry.list_agents()
            }
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent license gate storage is unavailable.",
        )


async def _authorize_agent_run(
    session: AsyncSession,
    principal: Principal,
    *,
    required_module: str,
) -> AgentRunAuthorization:
    try:
        license_status = await get_license_status_for_tenant(session, tenant_id=principal.tenant_id)
        if license_status.status != LicenseStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Active AgentHive license is required to run official Agents.",
            )
        if required_module not in license_status.allowed_modules:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This Agent module is not licensed for this deployment.",
            )

        module = await _agent_module_row(session, required_module)
        tenant_states = await _tenant_module_states(session, principal.tenant_id)
        tenant_module = tenant_states.get(module.id)
        if tenant_module is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Install and enable this Agent module before running it.",
            )
        module_state = AgentModuleState(tenant_module.state)
        if module_state != AgentModuleState.ENABLED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Enable this Agent module before running it.",
            )
        return AgentRunAuthorization(
            license_gate="enforced",
            licensed=True,
            installed=True,
            enabled=True,
            reason="active_license_and_enabled_module",
        )
    except HTTPException:
        raise
    except (OSError, SQLAlchemyError):
        if is_development_environment():
            return AgentRunAuthorization(
                license_gate="development_fallback",
                licensed=None,
                installed=None,
                enabled=None,
                reason="database_unavailable_in_development",
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent license gate storage is unavailable.",
        )


async def _agent_module_row(session: AsyncSession, module_key: str) -> AgentModule:
    result = await session.execute(
        select(AgentModule).where(
            AgentModule.module_key == module_key,
            cast(Any, AgentModule.is_active).is_(True),
        )
    )
    module = result.scalar_one_or_none()
    if module is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Agent module catalog is not initialized.",
        )
    return module


async def _tenant_module_states(
    session: AsyncSession,
    tenant_id: UUID,
) -> dict[UUID, TenantAgentModule]:
    result = await session.execute(
        select(TenantAgentModule).where(TenantAgentModule.tenant_id == tenant_id)
    )
    return {row.module_id: row for row in result.scalars().all()}


def _unknown_module_state() -> dict[str, bool | str | None]:
    return {
        "licensed": None,
        "installed": None,
        "enabled": None,
        "license_gate": "unknown",
    }


async def _get_agent_instance(
    session: AsyncSession,
    principal: Principal,
    agent_id: UUID,
    *,
    require_write: bool,
) -> AgentInstance:
    result = await session.execute(
        select(AgentInstance).where(
            AgentInstance.tenant_id == principal.tenant_id,
            AgentInstance.id == agent_id,
        )
    )
    instance = result.scalar_one_or_none()
    if instance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent instance not found.",
        )
    department_ids = await _principal_department_ids(session, principal)
    allowed = (
        _can_write_agent_instance(instance, principal, department_ids)
        if require_write
        else _can_read_agent_instance(instance, principal, department_ids)
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent instance access denied by visibility policy.",
        )
    return instance


async def _principal_department_ids(session: AsyncSession, principal: Principal) -> set[UUID]:
    if is_tenant_admin(principal):
        return set()
    result = await session.execute(
        select(UserDepartment.department_id)
        .join(Department, cast(ColumnElement[bool], Department.id == UserDepartment.department_id))
        .where(
            UserDepartment.user_id == principal.user_id,
            Department.tenant_id == principal.tenant_id,
        )
    )
    return set(result.scalars().all())


async def _normalize_agent_instance_department(
    session: AsyncSession,
    principal: Principal,
    visibility: str,
    department_id: UUID | None,
) -> UUID | None:
    if visibility != "department":
        return None
    if department_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="department_id is required for department-visible Agent instances.",
        )
    result = await session.execute(
        select(Department.id).where(
            Department.tenant_id == principal.tenant_id,
            Department.id == department_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found for this tenant.",
        )
    if not is_tenant_admin(principal):
        department_ids = await _principal_department_ids(session, principal)
        if department_id not in department_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot assign an Agent instance to a department outside the current user scope.",
            )
    return department_id


def _can_read_agent_instance(
    instance: AgentInstance,
    principal: Principal,
    principal_department_ids: set[UUID],
) -> bool:
    if is_tenant_admin(principal):
        return True
    if instance.visibility == "tenant":
        return True
    if instance.visibility == "private":
        return _is_agent_instance_owner(instance, principal)
    if instance.visibility == "department":
        return (
            instance.department_id is not None
            and instance.department_id in principal_department_ids
        )
    return False


def _can_write_agent_instance(
    instance: AgentInstance,
    principal: Principal,
    principal_department_ids: set[UUID],
) -> bool:
    if is_tenant_admin(principal):
        return True
    if _is_agent_instance_owner(instance, principal):
        return True
    if instance.visibility == "department":
        return (
            instance.department_id is not None
            and instance.department_id in principal_department_ids
        )
    return False


def _is_agent_instance_owner(instance: AgentInstance, principal: Principal) -> bool:
    return principal.user_id in {instance.owner_user_id, instance.created_by}


def _ensure_agent_instance_runnable(instance: AgentInstance) -> None:
    if instance.status in RUNNABLE_AGENT_INSTANCE_STATUSES:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Agent instance must be active before it can run.",
    )


async def _ensure_agent_instance_ready_for_runtime(
    session: AsyncSession,
    principal: Principal,
    instance: AgentInstance,
) -> None:
    if is_tenant_admin(principal) or "agents:write" in principal.permissions:
        return
    model_index = await _active_model_deployment_index(session, principal)
    readiness = _workbench_agent_readiness(instance, model_index=model_index)
    if readiness["runnable"]:
        return
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "agent_instance_not_ready",
            "message": "Agent instance is not ready for employee runtime.",
            "readiness": readiness["readiness"],
            "reasons": readiness["readiness_reasons"],
        },
    )


def _normalize_agent_instance_owner(principal: Principal, owner_user_id: UUID | None) -> UUID:
    if owner_user_id is None:
        return principal.user_id
    if not is_tenant_admin(principal) and owner_user_id != principal.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot assign an Agent instance owner outside the current user scope.",
        )
    return owner_user_id


async def _ensure_agent_slug_available(session: AsyncSession, tenant_id: UUID, slug: str) -> None:
    result = await session.execute(
        select(AgentInstance.id).where(
            AgentInstance.tenant_id == tenant_id,
            AgentInstance.slug == slug,
        )
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Agent instance slug already exists.",
        )


def _slugify(value: str) -> str:
    normalized = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    while "--" in normalized:
        normalized = normalized.replace("--", "-")
    normalized = normalized.strip("-")
    return normalized[:80] or "agent"


@dataclass(frozen=True)
class ActiveModelDeploymentIndex:
    routing_keys: frozenset[str]
    model_keys: frozenset[str]


class _AgentReadiness(TypedDict):
    runnable: bool
    readiness: str
    readiness_reasons: list[str]
    model_profile: str | None
    model_policy: str
    model_available: bool
    knowledge_base_count: int
    knowledge_enabled: bool


def _agent_instance_response(
    instance: AgentInstance,
    *,
    model_index: ActiveModelDeploymentIndex | None = None,
) -> AgentInstanceResponse:
    readiness = _workbench_agent_readiness(instance, model_index=model_index)
    return AgentInstanceResponse(
        id=instance.id,
        tenant_id=instance.tenant_id,
        name=instance.name,
        slug=instance.slug,
        agent_key=instance.agent_key,
        module_key=instance.module_key,
        description=instance.description,
        status=instance.status,
        visibility=instance.visibility,
        department_id=instance.department_id,
        owner_user_id=instance.owner_user_id,
        model_routing_key=instance.model_routing_key,
        model_key=instance.model_key,
        system_prompt=instance.system_prompt,
        config=instance.config,
        metadata=instance.metadata_json,
        created_by=instance.created_by,
        created_at=instance.created_at,
        updated_at=instance.updated_at,
        runnable=readiness["runnable"],
        readiness=readiness["readiness"],
        readiness_reasons=readiness["readiness_reasons"],
        model_available=readiness["model_available"],
        knowledge_base_count=readiness["knowledge_base_count"],
        knowledge_enabled=readiness["knowledge_enabled"],
    )


async def _visible_bound_knowledge_bases_by_id(
    session: AsyncSession,
    principal: Principal,
    instances: list[AgentInstance],
    department_ids: set[UUID],
) -> dict[UUID, KnowledgeBase]:
    bound_ids: set[UUID] = set()
    for instance in instances:
        bound_ids.update(_knowledge_base_uuids_from_config(instance.config))
    if not bound_ids:
        return {}
    try:
        result = await session.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.tenant_id == principal.tenant_id,
                cast(Any, KnowledgeBase.deleted_at).is_(None),
                KnowledgeBase.status == "active",
                cast(Any, KnowledgeBase.id).in_(bound_ids),
            )
        )
    except (OSError, SQLAlchemyError):
        await session.rollback()
        return {}
    return {
        base.id: base
        for base in result.scalars().all()
        if _can_access_base(base, principal, department_ids)
    }


async def _active_model_deployment_index(
    session: AsyncSession,
    principal: Principal,
) -> ActiveModelDeploymentIndex:
    try:
        result = await session.execute(
            select(LLMDeployment, LLMModel)
            .join(
                LLMProvider, cast(ColumnElement[bool], LLMProvider.id == LLMDeployment.provider_id)
            )
            .join(LLMModel, cast(ColumnElement[bool], LLMModel.id == LLMDeployment.model_id))
            .where(
                LLMDeployment.tenant_id == principal.tenant_id,
                cast(Any, LLMDeployment.is_active).is_(True),
                cast(Any, LLMProvider.is_active).is_(True),
            )
        )
    except (OSError, SQLAlchemyError):
        await session.rollback()
        return ActiveModelDeploymentIndex(routing_keys=frozenset(), model_keys=frozenset())
    routing_keys: set[str] = set()
    model_keys: set[str] = set()
    for deployment, model in result.all():
        routing_keys.add(deployment.routing_key)
        model_keys.add(model.model_key)
    return ActiveModelDeploymentIndex(
        routing_keys=frozenset(routing_keys), model_keys=frozenset(model_keys)
    )


def _workbench_agent_instance_response(
    instance: AgentInstance,
    *,
    knowledge_bases: list[KnowledgeBase] | None = None,
    model_index: ActiveModelDeploymentIndex | None = None,
) -> WorkbenchAgentInstanceResponse:
    readiness = _workbench_agent_readiness(instance, model_index=model_index)
    profile = _workbench_agent_profile(instance)
    return WorkbenchAgentInstanceResponse(
        id=instance.id,
        name=instance.name,
        slug=instance.slug,
        agent_key=instance.agent_key,
        module_key=instance.module_key,
        description=instance.description,
        status=instance.status,
        visibility=instance.visibility,
        department_id=instance.department_id,
        category=profile["category"],
        workflow_profile=profile["workflow_profile"],
        runnable=readiness["runnable"],
        readiness=readiness["readiness"],
        readiness_reasons=readiness["readiness_reasons"],
        model_profile=readiness["model_profile"],
        model_policy=readiness["model_policy"],
        model_available=readiness["model_available"],
        knowledge_base_count=readiness["knowledge_base_count"],
        knowledge_enabled=readiness["knowledge_enabled"],
        knowledge_bases=[_workbench_knowledge_base_summary(base) for base in knowledge_bases or []],
    )


_WORKBENCH_AGENT_PROFILES: dict[str, str] = {
    "content_analysis": "marketing",
    "copywriting": "marketing",
    "customer_service": "customer",
    "data_analyst": "analytics",
    "finance": "finance",
    "hr_screening": "hr",
    "image_generation": "media",
    "product_design": "marketing",
    "report_writer": "analytics",
    "store_operations": "operations",
    "video_generation": "media",
}


def _workbench_agent_profile(instance: AgentInstance) -> dict[str, str]:
    profile = _normalized_agent_key(instance.agent_key)
    if profile not in _WORKBENCH_AGENT_PROFILES:
        profile = _normalized_agent_key(instance.module_key)
    category = _WORKBENCH_AGENT_PROFILES.get(profile, "general")
    return {
        "category": category,
        "workflow_profile": profile if profile in _WORKBENCH_AGENT_PROFILES else "general",
    }


def _normalized_agent_key(value: str | None) -> str:
    if not value:
        return ""
    return value.removeprefix("agent.").lower()


def _workbench_knowledge_base_summary(base: KnowledgeBase) -> WorkbenchAgentKnowledgeBaseSummary:
    return WorkbenchAgentKnowledgeBaseSummary(
        id=base.id,
        name=base.name,
        description=base.description,
        visibility=base.visibility,
        status=base.status,
        document_count=base.document_count,
        tags=base.tags,
        updated_at=base.updated_at,
    )


def _workbench_agent_readiness(
    instance: AgentInstance,
    *,
    model_index: ActiveModelDeploymentIndex | None = None,
) -> _AgentReadiness:
    config = instance.config if isinstance(instance.config, dict) else {}
    knowledge_base_count = len(_knowledge_base_refs_from_config(config))
    model_profile = instance.model_routing_key or instance.model_key
    model_available = _agent_model_profile_available(instance, model_index)
    reasons: list[str] = []
    if instance.status != "active":
        reasons.append("agent_not_active")
    if not model_profile:
        reasons.append("model_policy_not_configured")
    elif not model_available:
        reasons.append(
            "model_route_unavailable" if instance.model_routing_key else "model_unavailable"
        )
    if _agent_benefits_from_knowledge(instance.agent_key) and knowledge_base_count == 0:
        reasons.append("knowledge_not_bound")
    return {
        "runnable": not reasons,
        "readiness": "ready" if not reasons else "needs_configuration",
        "readiness_reasons": reasons,
        "model_profile": model_profile,
        "model_policy": "configured" if model_profile else "system_default",
        "model_available": model_available,
        "knowledge_base_count": knowledge_base_count,
        "knowledge_enabled": knowledge_base_count > 0,
    }


def _agent_model_profile_available(
    instance: AgentInstance,
    model_index: ActiveModelDeploymentIndex | None,
) -> bool:
    if not instance.model_routing_key and not instance.model_key:
        return False
    if model_index is None:
        return True
    if instance.model_routing_key:
        return instance.model_routing_key in model_index.routing_keys
    if instance.model_key:
        return instance.model_key in model_index.model_keys
    return False


def _agent_benefits_from_knowledge(agent_key: str) -> bool:
    return agent_key in {
        "customer_service",
        "data_analyst",
        "finance",
        "hr_screening",
        "report_writer",
        "store_operations",
    }


def _knowledge_base_refs_from_config(config: dict[str, object]) -> list[str]:
    raw_ids: list[object] = []
    if config.get("knowledge_base_id"):
        raw_ids.append(config["knowledge_base_id"])
    raw_ids_value = config.get("knowledge_base_ids")
    if isinstance(raw_ids_value, list):
        raw_ids.extend(raw_ids_value)

    refs: list[str] = []
    for raw_id in raw_ids:
        value = str(raw_id).strip()
        if value and value not in refs:
            refs.append(value)
    return refs[:5]


def _knowledge_base_uuids_from_config(config: dict[str, object]) -> list[UUID]:
    result: list[UUID] = []
    for raw_id in _knowledge_base_refs_from_config(config):
        try:
            value = UUID(raw_id)
        except ValueError:
            continue
        if value not in result:
            result.append(value)
    return result[:5]
