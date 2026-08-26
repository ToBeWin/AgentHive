from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Column, DateTime, JSON
from sqlmodel import Field

from app.models.base import TenantScopedMixin, TimestampMixin, UUIDMixin


class MediaGenerationJob(UUIDMixin, TenantScopedMixin, TimestampMixin, table=True):
    __tablename__ = "media_generation_jobs"

    user_id: UUID | None = Field(default=None, foreign_key="users.id", index=True)
    department_id: UUID | None = Field(default=None, foreign_key="departments.id", index=True)
    agent_id: UUID | None = Field(default=None, foreign_key="agent_instances.id", index=True)
    conversation_id: UUID | None = Field(
        default=None, foreign_key="conversation_sessions.id", index=True
    )
    request_id: str | None = Field(default=None, max_length=64, index=True)
    kind: str = Field(max_length=20, index=True, nullable=False)
    mode: str = Field(max_length=40, index=True, nullable=False)
    status: str = Field(default="queued", max_length=30, index=True)
    provider_key: str = Field(max_length=80, index=True, nullable=False)
    provider_type: str = Field(max_length=80, nullable=False)
    model_key: str = Field(max_length=120, index=True, nullable=False)
    routing_key: str = Field(max_length=120, index=True, nullable=False)
    prompt: str = Field(nullable=False)
    negative_prompt: str | None = Field(default=None)
    reference_assets: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    request_parameters: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    normalized_parameters: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    output_storage: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    outputs: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    external_job_id: str | None = Field(default=None, max_length=160, index=True)
    error_message: str | None = Field(default=None)
    started_at: datetime | None = Field(default=None, sa_type=cast(Any, DateTime(timezone=True)))
    completed_at: datetime | None = Field(default=None, sa_type=cast(Any, DateTime(timezone=True)))
    metadata_json: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
