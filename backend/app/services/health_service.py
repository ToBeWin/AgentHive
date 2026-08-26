from __future__ import annotations

import asyncio
from io import BytesIO
import json
from datetime import datetime, timezone
import re
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote, urlparse
from uuid import UUID
from zipfile import ZIP_DEFLATED, ZipFile

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import (
    is_development_environment,
    is_production_environment,
    production_config_issues,
    settings,
)
from app.core.database import check_database_health, engine
from app.core.install_identity import get_install_identity
from app.health import support_bundle_rendering
from app.agents.runtime_dependencies import agent_runtime_dependency_status
from app.media.gateway import (
    list_media_model_capabilities,
    media_provider_diagnostics_from_settings,
)
from app.media.schemas import MediaGenerationKind, MediaProviderType
from app.models.audit_log import AuditLog
from app.rag.minio import MinIOObjectStorageAdapter
from app.rag.pgvector import PGVectorAdapter
from app.rag.ragflow import RAGFlowAdapter
from app.services.audit_service import record_audit_event
from app.services.agent_concurrency import agent_concurrency_limiter
from app.services.migration_service import get_migration_status
from app.services.schema_readiness import (
    expected_media_runtime_indexes,
    missing_media_runtime_indexes,
)
from app.workers.celery_app import celery_app

Component = dict[str, Any]

DIAGNOSTICS_SCHEMA_VERSION = "1.0"
SENSITIVE_KEY_PATTERN = re.compile(
    r"(secret|password|token|api.?key|master.?key|authorization|credential|license_key)",
    re.IGNORECASE,
)
SENSITIVE_VALUE_PATTERN = re.compile(
    r"(bearer\s+[a-z0-9._-]+|sk-[a-z0-9_-]{12,}|[a-z][a-z0-9+.-]*://[^/\s:]+:[^@\s]+@)",
    re.IGNORECASE,
)
REMEDIATION_STATUS_VALUES = {"degraded", "unhealthy", "not_configured", "error"}
DELIVERY_CRITICAL_COMPONENTS = {
    "database",
    "redis",
    "minio",
    "litellm",
    "frontend",
    "pgvector",
    "production_config",
    "license_identity",
    "agent_runtime",
}

COMPONENT_REMEDIATIONS: dict[str, dict[str, str]] = {
    "database": {
        "summary": "PostgreSQL is required for all core business data.",
        "action": "Check the PostgreSQL container, DATABASE_URL, credentials, network access, and migration status.",
        "docs_anchor": "deployment.database",
    },
    "redis": {
        "summary": "Redis is required for queues, cache, throttling, and short-lived runtime state.",
        "action": "Check the Redis container, REDIS_URL, password, network access, and whether the port is reachable.",
        "docs_anchor": "deployment.redis",
    },
    "minio": {
        "summary": "MinIO stores uploaded files, parsed source documents, avatars, and channel attachments.",
        "action": "Check the MinIO endpoint, access key, secret key, bucket policy, and object storage health.",
        "docs_anchor": "deployment.minio",
    },
    "litellm": {
        "summary": "LiteLLM is the default multi-model protocol adapter for AgentHive LLM Gateway.",
        "action": "Check LITELLM_BASE_URL, master key, LiteLLM container health, model config, and provider credentials.",
        "docs_anchor": "deployment.litellm",
    },
    "frontend": {
        "summary": "The frontend service serves the AgentHive management console.",
        "action": "Check the frontend container health, build artifact, nginx upstream, and AGENTHIVE_FRONTEND_HEALTH_URL.",
        "docs_anchor": "deployment.frontend",
    },
    "pgvector": {
        "summary": "pgvector is the default vector store and fallback retrieval backend.",
        "action": "Enable the pgvector extension, verify migrations, and ensure the database user can create/use vector indexes.",
        "docs_anchor": "deployment.pgvector",
    },
    "production_config": {
        "summary": "Production deployments must not use template secrets or development defaults.",
        "action": "Replace default secrets, Redis passwords, MinIO credentials, LiteLLM keys, and environment placeholders before delivery.",
        "docs_anchor": "deployment.production_config",
    },
    "license_identity": {
        "summary": "License identity binds a deployment package to one authorized installation.",
        "action": "Verify the install identity file, deployment ID, machine fingerprint, and Ed25519 license public key.",
        "docs_anchor": "deployment.license",
    },
    "agent_runtime": {
        "summary": "LangChain and LangGraph are required for production Agent orchestration.",
        "action": "Install backend dependencies with uv sync or rebuild the backend image from the locked dependency set.",
        "docs_anchor": "deployment.agent_runtime",
    },
    "agent_concurrency": {
        "summary": "Agent execution slots protect tenants, users, and Agent instances during concurrent usage.",
        "action": "Tune AGENTHIVE_AGENT_CONCURRENCY_* for the customer's CPU, memory, model latency, and worker count.",
        "docs_anchor": "deployment.agent_concurrency",
    },
    "media_generation": {
        "summary": "Media generation routes power the optional image and video creation Agents.",
        "action": "Configure at least one image provider and one video provider before selling or enabling media Agent modules.",
        "docs_anchor": "deployment.media_generation",
    },
    "media_worker": {
        "summary": "The media Worker executes queued image and video generation jobs.",
        "action": "Start the Celery worker with app.workers.celery_app, verify Redis broker connectivity, and confirm worker ping responses.",
        "docs_anchor": "deployment.media_worker",
    },
    "ragflow": {
        "summary": "RAGFlow is optional, but configured tenants depend on it for external RAG workflows.",
        "action": "Check RAGFLOW_URL, API credentials, RAGFlow service health, and unset the integration when it is not used.",
        "docs_anchor": "deployment.ragflow",
    },
}


