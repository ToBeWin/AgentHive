from typing import Any
from uuid import UUID

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field

from app.models.base import TenantScopedMixin, TimestampMixin, UUIDMixin


class ChannelConfig(UUIDMixin, TenantScopedMixin, TimestampMixin, table=True):
    __tablename__ = "channel_configs"
    __table_args__ = (UniqueConstraint("channel_type", "channel_key"),)

    name: str = Field(max_length=120, nullable=False)
    channel_type: str = Field(max_length=40, index=True, nullable=False)
    channel_key: str = Field(max_length=120, index=True, nullable=False)
    agent_id: UUID | None = Field(default=None, index=True)
    created_by: UUID | None = Field(default=None, foreign_key="users.id", index=True)
    status: str = Field(default="active", max_length=30, index=True)
    config: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    secret_ref: str | None = Field(default=None)
    previous_secret_ref: str | None = Field(default=None)
    secret_configured: bool = Field(default=False)
