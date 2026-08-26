"""Connection-test, acceptance, and diagnostic orchestration for LLM deployments."""

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol, cast
from uuid import UUID

from cryptography.fernet import InvalidToken
from fastapi import HTTPException, status
from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.deps import Principal
from app.core.config import settings
from app.core.secrets import decrypt_secret
from app.llm.diagnostics import (
    acceptance_error_message,
    connection_test_audit_details,
    connection_test_history_item,
    optional_bool,
    selected_route_attempt,
    summarize_route_attempts,
)
from app.llm.gateway import LLMGateway
from app.llm.schemas import (
    ConnectionTestRequest,
    ConnectionTestResult,
    LLMRequestContext,
    ProviderConfig,
)
from app.media.http_provider import HTTPMediaProviderAdapter
from app.media.schemas import MediaProviderType
from app.models.audit_log import AuditLog
from app.models.llm import LLMCredential, LLMDeployment, LLMModel, LLMProvider
from app.schemas.llm import (
    LLMChatRequest,
    LLMChatResponse,
    LLMConnectionTestHistoryResponse,
    LLMConnectionTestRequest,
    LLMConnectionTestResponse,
    LLMDeploymentAcceptanceTestRequest,
    LLMDeploymentAcceptanceTestResponse,
    LLMMessageRequest,
)
from app.services.audit_service import record_audit_event
from app.services.media_provider_config_service import resolve_database_media_provider_adapter


@dataclass(frozen=True)
class DeploymentAcceptanceTarget:
    deployment_id: UUID
    provider_key: str
    model_key: str
    routing_key: str
    credential_configured: bool


class GatewayBuilder(Protocol):
    async def __call__(self, session: AsyncSession | None, principal: Principal) -> LLMGateway: ...


class GatewayChatRunner(Protocol):
    async def __call__(
        self,
        payload: LLMChatRequest,
        principal: Principal,
        *,
        session: AsyncSession | None = None,
        source: str = "api",
    ) -> LLMChatResponse: ...


class AcceptanceTargetResolver(Protocol):
    async def __call__(
        self,
        session: AsyncSession,
        principal: Principal,
        deployment_id: UUID,
    ) -> DeploymentAcceptanceTarget: ...


ProviderConfigResolver = Callable[[str], ProviderConfig]
StringResolver = Callable[[str], str]

_MEDIA_PROVIDER_TYPES_BY_PROVIDER_KEY = {
    "openai_images": MediaProviderType.OPENAI_IMAGES,
    "nano_banana": MediaProviderType.NANO_BANANA,
    "volcengine_seedance": MediaProviderType.VOLCENGINE_SEEDANCE,
    "openai_compatible_media": MediaProviderType.OPENAI_COMPATIBLE_MEDIA,
}

_MEDIA_PROVIDER_KEY_BY_MODEL_KEY = {
    "openai/gpt-image-2": "openai_images",
    "google/nano-banana": "nano_banana",
    "volcengine/seedance-2.0": "volcengine_seedance",
    "openai-compatible-image": "openai_compatible_media",
    "openai-compatible-video": "openai_compatible_media",
}


async def list_connection_test_history(
    session: AsyncSession,
    principal: Principal,
    *,
    limit: int = 20,
) -> LLMConnectionTestHistoryResponse:
    """Return only connection/acceptance evidence belonging to the principal's tenant."""
    result = await session.execute(
        select(AuditLog)
        .where(
            cast(ColumnElement[bool], AuditLog.tenant_id == principal.tenant_id),
            cast(ColumnElement[str], AuditLog.action).in_(
                ["llm.connection_test", "llm.deployment.acceptance_test"]
            ),
        )
        .order_by(cast(ColumnElement[object], AuditLog.created_at).desc())
        .limit(max(1, min(limit, 100)))
    )
    return LLMConnectionTestHistoryResponse(
        tests=[connection_test_history_item(event) for event in result.scalars().all()]
    )


