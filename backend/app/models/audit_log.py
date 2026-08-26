from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Column, DateTime, JSON
from sqlmodel import Field

from app.models.base import TenantScopedMixin, UUIDMixin, utc_now


class AuditLog(UUIDMixin, TenantScopedMixin, table=True):
    __tablename__ = "audit_logs"

    request_id: str | None = Field(default=None, max_length=64, index=True)
    actor_id: UUID | None = Field(default=None, foreign_key="users.id", index=True)
    actor_type: str = Field(default="user", max_length=30, index=True)
    action: str = Field(max_length=100, index=True, nullable=False)
    resource_type: str | None = Field(default=None, max_length=50, index=True)
    resource_id: UUID | None = Field(default=None, index=True)
    status: str = Field(default="success", max_length=30, index=True)
    ip_address: str | None = Field(default=None, max_length=64)
    user_agent: str | None = Field(default=None)
    details: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now,
        nullable=False,
        sa_type=cast(Any, DateTime(timezone=True)),
    )
