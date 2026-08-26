from typing import Any, cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.deps import Principal, is_tenant_admin
from app.media.gateway import build_media_generation_plan
from app.media.schemas import (
    MediaGenerationJobEvent,
    MediaGenerationJobEventsResponse,
    MediaGenerationJobCreateRequest,
    MediaGenerationJobListResponse,
    MediaGenerationJobResponse,
    MediaGenerationJobStatus,
    MediaGenerationJobStatusUpdate,
    MediaGenerationKind,
    MediaGenerationMode,
    MediaGenerationPlan,
    MediaProviderType,
)
from app.models.audit_log import AuditLog
from app.models.base import utc_now
from app.models.media import MediaGenerationJob
from app.models.org import Department
from app.models.user import UserDepartment
from app.services.audit_service import record_audit_event
from app.services.audit_redaction import redact_audit_details
from app.services.media_generation_budget_service import (
    media_generation_estimated_cost_from_job,
    release_media_generation_budget,
    reservation_metadata,
    reserve_media_generation_budget,
    settle_media_generation_budget,
)
from app.services.media_generation_license_service import ensure_media_generation_module_runnable
from app.services.media_generation_policy_service import enforce_media_generation_model_policy
from app.services.media_output_archive_service import (
    MediaOutputArchiveError,
    validate_media_output_storage_references,
)
from app.services.media_provider_config_service import (
    ensure_media_provider_configured,
    media_provider_diagnostics,
)


TERMINAL_MEDIA_JOB_STATUSES = {
    MediaGenerationJobStatus.SUCCEEDED.value,
    MediaGenerationJobStatus.FAILED.value,
    MediaGenerationJobStatus.CANCELED.value,
}

RETRYABLE_MEDIA_JOB_STATUSES = {
    MediaGenerationJobStatus.FAILED.value,
    MediaGenerationJobStatus.CANCELED.value,
}

CANCELABLE_MEDIA_JOB_STATUSES = {
    MediaGenerationJobStatus.QUEUED.value,
    MediaGenerationJobStatus.RUNNING.value,
}

ALLOWED_MEDIA_JOB_TRANSITIONS = {
    MediaGenerationJobStatus.QUEUED.value: {
        MediaGenerationJobStatus.RUNNING.value,
        MediaGenerationJobStatus.FAILED.value,
        MediaGenerationJobStatus.CANCELED.value,
    },
    MediaGenerationJobStatus.RUNNING.value: {
        MediaGenerationJobStatus.SUCCEEDED.value,
        MediaGenerationJobStatus.FAILED.value,
        MediaGenerationJobStatus.CANCELED.value,
    },
    MediaGenerationJobStatus.SUCCEEDED.value: set(),
    MediaGenerationJobStatus.FAILED.value: set(),
    MediaGenerationJobStatus.CANCELED.value: set(),
}


async def create_media_generation_job(
    session: AsyncSession,
    principal: Principal,
    payload: MediaGenerationJobCreateRequest,
    *,
    request_id: str | None = None,
) -> MediaGenerationJobResponse:
    await ensure_media_generation_module_runnable(session, principal, payload.kind)
    agent_key = (
        "video_generation" if payload.kind == MediaGenerationKind.VIDEO else "image_generation"
    )
    diagnostics = await media_provider_diagnostics(session, principal)
    provider_statuses = {provider_type: not issues for provider_type, issues in diagnostics.items()}
    plan = build_media_generation_plan(
        payload,
        principal,
        agent_key=agent_key,
        provider_statuses=provider_statuses,
    )
    await ensure_media_provider_configured(
        session,
        principal,
        plan.provider_type,
        department_id=payload.department_id,
        user_id=principal.user_id,
    )
    await enforce_media_generation_model_policy(
        session,
        principal,
        plan,
        request_id=request_id,
        department_id=payload.department_id,
        agent_id=payload.agent_id,
        conversation_id=payload.conversation_id,
    )
    now = utc_now()
    job = MediaGenerationJob(
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        department_id=payload.department_id,
        agent_id=payload.agent_id,
        conversation_id=payload.conversation_id,
        request_id=request_id,
        kind=payload.kind.value,
        mode=payload.mode.value,
        status=MediaGenerationJobStatus.QUEUED.value,
        provider_key=plan.provider_key,
        provider_type=plan.provider_type.value,
        model_key=plan.model_key,
        routing_key=plan.routing_key,
        prompt=plan.prompt,
        negative_prompt=payload.negative_prompt,
        reference_assets=[asset.model_dump(mode="json") for asset in payload.reference_assets],
        request_parameters=_request_parameters(payload),
        normalized_parameters=dict(plan.normalized_parameters),
        output_storage=dict(plan.output_storage),
        metadata_json={
            **payload.metadata,
            "execution": plan.execution,
            "estimated_output_count": plan.estimated_output_count,
            "reference_asset_count": plan.reference_asset_count,
        },
        created_at=now,
        updated_at=now,
    )
    reservation = await reserve_media_generation_budget(
        session,
        principal,
        kind=job.kind,
        model_key=job.model_key,
        routing_key=job.routing_key,
        estimated_cost_usd=plan.estimated_cost_usd,
        request_id=request_id or job.id.hex,
        department_id=job.department_id,
        agent_id=job.agent_id,
        conversation_id=job.conversation_id,
    )
    job.metadata_json = {
        **dict(job.metadata_json),
        "estimated_cost_usd": str(plan.estimated_cost_usd),
        "pricing": dict(plan.pricing),
        "budget_reservation": reservation_metadata(
            reservation,
            estimated_cost_usd=plan.estimated_cost_usd,
        ),
    }
    session.add(job)
    await session.flush()
    await record_audit_event(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        request_id=request_id,
        action="media.generation.create",
        resource_type="media_generation_job",
        resource_id=job.id,
        details={
            "kind": job.kind,
            "mode": job.mode,
            "status": job.status,
            "model_key": job.model_key,
            "routing_key": job.routing_key,
            "estimated_cost_usd": str(plan.estimated_cost_usd),
            "external_call": False,
        },
    )
    await session.commit()
    await session.refresh(job)
    return _job_response(job)


