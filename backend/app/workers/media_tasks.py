import asyncio
from typing import Protocol, cast
from uuid import UUID

from app.api.deps import Principal
from app.core.database import AsyncSessionLocal
from app.core.security import Permission
from app.models.media import MediaGenerationJob
from app.services.media_generation_execution_service import (
    execute_media_generation_job,
    poll_media_generation_job,
)
from app.workers.celery_app import celery_app


class TaskHandle(Protocol):
    id: object


@celery_app.task(name="agenthive.media.execute_generation_job")  # type: ignore[no-untyped-call,misc]
def execute_media_generation_job_task(
    job_id: str,
    tenant_id: str,
    actor_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, object]:
    return asyncio.run(
        _execute_media_generation_job_task(
            job_id=UUID(job_id),
            tenant_id=UUID(tenant_id),
            actor_id=UUID(actor_id) if actor_id else None,
            request_id=request_id,
        )
    )


@celery_app.task(name="agenthive.media.poll_generation_job")  # type: ignore[no-untyped-call,misc]
def poll_media_generation_job_task(
    job_id: str,
    tenant_id: str,
    actor_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, object]:
    return asyncio.run(
        _poll_media_generation_job_task(
            job_id=UUID(job_id),
            tenant_id=UUID(tenant_id),
            actor_id=UUID(actor_id) if actor_id else None,
            request_id=request_id,
        )
    )


def enqueue_media_generation_job(
    *,
    job_id: UUID,
    tenant_id: UUID,
    actor_id: UUID | None,
    request_id: str | None = None,
) -> TaskHandle:
    return cast(
        TaskHandle,
        execute_media_generation_job_task.delay(
            str(job_id),
            str(tenant_id),
            str(actor_id) if actor_id else None,
            request_id,
        ),
    )


def enqueue_media_generation_poll(
    *,
    job_id: UUID,
    tenant_id: UUID,
    actor_id: UUID | None,
    request_id: str | None = None,
) -> TaskHandle:
    return cast(
        TaskHandle,
        poll_media_generation_job_task.delay(
            str(job_id),
            str(tenant_id),
            str(actor_id) if actor_id else None,
            request_id,
        ),
    )


async def _execute_media_generation_job_task(
    *,
    job_id: UUID,
    tenant_id: UUID,
    actor_id: UUID | None,
    request_id: str | None,
) -> dict[str, object]:
    async with AsyncSessionLocal() as session:
        job = await session.get(MediaGenerationJob, job_id)
        if job is None or job.tenant_id != tenant_id:
            return {
                "job_id": str(job_id),
                "tenant_id": str(tenant_id),
                "status": "not_found",
            }
        worker_actor_id = actor_id or job.user_id
        if worker_actor_id is None:
            return {
                "job_id": str(job_id),
                "tenant_id": str(tenant_id),
                "status": "missing_actor",
            }
        principal = Principal(
            user_id=worker_actor_id,
            tenant_id=tenant_id,
            permissions={Permission.AGENTS_WRITE.value},
        )
        response = await execute_media_generation_job(
            session,
            principal,
            job_id,
            request_id=request_id,
        )
        return {
            "job_id": str(response.id),
            "tenant_id": str(response.tenant_id),
            "status": response.status.value,
            "model_key": response.model_key,
            "external_job_id": response.external_job_id,
        }


async def _poll_media_generation_job_task(
    *,
    job_id: UUID,
    tenant_id: UUID,
    actor_id: UUID | None,
    request_id: str | None,
) -> dict[str, object]:
    async with AsyncSessionLocal() as session:
        job = await session.get(MediaGenerationJob, job_id)
        if job is None or job.tenant_id != tenant_id:
            return {
                "job_id": str(job_id),
                "tenant_id": str(tenant_id),
                "status": "not_found",
            }
        worker_actor_id = actor_id or job.user_id
        if worker_actor_id is None:
            return {
                "job_id": str(job_id),
                "tenant_id": str(tenant_id),
                "status": "missing_actor",
            }
        principal = Principal(
            user_id=worker_actor_id,
            tenant_id=tenant_id,
            permissions={Permission.AGENTS_WRITE.value},
        )
        response = await poll_media_generation_job(
            session,
            principal,
            job_id,
            request_id=request_id,
        )
        return {
            "job_id": str(response.id),
            "tenant_id": str(response.tenant_id),
            "status": response.status.value,
            "model_key": response.model_key,
            "external_job_id": response.external_job_id,
        }
