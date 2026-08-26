from secrets import compare_digest
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.deps import Principal
from app.media.schemas import (
    MediaGenerationJobResponse,
    MediaGenerationJobStatus,
    MediaGenerationProviderCallback,
)
from app.models.base import utc_now
from app.models.media import MediaGenerationJob
from app.services.audit_service import record_audit_event
from app.services.media_generation_service import (
    TERMINAL_MEDIA_JOB_STATUSES,
    _budget_reservation_audit_summary,
    _ensure_status_transition,
    _job_response,
    _media_output_archive_audit_details,
    _media_outputs_audit_summary,
)
from app.services.media_generation_budget_service import (
    release_media_generation_budget,
    settle_media_generation_budget,
)
from app.services.media_output_archive_service import MediaOutputArchiveError, archive_media_outputs


def assert_media_webhook_secret(provided_secret: str | None, expected_secret: str) -> None:
    if not expected_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Media provider webhook is not configured.",
        )
    if not provided_secret or not compare_digest(provided_secret, expected_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid media provider webhook secret.",
        )


async def handle_media_generation_provider_callback(
    session: AsyncSession,
    payload: MediaGenerationProviderCallback,
    *,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> MediaGenerationJobResponse:
    job = await _resolve_callback_job(session, payload)
    next_status = payload.status.value
    previous_status = job.status
    if previous_status in TERMINAL_MEDIA_JOB_STATUSES:
        return await _handle_terminal_callback(
            session,
            job,
            payload,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    try:
        _ensure_status_transition(previous_status, next_status)
    except HTTPException as exc:
        await _record_provider_callback_failure(
            session,
            job,
            payload,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            reason="invalid_status_transition",
            error_type=exc.__class__.__name__,
            error_message=str(exc.detail),
        )
        raise
    output_archive_metadata: dict[str, object] | None = None
    if payload.outputs is not None:
        try:
            job.outputs, output_archive_metadata = await archive_media_outputs(
                job, list(payload.outputs)
            )
        except MediaOutputArchiveError as exc:
            await _record_provider_callback_failure(
                session,
                job,
                payload,
                request_id=request_id,
                ip_address=ip_address,
                user_agent=user_agent,
                reason="output_archive_failed",
                error_type=exc.__class__.__name__,
                error_message=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
    now = utc_now()
    job.status = next_status
    job.updated_at = now
    if next_status == MediaGenerationJobStatus.RUNNING.value and job.started_at is None:
        job.started_at = now
    if next_status in TERMINAL_MEDIA_JOB_STATUSES and job.completed_at is None:
        job.completed_at = now
    if payload.external_job_id:
        job.external_job_id = payload.external_job_id
    if payload.error_message is not None:
        job.error_message = payload.error_message
    job.metadata_json = _merged_webhook_metadata(
        job,
        payload,
        previous_status=previous_status,
        output_archive_metadata=output_archive_metadata,
    )
    budget_event = None
    budget_release_reason = None
    if next_status in TERMINAL_MEDIA_JOB_STATUSES:
        principal = _job_principal(job)
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
        "external_job_id": job.external_job_id,
        "provider_key": payload.provider_key or job.provider_key,
        "provider_type": job.provider_type,
        "provider_status": payload.provider_status,
        "output_count": len(payload.outputs or []),
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
        tenant_id=job.tenant_id,
        actor_id=None,
        actor_type="provider",
        request_id=request_id,
        action="media.generation.provider_callback",
        resource_type="media_generation_job",
        resource_id=job.id,
        ip_address=ip_address,
        user_agent=user_agent,
        details=audit_details,
    )
    await session.commit()
    await session.refresh(job)
    return _job_response(job)


def _job_principal(job: MediaGenerationJob) -> Principal:
    return Principal(
        tenant_id=job.tenant_id,
        user_id=job.user_id or UUID("00000000-0000-4000-8000-000000000000"),
        permissions=set(),
    )


async def _resolve_callback_job(
    session: AsyncSession,
    payload: MediaGenerationProviderCallback,
) -> MediaGenerationJob:
    if payload.job_id is not None:
        job = await session.get(MediaGenerationJob, payload.job_id)
        if job is not None:
            _assert_callback_matches_job(job, payload)
            return job
    if payload.external_job_id:
        statement = select(MediaGenerationJob).where(
            MediaGenerationJob.external_job_id == payload.external_job_id
        )
        if payload.provider_key:
            statement = statement.where(MediaGenerationJob.provider_key == payload.provider_key)
        result = await session.execute(statement)
        jobs = list(result.scalars().all())
        if len(jobs) == 1:
            _assert_callback_matches_job(jobs[0], payload)
            return jobs[0]
        if len(jobs) > 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Media provider callback matched multiple jobs.",
            )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Media generation job not found."
    )