async def list_media_generation_jobs(
    session: AsyncSession,
    principal: Principal,
    *,
    kind: MediaGenerationKind | None = None,
    status_filter: MediaGenerationJobStatus | None = None,
    limit: int = 50,
) -> MediaGenerationJobListResponse:
    statement = select(MediaGenerationJob).where(
        cast(ColumnElement[bool], MediaGenerationJob.tenant_id == principal.tenant_id)
    )
    access_filters = await _media_generation_job_access_filters(session, principal)
    if access_filters:
        statement = statement.where(or_(*access_filters))
    if kind is not None:
        statement = statement.where(
            cast(ColumnElement[bool], MediaGenerationJob.kind == kind.value)
        )
    if status_filter is not None:
        statement = statement.where(
            cast(ColumnElement[bool], MediaGenerationJob.status == status_filter.value)
        )
    statement = statement.order_by(cast(Any, MediaGenerationJob.created_at).desc()).limit(limit)
    try:
        result = await session.execute(statement)
    except (OSError, SQLAlchemyError):
        await session.rollback()
        return MediaGenerationJobListResponse(jobs=[], total=0)
    rows = list(result.scalars().all())
    return MediaGenerationJobListResponse(
        jobs=[_job_response(row) for row in rows],
        total=len(rows),
    )


async def get_media_generation_job(
    session: AsyncSession,
    principal: Principal,
    job_id: UUID,
) -> MediaGenerationJobResponse:
    return _job_response(await _get_job(session, principal, job_id))


async def list_media_generation_job_events(
    session: AsyncSession,
    principal: Principal,
    job_id: UUID,
    *,
    limit: int = 50,
) -> MediaGenerationJobEventsResponse:
    await _get_job(session, principal, job_id)
    statement = (
        select(AuditLog)
        .where(
            cast(ColumnElement[bool], AuditLog.tenant_id == principal.tenant_id),
            cast(ColumnElement[bool], AuditLog.resource_type == "media_generation_job"),
            cast(ColumnElement[bool], AuditLog.resource_id == job_id),
        )
        .order_by(cast(Any, AuditLog.created_at).asc())
        .limit(limit)
    )
    try:
        result = await session.execute(statement)
    except (OSError, SQLAlchemyError):
        await session.rollback()
        return MediaGenerationJobEventsResponse(job_id=job_id, events=[], total=0)
    events = [_event_response(row) for row in result.scalars().all()]
    return MediaGenerationJobEventsResponse(job_id=job_id, events=events, total=len(events))


