from collections import defaultdict
from collections.abc import Iterable
import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import io
import json
from typing import Any, cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, case, func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.deps import Principal
from app.models.agent_module import AgentInstance
from app.models.base import utc_now
from app.models.channel import ChannelConfig
from app.models.llm import LLMBudget, LLMBudgetLedger, LLMUsage
from app.models.org import Department
from app.models.tenant import CostCenter
from app.models.user import User, UserDepartment
from app.schemas.budget import (
    BudgetEventType,
    BudgetGovernanceTargetItem,
    BudgetGovernanceTargetsResponse,
    BudgetLedgerItem,
    BudgetLedgerResponse,
    BudgetLimitHealth,
    BudgetLimitType,
    BudgetPeriod,
    BudgetPolicyListResponse,
    BudgetPolicyResponse,
    BudgetPolicyStatus,
    BudgetPolicyStatusUpdateRequest,
    BudgetPolicyUpsertRequest,
    BudgetScopeSummary,
    BudgetScopeType,
    BudgetSummaryResponse,
    UsageBreakdownDimension,
    UsageBreakdownItem,
    UsageBreakdownResponse,
    UsageLedgerItem,
    UsageLedgerResponse,
)
from app.services.audit_service import record_audit_event


async def get_budget_summary(
    session: AsyncSession,
    principal: Principal,
    *,
    period: BudgetPeriod = BudgetPeriod.MONTHLY,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> BudgetSummaryResponse:
    start, end = _resolve_period_window(period, period_start, period_end)
    generated_at = utc_now()
    default_response = BudgetSummaryResponse(
        tenant_id=principal.tenant_id,
        period=period,
        period_start=start,
        period_end=end,
        generated_at=generated_at,
        metadata={"storage": "unavailable"},
    )

    try:
        policy_visibility_filters = await _budget_policy_visibility_filters(session, principal)
        policies_result = await session.execute(
            select(LLMBudget).where(
                cast(ColumnElement[bool], LLMBudget.tenant_id == principal.tenant_id),
                *policy_visibility_filters,
            )
        )
        policies = list(policies_result.scalars().all())
        usage_visibility_filters = await _budget_data_visibility_filters(
            session, principal, LLMUsage
        )
        usage_result = await session.execute(
            select(
                func.coalesce(func.sum(LLMUsage.cost_usd), Decimal("0")),
                func.coalesce(func.sum(LLMUsage.total_tokens), 0),
            ).where(
                cast(ColumnElement[bool], LLMUsage.tenant_id == principal.tenant_id),
                cast(ColumnElement[bool], LLMUsage.created_at >= start),
                cast(ColumnElement[bool], LLMUsage.created_at < end),
                *usage_visibility_filters,
            )
        )
        total_amount_spent, total_tokens_used = usage_result.one()
    except (OSError, SQLAlchemyError):
        await session.rollback()
        return default_response

    policy_responses = [
        _to_policy_response(
            policy,
            amount_spent=amount_spent,
            tokens_used=tokens_used,
        )
        for policy, amount_spent, tokens_used in await _policies_with_usage(
            session,
            principal,
            policies,
            start,
            end,
        )
    ]
    active_policies = [
        policy for policy in policy_responses if policy.status == BudgetPolicyStatus.ACTIVE
    ]
    by_scope = _summarize_by_scope(active_policies)
    total_token_limit = _sum_optional_int(policy.token_limit for policy in active_policies)

    return BudgetSummaryResponse(
        tenant_id=principal.tenant_id,
        period=period,
        period_start=start,
        period_end=end,
        generated_at=generated_at,
        policy_count=len(policy_responses),
        active_policy_count=len(active_policies),
        hard_policy_count=sum(
            1 for policy in active_policies if policy.budget_type == BudgetLimitType.HARD
        ),
        soft_policy_count=sum(
            1 for policy in active_policies if policy.budget_type == BudgetLimitType.SOFT
        ),
        warning_policy_count=sum(
            1 for policy in policy_responses if policy.health == BudgetLimitHealth.WARNING
        ),
        exceeded_policy_count=sum(
            1 for policy in policy_responses if policy.health == BudgetLimitHealth.EXCEEDED
        ),
        total_amount_limit=sum((policy.amount_limit for policy in active_policies), Decimal("0")),
        total_amount_spent=Decimal(total_amount_spent or 0),
        total_token_limit=total_token_limit,
        total_tokens_used=int(total_tokens_used or 0),
        by_scope=by_scope,
        metadata={
            "storage": "llm_budgets",
            "usage_storage": "llm_usage",
            "currency_note": "Current persistence stores amount_usd; API currency is normalized to USD.",
        },
    )


async def list_budget_policies(
    session: AsyncSession,
    principal: Principal,
    *,
    scope_type: BudgetScopeType | None = None,
    status_filter: BudgetPolicyStatus | None = None,
) -> BudgetPolicyListResponse:
    try:
        visibility_filters = await _budget_policy_visibility_filters(session, principal)
        statement = select(LLMBudget).where(
            cast(ColumnElement[bool], LLMBudget.tenant_id == principal.tenant_id),
            *visibility_filters,
        )
        if scope_type is not None:
            statement = statement.where(
                cast(ColumnElement[bool], LLMBudget.scope_type == scope_type.value)
            )
        if status_filter is not None:
            statement = statement.where(
                cast(Any, LLMBudget.is_active).is_(status_filter == BudgetPolicyStatus.ACTIVE)
            )
        statement = statement.order_by(cast(Any, LLMBudget.created_at).desc())
        result = await session.execute(statement)
    except (OSError, SQLAlchemyError):
        await session.rollback()
        return BudgetPolicyListResponse(policies=[])

    policies = list(result.scalars().all())
    start, end = _resolve_period_window(BudgetPeriod.MONTHLY, None, None)
    return BudgetPolicyListResponse(
        policies=[
            _to_policy_response(policy, amount_spent=amount_spent, tokens_used=tokens_used)
            for policy, amount_spent, tokens_used in await _policies_with_usage(
                session,
                principal,
                policies,
                start,
                end,
            )
        ]
    )


async def list_budget_governance_targets(
    session: AsyncSession,
    principal: Principal,
) -> BudgetGovernanceTargetsResponse:
    departments_result = await session.execute(
        select(Department)
        .where(cast(ColumnElement[bool], Department.tenant_id == principal.tenant_id))
        .order_by(cast(Any, Department.sort_order), cast(Any, Department.name))
    )
    cost_centers_result = await session.execute(
        select(CostCenter)
        .where(cast(ColumnElement[bool], CostCenter.tenant_id == principal.tenant_id))
        .order_by(cast(Any, CostCenter.code), cast(Any, CostCenter.name))
    )
    users_result = await session.execute(
        select(User)
        .where(
            cast(ColumnElement[bool], User.tenant_id == principal.tenant_id),
            cast(Any, User.deleted_at).is_(None),
        )
        .order_by(cast(Any, User.full_name), cast(Any, User.email))
    )
    agents_result = await session.execute(
        select(AgentInstance)
        .where(AgentInstance.tenant_id == principal.tenant_id)
        .order_by(AgentInstance.name, AgentInstance.slug)
    )
    channels_result = await session.execute(
        select(ChannelConfig)
        .where(ChannelConfig.tenant_id == principal.tenant_id)
        .order_by(ChannelConfig.name, ChannelConfig.channel_type)
    )

    return BudgetGovernanceTargetsResponse(
        departments=[
            BudgetGovernanceTargetItem(
                id=department.id,
                label=department.name,
                description=department.description,
                metadata={
                    "parent_id": str(department.parent_id) if department.parent_id else None,
                    "sort_order": department.sort_order,
                },
            )
            for department in departments_result.scalars().all()
        ],
        cost_centers=[
            BudgetGovernanceTargetItem(
                id=cost_center.id,
                label=f"{cost_center.code} - {cost_center.name}",
                description=cost_center.description,
                status="active" if cost_center.is_active else "inactive",
                metadata={
                    "code": cost_center.code,
                    "department_id": str(cost_center.department_id)
                    if cost_center.department_id
                    else None,
                    "monthly_budget_usd": str(cost_center.monthly_budget_usd)
                    if cost_center.monthly_budget_usd is not None
                    else None,
                },
            )
            for cost_center in cost_centers_result.scalars().all()
        ],
        users=[
            BudgetGovernanceTargetItem(
                id=user.id,
                label=f"{user.full_name or user.username or user.email} ({user.email})",
                status="active" if user.is_active else "inactive",
                metadata={
                    "email": user.email,
                    "is_tenant_admin": user.is_tenant_admin,
                },
            )
            for user in users_result.scalars().all()
        ],
        agents=[
            BudgetGovernanceTargetItem(
                id=agent.id,
                label=f"{agent.name} ({agent.agent_key}:{agent.slug}, {agent.status})",
                description=agent.description,
                status=agent.status,
                metadata={
                    "agent_key": agent.agent_key,
                    "module_key": agent.module_key,
                    "department_id": str(agent.department_id) if agent.department_id else None,
                    "visibility": agent.visibility,
                },
            )
            for agent in agents_result.scalars().all()
        ],
        channels=[
            BudgetGovernanceTargetItem(
                id=channel.id,
                label=f"{channel.name} ({channel.channel_type}:{channel.channel_key})",
                status=channel.status,
                metadata={
                    "channel_type": channel.channel_type,
                    "channel_key": channel.channel_key,
                    "agent_id": str(channel.agent_id) if channel.agent_id else None,
                },
            )
            for channel in channels_result.scalars().all()
        ],
    )


async def upsert_budget_policy(
    session: AsyncSession,
    principal: Principal,
    payload: BudgetPolicyUpsertRequest,
    *,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> BudgetPolicyResponse:
    if payload.currency != "USD":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Only USD is currently persisted by the first budget storage version.",
        )

    try:
        await _validate_budget_scope_target(session, payload, principal)

        action = "budget.policy.create"
        policy: LLMBudget | None
        if payload.id is None:
            policy = LLMBudget(tenant_id=principal.tenant_id)
            session.add(policy)
        else:
            result = await session.execute(
                select(LLMBudget).where(
                    cast(ColumnElement[bool], LLMBudget.tenant_id == principal.tenant_id),
                    cast(ColumnElement[bool], LLMBudget.id == payload.id),
                )
            )
            policy = result.scalar_one_or_none()
            if policy is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Budget policy not found.",
                )
            action = "budget.policy.update"

        policy.scope_type = payload.scope_type.value
        policy.scope_id = payload.scope_id
        policy.period = payload.period.value
        policy.custom_period_start = (
            payload.custom_period_start if payload.period == BudgetPeriod.CUSTOM else None
        )
        policy.custom_period_end = (
            payload.custom_period_end if payload.period == BudgetPeriod.CUSTOM else None
        )
        policy.amount_usd = payload.amount_limit
        policy.token_limit = payload.token_limit
        policy.hard_limit = payload.budget_type == BudgetLimitType.HARD
        policy.alert_threshold_pct = payload.alert_threshold_pct
        policy.is_active = payload.status == BudgetPolicyStatus.ACTIVE
        policy.updated_at = utc_now()

        await session.flush()
        await record_audit_event(
            session,
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action=action,
            resource_type="llm_budget",
            resource_id=policy.id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "scope_type": payload.scope_type.value,
                "scope_id": str(payload.scope_id) if payload.scope_id else None,
                "period": payload.period.value,
                "custom_period_start": (
                    payload.custom_period_start.isoformat() if payload.custom_period_start else None
                ),
                "custom_period_end": (
                    payload.custom_period_end.isoformat() if payload.custom_period_end else None
                ),
                "budget_type": payload.budget_type.value,
                "currency": payload.currency,
                "amount_limit": str(payload.amount_limit),
                "token_limit": payload.token_limit,
                "alert_threshold_pct": payload.alert_threshold_pct,
                "status": payload.status.value,
            },
        )
        await session.commit()
        await session.refresh(policy)
    except HTTPException:
        await session.rollback()
        raise
    except (OSError, SQLAlchemyError) as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Budget policy storage is not available.",
        ) from exc

    return _to_policy_response(
        policy,
        amount_spent=Decimal("0"),
        tokens_used=0,
        name=payload.name,
        description=payload.description,
    )


