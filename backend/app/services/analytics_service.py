from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from sqlalchemy import ColumnElement, and_, case, func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.deps import Principal
from app.models.agent_module import AgentInstance
from app.models.base import utc_now
from app.models.llm import LLMUsage
from app.models.org import Department
from app.models.user import User, UserDepartment
from app.schemas.analytics import (
    AgentUsageItem,
    AnalyticsOverviewResponse,
    AnalyticsTotals,
    DailyUsageItem,
    DepartmentUsageItem,
    ModelUsageItem,
    UserUsageItem,
)


@dataclass(frozen=True)
class AnalyticsVisibilityScope:
    full_access: bool
    department_ids: set[UUID]


async def get_analytics_overview(
    session: AsyncSession,
    principal: Principal,
) -> AnalyticsOverviewResponse:
    generated_at = utc_now()
    default_response = AnalyticsOverviewResponse(
        generated_at=generated_at,
        metadata={"storage": "unavailable"},
    )

    try:
        visibility = await _resolve_visibility_scope(session, principal)
        totals = await _get_totals(session, principal, visibility)
        model_usage = await _get_model_usage(session, principal, visibility)
        daily_usage = await _get_daily_usage(session, principal, visibility, generated_at)
        department_usage = await _get_department_usage(session, principal, visibility)
        user_usage = await _get_user_usage(session, principal, visibility)
        agent_usage = await _get_agent_usage(session, principal, visibility)
    except (OSError, SQLAlchemyError):
        await session.rollback()
        return default_response

    return AnalyticsOverviewResponse(
        totals=totals,
        model_usage=model_usage,
        daily_usage=daily_usage,
        department_usage=department_usage,
        user_usage=user_usage,
        agent_usage=agent_usage,
        generated_at=generated_at,
        metadata={
            "storage": "llm_usage",
            "currency": "USD",
            "visibility_scope": "tenant" if visibility.full_access else "department",
        },
    )


async def _get_totals(
    session: AsyncSession,
    principal: Principal,
    visibility: AnalyticsVisibilityScope,
) -> AnalyticsTotals:
    result = await session.execute(
        select(
            func.count(cast(Any, LLMUsage.id)),
            func.coalesce(func.sum(LLMUsage.total_tokens), 0),
            func.coalesce(func.sum(LLMUsage.cost_usd), Decimal("0")),
            func.coalesce(
                func.sum(
                    case((cast(ColumnElement[bool], LLMUsage.status == "success"), 1), else_=0)
                ),
                0,
            ),
        ).where(
            cast(ColumnElement[bool], LLMUsage.tenant_id == principal.tenant_id),
            *_visibility_filters(principal, visibility),
        )
    )
    total_requests, total_tokens, total_cost_usd, success_requests = result.one()
    request_count = int(total_requests or 0)
    return AnalyticsTotals(
        total_requests=request_count,
        total_tokens=int(total_tokens or 0),
        total_cost_usd=_to_float(total_cost_usd),
        success_rate=(int(success_requests or 0) / request_count) if request_count else 0.0,
    )


async def _get_model_usage(
    session: AsyncSession,
    principal: Principal,
    visibility: AnalyticsVisibilityScope,
) -> list[ModelUsageItem]:
    total_tokens = func.coalesce(func.sum(LLMUsage.total_tokens), 0)
    result = await session.execute(
        select(
            LLMUsage.model_key,
            total_tokens,
            func.coalesce(func.sum(LLMUsage.cost_usd), Decimal("0")),
            func.count(cast(Any, LLMUsage.id)),
        )
        .where(
            cast(ColumnElement[bool], LLMUsage.tenant_id == principal.tenant_id),
            *_visibility_filters(principal, visibility),
        )
        .group_by(LLMUsage.model_key)
        .order_by(total_tokens.desc())
    )

    return [
        ModelUsageItem(
            model_key=model_key,
            tokens=int(tokens or 0),
            cost_usd=_to_float(cost_usd),
            requests=int(requests or 0),
        )
        for model_key, tokens, cost_usd, requests in result.all()
    ]


async def _get_daily_usage(
    session: AsyncSession,
    principal: Principal,
    visibility: AnalyticsVisibilityScope,
    generated_at: datetime,
) -> list[DailyUsageItem]:
    today = generated_at.astimezone(timezone.utc).date()
    start = datetime.combine(today - timedelta(days=6), datetime.min.time(), tzinfo=timezone.utc)
    usage_date = func.date(LLMUsage.created_at)

    result = await session.execute(
        select(
            usage_date,
            func.coalesce(func.sum(LLMUsage.total_tokens), 0),
            func.coalesce(func.sum(LLMUsage.cost_usd), Decimal("0")),
            func.count(cast(Any, LLMUsage.id)),
        )
        .where(
            cast(ColumnElement[bool], LLMUsage.tenant_id == principal.tenant_id),
            cast(ColumnElement[bool], LLMUsage.created_at >= start),
            *_visibility_filters(principal, visibility),
        )
        .group_by(usage_date)
        .order_by(usage_date)
    )

    return [
        DailyUsageItem(
            date=row_date,
            tokens=int(tokens or 0),
            cost_usd=_to_float(cost_usd),
            requests=int(requests or 0),
        )
        for row_date, tokens, cost_usd, requests in result.all()
    ]


