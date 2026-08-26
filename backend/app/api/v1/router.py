from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_permission
from app.core.config import settings
from app.core.database import get_session
from app.api.v1 import (
    agents,
    agent_modules,
    agent_assignments,
    analytics,
    audit,
    auth,
    budgets,
    builder,
    chat,
    channels,
    knowledge,
    license,
    media,
    mcp,
    models,
    orgs,
    roles,
    users,
)
from app.core.security import Permission
from app.observability.metrics import metrics_collector
from app.services.health_service import (
    build_diagnostics_report,
    build_health_report,
    build_readiness_report,
    build_support_bundle,
    build_system_info,
    is_ready,
    record_diagnostics_export_audit,
    record_support_bundle_export_audit,
)

router = APIRouter()


@router.get("/health", tags=["system"])
async def health() -> dict[str, object]:
    return await build_health_report(deep=False)


@router.get("/health/readiness", tags=["system"])
async def readiness(response: Response) -> dict[str, object]:
    report = await build_readiness_report()
    if not is_ready(report):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return report


@router.get("/system/info", tags=["system"])
async def system_info() -> dict[str, str]:
    return build_system_info()


@router.get("/metrics", tags=["system"])
async def metrics(response: Response) -> Response:
    if not settings.metrics_enabled:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response
    body = metrics_collector.render_prometheus()
    return Response(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")


@router.get("/llm/circuit-breaker", tags=["llm"])
async def list_circuit_breakers(
    principal: Annotated[Principal, Depends(require_permission(Permission.MODELS_READ))],
) -> dict[str, object]:
    """List the circuit-breaker state of all tracked LLM deployments."""
    from app.llm.circuit_breaker import circuit_breaker

    snapshots = circuit_breaker.snapshot_all()
    return {
        "enabled": settings.llm_circuit_breaker_enabled,
        "failure_threshold": settings.llm_circuit_breaker_failure_threshold,
        "cooldown_seconds": settings.llm_circuit_breaker_cooldown_seconds,
        "success_threshold": settings.llm_circuit_breaker_success_threshold,
        "circuits": [
            {
                "deployment_id": snap.deployment_id,
                "state": snap.state.value,
                "consecutive_failures": snap.consecutive_failures,
                "consecutive_successes": snap.consecutive_successes,
                "opened_at": snap.opened_at,
                "last_failure_at": snap.last_failure_at,
                "last_failure_code": snap.last_failure_code,
                "total_opened": snap.total_opened,
                "seconds_until_half_open": snap.seconds_until_half_open,
            }
            for snap in snapshots
        ],
    }


@router.post("/llm/circuit-breaker/{deployment_id}/reset", tags=["llm"])
async def reset_circuit_breaker(
    deployment_id: str,
    principal: Annotated[Principal, Depends(require_permission(Permission.MODELS_WRITE))],
) -> dict[str, str]:
    """Force-reset a single deployment's circuit to CLOSED (operator escape hatch)."""
    from app.llm.circuit_breaker import circuit_breaker

    circuit_breaker.reset(deployment_id)
    return {"status": "reset", "deployment_id": deployment_id}


@router.get("/system/diagnostics", tags=["system"])
async def system_diagnostics(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.SYSTEM_DIAGNOSTICS))],
) -> dict[str, object]:
    report = await build_diagnostics_report(session=session, principal=principal)
    await record_diagnostics_export_audit(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        report=report,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return report


@router.get("/system/support-bundle", tags=["system"])
async def system_support_bundle(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.SYSTEM_DIAGNOSTICS))],
) -> Response:
    bundle, filename = await build_support_bundle(session=session, principal=principal)
    await record_support_bundle_export_audit(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        filename=filename,
        bundle_size_bytes=len(bundle),
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return Response(
        content=bundle,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


api_router = router
api_router.include_router(auth.router)
api_router.include_router(license.router)
api_router.include_router(agents.router)
api_router.include_router(builder.router)
api_router.include_router(agent_modules.router)
api_router.include_router(agent_assignments.router)
api_router.include_router(analytics.router)
api_router.include_router(audit.router)
api_router.include_router(audit.export_router)
api_router.include_router(models.router)
api_router.include_router(media.router)
api_router.include_router(chat.router)
api_router.include_router(knowledge.router)
api_router.include_router(budgets.router)
api_router.include_router(channels.router)
api_router.include_router(orgs.router)
api_router.include_router(users.router)
api_router.include_router(roles.router)
api_router.include_router(mcp.router)
