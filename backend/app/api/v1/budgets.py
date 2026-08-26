from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_permission
from app.core.database import get_session
from app.core.security import Permission
from app.schemas.budget import (
    BudgetEventType,
    BudgetGovernanceTargetsResponse,
    BudgetLedgerResponse,
    BudgetPeriod,
    BudgetPolicyListResponse,
    BudgetPolicyResponse,
    BudgetPolicyStatus,
    BudgetPolicyStatusUpdateRequest,
    BudgetPolicyUpsertRequest,
    BudgetScopeType,
    BudgetSummaryResponse,
    UsageBreakdownDimension,
    UsageBreakdownResponse,
    UsageLedgerResponse,
)
from app.services.budget_admin_service import (
    export_budget_ledger_csv,
    export_budget_ledger_json,
    export_usage_ledger_csv,
    export_usage_ledger_json,
    get_budget_summary,
    list_budget_governance_targets,
    get_usage_breakdown,
    list_budget_ledger,
    list_budget_policies,
    list_usage_ledger,
    update_budget_policy_status,
    upsert_budget_policy,
)

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("/summary", response_model=BudgetSummaryResponse)
async def read_budget_summary(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.BUDGETS_READ))],
    period: BudgetPeriod = BudgetPeriod.MONTHLY,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> BudgetSummaryResponse:
    return await get_budget_summary(
        session,
        principal,
        period=period,
        period_start=period_start,
        period_end=period_end,
    )


@router.get("/policies", response_model=BudgetPolicyListResponse)
async def read_budget_policies(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.BUDGETS_READ))],
    scope_type: BudgetScopeType | None = None,
    status: BudgetPolicyStatus | None = None,
) -> BudgetPolicyListResponse:
    return await list_budget_policies(
        session,
        principal,
        scope_type=scope_type,
        status_filter=status,
    )


@router.get("/governance-targets", response_model=BudgetGovernanceTargetsResponse)
async def read_budget_governance_targets(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.BUDGETS_READ))],
) -> BudgetGovernanceTargetsResponse:
    return await list_budget_governance_targets(session, principal)


@router.post("/policies", response_model=BudgetPolicyResponse)
async def save_budget_policy(
    request: Request,
    payload: BudgetPolicyUpsertRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.BUDGETS_WRITE))],
) -> BudgetPolicyResponse:
    return await upsert_budget_policy(
        session,
        principal,
        payload,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.patch("/policies/{policy_id}/status", response_model=BudgetPolicyResponse)
async def patch_budget_policy_status(
    policy_id: UUID,
    request: Request,
    payload: BudgetPolicyStatusUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.BUDGETS_WRITE))],
) -> BudgetPolicyResponse:
    return await update_budget_policy_status(
        session,
        principal,
        policy_id,
        payload,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.get("/usage-ledger", response_model=UsageLedgerResponse)
async def read_usage_ledger(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.BUDGETS_READ))],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    start: datetime | None = None,
    end: datetime | None = None,
    user_id: UUID | None = None,
    department_id: UUID | None = None,
    cost_center_id: UUID | None = None,
    agent_id: UUID | None = None,
    channel_id: UUID | None = None,
    model_key: str | None = Query(default=None, max_length=120),
    status: str | None = Query(default=None, max_length=30),
) -> UsageLedgerResponse:
    return await list_usage_ledger(
        session,
        principal,
        limit=limit,
        offset=offset,
        start=start,
        end=end,
        user_id=user_id,
        department_id=department_id,
        cost_center_id=cost_center_id,
        agent_id=agent_id,
        channel_id=channel_id,
        model_key=model_key,
        status_filter=status,
    )