async def update_budget_policy_status(
    session: AsyncSession,
    principal: Principal,
    policy_id: UUID,
    payload: BudgetPolicyStatusUpdateRequest,
    *,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> BudgetPolicyResponse:
    try:
        result = await session.execute(
            select(LLMBudget).where(
                LLMBudget.tenant_id == principal.tenant_id,
                LLMBudget.id == policy_id,
            )
        )
        policy = result.scalar_one_or_none()
        if policy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Budget policy not found.",
            )

        previous_status = (
            BudgetPolicyStatus.ACTIVE if policy.is_active else BudgetPolicyStatus.INACTIVE
        )
        policy.is_active = payload.status == BudgetPolicyStatus.ACTIVE
        policy.updated_at = utc_now()

        await record_audit_event(
            session,
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action="budget.policy.status.update",
            resource_type="llm_budget",
            resource_id=policy.id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "previous_status": previous_status.value,
                "status": payload.status.value,
                "scope_type": policy.scope_type,
                "scope_id": str(policy.scope_id) if policy.scope_id else None,
            },
        )
        await session.commit()
        await session.refresh(policy)
    except HTTPException:
        await session.rollback()
        raise
    except (OSError, SQLAlchemyError) as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Budget policy storage is not available.",
        ) from exc

    return _to_policy_response(policy, amount_spent=Decimal("0"), tokens_used=0)