def _assert_callback_matches_job(
    job: MediaGenerationJob,
    payload: MediaGenerationProviderCallback,
) -> None:
    if payload.provider_key and payload.provider_key != job.provider_key:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Media provider callback provider_key does not match the job.",
        )
    if (
        payload.external_job_id
        and job.external_job_id
        and payload.external_job_id != job.external_job_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Media provider callback external_job_id does not match the job.",
        )


async def _handle_terminal_callback(
    session: AsyncSession,
    job: MediaGenerationJob,
    payload: MediaGenerationProviderCallback,
    *,
    request_id: str | None,
    ip_address: str | None,
    user_agent: str | None,
) -> MediaGenerationJobResponse:
    next_status = payload.status.value
    if next_status != job.status:
        await _record_provider_callback_failure(
            session,
            job,
            payload,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            reason="terminal_status_conflict",
            error_type="HTTPException",
            error_message=f"Media generation job is already terminal in {job.status} status.",
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Media generation job is already terminal in {job.status} status.",
        )
    await record_audit_event(
        session,
        tenant_id=job.tenant_id,
        actor_id=None,
        actor_type="provider",
        request_id=request_id,
        action="media.generation.provider_callback_ignored",
        resource_type="media_generation_job",
        resource_id=job.id,
        ip_address=ip_address,
        user_agent=user_agent,
        details={
            "status": job.status,
            "external_job_id": job.external_job_id,
            "provider_key": payload.provider_key or job.provider_key,
            "provider_status": payload.provider_status,
            "reason": "terminal_status_duplicate",
        },
    )
    await session.commit()
    await session.refresh(job)
    return _job_response(job)


async def _record_provider_callback_failure(
    session: AsyncSession,
    job: MediaGenerationJob,
    payload: MediaGenerationProviderCallback,
    *,
    request_id: str | None,
    ip_address: str | None,
    user_agent: str | None,
    reason: str,
    error_type: str,
    error_message: str,
) -> None:
    await record_audit_event(
        session,
        tenant_id=job.tenant_id,
        actor_id=None,
        actor_type="provider",
        request_id=request_id,
        action="media.generation.provider_callback_failed",
        status="failure",
        resource_type="media_generation_job",
        resource_id=job.id,
        ip_address=ip_address,
        user_agent=user_agent,
        details={
            "status": job.status,
            "callback_status": payload.status.value,
            "external_job_id": payload.external_job_id or job.external_job_id,
            "provider_key": payload.provider_key or job.provider_key,
            "provider_status": payload.provider_status,
            "output_count": len(payload.outputs or []),
            "reason": reason,
            "error_type": error_type,
            "error_message": error_message,
        },
    )
    await session.commit()


def _merged_webhook_metadata(
    job: MediaGenerationJob,
    payload: MediaGenerationProviderCallback,
    *,
    previous_status: str,
    output_archive_metadata: dict[str, object] | None,
) -> dict[str, object]:
    now = utc_now()
    return {
        **dict(job.metadata_json),
        "provider_webhook": {
            "at": now.isoformat(),
            "previous_status": previous_status,
            "next_status": payload.status.value,
            "provider_key": payload.provider_key or job.provider_key,
            "provider_status": payload.provider_status,
            "external_job_id": payload.external_job_id or job.external_job_id,
            "output_count": len(payload.outputs or []),
            "metadata": payload.metadata,
        },
        **(
            {"output_archive": output_archive_metadata}
            if output_archive_metadata is not None
            else {}
        ),
    }
