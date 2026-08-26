from typing import Any, cast
from uuid import UUID

from celery.exceptions import CeleryError
from fastapi import HTTPException, status
from kombu.exceptions import KombuError
from sqlalchemy import ColumnElement, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.deps import Principal
from app.media.schemas import (
    MediaGenerationJobEnqueueResponse,
    MediaGenerationJobStatus,
    MediaGenerationPollBatchItem,
    MediaGenerationPollBatchResponse,
)
from app.models.base import utc_now
from app.models.media import MediaGenerationJob
from app.services.audit_service import record_audit_event
from app.services.media_generation_license_service import ensure_media_generation_module_runnable
from app.services.media_generation_policy_service import enforce_media_generation_model_policy
from app.services.media_generation_service import (
    _assert_media_generation_job_access,
    _media_generation_job_access_filters,
    _plan_from_job,
)
from app.services.media_provider_config_service import ensure_media_provider_configured
from app.workers.media_tasks import (
    enqueue_media_generation_job as enqueue_worker_job,
    enqueue_media_generation_poll as enqueue_worker_poll,
)


async def enqueue_media_generation_job_for_worker(
    session: AsyncSession,
    principal: Principal,
    job_id: UUID,
    *,
    request_id: str | None = None,
) -> MediaGenerationJobEnqueueResponse:
    job = await session.get(MediaGenerationJob, job_id)
    if job is None or job.tenant_id != principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Media generation job not found."
        )
    await _assert_media_generation_job_access(session, principal, job)
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
    if job.status not in {
        MediaGenerationJobStatus.QUEUED.value,
        MediaGenerationJobStatus.RUNNING.value,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot enqueue media generation job in {job.status} status.",
        )
    existing_queue = _active_queue_metadata(job, "queue")
    if existing_queue is not None:
        await _record_duplicate_enqueue_audit(
            session,
            principal,
            job,
            request_id=request_id,
            action="media.generation.enqueue_skipped",
            task_id=str(existing_queue["task_id"]),
            queue_key="queue",
        )
        await session.commit()
        return MediaGenerationJobEnqueueResponse(
            job_id=job.id, task_id=str(existing_queue["task_id"]), queued=False
        )
    try:
        task = enqueue_worker_job(
            job_id=job.id,
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            request_id=request_id,
        )
    except (CeleryError, KombuError, OSError, RuntimeError, AttributeError) as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Media generation queue is unavailable: {exc.__class__.__name__}.",
        ) from exc
    now = utc_now()
    job.metadata_json = {
        **dict(job.metadata_json),
        "queue": {
            "task_id": str(task.id),
            "enqueued_at": now.isoformat(),
            "actor_id": str(principal.user_id),
            "request_id": request_id,
            "status_at_enqueue": job.status,
        },
    }
    job.updated_at = now
    await record_audit_event(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        request_id=request_id,
        action="media.generation.enqueue",
        resource_type="media_generation_job",
        resource_id=job.id,
        details={
            "task_id": str(task.id),
            "status": job.status,
            "model_key": job.model_key,
            "routing_key": job.routing_key,
        },
    )
    await session.commit()
    return MediaGenerationJobEnqueueResponse(job_id=job.id, task_id=str(task.id))