async def build_health_report(*, deep: bool = False) -> dict[str, Any]:
    components: dict[str, Component] = {
        "database": await _check_database(deep=deep),
        "redis": await _check_redis(),
        "minio": await _check_minio() if deep else _configured("configured"),
        "litellm": await _check_litellm() if deep else _configured("configured"),
        "pgvector": await _check_pgvector() if deep else _configured("configured"),
        "production_config": _check_production_config(),
        "license_identity": _check_license_identity(),
        "agent_runtime": agent_runtime_dependency_status(),
        "agent_concurrency": await _check_agent_concurrency(),
        "media_generation": _check_media_generation(),
        "media_worker": await _check_media_worker() if deep else _configured("configured"),
    }
    if deep:
        if _should_check_frontend(deep=deep):
            components["frontend"] = await _check_frontend()
    else:
        components["frontend"] = _configured("configured")
    if deep and settings.ragflow_url:
        components["ragflow"] = await _check_ragflow()
    components = {
        name: _with_remediation(name, component) for name, component in components.items()
    }
    status_value = _overall_status(components)
    report: dict[str, Any] = {
        "status": status_value,
        "service": "agenthive-backend",
        "version": settings.app_version,
        "environment": settings.environment,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "components": components,
    }
    if deep:
        report["delivery"] = _build_delivery_assessment(components)
    return report


async def build_readiness_report() -> dict[str, Any]:
    return await build_health_report(deep=True)


async def build_diagnostics_report(
    session: AsyncSession | None = None, principal: Any | None = None
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    health, readiness = await asyncio.gather(
        build_health_report(deep=False),
        build_readiness_report(),
    )
    diagnostics = {
        "health": health,
        "readiness": readiness,
        "info": build_system_info(),
    }
    if session is not None and principal is not None:
        diagnostics["connection_acceptance"] = await _build_connection_acceptance_evidence(
            session, principal
        )
        diagnostics["knowledge_acceptance"] = await _build_knowledge_acceptance_evidence(
            session, principal
        )
    redacted = redact_diagnostics(diagnostics)
    return {
        "product": "AgentHive",
        "report_type": "deployment_diagnostics",
        "schema_version": DIAGNOSTICS_SCHEMA_VERSION,
        "generated_at": generated_at,
        "redacted": True,
        "delivery": redacted["readiness"].get("delivery")
        if isinstance(redacted.get("readiness"), dict)
        else None,
        "diagnostics": redacted,
    }


async def build_support_bundle(
    session: AsyncSession | None = None, principal: Any | None = None
) -> tuple[bytes, str]:
    report = await build_diagnostics_report(session=session, principal=principal)
    generated_at = str(report["generated_at"])
    safe_generated_at = _safe_timestamp(generated_at)
    manifest = {
        "product": report.get("product", "AgentHive"),
        "bundle_type": "deployment_support_bundle",
        "schema_version": report.get("schema_version", DIAGNOSTICS_SCHEMA_VERSION),
        "generated_at": generated_at,
        "redacted": report.get("redacted") is True,
        "files": [
            "README.md",
            "acceptance-checklist.md",
            "diagnostics.json",
            "delivery-summary.md",
            "manifest.json",
        ],
    }

    archive = BytesIO()
    with ZipFile(archive, mode="w", compression=ZIP_DEFLATED) as bundle:
        bundle.writestr("README.md", _support_bundle_readme(report))
        bundle.writestr("acceptance-checklist.md", _support_bundle_acceptance_checklist(report))
        bundle.writestr(
            "diagnostics.json", json.dumps(report, indent=2, ensure_ascii=False, default=str)
        )
        bundle.writestr("delivery-summary.md", _support_bundle_delivery_summary(report))
        bundle.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))

    return archive.getvalue(), f"agenthive-support-bundle-{safe_generated_at}.zip"