async def retry_media_generation_job(
    session: AsyncSession,
    principal: Principal,
    job_id: UUID,
    *,
    request_id: str | None = None,
) -> MediaGenerationJobResponse:
    job = await _get_job(session, principal, job_id)
    await ensure_media_generation_module_runnable(session, principal, job.kind)
    await ensure_media_provider_configured(
        session,
        principal,
        job.provider_type,
        department_id=job.department_id,
        user_id=job.user_id,
    )
    await enforce_media_generation_model_policy(
        session,
        principal,
        _plan_from_job(job),
        request_id=request_id,
        department_id=job.department_id,
        agent_id=job.agent_id,
        conversation_id=job.conversation_id,
    )
    if job.status not in RETRYABLE_MEDIA_JOB_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot retry media generation job in {job.status} status.",
        )
    now = utc_now()
    previous_status = job.status
    estimated_cost = media_generation_estimated_cost_from_job(job)
    reservation = await reserve_media_generation_budget(
        session,
        principal,
        kind=job.kind,
        model_key=job.model_key,
        routing_key=job.routing_key,
        estimated_cost_usd=estimated_cost,
        request_id=request_id or job.id.hex,
        department_id=job.department_id,
        agent_id=job.agent_id,
        conversation_id=job.conversation_id,
    )
    metadata = dict(job.metadata_json)
    previous_queue = metadata.pop("queue", None)
    previous_budget = metadata.get("budget_reservation")
    retry_count = int(metadata.get("retry_count") or 0) + 1
    metadata.update(
        {
            "budget_reservation": reservation_metadata(
                reservation,
                estimated_cost_usd=estimated_cost,
            ),
            "retry_count": retry_count,
            "last_retry": {
                "at": now.isoformat(),
                "actor_id": str(principal.user_id),
                "request_id": request_id,
                "previous_status": previous_status,
            },
        }
    )
    if previous_queue is not None:
        metadata["previous_queue"] = previous_queue
    if previous_budget is not None:
        metadata["previous_budget_reservation"] = previous_budget
    job.status = MediaGenerationJobStatus.QUEUED.value
    job.outputs = []
    job.external_job_id = None
    job.error_message = None
    job.started_at = None
    job.completed_at = None
    job.metadata_json = metadata
    job.updated_at = now
    await record_audit_event(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        request_id=request_id,
        action="media.generation.retry",
        resource_type="media_generation_job",
        resource_id=job.id,
        details={
            "previous_status": previous_status,
            "next_status": job.status,
            "retry_count": retry_count,
            "model_key": job.model_key,
            "routing_key": job.routing_key,
        },
    )
    await session.commit()
    await session.refresh(job)
    return _job_response(job)


async def cancel_media_generation_job(
    session: AsyncSession,
    principal: Principal,
    job_id: UUID,
    *,
    request_id: str | None = None,
) -> MediaGenerationJobResponse:
    job = await _get_job(session, principal, job_id)
    if job.status not in CANCELABLE_MEDIA_JOB_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel media generation job in {job.status} status.",
        )
    now = utc_now()
    previous_status = job.status
    job.status = MediaGenerationJobStatus.CANCELED.value
    job.completed_at = now
    job.updated_at = now
    job.metadata_json = {
        **dict(job.metadata_json),
        "last_cancel": {
            "at": now.isoformat(),
            "actor_id": str(principal.user_id),
            "request_id": request_id,
            "previous_status": previous_status,
            "provider_cancel": "not_configured",
        },
    }
    await release_media_generation_budget(
        session,
        principal,
        job,
        request_id=request_id,
        reason="media_generation_canceled",
    )
    await record_audit_event(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        request_id=request_id,
        action="media.generation.cancel",
        resource_type="media_generation_job",
        resource_id=job.id,
        details={
            "previous_status": previous_status,
            "next_status": job.status,
            "external_job_id": job.external_job_id,
            "model_key": job.model_key,
            "routing_key": job.routing_key,
            "budget_release_reason": "media_generation_canceled",
            "budget_reservation": _budget_reservation_audit_summary(job),
        },
    )
    await session.commit()
    await session.refresh(job)
    return _job_response(job)


