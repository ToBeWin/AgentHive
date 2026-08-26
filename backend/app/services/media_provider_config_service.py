from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.deps import Principal
from app.core.config import settings
from app.core.secrets import decrypt_secret
from app.media.gateway import media_provider_diagnostics_from_settings
from app.media.http_provider import HTTPMediaProviderAdapter
from app.media.schemas import MediaProviderType
from app.models.llm import LLMCredential, LLMProvider


@dataclass(frozen=True)
class MediaProviderConfigBinding:
    provider_type: MediaProviderType
    provider_key: str
    image_path: str
    video_path: str


MEDIA_PROVIDER_CONFIG_BINDINGS: tuple[MediaProviderConfigBinding, ...] = (
    MediaProviderConfigBinding(
        provider_type=MediaProviderType.OPENAI_IMAGES,
        provider_key="openai_images",
        image_path="/images/generations",
        video_path=settings.media_openai_compatible_video_path,
    ),
    MediaProviderConfigBinding(
        provider_type=MediaProviderType.NANO_BANANA,
        provider_key="nano_banana",
        image_path=settings.media_openai_compatible_image_path,
        video_path=settings.media_openai_compatible_video_path,
    ),
    MediaProviderConfigBinding(
        provider_type=MediaProviderType.VOLCENGINE_SEEDANCE,
        provider_key="volcengine_seedance",
        image_path=settings.media_openai_compatible_image_path,
        video_path=settings.media_openai_compatible_video_path,
    ),
    MediaProviderConfigBinding(
        provider_type=MediaProviderType.OPENAI_COMPATIBLE_MEDIA,
        provider_key="openai_compatible_media",
        image_path=settings.media_openai_compatible_image_path,
        video_path=settings.media_openai_compatible_video_path,
    ),
)


async def media_provider_diagnostics(
    session: AsyncSession,
    principal: Principal,
) -> dict[MediaProviderType, list[str]]:
    diagnostics = media_provider_diagnostics_from_settings()
    configured = await _configured_media_provider_types(session, principal)
    for provider_type in configured:
        diagnostics[provider_type] = []
    return diagnostics


async def ensure_media_provider_configured(
    session: AsyncSession,
    principal: Principal,
    provider_type: str | MediaProviderType,
    *,
    department_id: UUID | None = None,
    user_id: UUID | None = None,
) -> None:
    normalized = MediaProviderType(provider_type)
    issues = await media_provider_configuration_issues(
        session,
        principal,
        normalized,
        department_id=department_id,
        user_id=user_id,
    )
    if not issues:
        return
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            f"Media provider {normalized.value} is not configured. "
            f"Missing configuration: {', '.join(issues)}."
        ),
    )


async def media_provider_configuration_issues(
    session: AsyncSession,
    principal: Principal,
    provider_type: str | MediaProviderType,
    *,
    department_id: UUID | None = None,
    user_id: UUID | None = None,
) -> list[str]:
    normalized = MediaProviderType(provider_type)
    settings_issues = media_provider_diagnostics_from_settings().get(normalized, [])
    if not settings_issues:
        return []
    binding = _binding_for_provider_type(normalized)
    if binding is None or not hasattr(session, "execute"):
        return settings_issues
    selection = await _select_media_provider_credential(
        session,
        principal,
        binding,
        department_id=department_id,
        user_id=user_id or principal.user_id,
    )
    if selection is None:
        return settings_issues
    provider, credential = selection
    base_url = provider.base_url or _default_base_url_for_provider_type(normalized)
    if base_url and credential.secret_ref:
        return []
    return settings_issues


async def resolve_database_media_provider_adapter(
    session: AsyncSession,
    principal: Principal,
    provider_type: str | MediaProviderType,
    *,
    department_id: UUID | None = None,
    user_id: UUID | None = None,
) -> HTTPMediaProviderAdapter | None:
    normalized = MediaProviderType(provider_type)
    binding = _binding_for_provider_type(normalized)
    if binding is None or not hasattr(session, "execute"):
        return None
    selection = await _select_media_provider_credential(
        session,
        principal,
        binding,
        department_id=department_id,
        user_id=user_id,
    )
    if selection is None:
        return None
    provider, credential = selection
    base_url = provider.base_url or _default_base_url_for_provider_type(normalized)
    if not base_url:
        return None
    return HTTPMediaProviderAdapter(
        provider_type=normalized,
        base_url=base_url,
        api_key=decrypt_secret(credential.secret_ref),
        image_path=binding.image_path,
        video_path=binding.video_path,
    )


async def _configured_media_provider_types(
    session: AsyncSession,
    principal: Principal,
) -> set[MediaProviderType]:
    configured: set[MediaProviderType] = set()
    for binding in MEDIA_PROVIDER_CONFIG_BINDINGS:
        selection = await _select_media_provider_credential(
            session,
            principal,
            binding,
            department_id=None,
            user_id=principal.user_id,
        )
        if selection is None:
            continue
        provider, credential = selection
        base_url = provider.base_url or _default_base_url_for_provider_type(binding.provider_type)
        if base_url and credential.secret_ref:
            configured.add(binding.provider_type)
    return configured


async def _select_media_provider_credential(
    session: AsyncSession,
    principal: Principal,
    binding: MediaProviderConfigBinding,
    *,
    department_id: UUID | None,
    user_id: UUID | None,
) -> tuple[LLMProvider, LLMCredential] | None:
    result = await session.execute(
        select(LLMProvider, LLMCredential)
        .join(LLMCredential, cast(ColumnElement[bool], LLMCredential.provider_id == LLMProvider.id))
        .where(
            cast(ColumnElement[bool], LLMProvider.tenant_id == principal.tenant_id),
            cast(ColumnElement[bool], LLMProvider.provider_key == binding.provider_key),
            cast(Any, LLMProvider.is_active).is_(True),
            cast(Any, LLMCredential.is_active).is_(True),
        )
    )
    selected: tuple[int, LLMProvider, LLMCredential] | None = None
    for provider, credential in result.all():
        if provider.provider_key != binding.provider_key:
            continue
        rank = _credential_scope_rank(credential, department_id=department_id, user_id=user_id)
        if rank is None:
            continue
        if selected is None or rank > selected[0]:
            selected = (rank, provider, credential)
    if selected is None:
        return None
    _, provider, credential = selected
    return provider, credential


def _credential_scope_rank(
    credential: LLMCredential,
    *,
    department_id: UUID | None,
    user_id: UUID | None,
) -> int | None:
    if credential.owner_type == "user":
        return 30 if credential.owner_id is not None and credential.owner_id == user_id else None
    if credential.owner_type == "department":
        return (
            20 if credential.owner_id is not None and credential.owner_id == department_id else None
        )
    if credential.owner_type == "tenant":
        return 10 if credential.owner_id is None else None
    return None


def _binding_for_provider_type(
    provider_type: MediaProviderType,
) -> MediaProviderConfigBinding | None:
    for binding in MEDIA_PROVIDER_CONFIG_BINDINGS:
        if binding.provider_type == provider_type:
            return binding
    return None


def _default_base_url_for_provider_type(provider_type: MediaProviderType) -> str | None:
    if provider_type == MediaProviderType.OPENAI_IMAGES:
        return settings.openai_images_base_url
    if provider_type == MediaProviderType.NANO_BANANA:
        return settings.nano_banana_base_url
    if provider_type == MediaProviderType.VOLCENGINE_SEEDANCE:
        return settings.volcengine_seedance_base_url
    if provider_type == MediaProviderType.OPENAI_COMPATIBLE_MEDIA:
        return settings.media_openai_compatible_base_url
    return None
