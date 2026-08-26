from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AuditLogItem(BaseModel):
    id: UUID
    tenant_id: UUID
    request_id: str | None
    actor_id: UUID | None
    actor_type: str
    action: str
    resource_type: str | None
    resource_id: UUID | None
    status: str
    ip_address: str | None
    user_agent: str | None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogItem]
    total: int
    limit: int
    offset: int
