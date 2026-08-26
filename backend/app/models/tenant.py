from datetime import datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Column, DateTime, JSON
from sqlmodel import Field

from app.models.base import TimestampMixin, UUIDMixin


class Tenant(UUIDMixin, TimestampMixin, table=True):
    __tablename__ = "tenants"

    name: str = Field(max_length=100, nullable=False)
    slug: str = Field(max_length=50, unique=True, index=True, nullable=False)
    license_key: str | None = Field(default=None)
    license_type: str = Field(default="basic", max_length=20)
    license_expires_at: datetime | None = Field(
        default=None, sa_type=cast(Any, DateTime(timezone=True))
    )
    max_users: int = Field(default=50)
    max_agents: int = Field(default=5)
    max_kb_size_gb: Decimal = Field(default=Decimal("5.0"), max_digits=10, decimal_places=2)
    config: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    is_active: bool = Field(default=True, index=True)


class CostCenter(UUIDMixin, TimestampMixin, table=True):
    __tablename__ = "cost_centers"

    tenant_id: UUID = Field(foreign_key="tenants.id", index=True, nullable=False)
    department_id: UUID | None = Field(default=None, foreign_key="departments.id", index=True)
    code: str = Field(max_length=50, nullable=False, index=True)
    name: str = Field(max_length=100, nullable=False)
    description: str | None = Field(default=None)
    monthly_budget_usd: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    is_active: bool = Field(default=True)