async def list_usage_ledger(
    session: AsyncSession,
    principal: Principal,
    *,
    limit: int = 50,
    offset: int = 0,
    start: datetime | None = None,
    end: datetime | None = None,
    user_id: UUID | None = None,
    department_id: UUID | None = None,
    cost_center_id: UUID | None = None,
    agent_id: UUID | None = None,
    channel_id: UUID | None = None,
    model_key: str | None = None,
    status_filter: str | None = None,
) -> UsageLedgerResponse:
    try:
        filters = _usage_ledger_filters(
            principal,
            start=start,
            end=end,
            user_id=user_id,
            department_id=department_id,
            cost_center_id=cost_center_id,
            agent_id=agent_id,
            channel_id=channel_id,
            model_key=model_key,
            status_filter=status_filter,
        )
        filters.extend(await _budget_data_visibility_filters(session, principal, LLMUsage))

        total_result = await session.execute(
            select(func.count()).select_from(LLMUsage).where(*filters)
        )
        total = int(total_result.scalar_one())
        rows_result = await session.execute(
            select(LLMUsage)
            .where(*filters)
            .order_by(cast(Any, LLMUsage.created_at).desc())
            .offset(offset)
            .limit(limit)
        )
    except (OSError, SQLAlchemyError):
        await session.rollback()
        return UsageLedgerResponse(items=[], total=0, limit=limit, offset=offset)

    return UsageLedgerResponse(
        items=[_to_usage_ledger_item(row) for row in rows_result.scalars().all()],
        total=total,
        limit=limit,
        offset=offset,
    )


