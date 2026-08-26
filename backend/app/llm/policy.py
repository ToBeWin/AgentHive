from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.cost_center import resolve_cost_center
from app.llm.schemas import LLMChatRequest, LLMRequestContext, PolicyDecision


@dataclass(frozen=True)
class ModelPolicyRule:
    id: UUID
    name: str
    scope_type: str
    scope_id: UUID | None
    effect: str
    allowed_models: tuple[str, ...]
    allowed_routing_keys: tuple[str, ...]
    default_model_key: str | None
    default_routing_key: str | None
    max_tokens: int | None
    priority: int
    # Free-form metadata mirrored from LLMPolicy.metadata_json. Used to carry
    # per-policy routing hints such as ``routing_strategy=cost_priority``.
    metadata: dict[str, Any] = field(default_factory=dict)


class ModelPolicyEngine:
    """Resolves tenant/cost-center/user/agent/channel policy before routing."""

    def __init__(
        self,
        policies: list[ModelPolicyRule] | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        self.policies = policies or []
        self.session = session

    async def evaluate(
        self,
        request: LLMChatRequest,
        context: LLMRequestContext,
    ) -> PolicyDecision:
        if not request.messages:
            return PolicyDecision(allowed=False, reason="messages_required")

        cost_center_id = await self._cost_center_id(context)
        matched = _matching_policies(self.policies, context, cost_center_id=cost_center_id)
        deny = _first_deny(matched, request)
        if deny is not None:
            return PolicyDecision(
                allowed=False,
                reason=f"model_policy_denied:{deny.name}",
                metadata={"policy_id": str(deny.id), "policy_scope": deny.scope_type},
            )

        allow = _first_allow(matched, request)
        if allow is not None:
            model_key = request.model_key or allow.default_model_key
            routing_key = request.routing_key or allow.default_routing_key
            max_tokens = _effective_max_tokens(request.max_tokens, allow.max_tokens)
            # Surface the allow-policy's routing_strategy (if any) so the
            # ModelRouter can apply cost-aware ordering when enabled.
            routing_strategy = allow.metadata.get("routing_strategy") if allow.metadata else None
            decision_metadata: dict[str, Any] = {
                "policy_id": str(allow.id),
                "policy_scope": allow.scope_type,
                "tenant_id": str(context.tenant_id),
            }
            if routing_strategy:
                decision_metadata["routing_strategy"] = routing_strategy
            return PolicyDecision(
                allowed=True,
                reason=f"model_policy_allowed:{allow.name}",
                model_key=model_key,
                routing_key=routing_key,
                max_tokens=max_tokens,
                metadata=decision_metadata,
            )

        if matched:
            return PolicyDecision(
                allowed=False,
                reason="model_policy_no_matching_allow",
                metadata={
                    "matched_policy_ids": [str(policy.id) for policy in matched],
                    "matched_policy_scopes": [policy.scope_type for policy in matched],
                    "tenant_id": str(context.tenant_id),
                },
            )

        if request.model_key is None and request.routing_key is None:
            return PolicyDecision(
                allowed=True,
                reason="default_route",
                routing_key="default-chat",
                max_tokens=request.max_tokens,
                metadata={"tenant_id": str(context.tenant_id)},
            )

        return PolicyDecision(
            allowed=True,
            reason="explicit_route",
            model_key=request.model_key,
            routing_key=request.routing_key,
            max_tokens=request.max_tokens,
            metadata={"tenant_id": str(context.tenant_id)},
        )

    async def _cost_center_id(self, context: LLMRequestContext) -> UUID | None:
        if context.cost_center_id is not None:
            return context.cost_center_id
        if not any(policy.scope_type == "cost_center" for policy in self.policies):
            return None
        cost_center_id, _source = await resolve_cost_center(self.session, context)
        return cost_center_id


def _matching_policies(
    policies: list[ModelPolicyRule],
    context: LLMRequestContext,
    *,
    cost_center_id: UUID | None = None,
) -> list[ModelPolicyRule]:
    matched = [
        policy for policy in policies if _matches(policy, context, cost_center_id=cost_center_id)
    ]
    return sorted(
        matched,
        key=lambda policy: (-_scope_rank(policy.scope_type), policy.priority, policy.name),
    )


def _matches(
    policy: ModelPolicyRule,
    context: LLMRequestContext,
    *,
    cost_center_id: UUID | None = None,
) -> bool:
    if policy.scope_type == "tenant":
        return policy.scope_id is None
    if policy.scope_type == "department":
        return policy.scope_id == context.department_id
    if policy.scope_type == "cost_center":
        return policy.scope_id == cost_center_id
    if policy.scope_type == "user":
        return policy.scope_id == context.user_id
    if policy.scope_type == "agent":
        return policy.scope_id == context.agent_id
    if policy.scope_type == "channel":
        return policy.scope_id == context.channel_id
    return False


def _scope_rank(scope_type: str) -> int:
    return {
        "tenant": 10,
        "department": 20,
        "cost_center": 25,
        "channel": 30,
        "agent": 40,
        "user": 50,
    }.get(scope_type, 0)


def _first_deny(
    policies: list[ModelPolicyRule],
    request: LLMChatRequest,
) -> ModelPolicyRule | None:
    for policy in policies:
        if policy.effect != "deny":
            continue
        if _policy_targets_request(policy, request):
            return policy
    return None


def _first_allow(
    policies: list[ModelPolicyRule],
    request: LLMChatRequest,
) -> ModelPolicyRule | None:
    for policy in policies:
        if policy.effect != "allow":
            continue
        if not _policy_allows_request(policy, request):
            continue
        return policy
    return None


def _policy_targets_request(
    policy: ModelPolicyRule,
    request: LLMChatRequest,
) -> bool:
    if not policy.allowed_models and not policy.allowed_routing_keys:
        return True
    return bool(
        (request.model_key and request.model_key in policy.allowed_models)
        or (request.routing_key and request.routing_key in policy.allowed_routing_keys)
    )


def _policy_allows_request(
    policy: ModelPolicyRule,
    request: LLMChatRequest,
) -> bool:
    if (
        request.model_key
        and policy.allowed_models
        and request.model_key not in policy.allowed_models
    ):
        return False
    if (
        request.routing_key
        and policy.allowed_routing_keys
        and request.routing_key not in policy.allowed_routing_keys
    ):
        return False
    if request.model_key is None and request.routing_key is None:
        return bool(policy.default_model_key or policy.default_routing_key)
    return True


def _effective_max_tokens(requested: int | None, policy_limit: int | None) -> int | None:
    if policy_limit is None:
        return requested
    if requested is None:
        return policy_limit
    return min(requested, policy_limit)
