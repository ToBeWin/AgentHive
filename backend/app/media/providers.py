from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from app.media.schemas import MediaGenerationJobStatus, MediaProviderType
from app.models.media import MediaGenerationJob


class MediaProviderSubmitResult(BaseModel):
    status: MediaGenerationJobStatus
    outputs: list[dict[str, Any]] = Field(default_factory=list)
    external_job_id: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MediaProviderProbeResult(BaseModel):
    ok: bool
    status_code: int | None = None
    latency_ms: int
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class MediaProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.metadata = metadata or {}


class MediaProviderNotConfiguredError(MediaProviderError):
    pass


class BaseMediaProviderAdapter(ABC):
    provider_type: MediaProviderType

    @abstractmethod
    async def submit(self, job: MediaGenerationJob) -> MediaProviderSubmitResult:
        """Submit one media generation job to a provider."""

    async def poll(self, job: MediaGenerationJob) -> MediaProviderSubmitResult:
        """Poll one asynchronous media generation job from a provider."""
        raise MediaProviderError(
            f"Media provider {job.provider_type} does not support status polling.",
            metadata={
                "provider_key": job.provider_key,
                "provider_type": job.provider_type,
                "model_key": job.model_key,
                "routing_key": job.routing_key,
                "external_job_id": job.external_job_id,
                "live_network_call": False,
                "poll_supported": False,
            },
        )


class NotConfiguredMediaProviderAdapter(BaseMediaProviderAdapter):
    def __init__(self, provider_type: MediaProviderType) -> None:
        self.provider_type = provider_type

    async def submit(self, job: MediaGenerationJob) -> MediaProviderSubmitResult:
        raise MediaProviderNotConfiguredError(
            f"Media provider {job.provider_type} is not configured for live generation.",
            metadata={
                "provider_key": job.provider_key,
                "provider_type": job.provider_type,
                "model_key": job.model_key,
                "routing_key": job.routing_key,
                "live_network_call": False,
            },
        )


class MediaProviderRegistry:
    def __init__(self) -> None:
        self._adapters: dict[MediaProviderType, BaseMediaProviderAdapter] = {}

    def register(self, adapter: BaseMediaProviderAdapter) -> None:
        self._adapters[adapter.provider_type] = adapter

    def resolve(self, provider_type: str | MediaProviderType) -> BaseMediaProviderAdapter:
        normalized = MediaProviderType(provider_type)
        return self._adapters.get(normalized) or NotConfiguredMediaProviderAdapter(normalized)


media_provider_registry = MediaProviderRegistry()
_default_providers_registered = False


def register_default_media_providers() -> None:
    global _default_providers_registered
    if _default_providers_registered:
        return
    from app.core.config import settings
    from app.media.http_provider import HTTPMediaProviderAdapter

    media_provider_registry.register(
        HTTPMediaProviderAdapter(
            provider_type=MediaProviderType.OPENAI_COMPATIBLE_MEDIA,
            base_url=settings.media_openai_compatible_base_url,
            api_key=settings.media_openai_compatible_api_key,
            image_path=settings.media_openai_compatible_image_path,
            video_path=settings.media_openai_compatible_video_path,
            status_path=settings.media_openai_compatible_status_path,
            callback_url=_media_webhook_callback_url(),
            webhook_secret=settings.media_webhook_secret,
        )
    )
    media_provider_registry.register(
        HTTPMediaProviderAdapter(
            provider_type=MediaProviderType.OPENAI_IMAGES,
            base_url=settings.openai_images_base_url,
            api_key=settings.openai_images_api_key,
            image_path="/images/generations",
            callback_url=_media_webhook_callback_url(),
            webhook_secret=settings.media_webhook_secret,
        )
    )
    media_provider_registry.register(
        HTTPMediaProviderAdapter(
            provider_type=MediaProviderType.NANO_BANANA,
            base_url=settings.nano_banana_base_url,
            api_key=settings.nano_banana_api_key,
            image_path=settings.media_openai_compatible_image_path,
            callback_url=_media_webhook_callback_url(),
            webhook_secret=settings.media_webhook_secret,
        )
    )
    media_provider_registry.register(
        HTTPMediaProviderAdapter(
            provider_type=MediaProviderType.VOLCENGINE_SEEDANCE,
            base_url=settings.volcengine_seedance_base_url,
            api_key=settings.volcengine_seedance_api_key,
            video_path=settings.media_openai_compatible_video_path,
            status_path=settings.volcengine_seedance_status_path,
            callback_url=_media_webhook_callback_url(),
            webhook_secret=settings.media_webhook_secret,
        )
    )
    _default_providers_registered = True


def _media_webhook_callback_url() -> str | None:
    from app.core.config import settings

    if settings.media_webhook_public_url:
        return settings.media_webhook_public_url
    if not settings.public_base_url:
        return None
    return f"{settings.public_base_url.rstrip('/')}/api/v1/media/webhooks/provider"
