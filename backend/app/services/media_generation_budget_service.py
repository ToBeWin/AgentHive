from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal
from app.llm.budget import BudgetGuard
from app.llm.cost_center import resolve_cost_center
from app.llm.schemas import BudgetReservation, LLMRequestContext, LLMUsageMetrics
from app.models.llm import LLMUsage
from app.models.media import MediaGenerationJob


def media_generation_usage(cost_usd: Decimal) -> LLMUsageMetrics:
    return LLMUsageMetrics(total_tokens=0, cost_usd=cost_usd.quantize(Decimal("0.000001")))


async def reserve_media_generation_budget(
    session: AsyncSession,
    principal: Principal,
    *,
    kind: str,
    model_key: str,
    routing_key: str,
    estimated_cost_usd: Decimal,
    request_id: str | None,
    department_id: UUID | None = None,
    agent_id: UUID | None = None,
    conversation_id: UUID | None = None,
) -> BudgetReservation:
    context = _context(
        principal,
        kind=kind,
        request_id=request_id,
        department_id=department_id,
        agent_id=agent_id,
        conversation_id=conversation_id,
    )
    reservation = await BudgetGuard(session=session).reserve_usage(
        media_generation_usage(estimated_cost_usd),
        context,
        metadata={
            "model_family": "media_generation",
            "media_kind": kind,
            "model_key": model_key,
            "routing_key": routing_key,
        },
    )
    if not reservation.approved:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Media generation budget denied request: {reservation.reason}",
        )
    return reservation


async def settle_media_generation_budget(
    session: AsyncSession,
    principal: Principal,
    job: MediaGenerationJob,
    *,
    request_id: str | None,
) -> None:
    reservation = _job_reservation(job)
    if reservation is None:
        return
    usage = media_generation_usage(_job_estimated_cost(job))
    context = _job_context(principal, job, request_id=request_id)
    await BudgetGuard(session=session).settle(reservation, usage, context)
    await _record_media_usage(
        session,
        context=context,
        job=job,
        usage=usage,
        status="success",
    )


async def release_media_generation_budget(
    session: AsyncSession,
    principal: Principal,
    job: MediaGenerationJob,
    *,
    request_id: str | None,
    reason: str,
) -> None:
    reservation = _job_reservation(job)
    if reservation is None:
        return
    await BudgetGuard(session=session).release(
        reservation,
        _job_context(principal, job, request_id=request_id),
        reason,
    )


def reservation_metadata(
    reservation: BudgetReservation, *, estimated_cost_usd: Decimal
) -> dict[str, object]:
    return {
        "approved": reservation.approved,
        "reservation_id": reservation.reservation_id,
        "reason": reservation.reason,
        "estimated_cost_usd": str(estimated_cost_usd.quantize(Decimal("0.000001"))),
        "budget_scopes": [scope.model_dump(mode="json") for scope in reservation.budget_scopes],
    }


def media_generation_estimated_cost_from_job(job: MediaGenerationJob) -> Decimal:
    return _job_estimated_cost(job)


def _job_reservation(job: MediaGenerationJob) -> BudgetReservation | None:
    metadata = dict(job.metadata_json)
    raw_reservation = metadata.get("budget_reservation")
    if not isinstance(raw_reservation, dict):
        return None
    return BudgetReservation(
        approved=bool(raw_reservation.get("approved", True)),
        reservation_id=str(raw_reservation.get("reservation_id")),
        reason=str(raw_reservation.get("reason", "budget_approved")),
        estimated_tokens=0,
        estimated_cost_usd=Decimal(str(raw_reservation.get("estimated_cost_usd", "0"))),
        budget_scopes=list(raw_reservation.get("budget_scopes") or []),
    )


def _job_estimated_cost(job: MediaGenerationJob) -> Decimal:
    raw_reservation = dict(job.metadata_json).get("budget_reservation")
    if isinstance(raw_reservation, dict):
        return Decimal(str(raw_reservation.get("estimated_cost_usd", "0")))
    return Decimal("0")