async def run_connection_test(
    payload: LLMConnectionTestRequest,
    principal: Principal,
    session: AsyncSession | None,
    *,
    request_id: str | None,
    build_gateway: GatewayBuilder,
    provider_config: ProviderConfigResolver,
    default_model_key: StringResolver,
    default_routing_key: StringResolver,
) -> LLMConnectionTestResponse:
    """Run a gateway or media-provider test and persist sanitized audit evidence."""
    if _is_media_connection_test(payload):
        response = await _test_media_provider_connection(
            payload,
            principal,
            session,
            provider_config=provider_config,
            default_model_key=default_model_key,
            default_routing_key=default_routing_key,
        )
        await _record_connection_test_result_audit(
            session,
            payload=payload,
            principal=principal,
            request_id=request_id,
            response=response,
        )
        return response

    gateway = await build_gateway(session, principal)
    if request_id:
        context = LLMRequestContext(
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            source="api",
            request_id=request_id,
        )
    else:
        context = LLMRequestContext(
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            source="api",
        )
    try:
        result = await gateway.test_connection(
            ConnectionTestRequest(**payload.model_dump()),
            context,
        )
    except HTTPException as exc:
        await _record_connection_test_failure_audit(
            session,
            payload=payload,
            principal=principal,
            request_id=request_id,
            exc=exc,
        )
        raise

    response = LLMConnectionTestResponse(**result.model_dump())
    await _record_connection_test_result_audit(
        session,
        payload=payload,
        principal=principal,
        request_id=request_id,
        response=response,
    )
    return response


async def run_deployment_acceptance_test(
    session: AsyncSession,
    deployment_id: UUID,
    principal: Principal,
    payload: LLMDeploymentAcceptanceTestRequest,
    *,
    request_id: str | None,
    resolve_target: AcceptanceTargetResolver,
    run_gateway_chat: GatewayChatRunner,
) -> LLMDeploymentAcceptanceTestResponse:
    """Run a saved deployment through the normal gateway and record acceptance evidence."""
    target: DeploymentAcceptanceTarget | None = None
    try:
        target = await resolve_target(session, principal, deployment_id)
        response = await run_gateway_chat(
            LLMChatRequest(
                routing_key=target.routing_key,
                messages=[LLMMessageRequest(role="user", content=payload.prompt)],
                max_tokens=payload.max_tokens,
                metadata={
                    "acceptance_test": True,
                    "deployment_id": str(target.deployment_id),
                },
            ),
            principal,
            session=session,
            source="model_acceptance_test",
        )
    except HTTPException as exc:
        await _record_deployment_acceptance_failure_audit(
            session,
            deployment_id=deployment_id,
            principal=principal,
            request_id=request_id,
            target=target,
            exc=exc,
        )
        raise
    except Exception as exc:
        await _record_deployment_acceptance_failure_audit(
            session,
            deployment_id=deployment_id,
            principal=principal,
            request_id=request_id,
            target=target,
            exc=exc,
        )
        raise

    route_attempts = summarize_route_attempts(response.metadata.get("route_attempts"))
    selected_attempt = selected_route_attempt(route_attempts, target.deployment_id)
    live_network_call = optional_bool(response.metadata.get("live_network_call"))
    mock = optional_bool(response.metadata.get("mock"))
    if selected_attempt is not None:
        live_network_call = (
            optional_bool(selected_attempt.get("live_network_call")) or live_network_call
        )
        mock = (
            optional_bool(selected_attempt.get("mock"))
            if selected_attempt.get("mock") is not None
            else mock
        )
    usage_recorded = response.request_id is not None
    acceptance_message = response.content[:240]
    await record_audit_event(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        action="llm.deployment.acceptance_test",
        status="success",
        resource_type="llm_deployment",
        resource_id=target.deployment_id,
        request_id=request_id or response.request_id,
        details={
            "provider_key": response.provider_key,
            "model_key": response.model_key,
            "deployment_id": str(target.deployment_id),
            "routing_key": target.routing_key,
            "ok": True,
            "operation": "deployment_acceptance_test",
            "configuration_source": "saved_deployment",
            "latency_ms": selected_attempt.get("latency_ms") if selected_attempt else None,
            "status_code": selected_attempt.get("status_code") if selected_attempt else None,
            "message": acceptance_message,
            "response_request_id": response.request_id,
            "usage_recorded": usage_recorded,
            "live_network_call": live_network_call,
            "mock": mock,
            "route_attempts": route_attempts,
            "pricing_rule": response.metadata.get("pricing_rule"),
        },
    )
    await session.commit()
    return LLMDeploymentAcceptanceTestResponse(
        ok=True,
        request_id=response.request_id,
        deployment_id=target.deployment_id,
        provider_key=response.provider_key,
        model_key=response.model_key,
        routing_key=target.routing_key,
        content_preview=acceptance_message,
        usage=response.usage,
        route_attempts=route_attempts,
        live_network_call=live_network_call,
        mock=mock,
        usage_recorded=usage_recorded,
        evidence={
            "credential_configured": target.credential_configured,
            "finish_reason": response.finish_reason,
            "pricing_rule": response.metadata.get("pricing_rule"),
            "fallback_attempt_count": response.metadata.get("fallback_attempt_count"),
            "selected_route_reason": response.metadata.get("selected_route_reason"),
        },
    )