async def _get_department_usage(
    session: AsyncSession,
    principal: Principal,
    visibility: AnalyticsVisibilityScope,
) -> list[DepartmentUsageItem]:
    total_tokens = func.coalesce(func.sum(LLMUsage.total_tokens), 0)
    dept_cols: list[Any] = [
        LLMUsage.department_id,
        Department.name,
        total_tokens,
        func.coalesce(func.sum(LLMUsage.cost_usd), Decimal("0")),
        func.count(cast(Any, LLMUsage.id)),
    ]
    result = await session.execute(
        select(*dept_cols)
        .select_from(LLMUsage)
        .outerjoin(
            Department,
            and_(
                cast(ColumnElement[bool], LLMUsage.department_id == Department.id),
                cast(ColumnElement[bool], Department.tenant_id == principal.tenant_id),
            ),
        )
        .where(
            cast(ColumnElement[bool], LLMUsage.tenant_id == principal.tenant_id),
            *_visibility_filters(principal, visibility),
        )
        .group_by(LLMUsage.department_id, Department.name)
        .order_by(total_tokens.desc())
    )

    return [
        DepartmentUsageItem(
            department_id=department_id,
            department_name=department_name or "Unassigned",
            tokens=int(tokens or 0),
            cost_usd=_to_float(cost_usd),
            requests=int(requests or 0),
        )
        for department_id, department_name, tokens, cost_usd, requests in result.all()
    ]


async def _get_user_usage(
    session: AsyncSession,
    principal: Principal,
    visibility: AnalyticsVisibilityScope,
) -> list[UserUsageItem]:
    total_tokens = func.coalesce(func.sum(LLMUsage.total_tokens), 0)
    user_cols: list[Any] = [
        LLMUsage.user_id,
        User.full_name,
        User.email,
        total_tokens,
        func.coalesce(func.sum(LLMUsage.cost_usd), Decimal("0")),
        func.count(cast(Any, LLMUsage.id)),
    ]
    result = await session.execute(
        select(*user_cols)
        .select_from(LLMUsage)
        .outerjoin(
            User,
            and_(
                cast(ColumnElement[bool], LLMUsage.user_id == User.id),
                cast(ColumnElement[bool], User.tenant_id == principal.tenant_id),
                cast(Any, User.deleted_at).is_(None),
            ),
        )
        .where(
            cast(ColumnElement[bool], LLMUsage.tenant_id == principal.tenant_id),
            *_visibility_filters(principal, visibility),
        )
        .group_by(LLMUsage.user_id, User.full_name, User.email)
        .order_by(total_tokens.desc())
    )

    return [
        UserUsageItem(
            user_id=user_id,
            user_name=full_name or email or "Unassigned",
            tokens=int(tokens or 0),
            cost_usd=_to_float(cost_usd),
            requests=int(requests or 0),
        )
        for user_id, full_name, email, tokens, cost_usd, requests in result.all()
    ]


async def _get_agent_usage(
    session: AsyncSession,
    principal: Principal,
    visibility: AnalyticsVisibilityScope,
) -> list[AgentUsageItem]:
    total_tokens = func.coalesce(func.sum(LLMUsage.total_tokens), 0)
    agent_cols: list[Any] = [
        LLMUsage.agent_id,
        AgentInstance.name,
        AgentInstance.agent_key,
        total_tokens,
        func.coalesce(func.sum(LLMUsage.cost_usd), Decimal("0")),
        func.count(cast(Any, LLMUsage.id)),
    ]
    result = await session.execute(
        select(*agent_cols)
        .select_from(LLMUsage)
        .outerjoin(
            AgentInstance,
            and_(
                cast(ColumnElement[bool], LLMUsage.agent_id == AgentInstance.id),
                cast(ColumnElement[bool], AgentInstance.tenant_id == principal.tenant_id),
            ),
        )
        .where(
            cast(ColumnElement[bool], LLMUsage.tenant_id == principal.tenant_id),
            *_visibility_filters(principal, visibility),
        )
        .group_by(LLMUsage.agent_id, AgentInstance.name, AgentInstance.agent_key)
        .order_by(total_tokens.desc())
    )

    return [
        AgentUsageItem(
            agent_id=agent_id,
            agent_name=agent_name or "Direct model calls",
            agent_key=agent_key,
            tokens=int(tokens or 0),
            cost_usd=_to_float(cost_usd),
            requests=int(requests or 0),
        )
        for agent_id, agent_name, agent_key, tokens, cost_usd, requests in result.all()
    ]


async def _resolve_visibility_scope(
    session: AsyncSession,
    principal: Principal,
) -> AnalyticsVisibilityScope:
    if _can_read_tenant_analytics(principal):
        return AnalyticsVisibilityScope(full_access=True, department_ids=set())

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
    return AnalyticsVisibilityScope(full_access=False, department_ids=set(result.scalars().all()))


def _can_read_tenant_analytics(principal: Principal) -> bool:
    return bool(
        {
            "tenant.admin",
            "budgets:write",
            "budgets:export",
        }.intersection(principal.permissions)
    )


def _visibility_filters(
    principal: Principal,
    visibility: AnalyticsVisibilityScope,
) -> list[ColumnElement[bool]]:
    if visibility.full_access:
        return []
    if visibility.department_ids:
        return [
            or_(
                cast(ColumnElement[bool], LLMUsage.user_id == principal.user_id),
                cast(Any, LLMUsage.department_id).in_(visibility.department_ids),
            )
        ]
    return [cast(ColumnElement[bool], LLMUsage.user_id == principal.user_id)]


def _to_float(value: object) -> float:
    if value is None:
        return 0.0
    return float(cast(Any, value))
