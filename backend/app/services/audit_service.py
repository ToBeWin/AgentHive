from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.services.audit_redaction import redact_audit_details


async def record_audit_event(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    action: str,
    status: str = "success",
    request_id: str | None = None,
    actor_id: UUID | None = None,
    actor_type: str = "user",
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    event = AuditLog(
        tenant_id=tenant_id,
        request_id=request_id,
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        status=status,
        ip_address=ip_address,
        user_agent=user_agent,
        details=redact_audit_details(details or {}),
    )
    session.add(event)
    return event
