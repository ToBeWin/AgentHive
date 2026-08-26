import csv
import io
import json
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import ColumnElement, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.deps import Principal
from app.models.audit_log import AuditLog
from app.schemas.audit import AuditLogItem, AuditLogListResponse
from app.services.audit_service import record_audit_event
from app.services.audit_redaction import redact_audit_details


async def list_audit_logs(
    session: AsyncSession,
    principal: Principal,
    *,
    action: str | None = None,
    actor_id: UUID | None = None,
    resource_type: str | None = None,
    status_filter: str | None = None,
    request_id: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> AuditLogListResponse:
    try:
        filters = _audit_log_filters(
            principal,
            action=action,
            actor_id=actor_id,
            resource_type=resource_type,
            status_filter=status_filter,
            request_id=request_id,
            created_from=created_from,
            created_to=created_to,
        )

        total_result = await session.execute(
            select(func.count()).select_from(AuditLog).where(*filters)
        )
        total = int(total_result.scalar_one())
        rows_result = await session.execute(
            select(AuditLog)
            .where(*filters)
            .order_by(cast(Any, AuditLog.created_at).desc())
            .offset(offset)
            .limit(limit)
        )
    except (OSError, SQLAlchemyError):
        await session.rollback()
        return AuditLogListResponse(items=[], total=0, limit=limit, offset=offset)

    return AuditLogListResponse(
        items=[_to_audit_log_item(row) for row in rows_result.scalars().all()],
        total=total,
        limit=limit,
        offset=offset,
    )


async def export_audit_logs_csv(
    session: AsyncSession,
    principal: Principal,
    *,
    action: str | None = None,
    actor_id: UUID | None = None,
    resource_type: str | None = None,
    status_filter: str | None = None,
    request_id: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = 5000,
    request_id_for_audit: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> str:
    items = await _export_audit_log_items(
        session,
        principal,
        action=action,
        actor_id=actor_id,
        resource_type=resource_type,
        status_filter=status_filter,
        request_id=request_id,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
    )
    await _record_audit_export_event(
        session,
        principal,
        export_format="csv",
        item_count=len(items),
        limit=limit,
        request_id=request_id_for_audit,
        ip_address=ip_address,
        user_agent=user_agent,
        filters={
            "action": action,
            "actor_id": actor_id,
            "resource_type": resource_type,
            "status": status_filter,
            "request_id": request_id,
            "created_from": created_from,
            "created_to": created_to,
        },
    )
    return audit_logs_to_csv(items)


async def export_audit_logs_json(
    session: AsyncSession,
    principal: Principal,
    *,
    action: str | None = None,
    actor_id: UUID | None = None,
    resource_type: str | None = None,
    status_filter: str | None = None,
    request_id: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = 5000,
    request_id_for_audit: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> str:
    items = await _export_audit_log_items(
        session,
        principal,
        action=action,
        actor_id=actor_id,
        resource_type=resource_type,
        status_filter=status_filter,
        request_id=request_id,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
    )
    await _record_audit_export_event(
        session,
        principal,
        export_format="json",
        item_count=len(items),
        limit=limit,
        request_id=request_id_for_audit,
        ip_address=ip_address,
        user_agent=user_agent,
        filters={
            "action": action,
            "actor_id": actor_id,
            "resource_type": resource_type,
            "status": status_filter,
            "request_id": request_id,
            "created_from": created_from,
            "created_to": created_to,
        },
    )
    return audit_logs_to_json(items)


async def _export_audit_log_items(
    session: AsyncSession,
    principal: Principal,
    *,
    action: str | None,
    actor_id: UUID | None,
    resource_type: str | None,
    status_filter: str | None,
    request_id: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
    limit: int,
) -> list[AuditLogItem]:
    try:
        filters = _audit_log_filters(
            principal,
            action=action,
            actor_id=actor_id,
            resource_type=resource_type,
            status_filter=status_filter,
            request_id=request_id,
            created_from=created_from,
            created_to=created_to,
        )

        rows_result = await session.execute(
            select(AuditLog)
            .where(*filters)
            .order_by(cast(Any, AuditLog.created_at).desc())
            .limit(limit)
        )
    except (OSError, SQLAlchemyError):
        await session.rollback()
        return []

    return [_to_audit_log_item(row) for row in rows_result.scalars().all()]


def _audit_log_filters(
    principal: Principal,
    *,
    action: str | None = None,
    actor_id: UUID | None = None,
    resource_type: str | None = None,
    status_filter: str | None = None,
    request_id: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = [
        cast(ColumnElement[bool], AuditLog.tenant_id == principal.tenant_id)
    ]
    if action is not None:
        filters.append(cast(ColumnElement[bool], AuditLog.action == action))
    if actor_id is not None:
        filters.append(cast(ColumnElement[bool], AuditLog.actor_id == actor_id))
    if resource_type is not None:
        filters.append(cast(ColumnElement[bool], AuditLog.resource_type == resource_type))
    if status_filter is not None:
        filters.append(cast(ColumnElement[bool], AuditLog.status == status_filter))
    if request_id is not None:
        filters.append(cast(ColumnElement[bool], AuditLog.request_id == request_id))
    if created_from is not None:
        filters.append(cast(ColumnElement[bool], AuditLog.created_at >= created_from))
    if created_to is not None:
        filters.append(cast(ColumnElement[bool], AuditLog.created_at <= created_to))
    return filters


async def _record_audit_export_event(
    session: AsyncSession,
    principal: Principal,
    *,
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
            action="audit.logs.export",
            resource_type="audit_log",
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


def audit_logs_to_csv(items: list[AuditLogItem]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "id",
            "tenant_id",
            "created_at",
            "request_id",
            "actor_id",
            "actor_type",
            "action",
            "resource_type",
            "resource_id",
            "status",
            "ip_address",
            "user_agent",
            "details_json",
        ],
    )
    writer.writeheader()
    for item in items:
        writer.writerow(
            {
                "id": str(item.id),
                "tenant_id": str(item.tenant_id),
                "created_at": item.created_at.isoformat(),
                "request_id": item.request_id or "",
                "actor_id": str(item.actor_id) if item.actor_id else "",
                "actor_type": item.actor_type,
                "action": item.action,
                "resource_type": item.resource_type or "",
                "resource_id": str(item.resource_id) if item.resource_id else "",
                "status": item.status,
                "ip_address": item.ip_address or "",
                "user_agent": item.user_agent or "",
                "details_json": json.dumps(item.details, ensure_ascii=False, sort_keys=True),
            }
        )
    return buffer.getvalue()


def audit_logs_to_json(items: list[AuditLogItem]) -> str:
    return json.dumps(
        {
            "format": "agenthive.audit.export.v1",
            "items": [
                {
                    "id": str(item.id),
                    "tenant_id": str(item.tenant_id),
                    "created_at": item.created_at.isoformat(),
                    "request_id": item.request_id,
                    "actor_id": str(item.actor_id) if item.actor_id else None,
                    "actor_type": item.actor_type,
                    "action": item.action,
                    "resource_type": item.resource_type,
                    "resource_id": str(item.resource_id) if item.resource_id else None,
                    "status": item.status,
                    "ip_address": item.ip_address,
                    "user_agent": item.user_agent,
                    "details": item.details,
                }
                for item in items
            ],
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def _to_audit_log_item(row: AuditLog) -> AuditLogItem:
    return AuditLogItem(
        id=row.id,
        tenant_id=row.tenant_id,
        request_id=row.request_id,
        actor_id=row.actor_id,
        actor_type=row.actor_type,
        action=row.action,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        status=row.status,
        ip_address=row.ip_address,
        user_agent=row.user_agent,
        details=redact_audit_details(row.details),
        created_at=row.created_at,
    )