async def record_diagnostics_export_audit(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    actor_id: UUID | None,
    report: dict[str, Any],
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    readiness = _dict_or_empty(report.get("diagnostics", {})).get("readiness", {})
    readiness_report = _dict_or_empty(readiness)
    delivery = _dict_or_empty(report.get("delivery"))
    components = _dict_or_empty(readiness_report.get("components"))
    try:
        await record_audit_event(
            session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            action="system.diagnostics.export",
            resource_type="system",
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "schema_version": report.get("schema_version"),
                "redacted": report.get("redacted") is True,
                "readiness_status": readiness_report.get("status"),
                "delivery_status": delivery.get("status"),
                "blocker_count": delivery.get("blocker_count", 0),
                "warning_count": delivery.get("warning_count", 0),
                "component_count": len(components),
            },
        )
        await session.commit()
    except Exception:
        await session.rollback()


async def record_support_bundle_export_audit(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    actor_id: UUID | None,
    filename: str,
    bundle_size_bytes: int,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    try:
        await record_audit_event(
            session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            action="system.support_bundle.export",
            resource_type="system",
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "filename": filename,
                "bundle_size_bytes": bundle_size_bytes,
                "redacted": True,
                "format": "zip",
            },
        )
        await session.commit()
    except Exception:
        await session.rollback()


def build_system_info() -> dict[str, str]:
    return {
        "name": "AgentHive",
        "edition": "private-deployment",
        "version": settings.app_version,
    }


async def _build_connection_acceptance_evidence(
    session: AsyncSession, principal: Any
) -> dict[str, Any]:
    from app.services.llm_service import list_connection_test_history

    try:
        history = await list_connection_test_history(session, principal, limit=8)
    except Exception as exc:
        return {
            "status": "unavailable",
            "summary": f"Connection test history could not be loaded: {exc.__class__.__name__}.",
            "recent_test_count": 0,
            "live_network_call_count": 0,
            "media_live_probe_count": 0,
            "failed_recent_count": 0,
            "providers": [],
            "recent_tests": [],
        }

    tests = history.tests
    live_tests = [item for item in tests if item.live_network_call is True]
    media_live_probes = [
        item
        for item in live_tests
        if item.operation == "media_provider_live_probe"
        or (item.provider_type or "").endswith("_media")
    ]
    failed_tests = [item for item in tests if not item.ok]
    providers = sorted({item.provider_key for item in tests if item.provider_key})
    status_value = (
        "healthy" if live_tests and not failed_tests else "degraded" if tests else "not_reported"
    )
    summary = _connection_acceptance_summary(
        recent_test_count=len(tests),
        live_network_call_count=len(live_tests),
        media_live_probe_count=len(media_live_probes),
        failed_recent_count=len(failed_tests),
    )
    return {
        "status": status_value,
        "summary": summary,
        "recent_test_count": len(tests),
        "live_network_call_count": len(live_tests),
        "media_live_probe_count": len(media_live_probes),
        "failed_recent_count": len(failed_tests),
        "providers": providers,
        "latest_live_probe": _connection_evidence_item(live_tests[0]) if live_tests else None,
        "latest_media_live_probe": _connection_evidence_item(media_live_probes[0])
        if media_live_probes
        else None,
        "recent_tests": [_connection_evidence_item(item) for item in tests],
    }


