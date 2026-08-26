from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.llm.schemas import LLMAdapterType, LLMDeploymentStatus, LLMProviderStatus


class LLMProviderResponse(BaseModel):
    provider_key: str
    name: str
    adapter_type: LLMAdapterType
    base_url: str | None
    region: str | None
    status: LLMProviderStatus
    capabilities: list[str]
    credential_configured: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMProviderListResponse(BaseModel):
    providers: list[LLMProviderResponse]


class LLMDeploymentResponse(BaseModel):
    id: UUID
    provider_key: str
    provider_name: str
    adapter_type: LLMAdapterType
    model_key: str
    display_name: str
    deployment_name: str
    routing_key: str
    status: LLMDeploymentStatus
    context_window: int | None
    capabilities: list[str]
    priority: int
    config: dict[str, Any] = Field(default_factory=dict)


class LLMDeploymentListResponse(BaseModel):
    deployments: list[LLMDeploymentResponse]


class LLMDeploymentReadinessResponse(BaseModel):
    deployment_id: UUID
    provider_key: str
    provider_name: str
    model_key: str
    display_name: str
    routing_key: str
    deployment_name: str
    readiness: str
    credential_configured: bool
    deployment_active: bool
    live_probe_ok: bool
    live_probe_checked_at: datetime | None = None
    last_probe_message: str | None = None
    pricing_configured: bool
    policy_referenced: bool
    fallback_configured: bool
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)


class LLMReadinessResponse(BaseModel):
    generated_at: datetime
    summary: dict[str, int] = Field(default_factory=dict)
    deployments: list[LLMDeploymentReadinessResponse]


class LLMModelPriceResponse(BaseModel):
    id: UUID
    model_id: UUID
    provider_key: str
    model_key: str
    display_name: str
    currency: str
    input_per_1k_tokens: Decimal
    output_per_1k_tokens: Decimal
    effective_from: datetime
    effective_to: datetime | None = None


class LLMModelPriceListResponse(BaseModel):
    prices: list[LLMModelPriceResponse]


class LLMModelPriceUpsertRequest(BaseModel):
    provider_key: str = Field(min_length=1, max_length=80)
    model_key: str = Field(min_length=1, max_length=120)
    display_name: str | None = Field(default=None, max_length=120)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    input_per_1k_tokens: Decimal = Field(ge=0)
    output_per_1k_tokens: Decimal = Field(ge=0)
    effective_from: datetime | None = None
    effective_to: datetime | None = None


class LLMConnectionTestRequest(BaseModel):
    provider_key: str | None = Field(default=None, max_length=80)
    deployment_id: UUID | None = None
    model_key: str | None = Field(default=None, max_length=120)
    adapter_type: LLMAdapterType | None = None
    base_url: str | None = None
    api_key: str | None = Field(default=None, min_length=1, max_length=4096)
    timeout_seconds: float = Field(default=10, gt=0, le=60)
    live_check: bool = False
    probe_path: str = Field(default="/models", min_length=1, max_length=200)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        return _normalize_http_url(value)

    @field_validator("probe_path")
    @classmethod
    def validate_probe_path(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("probe_path cannot be empty.")
        if not normalized.startswith("/"):
            normalized = f"/{normalized}"
        if "://" in normalized or "\\" in normalized:
            raise ValueError("probe_path must be a relative HTTP path.")
        return normalized


class LLMConnectionTestResponse(BaseModel):
    ok: bool
    provider_key: str | None
    adapter_type: LLMAdapterType
    model_key: str | None
    latency_ms: int
    checked_at: datetime
    message: str
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class LLMDeploymentAcceptanceTestRequest(BaseModel):
    prompt: str = Field(
        default="Reply with a short AgentHive model acceptance check.",
        min_length=1,
        max_length=500,
    )
    max_tokens: int = Field(default=64, ge=1, le=512)


class LLMDeploymentAcceptanceTestResponse(BaseModel):
    ok: bool
    request_id: str
    deployment_id: UUID
    provider_key: str
    model_key: str
    routing_key: str
    content_preview: str
    usage: LLMUsageResponse
    route_attempts: list[dict[str, Any]] = Field(default_factory=list)
    live_network_call: bool | None = None
    mock: bool | None = None
    usage_recorded: bool = False
    audit_action: str = "llm.deployment.acceptance_test"
    evidence: dict[str, Any] = Field(default_factory=dict)


class LLMConnectionTestHistoryItem(BaseModel):
    id: UUID
    request_id: str | None
    actor_id: UUID | None
    status: str
    ok: bool
    provider_key: str | None
    provider_type: str | None
    deployment_id: str | None
    model_key: str | None
    adapter_type: str | None
    latency_ms: int | None
    checked_at: datetime
    message: str | None
    operation: str | None
    configuration_source: str | None
    probe_path: str | None
    status_code: int | None
    fallback_attempt_count: int | None
    selected_route_reason: str | None
    temporary_api_key_provided: bool
    temporary_base_url_provided: bool
    live_network_call: bool | None


class LLMConnectionTestHistoryResponse(BaseModel):
    tests: list[LLMConnectionTestHistoryItem]


class LLMGovernanceTargetItem(BaseModel):
    id: UUID
    label: str
    description: str | None = None
    status: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMGovernanceTargetsResponse(BaseModel):
    departments: list[LLMGovernanceTargetItem] = Field(default_factory=list)
    cost_centers: list[LLMGovernanceTargetItem] = Field(default_factory=list)
    users: list[LLMGovernanceTargetItem] = Field(default_factory=list)
    agents: list[LLMGovernanceTargetItem] = Field(default_factory=list)
    channels: list[LLMGovernanceTargetItem] = Field(default_factory=list)


class LLMCredentialUpsertRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    api_key: str = Field(min_length=1, max_length=4096)
    base_url: str | None = Field(default=None, max_length=500)
    owner_type: str = Field(default="tenant", max_length=20)
    owner_id: UUID | None = None
    model_key: str | None = Field(default=None, min_length=1, max_length=120)
    deployment_name: str | None = Field(default=None, min_length=1, max_length=120)
    routing_key: str | None = Field(default=None, min_length=1, max_length=120)
    make_default: bool = True

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        return _normalize_http_url(value)

    @field_validator("owner_type")
    @classmethod
    def validate_owner_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"tenant", "department", "user"}:
            raise ValueError("owner_type must be tenant, department, or user.")
        return normalized

    @model_validator(mode="after")
    def validate_owner_scope(self) -> "LLMCredentialUpsertRequest":
        if self.owner_type == "tenant" and self.owner_id is not None:
            raise ValueError("owner_id must be empty for tenant-owned credentials.")
        if self.owner_type in {"department", "user"} and self.owner_id is None:
            raise ValueError("owner_id is required for department or user credentials.")
        return self