async def update_media_generation_job_status(
    session: AsyncSession,
    principal: Principal,
    job_id: UUID,
    payload: MediaGenerationJobStatusUpdate,
    *,
    request_id: str | None = None,
) -> MediaGenerationJobResponse:
    job = await _get_job(session, principal, job_id)
    next_status = payload.status.value
    _ensure_status_transition(job.status, next_status)
    validated_outputs: list[dict[str, object]] | None = None
    if payload.outputs is not None:
        try:
            validated_outputs = validate_media_output_storage_references(job, list(payload.outputs))
        except MediaOutputArchiveError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc
    now = utc_now()
    previous_status = job.status
    if previous_status != next_status:
        job.status = next_status
        job.updated_at = now
        if next_status == MediaGenerationJobStatus.RUNNING.value and job.started_at is None:
            job.started_at = now
        if next_status in TERMINAL_MEDIA_JOB_STATUSES and job.completed_at is None:
            job.completed_at = now
    if validated_outputs is not None:
        job.outputs = validated_outputs
    if payload.external_job_id is not None:
        job.external_job_id = payload.external_job_id
    if payload.error_message is not None:
        job.error_message = payload.error_message
    if payload.metadata:
        job.metadata_json = {**job.metadata_json, **payload.metadata}
    budget_event = None
    budget_release_reason = None
    if (
        previous_status not in TERMINAL_MEDIA_JOB_STATUSES
        and next_status in TERMINAL_MEDIA_JOB_STATUSES
    ):
        if next_status == MediaGenerationJobStatus.SUCCEEDED.value:
            await settle_media_generation_budget(
                session,
                principal,
                job,
                request_id=request_id,
            )
            budget_event = "settled"
        else:
            budget_release_reason = f"media_generation_{next_status}"
            await release_media_generation_budget(
                session,
                principal,
                job,
                request_id=request_id,
                reason=budget_release_reason,
            )
            budget_event = "released"
    audit_details = {
        "previous_status": previous_status,
        "next_status": job.status,
        "provider_key": job.provider_key,
        "provider_type": job.provider_type,
        "model_key": job.model_key,
        "routing_key": job.routing_key,
        "external_job_id": job.external_job_id,
        "output_summary": _media_outputs_audit_summary(job),
        **_media_output_archive_audit_details(job),
    }
    budget_reservation = _budget_reservation_audit_summary(job)
    if budget_event:
        audit_details["budget_event"] = budget_event
    if budget_release_reason:
        audit_details["budget_release_reason"] = budget_release_reason
    if budget_reservation:
        audit_details["budget_reservation"] = budget_reservation
    await record_audit_event(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        request_id=request_id,
        action="media.generation.status_update",
        resource_type="media_generation_job",
        resource_id=job.id,
        details=audit_details,
    )
    await session.commit()
    await session.refresh(job)
    return _job_response(job)


async def _get_job(session: AsyncSession, principal: Principal, job_id: UUID) -> MediaGenerationJob:
    job = await session.get(MediaGenerationJob, job_id)
    if job is None or job.tenant_id != principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Media generation job not found."
        )
    await _assert_media_generation_job_access(session, principal, job)
    return job


async def _assert_media_generation_job_access(
    session: AsyncSession,
    principal: Principal,
    job: MediaGenerationJob,
) -> None:
    if job.tenant_id != principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Media generation job not found."
        )
    if is_tenant_admin(principal) or job.user_id == principal.user_id:
        return
    department_ids = await _principal_department_ids(session, principal)
    if _can_access_media_generation_job(job, principal, department_ids):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Media generation job access denied.",
    )


async def _principal_department_ids(session: AsyncSession, principal: Principal) -> set[UUID]:
    if is_tenant_admin(principal):
        return set()
    result = await session.execute(
        select(UserDepartment.department_id)
        .join(Department, cast(ColumnElement[bool], Department.id == UserDepartment.department_id))
        .where(
            cast(ColumnElement[bool], UserDepartment.user_id == principal.user_id),
            cast(ColumnElement[bool], Department.tenant_id == principal.tenant_id),
        )
    )
    return set(result.scalars().all())


async def _media_generation_job_access_filters(
    session: AsyncSession, principal: Principal
) -> list[ColumnElement[bool]]:
    if is_tenant_admin(principal):
        return []
    filters: list[ColumnElement[bool]] = [
        cast(ColumnElement[bool], MediaGenerationJob.user_id == principal.user_id)
    ]
    department_ids = await _principal_department_ids(session, principal)
    if department_ids:
        filters.append(cast(Any, MediaGenerationJob.department_id).in_(department_ids))
    return filters


def _can_access_media_generation_job(
    job: MediaGenerationJob,
    principal: Principal,
    department_ids: set[UUID],
) -> bool:
    if job.tenant_id != principal.tenant_id:
        return False
    if is_tenant_admin(principal):
        return True
    if job.user_id == principal.user_id:
        return True
    return job.department_id is not None and job.department_id in department_ids


def _budget_reservation_audit_summary(job: MediaGenerationJob) -> dict[str, object] | None:
    raw_reservation = dict(job.metadata_json or {}).get("budget_reservation")
    if not isinstance(raw_reservation, dict):
        return None
    return {
        key: raw_reservation.get(key)
        for key in ("approved", "reservation_id", "reason", "estimated_cost_usd")
        if key in raw_reservation
    }


