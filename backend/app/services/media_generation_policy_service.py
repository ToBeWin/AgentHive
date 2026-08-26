from typing import Any, cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.deps import Principal
from app.llm.policy import ModelPolicyEngine, ModelPolicyRule
from app.llm.schemas import LLMChatRequest, LLMRequestContext, Message
from app.media.schemas import MediaGenerationPlan
from app.models.llm import LLMPolicy
from app.services.audit_service import record_audit_event


async def enforce_media_generation_model_policy(
    session: AsyncSession,
    principal: Principal,
    plan: MediaGenerationPlan,
    *,
    request_id: str | None = None,
    department_id: UUID | None = None,
    agent_id: UUID | None = None,
    conversation_id: UUID | None = None,
) -> None:
    context = LLMRequestContext(
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        department_id=department_id,
        agent_id=agent_id,
        conversation_id=conversation_id,
        request_id=request_id or "media-generation-policy",
        source=f"media_generation.{plan.kind.value}",
    )
    try:
        decision = await ModelPolicyEngine(
            await _runtime_policy_rules(session, principal),
            session=session,
        ).evaluate(
            LLMChatRequest(
                model_key=plan.model_key,
                routing_key=plan.routing_key,
                messages=[Message(role="user", content=plan.prompt)],
                metadata={
                    "media_kind": plan.kind.value,
                    "provider_key": plan.provider_key,
                    "provider_type": plan.provider_type.value,
                },
            ),
            context,
        )
    except (OSError, SQLAlchemyError) as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Media generation model policy storage is unavailable.",
        ) from exc

    if decision.allowed:
        return

    await record_audit_event(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        request_id=request_id,
        action="media.generation.policy_denied",
        resource_type="media_generation",
        resource_id=None,
        status="failure",
        details={
            "reason": decision.reason,
            "model_key": plan.model_key,
            "routing_key": plan.routing_key,
            "media_kind": plan.kind.value,
            "policy": decision.metadata,
        },
    )
    await session.commit()
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Media generation model policy denied request: {decision.reason}",
    )


async def _runtime_policy_rules(
    session: AsyncSession,
    principal: Principal,
) -> list[ModelPolicyRule]:
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