class LLMCredentialResponse(BaseModel):
    provider_key: str
    display_name: str
    masked_secret: str
    credential_configured: bool
    base_url: str | None = None
    owner_type: str = "tenant"
    owner_id: UUID | None = None
    deployment_id: UUID | None = None
    routing_key: str | None = None
    model_key: str | None = None


class LLMMessageRequest(BaseModel):
    role: str = Field(min_length=1, max_length=40)
    content: str = Field(min_length=1)
    name: str | None = Field(default=None, max_length=80)


class LLMChatRequest(BaseModel):
    model_key: str | None = Field(default=None, max_length=120)
    routing_key: str | None = Field(default=None, max_length=120)
    messages: list[LLMMessageRequest]
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMUsageResponse(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: Decimal


class LLMChatResponse(BaseModel):
    request_id: str
    provider_key: str
    deployment_id: UUID | None
    model_key: str
    content: str
    finish_reason: str | None
    usage: LLMUsageResponse
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMPolicyScope(StrEnum):
    TENANT = "tenant"
    DEPARTMENT = "department"
    COST_CENTER = "cost_center"
    USER = "user"
    AGENT = "agent"
    CHANNEL = "channel"


class LLMPolicyEffect(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class LLMPolicyStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class LLMPolicyUpsertRequest(BaseModel):
    id: UUID | None = None
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    scope_type: LLMPolicyScope = LLMPolicyScope.TENANT
    scope_id: UUID | None = None
    effect: LLMPolicyEffect = LLMPolicyEffect.ALLOW
    allowed_models: list[str] = Field(default_factory=list)
    allowed_routing_keys: list[str] = Field(default_factory=list)
    default_model_key: str | None = Field(default=None, max_length=120)
    default_routing_key: str | None = Field(default=None, max_length=120)
    max_tokens: int | None = Field(default=None, ge=1, le=200000)
    priority: int = Field(default=100, ge=1, le=10000)
    status: LLMPolicyStatus = LLMPolicyStatus.ACTIVE
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMPolicyStatusUpdateRequest(BaseModel):
    status: LLMPolicyStatus


class LLMPolicyResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None = None
    scope_type: LLMPolicyScope
    scope_id: UUID | None
    effect: LLMPolicyEffect
    allowed_models: list[str]
    allowed_routing_keys: list[str]
    default_model_key: str | None
    default_routing_key: str | None
    max_tokens: int | None
    priority: int
    status: LLMPolicyStatus
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class LLMPolicyListResponse(BaseModel):
    policies: list[LLMPolicyResponse]


def _normalize_http_url(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().rstrip("/")
    if not normalized:
        return None
    if not (normalized.startswith("http://") or normalized.startswith("https://")):
        raise ValueError("base_url must start with http:// or https://.")
    return normalized
