from datetime import datetime, timezone
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Column, DateTime, JSON
from sqlmodel import Field, SQLModel

from app.models.base import TenantScopedMixin, TimestampMixin, UUIDMixin


class Role(UUIDMixin, TenantScopedMixin, TimestampMixin, table=True):
    __tablename__ = "roles"

    name: str = Field(max_length=50, nullable=False, index=True)
    description: str | None = Field(default=None)
    permissions: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    is_system: bool = Field(default=False)


class UserRole(SQLModel, table=True):
    __tablename__ = "user_roles"

    user_id: UUID = Field(foreign_key="users.id", primary_key=True)
    role_id: UUID = Field(foreign_key="roles.id", primary_key=True)
    granted_by: UUID | None = Field(default=None, foreign_key="users.id")
    granted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        sa_type=cast(Any, DateTime(timezone=True)),
    )


class ResourcePermission(UUIDMixin, TenantScopedMixin, TimestampMixin, table=True):
    __tablename__ = "resource_permissions"

    resource_type: str = Field(max_length=50, nullable=False, index=True)
    resource_id: UUID = Field(index=True, nullable=False)
    subject_type: str = Field(max_length=20, nullable=False, index=True)
    subject_id: UUID = Field(index=True, nullable=False)
    permissions: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    conditions: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
