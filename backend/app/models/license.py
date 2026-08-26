from datetime import datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Column, DateTime, JSON
from sqlmodel import Field

from app.models.base import TenantScopedMixin, TimestampMixin, UUIDMixin


class License(UUIDMixin, TenantScopedMixin, TimestampMixin, table=True):
    __tablename__ = "licenses"

    license_key_hash: str = Field(max_length=128, index=True, nullable=False)
    license_type: str = Field(default="basic", max_length=20, index=True)
    customer_name: str = Field(max_length=100, nullable=False)
    status: str = Field(default="inactive", max_length=20, index=True)
    deployment_id: UUID = Field(index=True, nullable=False)
    install_id: UUID = Field(index=True, nullable=False)
    machine_fingerprint_hash: str = Field(max_length=128, index=True, nullable=False)
    allowed_modules: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    allowed_features: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    max_users: int | None = Field(default=None)
    max_agents: int | None = Field(default=None)
    max_kb_size_gb: Decimal | None = Field(default=None, max_digits=10, decimal_places=2)
    maintenance_until: datetime | None = Field(
        default=None, sa_type=cast(Any, DateTime(timezone=True))
    )
    expires_at: datetime | None = Field(default=None, sa_type=cast(Any, DateTime(timezone=True)))
    activated_at: datetime | None = Field(default=None, sa_type=cast(Any, DateTime(timezone=True)))
    signature_payload: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )


class LicenseActivation(UUIDMixin, TenantScopedMixin, TimestampMixin, table=True):
    __tablename__ = "license_activations"

    license_id: UUID = Field(foreign_key="licenses.id", index=True, nullable=False)
    deployment_id: UUID = Field(index=True, nullable=False)
    install_id: UUID = Field(index=True, nullable=False)
    machine_fingerprint_hash: str = Field(max_length=128, index=True, nullable=False)
    activation_type: str = Field(default="offline", max_length=20)
    status: str = Field(max_length=20, index=True, nullable=False)
    activated_by: UUID | None = Field(default=None, foreign_key="users.id")
    activated_at: datetime | None = Field(default=None, sa_type=cast(Any, DateTime(timezone=True)))
    deactivated_at: datetime | None = Field(
        default=None, sa_type=cast(Any, DateTime(timezone=True))
    )
    request_payload: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
