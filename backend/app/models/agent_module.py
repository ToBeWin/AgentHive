from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Column, DateTime, JSON
from sqlmodel import Field

from app.models.base import TenantScopedMixin, TimestampMixin, UUIDMixin


class AgentModule(UUIDMixin, TimestampMixin, table=True):
    __tablename__ = "agent_modules"

    module_key: str = Field(max_length=100, unique=True, index=True, nullable=False)
    name: str = Field(max_length=100, nullable=False)
    category: str = Field(max_length=50, nullable=False, index=True)
    priority: str = Field(max_length=10, nullable=False)
    description: str | None = Field(default=None)
    version: str = Field(max_length=30, nullable=False)
    manifest: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    is_official: bool = Field(default=True)
    is_active: bool = Field(default=True, index=True)


class TenantAgentModule(UUIDMixin, TenantScopedMixin, TimestampMixin, table=True):
    __tablename__ = "tenant_agent_modules"

    module_id: UUID = Field(foreign_key="agent_modules.id", index=True, nullable=False)
    state: str = Field(default="not_installed", max_length=30, index=True)
    installed_by: UUID | None = Field(default=None, foreign_key="users.id")
    installed_at: datetime | None = Field(default=None, sa_type=cast(Any, DateTime(timezone=True)))
    enabled_at: datetime | None = Field(default=None, sa_type=cast(Any, DateTime(timezone=True)))
    disabled_at: datetime | None = Field(default=None, sa_type=cast(Any, DateTime(timezone=True)))
    config: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class AgentInstance(UUIDMixin, TenantScopedMixin, TimestampMixin, table=True):
    __tablename__ = "agent_instances"

    name: str = Field(max_length=120, nullable=False)
    slug: str = Field(max_length=80, index=True, nullable=False)
    agent_key: str = Field(max_length=100, index=True, nullable=False)
    module_key: str = Field(max_length=100, index=True, nullable=False)
    description: str | None = Field(default=None, max_length=500)
    status: str = Field(default="draft", max_length=30, index=True)
    visibility: str = Field(default="tenant", max_length=30, index=True)
    department_id: UUID | None = Field(default=None, foreign_key="departments.id", index=True)
    owner_user_id: UUID | None = Field(default=None, foreign_key="users.id", index=True)
    model_routing_key: str | None = Field(default=None, max_length=120)
    model_key: str | None = Field(default=None, max_length=120)
    system_prompt: str | None = Field(default=None)
    config: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    metadata_json: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    created_by: UUID | None = Field(default=None, foreign_key="users.id", index=True)


class AgentUserAssignment(UUIDMixin, TenantScopedMixin, TimestampMixin, table=True):
    __tablename__ = "agent_user_assignments"

    agent_id: UUID = Field(foreign_key="agent_instances.id", index=True, nullable=False)
    user_id: UUID = Field(foreign_key="users.id", index=True, nullable=False)
    role: str = Field(default="user", max_length=30, nullable=False)
    # "owner" / "operator" / "viewer"
    assigned_by: UUID | None = Field(default=None, foreign_key="users.id")