def _media_outputs_audit_summary(job: MediaGenerationJob) -> dict[str, object]:
    outputs = [output for output in list(job.outputs or []) if isinstance(output, dict)]
    downloadable_outputs = [
        output for output in outputs if output.get("bucket") and output.get("object_key")
    ]
    total_size_bytes = 0
    buckets: set[str] = set()
    mime_types: set[str] = set()
    archive_sources: set[str] = set()
    for output in outputs:
        bucket = output.get("bucket")
        if isinstance(bucket, str) and bucket:
            buckets.add(bucket)
        mime_type = output.get("mime_type")
        if isinstance(mime_type, str) and mime_type:
            mime_types.add(mime_type)
        archive_source = output.get("archive_source")
        if isinstance(archive_source, str) and archive_source:
            archive_sources.add(archive_source)
        size_bytes = output.get("size_bytes")
        if isinstance(size_bytes, int) and size_bytes > 0:
            total_size_bytes += size_bytes
    return {
        "output_count": len(outputs),
        "downloadable_output_count": len(downloadable_outputs),
        "archived_output_count": sum(1 for output in outputs if output.get("archived") is True),
        "bucket_count": len(buckets),
        "buckets": sorted(buckets),
        "mime_types": sorted(mime_types),
        "archive_sources": sorted(archive_sources),
        "total_size_bytes": total_size_bytes,
        "output_storage_driver": dict(job.output_storage or {}).get("driver"),
    }


def _media_output_archive_audit_details(job: MediaGenerationJob) -> dict[str, object]:
    raw_archive = dict(job.metadata_json or {}).get("output_archive")
    if not isinstance(raw_archive, dict):
        return {}
    return {
        "output_archive": {
            key: raw_archive.get(key)
            for key in ("archived_count", "skipped_count", "bucket")
            if key in raw_archive
        }
    }


def _ensure_status_transition(previous_status: str, next_status: str) -> None:
    if previous_status == next_status:
        return
    allowed = ALLOWED_MEDIA_JOB_TRANSITIONS.get(previous_status, set())
    if next_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot move media generation job from {previous_status} to {next_status}.",
        )


def _request_parameters(payload: MediaGenerationJobCreateRequest) -> dict[str, object]:
    return {
        "model_key": payload.model_key,
        "routing_key": payload.routing_key,
        "image_count": payload.image_count,
        "aspect_ratio": payload.aspect_ratio,
        "resolution": payload.resolution,
        "duration_seconds": payload.duration_seconds,
        "fps": payload.fps,
        "seed": payload.seed,
    }


def _plan_from_job(job: MediaGenerationJob) -> MediaGenerationPlan:
    return MediaGenerationPlan(
        kind=MediaGenerationKind(job.kind),
        provider_key=job.provider_key,
        provider_type=MediaProviderType(job.provider_type),
        model_key=job.model_key,
        routing_key=job.routing_key,
        mode=MediaGenerationMode(job.mode),
        prompt=job.prompt,
        estimated_output_count=int(job.metadata_json.get("estimated_output_count") or 1),
        estimated_cost_usd=media_generation_estimated_cost_from_job(job),
        pricing=dict(job.metadata_json.get("pricing") or {}),
        normalized_parameters=dict(job.normalized_parameters),
        reference_asset_count=len(job.reference_assets),
        output_storage=dict(job.output_storage),
        execution=dict(job.metadata_json.get("execution") or {}),
    )


def _job_response(job: MediaGenerationJob) -> MediaGenerationJobResponse:
    return MediaGenerationJobResponse(
        id=job.id,
        tenant_id=job.tenant_id,
        user_id=job.user_id,
        department_id=job.department_id,
        agent_id=job.agent_id,
        conversation_id=job.conversation_id,
        request_id=job.request_id,
        kind=MediaGenerationKind(job.kind),
        mode=MediaGenerationMode(job.mode),
        status=MediaGenerationJobStatus(job.status),
        provider_key=job.provider_key,
        provider_type=MediaProviderType(job.provider_type),
        model_key=job.model_key,
        routing_key=job.routing_key,
        prompt=job.prompt,
        negative_prompt=job.negative_prompt,
        reference_assets=list(job.reference_assets),
        request_parameters=dict(job.request_parameters),
        normalized_parameters=dict(job.normalized_parameters),
        output_storage=dict(job.output_storage),
        outputs=list(job.outputs),
        external_job_id=job.external_job_id,
        error_message=job.error_message,
        metadata=dict(job.metadata_json),
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


def _event_response(row: AuditLog) -> MediaGenerationJobEvent:
    return MediaGenerationJobEvent(
        id=row.id,
        action=row.action,
        status=row.status,
        request_id=row.request_id,
        actor_id=row.actor_id,
        actor_type=row.actor_type,
        details=redact_audit_details(row.details),
        created_at=row.created_at,
    )
