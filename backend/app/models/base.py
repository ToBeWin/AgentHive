from datetime import datetime, timezone
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin(SQLModel):
    created_at: datetime = Field(
        default_factory=utc_now,
        nullable=False,
        sa_type=cast(Any, DateTime(timezone=True)),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        nullable=False,
        sa_type=cast(Any, DateTime(timezone=True)),
    )


class UUIDMixin(SQLModel):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)


class SoftDeleteMixin(SQLModel):
    deleted_at: datetime | None = Field(
        default=None,
        index=True,
        nullable=True,
        sa_type=cast(Any, DateTime(timezone=True)),
    )


class TenantScopedMixin(SQLModel):
    tenant_id: UUID = Field(foreign_key="tenants.id", index=True, nullable=False)
