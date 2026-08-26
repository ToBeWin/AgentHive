from datetime import datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Column, DateTime, JSON
from sqlmodel import Field

from app.models.base import TenantScopedMixin, TimestampMixin, UUIDMixin


class LLMProvider(UUIDMixin, TenantScopedMixin, TimestampMixin, table=True):
    __tablename__ = "llm_providers"

    provider_key: str = Field(max_length=80, index=True, nullable=False)
    name: str = Field(max_length=100, nullable=False)
    adapter_type: str = Field(max_length=40, nullable=False)
    base_url: str | None = Field(default=None)
    region: str | None = Field(default=None, max_length=50)
    is_active: bool = Field(default=True, index=True)
    config: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class LLMCredential(UUIDMixin, TenantScopedMixin, TimestampMixin, table=True):
    __tablename__ = "llm_credentials"

    provider_id: UUID = Field(foreign_key="llm_providers.id", index=True, nullable=False)
    owner_type: str = Field(default="tenant", max_length=20, index=True)
    owner_id: UUID | None = Field(default=None, index=True)
    display_name: str = Field(max_length=100, nullable=False)
    secret_ref: str = Field(nullable=False)
    masked_secret: str = Field(max_length=80, nullable=False)
    is_active: bool = Field(default=True, index=True)
    last_rotated_at: datetime | None = Field(
        default=None, sa_type=cast(Any, DateTime(timezone=True))
    )


class LLMModel(UUIDMixin, TimestampMixin, table=True):
    __tablename__ = "llm_models"

    provider_key: str = Field(max_length=80, index=True, nullable=False)
    model_key: str = Field(max_length=120, unique=True, index=True, nullable=False)
    display_name: str = Field(max_length=120, nullable=False)
    model_type: str = Field(default="chat", max_length=30, index=True)
    context_window: int | None = Field(default=None)
    capabilities: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    is_global: bool = Field(default=True, index=True)


class LLMDeployment(UUIDMixin, TenantScopedMixin, TimestampMixin, table=True):
    __tablename__ = "llm_deployments"

    provider_id: UUID = Field(foreign_key="llm_providers.id", index=True, nullable=False)
    model_id: UUID = Field(foreign_key="llm_models.id", index=True, nullable=False)
    credential_id: UUID | None = Field(default=None, foreign_key="llm_credentials.id", index=True)
    deployment_name: str = Field(max_length=120, nullable=False)
    routing_key: str = Field(max_length=120, index=True, nullable=False)
    is_active: bool = Field(default=True, index=True)
    priority: int = Field(default=100)
    config: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class LLMModelPrice(UUIDMixin, TimestampMixin, table=True):
    __tablename__ = "llm_model_prices"

    model_id: UUID = Field(foreign_key="llm_models.id", index=True, nullable=False)
    currency: str = Field(default="USD", max_length=3)
    input_per_1k_tokens: Decimal = Field(default=Decimal("0"), max_digits=12, decimal_places=8)
    output_per_1k_tokens: Decimal = Field(default=Decimal("0"), max_digits=12, decimal_places=8)
    effective_from: datetime = Field(
        index=True, nullable=False, sa_type=cast(Any, DateTime(timezone=True))
    )
    effective_to: datetime | None = Field(
        default=None, index=True, sa_type=cast(Any, DateTime(timezone=True))
    )


class LLMBudget(UUIDMixin, TenantScopedMixin, TimestampMixin, table=True):
    __tablename__ = "llm_budgets"

    scope_type: str = Field(max_length=30, index=True, nullable=False)
    scope_id: UUID | None = Field(default=None, index=True)
    period: str = Field(default="monthly", max_length=20, index=True)
    custom_period_start: datetime | None = Field(
        default=None,
        index=True,
        sa_type=cast(Any, DateTime(timezone=True)),
    )
    custom_period_end: datetime | None = Field(
        default=None,
        index=True,
        sa_type=cast(Any, DateTime(timezone=True)),
    )
    amount_usd: Decimal = Field(default=Decimal("0"), max_digits=12, decimal_places=4)
    token_limit: int | None = Field(default=None)
    hard_limit: bool = Field(default=True)
    alert_threshold_pct: int = Field(default=80)
    is_active: bool = Field(default=True, index=True)


class LLMBudgetLedger(UUIDMixin, TenantScopedMixin, TimestampMixin, table=True):
    __tablename__ = "llm_budget_ledger"

    budget_id: UUID | None = Field(default=None, foreign_key="llm_budgets.id", index=True)
    reservation_id: str = Field(max_length=64, index=True, nullable=False)
    request_id: str = Field(max_length=64, index=True, nullable=False)
    event_type: str = Field(max_length=30, index=True, nullable=False)
    scope_type: str = Field(max_length=30, index=True, nullable=False)
    scope_id: UUID | None = Field(default=None, index=True)
    user_id: UUID | None = Field(default=None, foreign_key="users.id", index=True)
    department_id: UUID | None = Field(default=None, foreign_key="departments.id", index=True)
    cost_center_id: UUID | None = Field(default=None, foreign_key="cost_centers.id", index=True)
    agent_id: UUID | None = Field(default=None, index=True)
    channel_id: UUID | None = Field(default=None, index=True)
    conversation_id: UUID | None = Field(
        default=None, foreign_key="conversation_sessions.id", index=True
    )
    estimated_tokens: int = Field(default=0)
    actual_tokens: int = Field(default=0)
    estimated_cost_usd: Decimal = Field(default=Decimal("0"), max_digits=12, decimal_places=6)
    actual_cost_usd: Decimal = Field(default=Decimal("0"), max_digits=12, decimal_places=6)
    reason: str | None = Field(default=None, max_length=240)
    metadata_json: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )


class LLMPolicy(UUIDMixin, TenantScopedMixin, TimestampMixin, table=True):
    __tablename__ = "llm_policies"

    name: str = Field(max_length=120, nullable=False)
    description: str | None = Field(default=None)
    scope_type: str = Field(max_length=30, index=True, nullable=False)
    scope_id: UUID | None = Field(default=None, index=True)
    effect: str = Field(default="allow", max_length=20, index=True)
    allowed_models: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    allowed_routing_keys: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    default_model_key: str | None = Field(default=None, max_length=120)
    default_routing_key: str | None = Field(default=None, max_length=120)
    max_tokens: int | None = Field(default=None)
    priority: int = Field(default=100, index=True)
    is_active: bool = Field(default=True, index=True)
    metadata_json: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )


class LLMUsage(UUIDMixin, TenantScopedMixin, TimestampMixin, table=True):
    __tablename__ = "llm_usage"

    deployment_id: UUID | None = Field(default=None, foreign_key="llm_deployments.id", index=True)
    user_id: UUID | None = Field(default=None, foreign_key="users.id", index=True)
    department_id: UUID | None = Field(default=None, foreign_key="departments.id", index=True)
    cost_center_id: UUID | None = Field(default=None, foreign_key="cost_centers.id", index=True)
    agent_id: UUID | None = Field(default=None, index=True)
    channel_id: UUID | None = Field(default=None, index=True)
    conversation_id: UUID | None = Field(
        default=None, foreign_key="conversation_sessions.id", index=True
    )
    request_id: str = Field(max_length=64, index=True, nullable=False)
    model_key: str = Field(max_length=120, index=True, nullable=False)
    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)
    cost_usd: Decimal = Field(default=Decimal("0"), max_digits=12, decimal_places=6)
    status: str = Field(default="success", max_length=30, index=True)
    error_code: str | None = Field(default=None, max_length=80)
    metadata_json: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