async def _build_knowledge_acceptance_evidence(
    session: AsyncSession, principal: Any
) -> dict[str, Any]:
    try:
        result = await session.execute(
            select(AuditLog)
            .where(
                AuditLog.tenant_id == principal.tenant_id,
                AuditLog.action == "agent.run",
            )
            .order_by(cast(Any, AuditLog.created_at).desc())
            .limit(12)
        )
        events = list(result.scalars().all())
    except Exception as exc:
        return {
            "status": "unavailable",
            "summary": f"Knowledge Agent run evidence could not be loaded: {exc.__class__.__name__}.",
            "recent_run_count": 0,
            "knowledge_enabled_run_count": 0,
            "runs_with_sources_count": 0,
            "human_review_required_count": 0,
            "guardrail_triggered_count": 0,
            "agents": [],
            "recent_runs": [],
        }

    runs = [_knowledge_evidence_item(event) for event in events]
    enabled_runs = [item for item in runs if item["knowledge_enabled"] is True]
    sourced_runs = []
    for item in enabled_runs:
        source_count = _optional_int(item.get("source_count"))
        if source_count is not None and source_count > 0:
            sourced_runs.append(item)
    review_runs = [item for item in enabled_runs if item["requires_human_review"] is True]
    guardrail_runs = [item for item in enabled_runs if item["guardrail_triggered"] is True]
    agents = sorted({str(item["agent_key"]) for item in runs if item.get("agent_key")})
    status_value = (
        "healthy" if sourced_runs and not guardrail_runs else "degraded" if runs else "not_reported"
    )
    return {
        "status": status_value,
        "summary": _knowledge_acceptance_summary(
            recent_run_count=len(runs),
            knowledge_enabled_run_count=len(enabled_runs),
            runs_with_sources_count=len(sourced_runs),
            human_review_required_count=len(review_runs),
            guardrail_triggered_count=len(guardrail_runs),
        ),
        "recent_run_count": len(runs),
        "knowledge_enabled_run_count": len(enabled_runs),
        "runs_with_sources_count": len(sourced_runs),
        "human_review_required_count": len(review_runs),
        "guardrail_triggered_count": len(guardrail_runs),
        "agents": agents,
        "latest_knowledge_run": sourced_runs[0]
        if sourced_runs
        else enabled_runs[0]
        if enabled_runs
        else None,
        "recent_runs": runs,
    }


def _knowledge_acceptance_summary(
    *,
    recent_run_count: int,
    knowledge_enabled_run_count: int,
    runs_with_sources_count: int,
    human_review_required_count: int,
    guardrail_triggered_count: int,
) -> str:
    if recent_run_count == 0:
        return "No Agent run audit events have been recorded for this tenant."
    if knowledge_enabled_run_count == 0:
        return f"{recent_run_count} recent Agent run(s) are recorded, but none used knowledge retrieval."
    if guardrail_triggered_count:
        return (
            f"{knowledge_enabled_run_count} knowledge-enabled Agent run(s) are recorded; "
            f"{guardrail_triggered_count} strict knowledge guardrail trigger(s) require review."
        )
    if human_review_required_count:
        return (
            f"{knowledge_enabled_run_count} knowledge-enabled Agent run(s) are recorded; "
            f"{human_review_required_count} run(s) require human review."
        )
    return (
        f"{knowledge_enabled_run_count} knowledge-enabled Agent run(s) are recorded; "
        f"{runs_with_sources_count} run(s) returned cited knowledge sources."
    )


def _knowledge_evidence_item(event: AuditLog) -> dict[str, Any]:
    details = event.details if isinstance(event.details, dict) else {}
    knowledge = _dict_or_empty(details.get("knowledge"))
    guardrail = _dict_or_empty(knowledge.get("guardrail"))
    agent_instance = _dict_or_empty(details.get("agent_instance"))
    source_count = _optional_int(knowledge.get("source_count"))
    if source_count is None:
        source_count = _optional_int(details.get("source_count"))
    return {
        "agent_key": details.get("agent_key"),
        "agent_instance_id": agent_instance.get("agent_id"),
        "agent_instance_name": agent_instance.get("name"),
        "required_module": details.get("required_module"),
        "model_key": details.get("model_key"),
        "routing_key": details.get("routing_key"),
        "department_id": details.get("department_id"),
        "channel_id": details.get("channel_id"),
        "checked_at": event.created_at.isoformat()
        if hasattr(event.created_at, "isoformat")
        else event.created_at,
        "status": event.status,
        "knowledge_enabled": knowledge.get("enabled") is True,
        "knowledge_base_ids": knowledge.get("knowledge_base_ids")
        if isinstance(knowledge.get("knowledge_base_ids"), list)
        else [],
        "source_count": source_count,
        "confidence_level": knowledge.get("confidence_level"),
        "max_score": knowledge.get("max_score"),
        "min_score": knowledge.get("min_score"),
        "requires_human_review": knowledge.get("requires_human_review") is True,
        "review_reason": knowledge.get("review_reason"),
        "guardrail_mode": guardrail.get("mode"),
        "guardrail_triggered": guardrail.get("triggered") is True,
        "skipped_model_call": guardrail.get("skipped_model_call") is True,
    }


def _connection_acceptance_summary(
    *,
    recent_test_count: int,
    live_network_call_count: int,
    media_live_probe_count: int,
    failed_recent_count: int,
) -> str:
    if recent_test_count == 0:
        return "No model or media provider connection tests have been recorded for this tenant."
    if live_network_call_count == 0:
        return f"{recent_test_count} recent connection test(s) are recorded, but none used a live provider network call."
    if failed_recent_count:
        return (
            f"{live_network_call_count} live provider network call(s) are recorded, "
            f"including {failed_recent_count} recent failure(s) that require review."
        )
    return (
        f"{live_network_call_count} live provider network call(s) are recorded; "
        f"{media_live_probe_count} media provider live probe(s) are included."
    )


