"""Safe, serializable evidence for LLM connection and acceptance diagnostics."""

from typing import Any
from uuid import UUID

from fastapi import HTTPException

from app.models.audit_log import AuditLog
from app.schemas.llm import (
    LLMConnectionTestHistoryItem,
    LLMConnectionTestRequest,
    LLMConnectionTestResponse,
)


def acceptance_error_message(exc: Exception) -> str:
    """Return a bounded error summary suitable for immutable audit evidence."""
    detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
    message = str(detail)
    if len(message) > 500:
        return f"{message[:497]}..."
    return message


def connection_test_audit_details(
    payload: LLMConnectionTestRequest,
    *,
    response: LLMConnectionTestResponse | None = None,
    exc: HTTPException | None = None,
) -> dict[str, Any]:
    """Build audit-safe connection test details without retaining request secrets."""
    diagnostics = response.diagnostics if response else {}
    details: dict[str, Any] = {
        "provider_key": payload.provider_key or (response.provider_key if response else None),
        "deployment_id": str(payload.deployment_id) if payload.deployment_id else None,
        "model_key": payload.model_key or (response.model_key if response else None),
        "adapter_type": str(payload.adapter_type or (response.adapter_type if response else ""))
        or None,
        "timeout_seconds": payload.timeout_seconds,
        "temporary_api_key_provided": bool(payload.api_key),
        "temporary_base_url_provided": bool(payload.base_url),
    }
    if response is not None:
        details.update(
            {
                "ok": response.ok,
                "latency_ms": response.latency_ms,
                "message": sanitize_connection_message(response.message, payload),
                "operation": diagnostics.get("operation"),
                "provider_type": diagnostics.get("provider_type"),
                "configuration_source": diagnostics.get("configuration_source"),
                "probe_path": diagnostics.get("probe_path"),
                "status_code": diagnostics.get("status_code"),
                "fallback_attempt_count": diagnostics.get("fallback_attempt_count"),
                "selected_route_reason": diagnostics.get("selected_route_reason"),
                "all_candidates_failed": diagnostics.get("all_candidates_failed"),
                "mock_allowed": diagnostics.get("mock_allowed"),
                "live_network_call": diagnostics.get("live_network_call"),
                "route_attempts": summarize_route_attempts(diagnostics.get("route_attempts")),
            }
        )
    if exc is not None:
        details.update(
            {
                "ok": False,
                "status_code": exc.status_code,
                "error_type": exc.__class__.__name__,
                "message": sanitize_connection_message(str(exc.detail), payload),
            }
        )
    return details


def connection_test_history_item(event: AuditLog) -> LLMConnectionTestHistoryItem:
    """Map the immutable audit row to the history API without trusting JSON types."""
    details = event.details if isinstance(event.details, dict) else {}
    return LLMConnectionTestHistoryItem(
        id=event.id,
        request_id=event.request_id,
        actor_id=event.actor_id,
        status=event.status,
        ok=bool(details.get("ok", event.status == "success")),
        provider_key=_optional_str(details.get("provider_key")),
        provider_type=_optional_str(details.get("provider_type")),
        deployment_id=_optional_str(details.get("deployment_id")),
        model_key=_optional_str(details.get("model_key")),
        adapter_type=_optional_str(details.get("adapter_type")),
        latency_ms=_optional_int(details.get("latency_ms")),
        checked_at=event.created_at,
        message=_optional_str(details.get("message")),
        operation=_optional_str(details.get("operation")),
        configuration_source=_optional_str(details.get("configuration_source")),
        probe_path=_optional_str(details.get("probe_path")),
        status_code=_optional_int(details.get("status_code")),
        fallback_attempt_count=_optional_int(details.get("fallback_attempt_count")),
        selected_route_reason=_optional_str(details.get("selected_route_reason")),
        temporary_api_key_provided=bool(details.get("temporary_api_key_provided")),
        temporary_base_url_provided=bool(details.get("temporary_base_url_provided")),
        live_network_call=optional_bool(details.get("live_network_call")),
    )


def selected_route_attempt(
    route_attempts: list[dict[str, Any]],
    deployment_id: UUID,
) -> dict[str, Any] | None:
    deployment_id_text = str(deployment_id)
    for attempt in route_attempts:
        if attempt.get("deployment_id") == deployment_id_text and attempt.get("status") == "success":
            return attempt
    return None


def summarize_route_attempts(value: Any) -> list[dict[str, Any]]:
    """Keep a bounded allowlist of route evidence and discard provider error text."""
    if not isinstance(value, list):
        return []
    attempts: list[dict[str, Any]] = []
    for item in value[:5]:
        if not isinstance(item, dict):
            continue
        attempts.append(
            {
                "attempt": item.get("attempt"),
                "provider_key": item.get("provider_key"),
                "model_key": item.get("model_key"),
                "deployment_id": item.get("deployment_id"),
                "routing_key": item.get("routing_key"),
                "status": item.get("status"),
                "latency_ms": item.get("latency_ms"),
                "status_code": item.get("status_code"),
                "probe_path": item.get("probe_path"),
                "error_code": item.get("error_code"),
                "live_network_call": item.get("live_network_call"),
                "mock": item.get("mock"),
            }
        )
    return attempts


def sanitize_connection_message(message: str, payload: LLMConnectionTestRequest) -> str:
    sanitized = message
    if payload.base_url:
        sanitized = sanitized.replace(payload.base_url, "[REDACTED_BASE_URL]")
    if payload.api_key:
        sanitized = sanitized.replace(payload.api_key, "[REDACTED_API_KEY]")
    return sanitized


def optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    return bool(value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
