from enum import StrEnum
from decimal import Decimal
from ipaddress import ip_address
from typing import Any, Literal
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class MediaGenerationKind(StrEnum):
    IMAGE = "image"
    VIDEO = "video"


class MediaGenerationMode(StrEnum):
    MANUAL_PROMPT = "manual_prompt"
    NATURAL_LANGUAGE = "natural_language"
    MATERIAL_BREAKDOWN = "material_breakdown"


class MediaGenerationJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class MediaAssetKind(StrEnum):
    IMAGE = "image"
    VIDEO = "video"


class MediaProviderType(StrEnum):
    OPENAI_IMAGES = "openai_images"
    NANO_BANANA = "nano_banana"
    VOLCENGINE_SEEDANCE = "volcengine_seedance"
    OPENAI_COMPATIBLE_MEDIA = "openai_compatible_media"
    CUSTOM = "custom"


class MediaAssetRef(BaseModel):
    kind: MediaAssetKind
    bucket: str | None = Field(default=None, max_length=120)
    object_key: str | None = Field(default=None, max_length=500)
    url: str | None = Field(default=None, max_length=2000)
    mime_type: str | None = Field(default=None, max_length=120)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("url")
    @classmethod
    def validate_reference_url(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return value
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("asset url must use http or https.")
        if parsed.username or parsed.password:
            raise ValueError("asset url cannot contain embedded credentials.")
        if not parsed.hostname:
            raise ValueError("asset url requires a host.")
        hostname = parsed.hostname.lower()
        if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".localhost"):
            raise ValueError("asset url cannot target localhost.")
        if hostname.endswith((".local", ".internal", ".lan", ".home")):
            raise ValueError("asset url cannot target private DNS zones.")
        try:
            parsed_ip = ip_address(hostname)
        except ValueError:
            return value
        if (
            parsed_ip.is_private
            or parsed_ip.is_loopback
            or parsed_ip.is_link_local
            or parsed_ip.is_multicast
            or parsed_ip.is_reserved
            or parsed_ip.is_unspecified
        ):
            raise ValueError("asset url cannot target private or local network addresses.")
        return value

    @model_validator(mode="after")
    def validate_location(self) -> "MediaAssetRef":
        if not self.url and not (self.bucket and self.object_key):
            raise ValueError("asset reference requires url or bucket + object_key.")
        return self