async def get_acceptance_target(
    session: AsyncSession,
    principal: Principal,
    deployment_id: UUID,
) -> DeploymentAcceptanceTarget:
    """Resolve an active deployment and credential within the principal's tenant."""
    result = await session.execute(
        select(LLMDeployment, LLMProvider, LLMModel, LLMCredential)
        .join(LLMProvider, cast(ColumnElement[bool], LLMProvider.id == LLMDeployment.provider_id))
        .join(LLMModel, cast(ColumnElement[bool], LLMModel.id == LLMDeployment.model_id))
        .join(
            LLMCredential,
            cast(ColumnElement[bool], LLMCredential.id == LLMDeployment.credential_id),
        )
        .where(
            cast(ColumnElement[bool], LLMDeployment.tenant_id == principal.tenant_id),
            cast(ColumnElement[bool], LLMDeployment.id == deployment_id),
            cast(ColumnElement[bool], LLMDeployment.is_active).is_(True),
            cast(ColumnElement[bool], LLMProvider.is_active).is_(True),
            cast(ColumnElement[bool], LLMCredential.is_active).is_(True),
        )
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active model deployment with an active credential was not found.",
        )
    deployment, provider, model, credential = row
    try:
        decrypt_secret(credential.secret_ref)
    except InvalidToken as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Deployment credential cannot be decrypted. Rotate the credential before acceptance testing.",
        ) from exc
    return DeploymentAcceptanceTarget(
        deployment_id=deployment.id,
        provider_key=provider.provider_key,
        model_key=model.model_key,
        routing_key=deployment.routing_key,
        credential_configured=True,
    )


async def _test_media_provider_connection(
    payload: LLMConnectionTestRequest,
    principal: Principal,
    session: AsyncSession | None,
    *,
    provider_config: ProviderConfigResolver,
    default_model_key: StringResolver,
    default_routing_key: StringResolver,
) -> LLMConnectionTestResponse:
    started = perf_counter()
    provider_key = _media_provider_key_for_connection_test(payload)
    provider_type = _MEDIA_PROVIDER_TYPES_BY_PROVIDER_KEY[provider_key]
    config = provider_config(provider_key)
    database_adapter = None
    if session is not None:
        database_adapter = await resolve_database_media_provider_adapter(
            session,
            principal,
            provider_type,
            user_id=principal.user_id,
        )

    base_url = (
        payload.base_url
        or (database_adapter.base_url if database_adapter else None)
        or config.base_url
    )
    api_key = (
        payload.api_key
        or (database_adapter.api_key if database_adapter else None)
        or _media_api_key_for_provider_key(provider_key)
    )
    missing: list[str] = []
    if not base_url:
        missing.append("base_url")
    if not api_key:
        missing.append("api_key")

    ok = not missing
    latency_ms = max(0, int((perf_counter() - started) * 1000))
    model_key = payload.model_key or default_model_key(provider_key)
    operation = "media_provider_configuration_check"
    message = (
        f"{config.name} media provider configuration is ready."
        if ok
        else f"{config.name} media provider is missing: {', '.join(missing)}."
    )
    live_metadata: dict[str, object] = {"live_network_call": False}
    if ok and payload.live_check:
        adapter = HTTPMediaProviderAdapter(
            provider_type=provider_type,
            base_url=base_url,
            api_key=api_key or "",
            timeout_seconds=payload.timeout_seconds,
        )
        probe = await adapter.probe(probe_path=payload.probe_path)
        ok = probe.ok
        latency_ms = probe.latency_ms
        operation = "media_provider_live_probe"
        message = probe.message
        live_metadata = {
            **probe.metadata,
            "live_network_call": True,
            "status_code": probe.status_code,
        }
    route_attempt: dict[str, object] = {
        "attempt": 1,
        "provider_key": provider_key,
        "model_key": model_key,
        "routing_key": default_routing_key(provider_key),
        "status": "success" if ok else "error",
        "latency_ms": latency_ms,
    }
    if live_metadata.get("status_code") is not None:
        route_attempt["status_code"] = live_metadata["status_code"]
    result = ConnectionTestResult(
        ok=ok,
        provider_key=provider_key,
        adapter_type=config.adapter_type,
        model_key=model_key,
        latency_ms=latency_ms,
        message=message,
        diagnostics={
            "operation": operation,
            "provider_type": provider_type.value,
            "configuration_source": _media_connection_source(
                payload,
                database_adapter is not None,
                config,
            ),
            **live_metadata,
            "mock_allowed": False,
            "missing": missing,
            "probe_path": payload.probe_path,
            "route_attempts": [route_attempt],
            "fallback_attempt_count": 0,
            "selected_route_reason": "media_provider_configuration",
        },
    )
    return LLMConnectionTestResponse(**result.model_dump())


