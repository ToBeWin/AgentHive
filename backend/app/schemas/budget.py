from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class BudgetScopeType(StrEnum):
    TENANT = "tenant"
    DEPARTMENT = "department"
    COST_CENTER = "cost_center"
    USER = "user"
    AGENT = "agent"
    CHANNEL = "channel"


class BudgetPeriod(StrEnum):
    DAILY = "daily"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    CUSTOM = "custom"


class BudgetLimitType(StrEnum):
    HARD = "hard"
    SOFT = "soft"


class BudgetPolicyStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class UsageBreakdownDimension(StrEnum):
    DEPARTMENT = "department"
    USER = "user"
    COST_CENTER = "cost_center"
    AGENT = "agent"
    CHANNEL = "channel"
    MODEL = "model"
    STATUS = "status"


class BudgetLimitHealth(StrEnum):
    OK = "ok"
    WARNING = "warning"
    EXCEEDED = "exceeded"


class BudgetEventType(StrEnum):
    RESERVE = "reserve"
    SETTLE = "settle"
    RELEASE = "release"
    DENY = "deny"
    ALERT = "alert"


class BudgetPolicyUpsertRequest(BaseModel):
    id: UUID | None = None
    name: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    scope_type: BudgetScopeType
    scope_id: UUID | None = None
    period: BudgetPeriod = BudgetPeriod.MONTHLY
    custom_period_start: datetime | None = None
    custom_period_end: datetime | None = None
    budget_type: BudgetLimitType = BudgetLimitType.HARD
    currency: str = Field(default="USD", min_length=3, max_length=3)
    amount_limit: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=4)
    token_limit: int | None = Field(default=None, ge=1)
    alert_threshold_pct: int = Field(default=80, ge=1, le=100)
    status: BudgetPolicyStatus = BudgetPolicyStatus.ACTIVE

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def validate_budget_policy(self) -> "BudgetPolicyUpsertRequest":
        if self.scope_type == BudgetScopeType.TENANT:
            self.scope_id = None
        elif self.scope_id is None:
            raise ValueError("scope_id is required for non-tenant budget policies.")

        if self.amount_limit <= Decimal("0") and self.token_limit is None:
            raise ValueError("budget policy requires amount_limit or token_limit.")

        if self.period == BudgetPeriod.CUSTOM:
            if self.custom_period_start is None or self.custom_period_end is None:
                raise ValueError(
                    "custom period requires custom_period_start and custom_period_end."
                )
            if self.custom_period_end <= self.custom_period_start:
                raise ValueError("custom_period_end must be later than custom_period_start.")
        return self


class BudgetPolicyStatusUpdateRequest(BaseModel):
    status: BudgetPolicyStatus


class BudgetPolicyResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str | None = None
    description: str | None = None
    scope_type: BudgetScopeType
    scope_id: UUID | None
    period: BudgetPeriod
    custom_period_start: datetime | None = None
    custom_period_end: datetime | None = None
    budget_type: BudgetLimitType
    currency: str = "USD"
    amount_limit: Decimal
    amount_spent: Decimal = Decimal("0")
    token_limit: int | None = None
    tokens_used: int = 0
    alert_threshold_pct: int
    status: BudgetPolicyStatus
    health: BudgetLimitHealth = BudgetLimitHealth.OK
    created_at: datetime
    updated_at: datetime


class BudgetPolicyListResponse(BaseModel):
    policies: list[BudgetPolicyResponse]


class BudgetGovernanceTargetItem(BaseModel):
    id: UUID
    label: str
    description: str | None = None
    status: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BudgetGovernanceTargetsResponse(BaseModel):
    departments: list[BudgetGovernanceTargetItem] = Field(default_factory=list)
    cost_centers: list[BudgetGovernanceTargetItem] = Field(default_factory=list)
    users: list[BudgetGovernanceTargetItem] = Field(default_factory=list)
    agents: list[BudgetGovernanceTargetItem] = Field(default_factory=list)
    channels: list[BudgetGovernanceTargetItem] = Field(default_factory=list)


class BudgetScopeSummary(BaseModel):
    scope_type: BudgetScopeType
    policy_count: int = 0
    active_policy_count: int = 0
    amount_limit: Decimal = Decimal("0")
    amount_spent: Decimal = Decimal("0")
    token_limit: int | None = None
    tokens_used: int = 0


class BudgetSummaryResponse(BaseModel):
    tenant_id: UUID
    currency: str = "USD"
    period: BudgetPeriod
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    policy_count: int = 0
    active_policy_count: int = 0
    hard_policy_count: int = 0
    soft_policy_count: int = 0
    warning_policy_count: int = 0
    exceeded_policy_count: int = 0
    total_amount_limit: Decimal = Decimal("0")
    total_amount_spent: Decimal = Decimal("0")
    total_token_limit: int | None = None
    total_tokens_used: int = 0
    by_scope: list[BudgetScopeSummary] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UsageLedgerItem(BaseModel):
    id: UUID
    tenant_id: UUID
    created_at: datetime
    deployment_id: UUID | None
    user_id: UUID | None
    department_id: UUID | None
    agent_id: UUID | None
    channel_id: UUID | None
    conversation_id: UUID | None
    cost_center_id: UUID | None = None
    request_id: str
    model_key: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_amount: Decimal
    currency: str = "USD"
    status: str
    error_code: str | None
    metadata: dict[str, Any] = Field(default_factory=dict)


class UsageLedgerResponse(BaseModel):
    items: list[UsageLedgerItem]
    total: int
    limit: int
    offset: int


class BudgetLedgerItem(BaseModel):
    id: UUID
    tenant_id: UUID
    created_at: datetime
    budget_id: UUID | None
    reservation_id: str
    request_id: str
    event_type: BudgetEventType
    scope_type: BudgetScopeType
    scope_id: UUID | None
    user_id: UUID | None
    department_id: UUID | None
    cost_center_id: UUID | None
    agent_id: UUID | None
    channel_id: UUID | None
    conversation_id: UUID | None
    estimated_tokens: int
    actual_tokens: int
    estimated_cost_amount: Decimal
    actual_cost_amount: Decimal
    currency: str = "USD"
    reason: str | None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BudgetLedgerResponse(BaseModel):
    items: list[BudgetLedgerItem]
    total: int
    limit: int
    offset: int


class UsageBreakdownItem(BaseModel):
    dimension: UsageBreakdownDimension
    key: str
    label: str | None = None
    request_count: int = 0
    success_count: int = 0
    error_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_amount: Decimal = Decimal("0")
    currency: str = "USD"
    last_used_at: datetime | None = None


class UsageBreakdownResponse(BaseModel):
    tenant_id: UUID
    dimension: UsageBreakdownDimension
    period_start: datetime | None = None
    period_end: datetime | None = None
    items: list[UsageBreakdownItem] = Field(default_factory=list)
    total_request_count: int = 0
    total_cost_amount: Decimal = Decimal("0")
    total_tokens: int = 0