class MediaGenerationRequest(BaseModel):
    kind: MediaGenerationKind
    mode: MediaGenerationMode = MediaGenerationMode.NATURAL_LANGUAGE
    prompt: str = Field(min_length=1, max_length=12000)
    negative_prompt: str | None = Field(default=None, max_length=4000)
    model_key: str | None = Field(default=None, max_length=120)
    routing_key: str | None = Field(default=None, max_length=120)
    reference_assets: list[MediaAssetRef] = Field(default_factory=list, max_length=12)
    image_count: int = Field(default=1, ge=1, le=8)
    aspect_ratio: str | None = Field(default=None, max_length=20)
    resolution: str | None = Field(default=None, max_length=40)
    duration_seconds: float | None = Field(default=None, gt=0, le=60)
    fps: int | None = Field(default=None, ge=1, le=120)
    seed: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("fps")
    @classmethod
    def validate_common_fps(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if value not in {16, 24, 25, 30, 50, 60}:
            raise ValueError("fps must be one of 16, 24, 25, 30, 50, or 60.")
        return value

    @model_validator(mode="after")
    def validate_kind_specific_options(self) -> "MediaGenerationRequest":
        if self.kind == MediaGenerationKind.IMAGE:
            video_refs = [
                asset for asset in self.reference_assets if asset.kind == MediaAssetKind.VIDEO
            ]
            if video_refs and self.mode != MediaGenerationMode.MATERIAL_BREAKDOWN:
                raise ValueError(
                    "image generation only accepts video references in material_breakdown mode."
                )
            if self.duration_seconds is not None or self.fps is not None:
                raise ValueError("image generation cannot set duration_seconds or fps.")
        if self.kind == MediaGenerationKind.VIDEO:
            if self.image_count != 1:
                raise ValueError(
                    "video generation outputs one video per request in the initial contract."
                )
            if self.duration_seconds is None:
                self.duration_seconds = 5
            if self.fps is None:
                self.fps = 24
        return self


class MediaModelCapability(BaseModel):
    provider_key: str
    provider_type: MediaProviderType
    model_key: str
    routing_key: str
    kind: MediaGenerationKind
    display_name: str
    capabilities: list[str]
    default_parameters: dict[str, Any] = Field(default_factory=dict)
    price_unit: Literal["output", "second"] = "output"
    price_usd: Decimal = Field(default=Decimal("0"), ge=0)
    pricing_note: str | None = Field(default=None, max_length=240)
    status: Literal["active", "not_configured"] = "not_configured"
    configuration_issues: list[str] = Field(default_factory=list)
    configuration_hint: str | None = Field(default=None, max_length=300)


class MediaGenerationPlan(BaseModel):
    kind: MediaGenerationKind
    provider_key: str
    provider_type: MediaProviderType
    model_key: str
    routing_key: str
    mode: MediaGenerationMode
    prompt: str
    estimated_output_count: int
    estimated_cost_usd: Decimal = Field(default=Decimal("0"), ge=0)
    pricing: dict[str, Any] = Field(default_factory=dict)
    normalized_parameters: dict[str, Any]
    reference_asset_count: int
    output_storage: dict[str, Any]
    execution: dict[str, Any]


class MediaGenerationJobCreateRequest(MediaGenerationRequest):
    agent_id: UUID | None = None
    department_id: UUID | None = None
    conversation_id: UUID | None = None


class MediaGenerationJobStatusUpdate(BaseModel):
    status: MediaGenerationJobStatus
    outputs: list[dict[str, Any]] | None = None
    external_job_id: str | None = Field(default=None, max_length=160)
    error_message: str | None = Field(default=None, max_length=4000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MediaGenerationProviderCallback(BaseModel):
    job_id: UUID | None = None
    external_job_id: str | None = Field(default=None, max_length=160)
    status: MediaGenerationJobStatus
    outputs: list[dict[str, Any]] | None = None
    error_message: str | None = Field(default=None, max_length=4000)
    provider_key: str | None = Field(default=None, max_length=80)
    provider_status: str | None = Field(default=None, max_length=80)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_identifier(self) -> "MediaGenerationProviderCallback":
        if self.job_id is None and not self.external_job_id:
            raise ValueError("provider callback requires job_id or external_job_id.")
        return self


class MediaGenerationJobResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID | None
    department_id: UUID | None
    agent_id: UUID | None
    conversation_id: UUID | None
    request_id: str | None
    kind: MediaGenerationKind
    mode: MediaGenerationMode
    status: MediaGenerationJobStatus
    provider_key: str
    provider_type: MediaProviderType
    model_key: str
    routing_key: str
    prompt: str
    negative_prompt: str | None
    reference_assets: list[dict[str, Any]]
    request_parameters: dict[str, Any]
    normalized_parameters: dict[str, Any]
    output_storage: dict[str, Any]
    outputs: list[dict[str, Any]]
    external_job_id: str | None
    error_message: str | None
    metadata: dict[str, Any]
    created_at: Any
    updated_at: Any
    started_at: Any
    completed_at: Any


class MediaGenerationJobListResponse(BaseModel):
    jobs: list[MediaGenerationJobResponse]
    total: int


class MediaGenerationJobEnqueueResponse(BaseModel):
    job_id: UUID
    task_id: str
    queued: bool = True


class MediaGenerationPollBatchItem(BaseModel):
    job_id: UUID
    external_job_id: str | None = None
    task_id: str | None = None
    queued: bool
    reason: str | None = None


class MediaGenerationPollBatchResponse(BaseModel):
    requested: int
    queued: int
    skipped: int
    failed: int
    items: list[MediaGenerationPollBatchItem]


class MediaGenerationJobEvent(BaseModel):
    id: UUID
    action: str
    status: str
    request_id: str | None = None
    actor_id: UUID | None = None
    actor_type: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: Any


class MediaGenerationJobEventsResponse(BaseModel):
    job_id: UUID
    events: list[MediaGenerationJobEvent]
    total: int