@router.get("/usage-ledger/export", response_class=Response)
async def export_usage_ledger(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.BUDGETS_EXPORT))],
    limit: int = Query(default=5000, ge=1, le=20000),
    start: datetime | None = None,
    end: datetime | None = None,
    user_id: UUID | None = None,
    department_id: UUID | None = None,
    cost_center_id: UUID | None = None,
    agent_id: UUID | None = None,
    channel_id: UUID | None = None,
    model_key: str | None = Query(default=None, max_length=120),
    status: str | None = Query(default=None, max_length=30),
    format: str = Query(default="csv", pattern="^(csv|json)$"),
) -> Response:
    audit_request_id = getattr(request.state, "request_id", None)
    audit_ip_address = request.client.host if request.client else None
    audit_user_agent = request.headers.get("user-agent")
    if format == "json":
        body = await export_usage_ledger_json(
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
            status_filter=status,
            request_id=audit_request_id,
            ip_address=audit_ip_address,
            user_agent=audit_user_agent,
        )
        return Response(
            content=body,
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="agenthive-usage-ledger.json"'},
        )

    body = await export_usage_ledger_csv(
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
        status_filter=status,
        request_id=audit_request_id,
        ip_address=audit_ip_address,
        user_agent=audit_user_agent,
    )
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="agenthive-usage-ledger.csv"'},
    )


@router.get("/budget-ledger", response_model=BudgetLedgerResponse)
async def read_budget_ledger(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.BUDGETS_READ))],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    start: datetime | None = None,
    end: datetime | None = None,
    budget_id: UUID | None = None,
    reservation_id: str | None = Query(default=None, max_length=64),
    request_id: str | None = Query(default=None, max_length=64),
    event_type: BudgetEventType | None = None,
    scope_type: BudgetScopeType | None = None,
    scope_id: UUID | None = None,
    user_id: UUID | None = None,
    department_id: UUID | None = None,
    cost_center_id: UUID | None = None,
    agent_id: UUID | None = None,
    channel_id: UUID | None = None,
) -> BudgetLedgerResponse:
    return await list_budget_ledger(
        session,
        principal,
        limit=limit,
        offset=offset,
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


@router.get("/budget-ledger/export", response_class=Response)
async def export_budget_ledger(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.BUDGETS_EXPORT))],
    limit: int = Query(default=5000, ge=1, le=20000),
    start: datetime | None = None,
    end: datetime | None = None,
    budget_id: UUID | None = None,
    reservation_id: str | None = Query(default=None, max_length=64),
    request_id: str | None = Query(default=None, max_length=64),
    event_type: BudgetEventType | None = None,
    scope_type: BudgetScopeType | None = None,
    scope_id: UUID | None = None,
    user_id: UUID | None = None,
    department_id: UUID | None = None,
    cost_center_id: UUID | None = None,
    agent_id: UUID | None = None,
    channel_id: UUID | None = None,
    format: str = Query(default="csv", pattern="^(csv|json)$"),
) -> Response:
    audit_request_id = getattr(request.state, "request_id", None)
    audit_ip_address = request.client.host if request.client else None
    audit_user_agent = request.headers.get("user-agent")
    if format == "json":
        body = await export_budget_ledger_json(
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
            request_id_for_audit=audit_request_id,
            ip_address=audit_ip_address,
            user_agent=audit_user_agent,
        )
        return Response(
            content=body,
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="agenthive-budget-ledger.json"'},
        )

    body = await export_budget_ledger_csv(
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
        request_id_for_audit=audit_request_id,
        ip_address=audit_ip_address,
        user_agent=audit_user_agent,
    )
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="agenthive-budget-ledger.csv"'},
    )


@router.get("/usage-breakdown", response_model=UsageBreakdownResponse)
async def read_usage_breakdown(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.BUDGETS_READ))],
    dimension: UsageBreakdownDimension = UsageBreakdownDimension.DEPARTMENT,
    limit: int = Query(default=20, ge=1, le=100),
    start: datetime | None = None,
    end: datetime | None = None,
    status: str | None = Query(default=None, max_length=30),
) -> UsageBreakdownResponse:
    return await get_usage_breakdown(
        session,
        principal,
        dimension=dimension,
        limit=limit,
        start=start,
        end=end,
        status_filter=status,
    )
