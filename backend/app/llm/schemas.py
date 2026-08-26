from collections.abc import AsyncIterator
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class LLMAdapterType(StrEnum):
    LITELLM = "litellm"
    OPENAI_COMPATIBLE = "openai_compatible"
    ANTHROPIC_COMPATIBLE = "anthropic_compatible"


class LLMProviderStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    NOT_CONFIGURED = "not_configured"


class LLMDeploymentStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class LLMCallStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    DENIED = "denied"
    BUDGET_EXCEEDED = "budget_exceeded"


class Message(BaseModel):
    role: str = Field(min_length=1, max_length=40)
    content: str = Field(min_length=1)
    name: str | None = Field(default=None, max_length=80)


class LLMUsageMetrics(BaseModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    cost_usd: Decimal = Field(default=Decimal("0"), ge=0)


class LLMResponse(BaseModel):
    request_id: str
    model_key: str
    content: str
    usage: LLMUsageMetrics
    provider_key: str
    deployment_id: UUID | None = None
    finish_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMRequestContext(BaseModel):
    tenant_id: UUID
    user_id: UUID | None = None
    department_id: UUID | None = None
    cost_center_id: UUID | None = None
    agent_id: UUID | None = None
    channel_id: UUID | None = None
    conversation_id: UUID | None = None
    request_id: str = Field(default_factory=lambda: uuid4().hex)
    source: str = Field(default="api", max_length=40)


class LLMChatRequest(BaseModel):
    model_key: str | None = Field(default=None, max_length=120)
    routing_key: str | None = Field(default=None, max_length=120)
    messages: list[Message]
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderConfig(BaseModel):
    provider_key: str
    name: str
    adapter_type: LLMAdapterType
    base_url: str | None = None
    region: str | None = None
    status: LLMProviderStatus = LLMProviderStatus.ACTIVE
    capabilities: list[str] = Field(default_factory=list)
    credential_configured: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeploymentConfig(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    provider_key: str
    provider_name: str
    adapter_type: LLMAdapterType
    model_key: str
    display_name: str
    deployment_name: str
    routing_key: str
    status: LLMDeploymentStatus = LLMDeploymentStatus.ACTIVE
    context_window: int | None = None
    capabilities: list[str] = Field(default_factory=list)
    priority: int = 100
    base_url: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class PolicyDecision(BaseModel):
    allowed: bool
    reason: str = "allowed"
    model_key: str | None = None
    routing_key: str | None = None
    max_tokens: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BudgetReservationScope(BaseModel):
    budget_id: UUID
    scope_type: str
    scope_id: UUID | None = None


class BudgetReservation(BaseModel):
    reservation_id: str = Field(default_factory=lambda: uuid4().hex)
    approved: bool
    reason: str = "approved"
    estimated_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: Decimal = Field(default=Decimal("0"), ge=0)
    budget_scopes: list[BudgetReservationScope] = Field(default_factory=list)


class RouteSelection(BaseModel):
    deployment: DeploymentConfig
    provider: ProviderConfig
    reason: str = "primary"


class ConnectionTestRequest(BaseModel):
    provider_key: str | None = Field(default=None, max_length=80)
    deployment_id: UUID | None = None
    model_key: str | None = Field(default=None, max_length=120)
    adapter_type: LLMAdapterType | None = None
    base_url: str | None = None
    api_key: str | None = Field(default=None, repr=False, exclude=True)
    timeout_seconds: float = Field(default=10, gt=0, le=60)
    live_check: bool = False
    probe_path: str = Field(default="/models", min_length=1, max_length=200)


class ConnectionTestResult(BaseModel):
    ok: bool
    provider_key: str | None = None
    adapter_type: LLMAdapterType
    model_key: str | None = None
    latency_ms: int
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message: str
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class UsageRecord(BaseModel):
    request_id: str
    tenant_id: UUID
    status: LLMCallStatus
    provider_key: str | None = None
    model_key: str | None = None
    deployment_id: UUID | None = None
    usage: LLMUsageMetrics = Field(default_factory=LLMUsageMetrics)
    error_code: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


StreamChunks = AsyncIterator[str]