def _context(
    principal: Principal,
    *,
    kind: str,
    request_id: str | None,
    department_id: UUID | None,
    agent_id: UUID | None,
    conversation_id: UUID | None,
) -> LLMRequestContext:
    return LLMRequestContext(
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        department_id=department_id,
        agent_id=agent_id,
        conversation_id=conversation_id,
        request_id=request_id or "media-generation",
        source=f"media_generation.{kind}",
    )


def _job_context(
    principal: Principal,
    job: MediaGenerationJob,
    *,
    request_id: str | None,
) -> LLMRequestContext:
    return _context(
        principal,
        kind=job.kind,
        request_id=request_id or job.request_id or job.id.hex,
        department_id=job.department_id,
        agent_id=job.agent_id,
        conversation_id=job.conversation_id,
    )


async def _record_media_usage(
    session: AsyncSession,
    *,
    context: LLMRequestContext,
    job: MediaGenerationJob,
    usage: LLMUsageMetrics,
    status: str,
) -> None:
    cost_center_id, cost_center_source = await resolve_cost_center(session, context)
    session.add(
        LLMUsage(
            tenant_id=context.tenant_id,
            deployment_id=None,
            user_id=context.user_id,
            department_id=context.department_id,
            cost_center_id=cost_center_id,
            agent_id=context.agent_id,
            channel_id=context.channel_id,
            conversation_id=context.conversation_id,
            request_id=context.request_id,
            model_key=job.model_key,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            cost_usd=usage.cost_usd,
            status=status,
            metadata_json=_media_usage_metadata(
                context=context,
                job=job,
                usage=usage,
                status=status,
                cost_center_source=cost_center_source,
            ),
        )
    )
    await session.commit()


def _media_usage_metadata(
    *,
    context: LLMRequestContext,
    job: MediaGenerationJob,
    usage: LLMUsageMetrics,
    status: str,
    cost_center_source: str,
) -> dict[str, Any]:
    normalized_parameters = _normalized_parameter_snapshot(job)
    return {
        "provider_key": job.provider_key,
        "provider_type": job.provider_type,
        "source": context.source,
        "media_generation_job_id": str(job.id),
        "media_kind": job.kind,
        "routing_key": job.routing_key,
        "status": status,
        "usage_family": "media_generation",
        "estimated_cost_usd": str(usage.cost_usd),
        "cost_center_source": cost_center_source,
        "output_storage": _output_storage_snapshot(job),
        "output_count": len(job.outputs),
        "reference_asset_count": _reference_asset_count(job),
        "normalized_parameters": normalized_parameters,
        **_scalar_parameter_summary(normalized_parameters),
    }


def _normalized_parameter_snapshot(job: MediaGenerationJob) -> dict[str, Any]:
    parameters = dict(job.normalized_parameters or {})
    if "reference_assets" in parameters and isinstance(parameters["reference_assets"], dict):
        parameters["reference_assets"] = {
            key: value
            for key, value in dict(parameters["reference_assets"]).items()
            if key in {"count", "by_kind", "locations", "material_breakdown", "policy"}
        }
    if "command_interpretation" in parameters and isinstance(
        parameters["command_interpretation"], dict
    ):
        parameters["command_interpretation"] = {
            key: value
            for key, value in dict(parameters["command_interpretation"]).items()
            if key in {"inferred_fields", "confidence", "language"}
        }
    return parameters


def _scalar_parameter_summary(parameters: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key in ("image_count", "duration_seconds", "fps", "resolution", "aspect_ratio", "seed"):
        value = parameters.get(key)
        if value is not None:
            summary[key] = value
    return summary


def _reference_asset_count(job: MediaGenerationJob) -> int:
    reference_assets = job.reference_assets or []
    if reference_assets:
        return len(reference_assets)
    normalized_reference_assets = dict(job.normalized_parameters or {}).get("reference_assets")
    if isinstance(normalized_reference_assets, dict):
        raw_count = normalized_reference_assets.get("count")
        if raw_count is not None:
            try:
                return int(raw_count)
            except (TypeError, ValueError):
                return 0
    return 0


def _output_storage_snapshot(job: MediaGenerationJob) -> dict[str, Any]:
    output_storage = dict(job.output_storage or {})
    return {
        key: value
        for key, value in output_storage.items()
        if key in {"driver", "bucket", "bucket_scope", "tenant_id", "prefix", "region"}
    }
