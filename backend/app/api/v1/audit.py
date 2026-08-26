from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_permission
from app.core.database import get_session
from app.core.security import Permission
from app.schemas.audit import AuditLogListResponse
from app.services.audit_query_service import (
    export_audit_logs_csv,
    export_audit_logs_json,
    list_audit_logs,
)

router = APIRouter(prefix="/audit", tags=["audit"])
export_router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("/logs", response_model=AuditLogListResponse)
async def read_audit_logs(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AUDIT_READ))],
    action: str | None = Query(default=None, max_length=100),
    actor_id: UUID | None = None,
    resource_type: str | None = Query(default=None, max_length=50),
    status: str | None = Query(default=None, max_length=30),
    request_id: str | None = Query(default=None, max_length=64),
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AuditLogListResponse:
    return await list_audit_logs(
        session,
        principal,
        action=action,
        actor_id=actor_id,
        resource_type=resource_type,
        status_filter=status,
        request_id=request_id,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
        offset=offset,
    )


@router.get("/logs/export", response_class=Response)
@export_router.get("/export", response_class=Response)
async def export_audit_logs(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AUDIT_EXPORT))],
    action: str | None = Query(default=None, max_length=100),
    actor_id: UUID | None = None,
    resource_type: str | None = Query(default=None, max_length=50),
    status: str | None = Query(default=None, max_length=30),
    request_id: str | None = Query(default=None, max_length=64),
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = Query(default=5000, ge=1, le=20000),
    format: str = Query(default="csv", pattern="^(csv|json)$"),
) -> Response:
    audit_request_id = getattr(request.state, "request_id", None)
    audit_ip_address = request.client.host if request.client else None
    audit_user_agent = request.headers.get("user-agent")
    if format == "json":
        json_body = await export_audit_logs_json(
            session,
            principal,
            action=action,
            actor_id=actor_id,
            resource_type=resource_type,
            status_filter=status,
            request_id=request_id,
            created_from=created_from,
            created_to=created_to,
            limit=limit,
            request_id_for_audit=audit_request_id,
            ip_address=audit_ip_address,
            user_agent=audit_user_agent,
        )
        return Response(
            content=json_body,
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="agenthive-audit-logs.json"'},
        )

    csv_body = await export_audit_logs_csv(
        session,
        principal,
        action=action,
        actor_id=actor_id,
        resource_type=resource_type,
        status_filter=status,
        request_id=request_id,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
        request_id_for_audit=audit_request_id,
        ip_address=audit_ip_address,
        user_agent=audit_user_agent,
    )
    return Response(
        content=csv_body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="agenthive-audit-logs.csv"'},
    )
