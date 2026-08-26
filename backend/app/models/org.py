from uuid import UUID

from sqlmodel import Field

from app.models.base import TenantScopedMixin, TimestampMixin, UUIDMixin


class Department(UUIDMixin, TenantScopedMixin, TimestampMixin, table=True):
    __tablename__ = "departments"

    parent_id: UUID | None = Field(default=None, foreign_key="departments.id", index=True)
    name: str = Field(max_length=100, nullable=False)
    description: str | None = Field(default=None)
    sort_order: int = Field(default=0)
