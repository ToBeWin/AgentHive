from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import DateTime
from sqlmodel import Field

from app.models.base import SoftDeleteMixin, TenantScopedMixin, TimestampMixin, UUIDMixin


class User(UUIDMixin, TenantScopedMixin, TimestampMixin, SoftDeleteMixin, table=True):
    __tablename__ = "users"

    email: str = Field(max_length=255, index=True, nullable=False)
    username: str | None = Field(default=None, max_length=50, index=True)
    hashed_password: str = Field(nullable=False)
    full_name: str | None = Field(default=None, max_length=100)
    avatar_url: str | None = Field(default=None)
    phone: str | None = Field(default=None, max_length=20)
    is_super_admin: bool = Field(default=False, index=True)
    is_tenant_admin: bool = Field(default=False, index=True)
    is_active: bool = Field(default=True, index=True)
    auth_version: int = Field(default=0, nullable=False)
    last_login_at: datetime | None = Field(default=None, sa_type=cast(Any, DateTime(timezone=True)))


class UserDepartment(TimestampMixin, table=True):
    __tablename__ = "user_departments"

    user_id: UUID = Field(foreign_key="users.id", primary_key=True)
    department_id: UUID = Field(foreign_key="departments.id", primary_key=True)
    is_leader: bool = Field(default=False)
    is_primary: bool = Field(default=False)
    position_title: str | None = Field(default=None, max_length=100)
    cost_center_id: UUID | None = Field(default=None, foreign_key="cost_centers.id")