async def enqueue_media_generation_poll_for_worker(
    session: AsyncSession,
    principal: Principal,
    job_id: UUID,
    *,
    request_id: str | None = None,
) -> MediaGenerationJobEnqueueResponse:
    job = await session.get(MediaGenerationJob, job_id)
    if job is None or job.tenant_id != principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Media generation job not found."
        )
    await _assert_media_generation_job_access(session, principal, job)
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
    if job.status != MediaGenerationJobStatus.RUNNING.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot enqueue media generation poll in {job.status} status.",
        )
    if not job.external_job_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot enqueue media generation poll before an external job id is available.",
        )
    existing_poll_queue = _active_queue_metadata(job, "poll_queue")
    if (
        existing_poll_queue is not None
        and existing_poll_queue.get("external_job_id") == job.external_job_id
    ):
        await _record_duplicate_enqueue_audit(
            session,
            principal,
            job,
            request_id=request_id,
            action="media.generation.poll_enqueue_skipped",
            task_id=str(existing_poll_queue["task_id"]),
            queue_key="poll_queue",
        )
        await session.commit()
        return MediaGenerationJobEnqueueResponse(
            job_id=job.id,
            task_id=str(existing_poll_queue["task_id"]),
            queued=False,
        )
    try:
        task = enqueue_worker_poll(
            job_id=job.id,
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            request_id=request_id,
        )
    except (CeleryError, KombuError, OSError, RuntimeError, AttributeError) as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Media generation poll queue is unavailable: {exc.__class__.__name__}.",
        ) from exc
    now = utc_now()
    job.metadata_json = {
        **dict(job.metadata_json),
        "poll_queue": {
            "task_id": str(task.id),
            "enqueued_at": now.isoformat(),
            "actor_id": str(principal.user_id),
            "request_id": request_id,
            "status_at_enqueue": job.status,
            "external_job_id": job.external_job_id,
        },
    }
    job.updated_at = now
    await record_audit_event(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        request_id=request_id,
        action="media.generation.poll_enqueue",
        resource_type="media_generation_job",
        resource_id=job.id,
        details={
            "task_id": str(task.id),
            "status": job.status,
            "external_job_id": job.external_job_id,
            "model_key": job.model_key,
            "routing_key": job.routing_key,
        },
    )
    await session.commit()
    return MediaGenerationJobEnqueueResponse(job_id=job.id, task_id=str(task.id))


async def enqueue_running_media_generation_polls_for_worker(
    session: AsyncSession,
    principal: Principal,
    *,
    limit: int = 20,
    request_id: str | None = None,
) -> MediaGenerationPollBatchResponse:
    statement = select(MediaGenerationJob).where(
        cast(ColumnElement[bool], MediaGenerationJob.tenant_id == principal.tenant_id),
        cast(
            ColumnElement[bool], MediaGenerationJob.status == MediaGenerationJobStatus.RUNNING.value
        ),
        cast(Any, MediaGenerationJob.external_job_id).is_not(None),
    )
    access_filters = await _media_generation_job_access_filters(session, principal)
    if access_filters:
        statement = statement.where(or_(*access_filters))
    statement = statement.order_by(cast(Any, MediaGenerationJob.updated_at).asc()).limit(limit)
    result = await session.execute(statement)
    jobs = list(result.scalars().all())
    items: list[MediaGenerationPollBatchItem] = []
    for job in jobs:
        try:
            response = await enqueue_media_generation_poll_for_worker(
                session,
                principal,
                job.id,
                request_id=request_id,
            )
        except HTTPException as exc:
            reason = str(exc.detail)
            items.append(
                MediaGenerationPollBatchItem(
                    job_id=job.id,
                    external_job_id=job.external_job_id,
                    queued=False,
                    reason=reason,
                )
            )
        else:
            items.append(
                MediaGenerationPollBatchItem(
                    job_id=response.job_id,
                    external_job_id=job.external_job_id,
                    task_id=response.task_id,
                    queued=response.queued,
                    reason=None if response.queued else "duplicate_active_queue",
                )
            )
    queued = sum(1 for item in items if item.queued)
    skipped = sum(
        1 for item in items if not item.queued and item.reason == "duplicate_active_queue"
    )
    failed = sum(1 for item in items if not item.queued)
    return MediaGenerationPollBatchResponse(
        requested=len(jobs),
        queued=queued,
        skipped=skipped,
        failed=failed - skipped,
        items=items,
    )


def _active_queue_metadata(job: MediaGenerationJob, key: str) -> dict[str, object] | None:
    queue_metadata = dict(job.metadata_json or {}).get(key)
    if not isinstance(queue_metadata, dict):
        return None
    task_id = queue_metadata.get("task_id")
    status_at_enqueue = queue_metadata.get("status_at_enqueue")
    if not task_id or status_at_enqueue != job.status:
        return None
    return queue_metadata


async def _record_duplicate_enqueue_audit(
    session: AsyncSession,
    principal: Principal,
    job: MediaGenerationJob,
    *,
    request_id: str | None,
    action: str,
    task_id: str,
    queue_key: str,
) -> None:
    await record_audit_event(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        request_id=request_id,
        action=action,
        resource_type="media_generation_job",
        resource_id=job.id,
        details={
            "task_id": task_id,
            "status": job.status,
            "queue_key": queue_key,
            "reason": "duplicate_active_queue",
            "model_key": job.model_key,
            "routing_key": job.routing_key,
        },
    )
