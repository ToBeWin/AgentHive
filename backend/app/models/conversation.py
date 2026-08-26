from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Column, JSON
from sqlmodel import Field

from app.models.base import SoftDeleteMixin, TenantScopedMixin, TimestampMixin, UUIDMixin


class ConversationSession(
    UUIDMixin, TenantScopedMixin, TimestampMixin, SoftDeleteMixin, table=True
):
    __tablename__ = "conversation_sessions"

    title: str = Field(max_length=160, nullable=False)
    agent_id: UUID | None = Field(default=None, index=True)
    channel_id: UUID | None = Field(default=None, index=True)
    user_id: UUID | None = Field(default=None, foreign_key="users.id", index=True)
    department_id: UUID | None = Field(default=None, foreign_key="departments.id", index=True)
    source: str = Field(default="chat_console", max_length=40, index=True)
    status: str = Field(default="active", max_length=30, index=True)
    metadata_json: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )


class ConversationMessage(UUIDMixin, TenantScopedMixin, TimestampMixin, table=True):
    __tablename__ = "conversation_messages"

    conversation_id: UUID = Field(
        foreign_key="conversation_sessions.id", index=True, nullable=False
    )
    role: str = Field(max_length=40, index=True, nullable=False)
    content: str = Field(nullable=False)
    user_id: UUID | None = Field(default=None, foreign_key="users.id", index=True)
    request_id: str | None = Field(default=None, max_length=64, index=True)
    model_key: str | None = Field(default=None, max_length=120, index=True)
    provider_key: str | None = Field(default=None, max_length=80)
    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)
    cost_usd: Decimal = Field(default=Decimal("0"), max_digits=12, decimal_places=6)
    metadata_json: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