async def export_usage_ledger_csv(
    session: AsyncSession,
    principal: Principal,
    *,
    limit: int = 5000,
    start: datetime | None = None,
    end: datetime | None = None,
    user_id: UUID | None = None,
    department_id: UUID | None = None,
    cost_center_id: UUID | None = None,
    agent_id: UUID | None = None,
    channel_id: UUID | None = None,
    model_key: str | None = None,
    status_filter: str | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> str:
    items = await _export_usage_ledger_items(
        session,
        principal,
        limit=limit,
        start=start,
        end=end,
        user_id=user_id,
        department_id=department_id,
        cost_center_id=cost_center_id,
        agent_id=agent_id,
        channel_id=channel_id,
        model_key=model_key,
        status_filter=status_filter,
    )
    await _record_ledger_export_audit(
        session,
        principal,
        action="budget.usage_ledger.export",
        export_format="csv",
        item_count=len(items),
        limit=limit,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        filters={
            "start": start,
            "end": end,
            "user_id": user_id,
            "department_id": department_id,
            "cost_center_id": cost_center_id,
            "agent_id": agent_id,
            "channel_id": channel_id,
            "model_key": model_key,
            "status": status_filter,
        },
    )
    return usage_ledger_to_csv(items)


async def export_usage_ledger_json(
    session: AsyncSession,
    principal: Principal,
    *,
    limit: int = 5000,
    start: datetime | None = None,
    end: datetime | None = None,
    user_id: UUID | None = None,
    department_id: UUID | None = None,
    cost_center_id: UUID | None = None,
    agent_id: UUID | None = None,
    channel_id: UUID | None = None,
    model_key: str | None = None,
    status_filter: str | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> str:
    items = await _export_usage_ledger_items(
        session,
        principal,
        limit=limit,
        start=start,
        end=end,
        user_id=user_id,
        department_id=department_id,
        cost_center_id=cost_center_id,
        agent_id=agent_id,
        channel_id=channel_id,
        model_key=model_key,
        status_filter=status_filter,
    )
    await _record_ledger_export_audit(
        session,
        principal,
        action="budget.usage_ledger.export",
        export_format="json",
        item_count=len(items),
        limit=limit,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        filters={
            "start": start,
            "end": end,
            "user_id": user_id,
            "department_id": department_id,
            "cost_center_id": cost_center_id,
            "agent_id": agent_id,
            "channel_id": channel_id,
            "model_key": model_key,
            "status": status_filter,
        },
    )
    return usage_ledger_to_json(items)


async def list_budget_ledger(
    session: AsyncSession,
    principal: Principal,
    *,
    limit: int = 50,
    offset: int = 0,
    start: datetime | None = None,
    end: datetime | None = None,
    budget_id: UUID | None = None,
    reservation_id: str | None = None,
    request_id: str | None = None,
    event_type: BudgetEventType | None = None,
    scope_type: BudgetScopeType | None = None,
    scope_id: UUID | None = None,
    user_id: UUID | None = None,
    department_id: UUID | None = None,
    cost_center_id: UUID | None = None,
    agent_id: UUID | None = None,
    channel_id: UUID | None = None,
) -> BudgetLedgerResponse:
    try:
        filters = _budget_ledger_filters(
            principal,
            start=start,
            end=end,
            budget_id=budget_id,
            reservation_id=reservation_id,
            request_id=request_id,
            event_type=event_type,
            scope_type=scope_type,
            scope_id=scope_id,
            user_id=user_id,
            department_id=department_id,
            cost_center_id=cost_center_id,
            agent_id=agent_id,
            channel_id=channel_id,
        )
        filters.extend(await _budget_data_visibility_filters(session, principal, LLMBudgetLedger))

        total_result = await session.execute(
            select(func.count()).select_from(LLMBudgetLedger).where(*filters)
        )
        total = int(total_result.scalar_one())
        rows_result = await session.execute(
            select(LLMBudgetLedger)
            .where(*filters)
            .order_by(cast(Any, LLMBudgetLedger.created_at).desc())
            .offset(offset)
            .limit(limit)
        )
    except (OSError, SQLAlchemyError):
        await session.rollback()
        return BudgetLedgerResponse(items=[], total=0, limit=limit, offset=offset)

    return BudgetLedgerResponse(
        items=[_to_budget_ledger_item(row) for row in rows_result.scalars().all()],
        total=total,
        limit=limit,
        offset=offset,
    )


async def export_budget_ledger_csv(
    session: AsyncSession,
    principal: Principal,
    *,
    limit: int = 5000,
    start: datetime | None = None,
    end: datetime | None = None,
    budget_id: UUID | None = None,
    reservation_id: str | None = None,
    request_id: str | None = None,
    event_type: BudgetEventType | None = None,
    scope_type: BudgetScopeType | None = None,
    scope_id: UUID | None = None,
    user_id: UUID | None = None,
    department_id: UUID | None = None,
    cost_center_id: UUID | None = None,
    agent_id: UUID | None = None,
    channel_id: UUID | None = None,
    request_id_for_audit: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> str:
    items = await _export_budget_ledger_items(
        session,
        principal,
        limit=limit,
        start=start,
        end=end,
        budget_id=budget_id,
        reservation_id=reservation_id,
        request_id=request_id,
        event_type=event_type,
        scope_type=scope_type,
        scope_id=scope_id,
        user_id=user_id,
        department_id=department_id,
        cost_center_id=cost_center_id,
        agent_id=agent_id,
        channel_id=channel_id,
    )
    await _record_ledger_export_audit(
        session,
        principal,
        action="budget.budget_ledger.export",
        export_format="csv",
        item_count=len(items),
        limit=limit,
        request_id=request_id_for_audit,
        ip_address=ip_address,
        user_agent=user_agent,
        filters={
            "start": start,
            "end": end,
            "budget_id": budget_id,
            "reservation_id": reservation_id,
            "request_id": request_id,
            "event_type": event_type.value if event_type else None,
            "scope_type": scope_type.value if scope_type else None,
            "scope_id": scope_id,
            "user_id": user_id,
            "department_id": department_id,
            "cost_center_id": cost_center_id,
            "agent_id": agent_id,
            "channel_id": channel_id,
        },
    )
    return budget_ledger_to_csv(items)


async def export_budget_ledger_json(
    session: AsyncSession,
    principal: Principal,
    *,
    limit: int = 5000,
    start: datetime | None = None,
    end: datetime | None = None,
    budget_id: UUID | None = None,
    reservation_id: str | None = None,
    request_id: str | None = None,
    event_type: BudgetEventType | None = None,
    scope_type: BudgetScopeType | None = None,
    scope_id: UUID | None = None,
    user_id: UUID | None = None,
    department_id: UUID | None = None,
    cost_center_id: UUID | None = None,
    agent_id: UUID | None = None,
    channel_id: UUID | None = None,
    request_id_for_audit: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> str:
    items = await _export_budget_ledger_items(
        session,
        principal,
        limit=limit,
        start=start,
        end=end,
        budget_id=budget_id,
        reservation_id=reservation_id,
        request_id=request_id,
        event_type=event_type,
        scope_type=scope_type,
        scope_id=scope_id,
        user_id=user_id,
        department_id=department_id,
        cost_center_id=cost_center_id,
        agent_id=agent_id,
        channel_id=channel_id,
    )
    await _record_ledger_export_audit(
        session,
        principal,
        action="budget.budget_ledger.export",
        export_format="json",
        item_count=len(items),
        limit=limit,
        request_id=request_id_for_audit,
        ip_address=ip_address,
        user_agent=user_agent,
        filters={
            "start": start,
            "end": end,
            "budget_id": budget_id,
            "reservation_id": reservation_id,
            "request_id": request_id,
            "event_type": event_type.value if event_type else None,
            "scope_type": scope_type.value if scope_type else None,
            "scope_id": scope_id,
            "user_id": user_id,
            "department_id": department_id,
            "cost_center_id": cost_center_id,
            "agent_id": agent_id,
            "channel_id": channel_id,
        },
    )
    return budget_ledger_to_json(items)


async def get_usage_breakdown(
    session: AsyncSession,
    principal: Principal,
    *,
    dimension: UsageBreakdownDimension,
    limit: int = 20,
    start: datetime | None = None,
    end: datetime | None = None,
    status_filter: str | None = None,
) -> UsageBreakdownResponse:
    field = _usage_breakdown_field(dimension)
    try:
        filters: list[ColumnElement[bool]] = [
            cast(ColumnElement[bool], LLMUsage.tenant_id == principal.tenant_id)
        ]
        filters.extend(await _budget_data_visibility_filters(session, principal, LLMUsage))
        if start is not None:
            filters.append(cast(ColumnElement[bool], LLMUsage.created_at >= start))
        if end is not None:
            filters.append(cast(ColumnElement[bool], LLMUsage.created_at < end))
        if status_filter is not None:
            filters.append(cast(ColumnElement[bool], LLMUsage.status == status_filter))

        breakdown_cols: list[Any] = [
            field,
            func.count(cast(Any, LLMUsage.id)),
            func.coalesce(
                func.sum(
                    case((cast(ColumnElement[bool], LLMUsage.status == "success"), 1), else_=0)
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case((cast(ColumnElement[bool], LLMUsage.status != "success"), 1), else_=0)
                ),
                0,
            ),
            func.coalesce(func.sum(LLMUsage.input_tokens), 0),
            func.coalesce(func.sum(LLMUsage.output_tokens), 0),
            func.coalesce(func.sum(LLMUsage.total_tokens), 0),
            func.coalesce(func.sum(LLMUsage.cost_usd), Decimal("0")),
            func.max(LLMUsage.created_at),
        ]
        result = await session.execute(
            select(*breakdown_cols)
            .where(*filters)
            .group_by(field)
            .order_by(func.coalesce(func.sum(LLMUsage.cost_usd), Decimal("0")).desc())
            .limit(limit)
        )
        items = [_to_usage_breakdown_item(dimension, row) for row in result.all()]
    except (OSError, SQLAlchemyError):
        await session.rollback()
        items = []

    return UsageBreakdownResponse(
        tenant_id=principal.tenant_id,
        dimension=dimension,
        period_start=start,
        period_end=end,
        items=items,
        total_request_count=sum(item.request_count for item in items),
        total_cost_amount=sum((item.cost_amount for item in items), Decimal("0")),
        total_tokens=sum(item.total_tokens for item in items),
    )


async def _record_ledger_export_audit(
    session: AsyncSession,
    principal: Principal,
    *,
    action: str,
    export_format: str,
    item_count: int,
    limit: int,
    request_id: str | None,
    ip_address: str | None,
    user_agent: str | None,
    filters: dict[str, object],
) -> None:
    try:
        await record_audit_event(
            session,
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action=action,
            resource_type="llm_budget",
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "format": export_format,
                "item_count": item_count,
                "limit": limit,
                "filters": _serialize_export_filters(filters),
            },
        )
        await session.commit()
    except Exception:
        await session.rollback()


def _serialize_export_filters(filters: dict[str, object]) -> dict[str, object]:
    serialized: dict[str, object] = {}
    for key, value in filters.items():
        if value is None:
            continue
        if isinstance(value, datetime):
            serialized[key] = value.isoformat()
        elif isinstance(value, UUID):
            serialized[key] = str(value)
        else:
            serialized[key] = value
    return serialized


def _can_read_all_budget_data(principal: Principal) -> bool:
    return bool(
        {
            "tenant.admin",
            "budgets:write",
            "budgets:export",
        }.intersection(principal.permissions)
    )


async def _principal_department_ids(session: AsyncSession, principal: Principal) -> set[UUID]:
    result = await session.execute(
        select(UserDepartment.department_id)
        .join(
            Department,
            cast(ColumnElement[bool], Department.id == UserDepartment.department_id),
        )
        .where(
            cast(ColumnElement[bool], UserDepartment.user_id == principal.user_id),
            cast(ColumnElement[bool], Department.tenant_id == principal.tenant_id),
        )
    )
    return set(result.scalars().all())


async def _budget_data_visibility_filters(
    session: AsyncSession,
    principal: Principal,
    model: type[LLMUsage] | type[LLMBudgetLedger],
) -> list[ColumnElement[bool]]:
    if _can_read_all_budget_data(principal):
        return []

    department_ids = await _principal_department_ids(session, principal)
    user_column = model.user_id
    department_column = model.department_id
    if department_ids:
        return [
            or_(
                cast(ColumnElement[bool], user_column == principal.user_id),
                cast(Any, department_column).in_(department_ids),
            )
        ]
    return [cast(ColumnElement[bool], user_column == principal.user_id)]


async def _budget_policy_visibility_filters(
    session: AsyncSession,
    principal: Principal,
) -> list[ColumnElement[bool]]:
    if _can_read_all_budget_data(principal):
        return []

    department_ids = await _principal_department_ids(session, principal)
    filters = [
        cast(ColumnElement[bool], LLMBudget.scope_type == BudgetScopeType.USER.value),
        cast(ColumnElement[bool], LLMBudget.scope_id == principal.user_id),
    ]
    if department_ids:
        return [
            or_(
                cast(
                    ColumnElement[bool],
                    (LLMBudget.scope_type == BudgetScopeType.USER.value)
                    & (LLMBudget.scope_id == principal.user_id),
                ),
                cast(
                    ColumnElement[bool],
                    (LLMBudget.scope_type == BudgetScopeType.DEPARTMENT.value)
                    & cast(Any, LLMBudget.scope_id).in_(department_ids),
                ),
            )
        ]
    return filters


async def _export_usage_ledger_items(
    session: AsyncSession,
    principal: Principal,
    *,
    limit: int,
    start: datetime | None,
    end: datetime | None,
    user_id: UUID | None,
    department_id: UUID | None,
    cost_center_id: UUID | None,
    agent_id: UUID | None,
    channel_id: UUID | None,
    model_key: str | None,
    status_filter: str | None,
) -> list[UsageLedgerItem]:
    try:
        filters = _usage_ledger_filters(
            principal,
            start=start,
            end=end,
            user_id=user_id,
            department_id=department_id,
            cost_center_id=cost_center_id,
            agent_id=agent_id,
            channel_id=channel_id,
            model_key=model_key,
            status_filter=status_filter,
        )
        filters.extend(await _budget_data_visibility_filters(session, principal, LLMUsage))
        rows_result = await session.execute(
            select(LLMUsage)
            .where(*filters)
            .order_by(cast(Any, LLMUsage.created_at).desc())
            .limit(limit)
        )
    except (OSError, SQLAlchemyError):
        await session.rollback()
        return []

    return [_to_usage_ledger_item(row) for row in rows_result.scalars().all()]


async def _export_budget_ledger_items(
    session: AsyncSession,
    principal: Principal,
    *,
    limit: int,
    start: datetime | None,
    end: datetime | None,
    budget_id: UUID | None,
    reservation_id: str | None,
    request_id: str | None,
    event_type: BudgetEventType | None,
    scope_type: BudgetScopeType | None,
    scope_id: UUID | None,
    user_id: UUID | None,
    department_id: UUID | None,
    cost_center_id: UUID | None,
    agent_id: UUID | None,
    channel_id: UUID | None,
) -> list[BudgetLedgerItem]:
    try:
        filters = _budget_ledger_filters(
            principal,
            start=start,
            end=end,
            budget_id=budget_id,
            reservation_id=reservation_id,
            request_id=request_id,
            event_type=event_type,
            scope_type=scope_type,
            scope_id=scope_id,
            user_id=user_id,
            department_id=department_id,
            cost_center_id=cost_center_id,
            agent_id=agent_id,
            channel_id=channel_id,
        )
        filters.extend(await _budget_data_visibility_filters(session, principal, LLMBudgetLedger))
        rows_result = await session.execute(
            select(LLMBudgetLedger)
            .where(*filters)
            .order_by(cast(Any, LLMBudgetLedger.created_at).desc())
            .limit(limit)
        )
    except (OSError, SQLAlchemyError):
        await session.rollback()
        return []

    return [_to_budget_ledger_item(row) for row in rows_result.scalars().all()]


def _usage_ledger_filters(
    principal: Principal,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    user_id: UUID | None = None,
    department_id: UUID | None = None,
    cost_center_id: UUID | None = None,
    agent_id: UUID | None = None,
    channel_id: UUID | None = None,
    model_key: str | None = None,
    status_filter: str | None = None,
) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = [
        cast(ColumnElement[bool], LLMUsage.tenant_id == principal.tenant_id)
    ]
    if start is not None:
        filters.append(cast(ColumnElement[bool], LLMUsage.created_at >= start))
    if end is not None:
        filters.append(cast(ColumnElement[bool], LLMUsage.created_at < end))
    if user_id is not None:
        filters.append(cast(ColumnElement[bool], LLMUsage.user_id == user_id))
    if department_id is not None:
        filters.append(cast(ColumnElement[bool], LLMUsage.department_id == department_id))
    if cost_center_id is not None:
        filters.append(cast(ColumnElement[bool], LLMUsage.cost_center_id == cost_center_id))
    if agent_id is not None:
        filters.append(cast(ColumnElement[bool], LLMUsage.agent_id == agent_id))
    if channel_id is not None:
        filters.append(cast(ColumnElement[bool], LLMUsage.channel_id == channel_id))
    if model_key is not None:
        filters.append(cast(ColumnElement[bool], LLMUsage.model_key == model_key))
    if status_filter is not None:
        filters.append(cast(ColumnElement[bool], LLMUsage.status == status_filter))
    return filters


def _budget_ledger_filters(
    principal: Principal,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    budget_id: UUID | None = None,
    reservation_id: str | None = None,
    request_id: str | None = None,
    event_type: BudgetEventType | None = None,
    scope_type: BudgetScopeType | None = None,
    scope_id: UUID | None = None,
    user_id: UUID | None = None,
    department_id: UUID | None = None,
    cost_center_id: UUID | None = None,
    agent_id: UUID | None = None,
    channel_id: UUID | None = None,
) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = [
        cast(ColumnElement[bool], LLMBudgetLedger.tenant_id == principal.tenant_id)
    ]
    if start is not None:
        filters.append(cast(ColumnElement[bool], LLMBudgetLedger.created_at >= start))
    if end is not None:
        filters.append(cast(ColumnElement[bool], LLMBudgetLedger.created_at < end))
    if budget_id is not None:
        filters.append(cast(ColumnElement[bool], LLMBudgetLedger.budget_id == budget_id))
    if reservation_id is not None:
        filters.append(cast(ColumnElement[bool], LLMBudgetLedger.reservation_id == reservation_id))
    if request_id is not None:
        filters.append(cast(ColumnElement[bool], LLMBudgetLedger.request_id == request_id))
    if event_type is not None:
        filters.append(cast(ColumnElement[bool], LLMBudgetLedger.event_type == event_type.value))
    if scope_type is not None:
        filters.append(cast(ColumnElement[bool], LLMBudgetLedger.scope_type == scope_type.value))
    if scope_id is not None:
        filters.append(cast(ColumnElement[bool], LLMBudgetLedger.scope_id == scope_id))
    if user_id is not None:
        filters.append(cast(ColumnElement[bool], LLMBudgetLedger.user_id == user_id))
    if department_id is not None:
        filters.append(cast(ColumnElement[bool], LLMBudgetLedger.department_id == department_id))
    if cost_center_id is not None:
        filters.append(cast(ColumnElement[bool], LLMBudgetLedger.cost_center_id == cost_center_id))
    if agent_id is not None:
        filters.append(cast(ColumnElement[bool], LLMBudgetLedger.agent_id == agent_id))
    if channel_id is not None:
        filters.append(cast(ColumnElement[bool], LLMBudgetLedger.channel_id == channel_id))
    return filters


async def _policies_with_usage(
    session: AsyncSession,
    principal: Principal,
    policies: list[LLMBudget],
    start: datetime,
    end: datetime,
) -> list[tuple[LLMBudget, Decimal, int]]:
    rows: list[tuple[LLMBudget, Decimal, int]] = []
    for policy in policies:
        policy_start, policy_end = _policy_period_window(
            policy, default_start=start, default_end=end
        )
        filters: list[ColumnElement[bool]] = [
            cast(ColumnElement[bool], LLMUsage.tenant_id == principal.tenant_id),
            cast(ColumnElement[bool], LLMUsage.status == "success"),
            cast(ColumnElement[bool], LLMUsage.created_at >= policy_start),
            cast(ColumnElement[bool], LLMUsage.created_at < policy_end),
        ]
        if policy.scope_type == BudgetScopeType.DEPARTMENT.value and policy.scope_id is not None:
            filters.append(cast(ColumnElement[bool], LLMUsage.department_id == policy.scope_id))
        elif policy.scope_type == BudgetScopeType.COST_CENTER.value and policy.scope_id is not None:
            filters.append(cast(ColumnElement[bool], LLMUsage.cost_center_id == policy.scope_id))
        elif policy.scope_type == BudgetScopeType.USER.value and policy.scope_id is not None:
            filters.append(cast(ColumnElement[bool], LLMUsage.user_id == policy.scope_id))
        elif policy.scope_type == BudgetScopeType.AGENT.value and policy.scope_id is not None:
            filters.append(cast(ColumnElement[bool], LLMUsage.agent_id == policy.scope_id))
        elif policy.scope_type == BudgetScopeType.CHANNEL.value and policy.scope_id is not None:
            filters.append(cast(ColumnElement[bool], LLMUsage.channel_id == policy.scope_id))
        elif policy.scope_type != BudgetScopeType.TENANT.value:
            rows.append((policy, Decimal("0"), 0))
            continue

        result = await session.execute(
            select(
                func.coalesce(func.sum(LLMUsage.cost_usd), Decimal("0")),
                func.coalesce(func.sum(LLMUsage.total_tokens), 0),
            ).where(*filters)
        )
        amount_spent, tokens_used = result.one()
        rows.append((policy, Decimal(amount_spent or 0), int(tokens_used or 0)))
    return rows


def _to_policy_response(
    policy: LLMBudget,
    *,
    amount_spent: Decimal,
    tokens_used: int,
    custom_period_start: datetime | None = None,
    custom_period_end: datetime | None = None,
    name: str | None = None,
    description: str | None = None,
) -> BudgetPolicyResponse:
    amount_limit = Decimal(policy.amount_usd or 0)
    token_limit = policy.token_limit
    return BudgetPolicyResponse(
        id=policy.id,
        tenant_id=policy.tenant_id,
        name=name,
        description=description,
        scope_type=_budget_scope_type(policy.scope_type),
        scope_id=policy.scope_id,
        period=_budget_period(policy.period),
        custom_period_start=custom_period_start or policy.custom_period_start,
        custom_period_end=custom_period_end or policy.custom_period_end,
        budget_type=BudgetLimitType.HARD if policy.hard_limit else BudgetLimitType.SOFT,
        currency="USD",
        amount_limit=amount_limit,
        amount_spent=amount_spent,
        token_limit=token_limit,
        tokens_used=tokens_used,
        alert_threshold_pct=policy.alert_threshold_pct,
        status=BudgetPolicyStatus.ACTIVE if policy.is_active else BudgetPolicyStatus.INACTIVE,
        health=_budget_health(
            amount_limit=amount_limit,
            amount_spent=amount_spent,
            token_limit=token_limit,
            tokens_used=tokens_used,
            alert_threshold_pct=policy.alert_threshold_pct,
        ),
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


def _to_usage_ledger_item(row: LLMUsage) -> UsageLedgerItem:
    return UsageLedgerItem(
        id=row.id,
        tenant_id=row.tenant_id,
        created_at=row.created_at,
        deployment_id=row.deployment_id,
        user_id=row.user_id,
        department_id=row.department_id,
        cost_center_id=row.cost_center_id,
        agent_id=row.agent_id,
        channel_id=row.channel_id,
        conversation_id=row.conversation_id,
        request_id=row.request_id,
        model_key=row.model_key,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        total_tokens=row.total_tokens,
        cost_amount=Decimal(row.cost_usd or 0),
        status=row.status,
        error_code=row.error_code,
        metadata=row.metadata_json,
    )


def _to_budget_ledger_item(row: LLMBudgetLedger) -> BudgetLedgerItem:
    return BudgetLedgerItem(
        id=row.id,
        tenant_id=row.tenant_id,
        created_at=row.created_at,
        budget_id=row.budget_id,
        reservation_id=row.reservation_id,
        request_id=row.request_id,
        event_type=_budget_event_type(row.event_type),
        scope_type=_budget_scope_type(row.scope_type),
        scope_id=row.scope_id,
        user_id=row.user_id,
        department_id=row.department_id,
        cost_center_id=row.cost_center_id,
        agent_id=row.agent_id,
        channel_id=row.channel_id,
        conversation_id=row.conversation_id,
        estimated_tokens=row.estimated_tokens,
        actual_tokens=row.actual_tokens,
        estimated_cost_amount=Decimal(row.estimated_cost_usd or 0),
        actual_cost_amount=Decimal(row.actual_cost_usd or 0),
        reason=row.reason,
        metadata=row.metadata_json,
    )


def usage_ledger_to_csv(items: list[UsageLedgerItem]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "id",
            "tenant_id",
            "created_at",
            "request_id",
            "deployment_id",
            "user_id",
            "department_id",
            "cost_center_id",
            "agent_id",
            "channel_id",
            "conversation_id",
            "model_key",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "cost_amount",
            "currency",
            "status",
            "error_code",
            "metadata_json",
        ],
    )
    writer.writeheader()
    for item in items:
        writer.writerow(
            {
                "id": str(item.id),
                "tenant_id": str(item.tenant_id),
                "created_at": item.created_at.isoformat(),
                "request_id": item.request_id,
                "deployment_id": _optional_uuid(item.deployment_id),
                "user_id": _optional_uuid(item.user_id),
                "department_id": _optional_uuid(item.department_id),
                "cost_center_id": _optional_uuid(item.cost_center_id),
                "agent_id": _optional_uuid(item.agent_id),
                "channel_id": _optional_uuid(item.channel_id),
                "conversation_id": _optional_uuid(item.conversation_id),
                "model_key": item.model_key,
                "input_tokens": item.input_tokens,
                "output_tokens": item.output_tokens,
                "total_tokens": item.total_tokens,
                "cost_amount": str(item.cost_amount),
                "currency": item.currency,
                "status": item.status,
                "error_code": item.error_code or "",
                "metadata_json": json.dumps(item.metadata, ensure_ascii=False, default=str),
            }
        )
    return buffer.getvalue()


def usage_ledger_to_json(items: list[UsageLedgerItem]) -> str:
    return json.dumps(
        [item.model_dump(mode="json") for item in items],
        ensure_ascii=False,
        indent=2,
        default=str,
    )


def budget_ledger_to_csv(items: list[BudgetLedgerItem]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "id",
            "tenant_id",
            "created_at",
            "budget_id",
            "reservation_id",
            "request_id",
            "event_type",
            "scope_type",
            "scope_id",
            "user_id",
            "department_id",
            "cost_center_id",
            "agent_id",
            "channel_id",
            "conversation_id",
            "estimated_tokens",
            "actual_tokens",
            "estimated_cost_amount",
            "actual_cost_amount",
            "currency",
            "reason",
            "metadata_json",
        ],
    )
    writer.writeheader()
    for item in items:
        writer.writerow(
            {
                "id": str(item.id),
                "tenant_id": str(item.tenant_id),
                "created_at": item.created_at.isoformat(),
                "budget_id": _optional_uuid(item.budget_id),
                "reservation_id": item.reservation_id,
                "request_id": item.request_id,
                "event_type": item.event_type.value,
                "scope_type": item.scope_type.value,
                "scope_id": _optional_uuid(item.scope_id),
                "user_id": _optional_uuid(item.user_id),
                "department_id": _optional_uuid(item.department_id),
                "cost_center_id": _optional_uuid(item.cost_center_id),
                "agent_id": _optional_uuid(item.agent_id),
                "channel_id": _optional_uuid(item.channel_id),
                "conversation_id": _optional_uuid(item.conversation_id),
                "estimated_tokens": item.estimated_tokens,
                "actual_tokens": item.actual_tokens,
                "estimated_cost_amount": str(item.estimated_cost_amount),
                "actual_cost_amount": str(item.actual_cost_amount),
                "currency": item.currency,
                "reason": item.reason or "",
                "metadata_json": json.dumps(item.metadata, ensure_ascii=False, default=str),
            }
        )
    return buffer.getvalue()


def budget_ledger_to_json(items: list[BudgetLedgerItem]) -> str:
    return json.dumps(
        [item.model_dump(mode="json") for item in items],
        ensure_ascii=False,
        indent=2,
        default=str,
    )


def _optional_uuid(value: UUID | None) -> str:
    return str(value) if value else ""


def _usage_breakdown_field(dimension: UsageBreakdownDimension) -> Any:
    if dimension == UsageBreakdownDimension.DEPARTMENT:
        return LLMUsage.department_id
    if dimension == UsageBreakdownDimension.USER:
        return LLMUsage.user_id
    if dimension == UsageBreakdownDimension.COST_CENTER:
        return LLMUsage.cost_center_id
    if dimension == UsageBreakdownDimension.AGENT:
        return LLMUsage.agent_id
    if dimension == UsageBreakdownDimension.CHANNEL:
        return LLMUsage.channel_id
    if dimension == UsageBreakdownDimension.STATUS:
        return LLMUsage.status
    return LLMUsage.model_key


def _to_usage_breakdown_item(dimension: UsageBreakdownDimension, row: Any) -> UsageBreakdownItem:
    (
        key,
        request_count,
        success_count,
        error_count,
        input_tokens,
        output_tokens,
        total_tokens,
        cost_amount,
        last_used_at,
    ) = row
    return UsageBreakdownItem(
        dimension=dimension,
        key=str(key) if key is not None else "unassigned",
        request_count=int(request_count or 0),
        success_count=int(success_count or 0),
        error_count=int(error_count or 0),
        input_tokens=int(input_tokens or 0),
        output_tokens=int(output_tokens or 0),
        total_tokens=int(total_tokens or 0),
        cost_amount=Decimal(cost_amount or 0),
        last_used_at=last_used_at,
    )


def _resolve_period_window(
    period: BudgetPeriod,
    period_start: datetime | None,
    period_end: datetime | None,
) -> tuple[datetime, datetime]:
    if period == BudgetPeriod.CUSTOM and period_start is not None and period_end is not None:
        return period_start, period_end

    now = utc_now()
    if period == BudgetPeriod.DAILY:
        start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        return start, start + timedelta(days=1)

    start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    if now.month == 12:
        return start, datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    return start, datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)


def _policy_period_window(
    policy: LLMBudget,
    *,
    default_start: datetime,
    default_end: datetime,
) -> tuple[datetime, datetime]:
    if policy.period == BudgetPeriod.CUSTOM.value:
        if policy.custom_period_start is not None and policy.custom_period_end is not None:
            return policy.custom_period_start, policy.custom_period_end
        return default_start, default_end
    return _resolve_period_window(_budget_period(policy.period), None, None)


def _summarize_by_scope(policies: list[BudgetPolicyResponse]) -> list[BudgetScopeSummary]:
    grouped: dict[BudgetScopeType, list[BudgetPolicyResponse]] = defaultdict(list)
    for policy in policies:
        grouped[policy.scope_type].append(policy)

    summaries: list[BudgetScopeSummary] = []
    for scope_type in BudgetScopeType:
        scope_policies = grouped.get(scope_type, [])
        if not scope_policies:
            continue
        summaries.append(
            BudgetScopeSummary(
                scope_type=scope_type,
                policy_count=len(scope_policies),
                active_policy_count=len(scope_policies),
                amount_limit=sum(
                    (policy.amount_limit for policy in scope_policies),
                    Decimal("0"),
                ),
                amount_spent=sum(
                    (policy.amount_spent for policy in scope_policies),
                    Decimal("0"),
                ),
                token_limit=_sum_optional_int(policy.token_limit for policy in scope_policies),
                tokens_used=sum(policy.tokens_used for policy in scope_policies),
            )
        )
    return summaries


def _sum_optional_int(values: Iterable[int | None]) -> int | None:
    total = 0
    has_value = False
    for value in values:
        if value is None:
            continue
        has_value = True
        total += int(value)
    return total if has_value else None


def _budget_health(
    *,
    amount_limit: Decimal,
    amount_spent: Decimal,
    token_limit: int | None,
    tokens_used: int,
    alert_threshold_pct: int,
) -> BudgetLimitHealth:
    amount_ratio = _ratio(amount_spent, amount_limit)
    token_ratio = (
        _ratio(Decimal(tokens_used), Decimal(token_limit)) if token_limit else Decimal("0")
    )
    ratio = max(amount_ratio, token_ratio)
    if ratio >= Decimal("1"):
        return BudgetLimitHealth.EXCEEDED
    if ratio >= Decimal(alert_threshold_pct) / Decimal("100"):
        return BudgetLimitHealth.WARNING
    return BudgetLimitHealth.OK


def _ratio(value: Decimal, limit: Decimal) -> Decimal:
    if limit <= 0:
        return Decimal("0")
    return value / limit


def _budget_scope_type(value: str) -> BudgetScopeType:
    try:
        return BudgetScopeType(value)
    except ValueError:
        return BudgetScopeType.TENANT


async def _validate_budget_scope_target(
    session: AsyncSession,
    payload: BudgetPolicyUpsertRequest,
    principal: Principal,
) -> None:
    if payload.scope_type == BudgetScopeType.TENANT:
        return
    if payload.scope_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="scope_id is required for non-tenant budget policies.",
        )

    model = _budget_scope_model(payload.scope_type)
    conditions: list[ColumnElement[bool]] = [
        cast(ColumnElement[bool], model.id == payload.scope_id),
        cast(ColumnElement[bool], model.tenant_id == principal.tenant_id),
    ]
    if model is User:
        conditions.append(cast(Any, User.deleted_at).is_(None))
    result = await session.execute(select(model.id).where(*conditions))
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Budget policy {payload.scope_type.value} scope target was not found in this tenant.",
        )


def _budget_scope_model(scope_type: BudgetScopeType) -> Any:
    return {
        BudgetScopeType.DEPARTMENT: Department,
        BudgetScopeType.COST_CENTER: CostCenter,
        BudgetScopeType.USER: User,
        BudgetScopeType.AGENT: AgentInstance,
        BudgetScopeType.CHANNEL: ChannelConfig,
    }[scope_type]


def _budget_event_type(value: str) -> BudgetEventType:
    try:
        return BudgetEventType(value)
    except ValueError:
        return BudgetEventType.RESERVE


def _budget_period(value: str) -> BudgetPeriod:
    try:
        return BudgetPeriod(value)
    except ValueError:
        return BudgetPeriod.MONTHLY