def _connection_evidence_item(item: Any) -> dict[str, Any]:
    return {
        "provider_key": item.provider_key,
        "provider_type": item.provider_type,
        "model_key": item.model_key,
        "operation": item.operation,
        "ok": item.ok,
        "status": item.status,
        "checked_at": item.checked_at.isoformat()
        if hasattr(item.checked_at, "isoformat")
        else item.checked_at,
        "latency_ms": item.latency_ms,
        "live_network_call": item.live_network_call,
        "status_code": item.status_code,
        "probe_path": item.probe_path,
        "configuration_source": item.configuration_source,
        "selected_route_reason": item.selected_route_reason,
    }


def redact_diagnostics(value: Any, *, key: str = "") -> Any:
    if SENSITIVE_KEY_PATTERN.search(key):
        return "[REDACTED]"
    if isinstance(value, str):
        return "[REDACTED]" if SENSITIVE_VALUE_PATTERN.search(value) else value
    if isinstance(value, list):
        return [redact_diagnostics(item) for item in value]
    if isinstance(value, tuple):
        return [redact_diagnostics(item) for item in value]
    if isinstance(value, dict):
        return {
            str(item_key): redact_diagnostics(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    return value


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def is_ready(report: dict[str, Any]) -> bool:
    delivery = report.get("delivery")
    if isinstance(delivery, dict):
        blocker_count = _optional_int(delivery.get("blocker_count")) or 0
        return blocker_count == 0 and delivery.get("status") != "blocked"
    return report.get("status") == "healthy"


def _build_delivery_assessment(components: dict[str, Component]) -> dict[str, Any]:
    checks = [_delivery_check(name, component) for name, component in components.items()]
    blockers = [check for check in checks if check["severity"] == "blocker"]
    warnings = [check for check in checks if check["severity"] == "warning"]
    if blockers:
        status_value = "blocked"
        summary = f"{len(blockers)} deployment blocker(s) must be fixed before customer delivery."
    elif warnings:
        status_value = "ready_with_warnings"
        summary = f"Deployment is usable, but {len(warnings)} warning(s) should be reviewed before handoff."
    else:
        status_value = "ready"
        summary = "All critical delivery checks passed."
    return {
        "status": status_value,
        "summary": summary,
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "blockers": blockers,
        "warnings": warnings,
        "checks": checks,
    }


def _delivery_check(name: str, component: Component) -> dict[str, Any]:
    status_value = str(component.get("status", "unknown"))
    severity = _delivery_severity(name, status_value)
    remediation = component.get("remediation")
    return {
        "id": name,
        "label": _delivery_label(name),
        "component": name,
        "status": status_value,
        "severity": severity,
        "message": component.get("message") or "",
        "remediation": remediation if isinstance(remediation, dict) else None,
    }


def _delivery_severity(component_name: str, status_value: str) -> str:
    if status_value == "healthy":
        return "pass"
    if component_name in DELIVERY_CRITICAL_COMPONENTS:
        return "blocker"
    if status_value in {"unhealthy", "error", "not_configured"}:
        return "blocker"
    return "warning"


def _delivery_label(component_name: str) -> str:
    labels = {
        "database": "PostgreSQL business database",
        "redis": "Redis cache and queue runtime",
        "minio": "MinIO object storage",
        "litellm": "LiteLLM model gateway adapter",
        "frontend": "AgentHive management console",
        "pgvector": "PostgreSQL pgvector retrieval store",
        "production_config": "Production secret and config gate",
        "license_identity": "License install identity",
        "media_generation": "Media generation gateway",
        "media_worker": "Media generation worker queue",
        "ragflow": "Optional RAGFlow integration",
    }
    return labels.get(component_name, component_name.replace("_", " ").title())


def _support_bundle_readme(report: dict[str, Any]) -> str:
    return support_bundle_rendering.support_bundle_readme(report)


def _support_bundle_acceptance_checklist(report: dict[str, Any]) -> str:
    return support_bundle_rendering.support_bundle_acceptance_checklist(report)


def _support_bundle_delivery_summary(report: dict[str, Any]) -> str:
    return support_bundle_rendering.support_bundle_delivery_summary(report)


def _acceptance_decision(delivery: dict[str, Any]) -> str:
    return support_bundle_rendering.acceptance_decision(delivery)


def _acceptance_evidence_line(component_id: str, label: str, components: dict[str, Any]) -> str:
    return support_bundle_rendering.acceptance_evidence_line(component_id, label, components)


def _acceptance_component_detail_lines(component: dict[str, Any]) -> list[str]:
    return support_bundle_rendering.acceptance_component_detail_lines(component)


def _connection_acceptance_lines(evidence: dict[str, Any]) -> list[str]:
    return support_bundle_rendering.connection_acceptance_lines(evidence)


def _connection_probe_detail_lines(item: dict[str, Any]) -> list[str]:
    return support_bundle_rendering.connection_probe_detail_lines(item)


def _knowledge_acceptance_lines(evidence: dict[str, Any]) -> list[str]:
    return support_bundle_rendering.knowledge_acceptance_lines(evidence)


def _knowledge_run_detail_lines(item: dict[str, Any]) -> list[str]:
    return support_bundle_rendering.knowledge_run_detail_lines(item)


def _support_bundle_issue_lines(value: Any) -> list[str]:
    return support_bundle_rendering.support_bundle_issue_lines(value)


def _markdown_cell(value: str) -> str:
    return support_bundle_rendering._markdown_cell(value)


def _safe_timestamp(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z-]+", "-", value).strip("-") or "current"


async def _check_agent_concurrency() -> Component:
    snapshot = await agent_concurrency_limiter.snapshot()
    enabled_label = "enabled" if snapshot.enabled else "disabled"
    return {
        "status": "healthy",
        "message": f"Agent concurrency guard is {enabled_label}.",
        "details": {
            "enabled": snapshot.enabled,
            "tenant_limit": snapshot.tenant_limit,
            "user_limit": snapshot.user_limit,
            "agent_limit": snapshot.agent_limit,
            "active_slot_count": len(snapshot.active),
        },
    }


async def _check_redis() -> Component:
    parsed = urlparse(settings.redis_url)
    host = parsed.hostname
    port = parsed.port or 6379
    password = unquote(parsed.password) if parsed.password else None
    if not host:
        return {"status": "not_configured", "message": "Redis URL is missing a host."}
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=2.0)
        try:
            if password:
                writer.write(_redis_command("AUTH", password))
                await writer.drain()
                auth_response = await asyncio.wait_for(reader.readline(), timeout=2.0)
                if not auth_response.startswith(b"+OK"):
                    return {
                        "status": "unhealthy",
                        "message": "Redis AUTH failed.",
                        "details": {"host": host, "port": port},
                    }
            writer.write(_redis_command("PING"))
            await writer.drain()
            response = await asyncio.wait_for(reader.readline(), timeout=2.0)
            healthy = response.startswith(b"+PONG")
            return {
                "status": "healthy" if healthy else "unhealthy",
                "message": "Redis PING succeeded." if healthy else "Redis PING failed.",
                "details": {"host": host, "port": port},
            }
        finally:
            writer.close()
            await writer.wait_closed()
    except Exception as exc:
        return {
            "status": "unhealthy",
            "message": f"Redis is not reachable: {exc.__class__.__name__}.",
            "details": {"host": host, "port": port},
        }


async def _check_minio() -> Component:
    status = await MinIOObjectStorageAdapter().health_check()
    return status.model_dump(mode="json")


async def _check_pgvector() -> Component:
    status = await PGVectorAdapter().health_check()
    return status.model_dump(mode="json")


async def _check_ragflow() -> Component:
    status = await RAGFlowAdapter().health_check()
    return status.model_dump(mode="json")


async def _check_litellm() -> Component:
    if not settings.litellm_base_url:
        return {"status": "not_configured", "message": "LiteLLM base URL is not configured."}
    url = settings.litellm_base_url.rstrip("/")
    headers = (
        {"Authorization": f"Bearer {settings.litellm_master_key}"}
        if settings.litellm_master_key
        else {}
    )
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{url}/health", headers=headers)
        healthy = 200 <= response.status_code < 300
        return {
            "status": "healthy" if healthy else "unhealthy",
            "message": f"LiteLLM health endpoint returned HTTP {response.status_code}.",
            "details": {"base_url": url, "status_code": response.status_code},
        }
    except Exception as exc:
        return {
            "status": "unhealthy",
            "message": f"LiteLLM is not reachable: {exc.__class__.__name__}.",
            "details": {"base_url": url},
        }


async def _check_frontend() -> Component:
    url = settings.frontend_health_url.strip()
    if url:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(url)
            healthy = 200 <= response.status_code < 300
            return {
                "status": "healthy" if healthy else "unhealthy",
                "message": f"Frontend health endpoint returned HTTP {response.status_code}.",
                "details": {"url": url, "status_code": response.status_code},
            }
        except Exception as exc:
            return {
                "status": "unhealthy",
                "message": f"Frontend service is not reachable: {exc.__class__.__name__}.",
                "details": {"url": url},
            }

    if is_production_environment():
        return {
            "status": "not_configured",
            "message": "Frontend health URL is not configured for production readiness.",
            "details": {"frontend_health_url_configured": False},
        }

    artifact = _find_frontend_dist_index()
    if artifact is not None:
        return {
            "status": "healthy",
            "message": "Frontend build artifact is present.",
            "details": {"artifact": str(artifact), "mode": "development_artifact_check"},
        }
    return {
        "status": "degraded",
        "message": "Frontend build artifact is missing.",
        "details": {
            "checked_paths": [str(path) for path in _frontend_dist_candidates()],
            "mode": "development_artifact_check",
        },
    }


def _should_check_frontend(*, deep: bool) -> bool:
    if not deep:
        return False
    return (
        bool(settings.frontend_health_url.strip())
        or is_production_environment()
        or _find_frontend_dist_index() is not None
    )


def _find_frontend_dist_index() -> Path | None:
    for path in _frontend_dist_candidates():
        if path.exists():
            return path
    return None


def _frontend_dist_candidates() -> list[Path]:
    return [
        Path("frontend/dist/index.html"),
        Path("../frontend/dist/index.html"),
    ]


def _check_license_identity() -> Component:
    try:
        identity = get_install_identity()
    except Exception as exc:
        return {
            "status": "unhealthy",
            "message": f"Install identity is invalid: {exc.__class__.__name__}.",
        }
    public_key_path = (
        Path(settings.license_public_key_path) if settings.license_public_key_path else None
    )
    public_key_present = bool(public_key_path and public_key_path.exists())
    public_key_error: str | None = None
    public_key_valid = False
    if public_key_path and public_key_present:
        try:
            public_key = serialization.load_pem_public_key(public_key_path.read_bytes())
            public_key_valid = isinstance(public_key, Ed25519PublicKey)
            if not public_key_valid:
                public_key_error = "public_key_is_not_ed25519"
        except Exception as exc:
            public_key_error = f"{exc.__class__.__name__}"
    if public_key_error:
        return {
            "status": "unhealthy",
            "message": "License public key is invalid.",
            "details": {
                "deployment_id": str(identity.deployment_id),
                "install_id": str(identity.install_id),
                "fingerprint_algorithm": identity.fingerprint_algorithm,
                "license_public_key_present": public_key_present,
                "license_public_key_valid": False,
                "license_public_key_error": public_key_error,
            },
        }
    return {
        "status": "healthy" if public_key_valid or is_development_environment() else "degraded",
        "message": "Install identity is present.",
        "details": {
            "deployment_id": str(identity.deployment_id),
            "install_id": str(identity.install_id),
            "fingerprint_algorithm": identity.fingerprint_algorithm,
            "license_public_key_present": public_key_present,
            "license_public_key_valid": public_key_valid,
        },
    }


def _check_production_config() -> Component:
    issues = production_config_issues(settings)
    if not issues:
        return {
            "status": "healthy",
            "message": "Production security configuration passed.",
            "details": {"environment": settings.environment},
        }
    return {
        "status": "unhealthy",
        "message": "Production security configuration is unsafe.",
        "details": {"issues": issues, "environment": settings.environment},
    }


def _check_media_generation() -> Component:
    diagnostics = media_provider_diagnostics_from_settings()
    models = list_media_model_capabilities(provider_diagnostics=diagnostics)
    active_models = [model for model in models if model.status == "active"]
    active_image_models = [
        model for model in active_models if model.kind == MediaGenerationKind.IMAGE
    ]
    active_video_models = [
        model for model in active_models if model.kind == MediaGenerationKind.VIDEO
    ]
    configured_provider_types = sorted({model.provider_type.value for model in active_models})
    webhook_public_url_configured = bool(settings.media_webhook_public_url)
    missing_by_provider = {
        provider_type.value: issues
        for provider_type, issues in diagnostics.items()
        if issues and provider_type != MediaProviderType.CUSTOM
    }
    details = {
        "catalog_model_count": len(models),
        "configured_model_count": len(active_models),
        "image_model_count": len(active_image_models),
        "video_model_count": len(active_video_models),
        "configured_provider_types": configured_provider_types,
        "webhook_public_url_configured": webhook_public_url_configured,
        "missing_by_provider": missing_by_provider,
    }
    if active_video_models and is_production_environment() and not webhook_public_url_configured:
        return {
            "status": "degraded",
            "message": "Media generation video routes are configured, but provider webhook public URL is missing.",
            "details": {
                **details,
                "missing_operational_settings": ["MEDIA_WEBHOOK_PUBLIC_URL"],
            },
        }
    if active_image_models and active_video_models:
        return {
            "status": "healthy",
            "message": "Media generation image and video routes are configured.",
            "details": details,
        }
    if active_models:
        return {
            "status": "degraded",
            "message": "Media generation is partially configured; both image and video routes are recommended.",
            "details": details,
        }
    return {
        "status": "degraded",
        "message": "Media generation providers are not configured; optional media Agents are not ready.",
        "details": details,
    }


async def _check_media_worker() -> Component:
    try:
        pings = await asyncio.wait_for(asyncio.to_thread(_celery_worker_pings), timeout=3.0)
    except Exception as exc:
        return {
            "status": "degraded",
            "message": f"Media generation Worker did not respond: {exc.__class__.__name__}.",
            "details": {
                "worker_ping_ok": False,
                "broker_url_configured": bool(settings.redis_url),
            },
        }
    workers = _normalize_celery_pings(pings)
    if workers:
        return {
            "status": "healthy",
            "message": f"Media generation Worker responded from {len(workers)} worker(s).",
            "details": {
                "worker_ping_ok": True,
                "worker_count": len(workers),
                "workers": workers,
                "broker": "redis",
            },
        }
    return {
        "status": "degraded",
        "message": "No media generation Worker responded to Celery ping.",
        "details": {
            "worker_ping_ok": False,
            "worker_count": 0,
            "broker": "redis",
        },
    }


def _celery_worker_pings() -> list[dict[str, Any]] | None:
    inspect = celery_app.control.inspect(timeout=1.0)
    value = inspect.ping()
    return cast(list[dict[str, Any]] | None, value)


def _normalize_celery_pings(value: Any) -> list[str]:
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return []
    workers: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        for worker_name, response in item.items():
            if isinstance(response, dict) and response.get("ok") == "pong":
                workers.append(str(worker_name))
    return sorted(workers)


def _configured(message: str) -> Component:
    return {"status": "configured", "message": message}


def _with_remediation(component_name: str, component: Component) -> Component:
    remediation = COMPONENT_REMEDIATIONS.get(component_name)
    status_value = str(component.get("status"))
    if not remediation or status_value not in REMEDIATION_STATUS_VALUES:
        return component
    return {**component, "remediation": remediation}


def _overall_status(components: dict[str, Component]) -> str:
    statuses = {str(component.get("status")) for component in components.values()}
    if "unhealthy" in statuses or "error" in statuses:
        return "unhealthy"
    if "degraded" in statuses or "not_configured" in statuses:
        return "degraded"
    return "healthy"


def _redis_command(*parts: str) -> bytes:
    encoded = [part.encode("utf-8") for part in parts]
    command = [f"*{len(encoded)}\r\n".encode("ascii")]
    for part in encoded:
        command.append(f"${len(part)}\r\n".encode("ascii"))
        command.append(part)
        command.append(b"\r\n")
    return b"".join(command)


async def _check_database(*, deep: bool) -> Component:
    database: Component = dict(await check_database_health())
    if database.get("status") != "healthy":
        return {
            **database,
            "message": database.get("message") or "PostgreSQL is not reachable.",
            "details": database.get("details", {}),
        }
    if deep and database.get("status") == "healthy":
        migration_status = await get_migration_status()
        media_runtime_indexes = await _check_media_runtime_indexes()
        database_ready = migration_status.is_current and bool(media_runtime_indexes.get("ready"))
        database = {
            **database,
            "migrations": migration_status.as_dict(),
            "media_runtime_indexes": media_runtime_indexes,
            "status": "healthy" if database_ready else "degraded",
            "message": _database_readiness_message(
                migrations_current=migration_status.is_current,
                media_indexes_ready=bool(media_runtime_indexes.get("ready")),
            ),
        }
    return database


async def _check_media_runtime_indexes() -> dict[str, Any]:
    expected_indexes = expected_media_runtime_indexes()
    async with engine.connect() as connection:
        result = await connection.execute(
            text(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'media_generation_jobs'
                """
            )
        )
        index_names = set(result.scalars().all())
    missing_indexes = missing_media_runtime_indexes(index_names, expected_indexes)
    return {
        "ready": not missing_indexes,
        "present_count": len(expected_indexes) - len(missing_indexes),
        "expected_count": len(expected_indexes),
        "missing": missing_indexes,
    }


def _database_readiness_message(*, migrations_current: bool, media_indexes_ready: bool) -> str:
    if migrations_current and media_indexes_ready:
        return "Database is reachable and migrations are current."
    if not migrations_current:
        return "Database is reachable, but migrations are not at head."
    return "Database is reachable, but media generation runtime indexes are missing."