def _is_media_connection_test(payload: LLMConnectionTestRequest) -> bool:
    return _media_provider_key_for_connection_test(payload) in _MEDIA_PROVIDER_TYPES_BY_PROVIDER_KEY


def _media_provider_key_for_connection_test(payload: LLMConnectionTestRequest) -> str:
    if payload.provider_key in _MEDIA_PROVIDER_TYPES_BY_PROVIDER_KEY:
        return payload.provider_key
    if payload.model_key and payload.model_key in _MEDIA_PROVIDER_KEY_BY_MODEL_KEY:
        return _MEDIA_PROVIDER_KEY_BY_MODEL_KEY[payload.model_key]
    return ""


def _media_connection_source(
    payload: LLMConnectionTestRequest,
    has_database_adapter: bool,
    provider_config: ProviderConfig,
) -> str:
    if payload.api_key or payload.base_url:
        return "temporary_request"
    if has_database_adapter:
        return "database_credential"
    if provider_config.credential_configured:
        return "environment"
    return "missing"


def _media_api_key_for_provider_key(provider_key: str) -> str:
    api_keys = {
        "openai_images": settings.openai_images_api_key,
        "nano_banana": settings.nano_banana_api_key,
        "volcengine_seedance": settings.volcengine_seedance_api_key,
        "openai_compatible_media": settings.media_openai_compatible_api_key,
    }
    return str(api_keys.get(provider_key) or "")


async def _record_connection_test_result_audit(
    session: AsyncSession | None,
    *,
    payload: LLMConnectionTestRequest,
    principal: Principal,
    request_id: str | None,
    response: LLMConnectionTestResponse,
) -> None:
    if session is None:
        return
    await record_audit_event(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        action="llm.connection_test",
        resource_type="llm_provider",
        status="success" if response.ok else "failure",
        request_id=request_id,
        details=connection_test_audit_details(payload, response=response),
    )
    await session.commit()


async def _record_connection_test_failure_audit(
    session: AsyncSession | None,
    *,
    payload: LLMConnectionTestRequest,
    principal: Principal,
    request_id: str | None,
    exc: HTTPException,
) -> None:
    if session is None:
        return
    try:
        await session.rollback()
        await record_audit_event(
            session,
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action="llm.connection_test",
            resource_type="llm_provider",
            status="failure",
            request_id=request_id,
            details=connection_test_audit_details(payload, exc=exc),
        )
        await session.commit()
    except Exception:
        await session.rollback()


async def _record_deployment_acceptance_failure_audit(
    session: AsyncSession,
    *,
    deployment_id: UUID,
    principal: Principal,
    request_id: str | None,
    target: DeploymentAcceptanceTarget | None,
    exc: Exception,
) -> None:
    try:
        await session.rollback()
        await record_audit_event(
            session,
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action="llm.deployment.acceptance_test",
            status="failure",
            resource_type="llm_deployment",
            resource_id=deployment_id,
            request_id=request_id,
            details={
                "deployment_id": str(deployment_id),
                "provider_key": target.provider_key if target else None,
                "model_key": target.model_key if target else None,
                "routing_key": target.routing_key if target else None,
                "ok": False,
                "operation": "deployment_acceptance_test",
                "configuration_source": "saved_deployment" if target else None,
                "credential_configured": target.credential_configured if target else None,
                "status_code": exc.status_code if isinstance(exc, HTTPException) else None,
                "error_type": exc.__class__.__name__,
                "message": acceptance_error_message(exc),
            },
        )
        await session.commit()
    except Exception:
        await session.rollback()
