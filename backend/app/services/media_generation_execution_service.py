from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal
from app.media.providers import (
    BaseMediaProviderAdapter,
    MediaProviderError,
    MediaProviderSubmitResult,
    media_provider_registry,
    register_default_media_providers,
)
from app.media.schemas import (
    MediaGenerationJobResponse,
    MediaGenerationJobStatus,
    MediaGenerationJobStatusUpdate,
)
from app.models.media import MediaGenerationJob
from app.services.media_generation_license_service import ensure_media_generation_module_runnable
from app.services.media_generation_policy_service import enforce_media_generation_model_policy
from app.services.media_generation_service import (
    _assert_media_generation_job_access,
    _plan_from_job,
    update_media_generation_job_status,
)
from app.services.media_output_archive_service import MediaOutputArchiveError, archive_media_outputs
from app.services.media_provider_config_service import (
    ensure_media_provider_configured,
    resolve_database_media_provider_adapter,
)


async def execute_media_generation_job(
    session: AsyncSession,
    principal: Principal,
    job_id: UUID,
    *,
    adapter: BaseMediaProviderAdapter | None = None,
    request_id: str | None = None,
) -> MediaGenerationJobResponse:
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
            detail=f"Cannot execute media generation job in {job.status} status.",
        )

    if job.status == MediaGenerationJobStatus.QUEUED.value:
        await update_media_generation_job_status(
            session,
            principal,
            job_id,
            MediaGenerationJobStatusUpdate(
                status=MediaGenerationJobStatus.RUNNING,
                metadata={"executor": "agenthive_media_generation_executor"},
            ),
            request_id=request_id,
        )
        job = await session.get(MediaGenerationJob, job_id)

    if job is None:
        raise RuntimeError("Media generation job disappeared after status transition.")

    if adapter is None:
        adapter = await resolve_database_media_provider_adapter(
            session,
            principal,
            job.provider_type,
            department_id=job.department_id,
            user_id=job.user_id,
        )
    if adapter is None:
        register_default_media_providers()
    provider = adapter or media_provider_registry.resolve(job.provider_type)
    try:
        result = await provider.submit(job)
    except MediaProviderError as exc:
        return await update_media_generation_job_status(
            session,
            principal,
            job_id,
            MediaGenerationJobStatusUpdate(
                status=MediaGenerationJobStatus.FAILED,
                error_message=str(exc),
                metadata={
                    "executor": "agenthive_media_generation_executor",
                    "error_type": exc.__class__.__name__,
                    **exc.metadata,
                },
            ),
            request_id=request_id,
        )
    except Exception as exc:
        return await update_media_generation_job_status(
            session,
            principal,
            job_id,
            MediaGenerationJobStatusUpdate(
                status=MediaGenerationJobStatus.FAILED,
                error_message=f"Media provider call failed: {exc.__class__.__name__}",
                metadata={
                    "executor": "agenthive_media_generation_executor",
                    "error_type": exc.__class__.__name__,
                },
            ),
            request_id=request_id,
        )

    try:
        return await _apply_provider_result(
            session, principal, job_id, result, request_id=request_id
        )
    except MediaOutputArchiveError as exc:
        return await update_media_generation_job_status(
            session,
            principal,
            job_id,
            MediaGenerationJobStatusUpdate(
                status=MediaGenerationJobStatus.FAILED,
                error_message=str(exc),
                metadata={
                    "executor": "agenthive_media_generation_executor",
                    "error_type": exc.__class__.__name__,
                    "archive_failed": True,
                },
            ),
            request_id=request_id,
        )


async def poll_media_generation_job(
    session: AsyncSession,
    principal: Principal,
    job_id: UUID,
    *,
    adapter: BaseMediaProviderAdapter | None = None,
    request_id: str | None = None,
) -> MediaGenerationJobResponse:
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
            detail=f"Cannot poll media generation job in {job.status} status.",
        )
    if not job.external_job_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot poll media generation job before an external job id is available.",
        )

    if adapter is None:
        adapter = await resolve_database_media_provider_adapter(
            session,
            principal,
            job.provider_type,
            department_id=job.department_id,
            user_id=job.user_id,
        )
    if adapter is None:
        register_default_media_providers()
    provider = adapter or media_provider_registry.resolve(job.provider_type)
    try:
        result = await provider.poll(job)
    except MediaProviderError as exc:
        return await update_media_generation_job_status(
            session,
            principal,
            job_id,
            MediaGenerationJobStatusUpdate(
                status=MediaGenerationJobStatus.RUNNING,
                error_message=str(exc),
                metadata={
                    "executor": "agenthive_media_generation_poller",
                    "error_type": exc.__class__.__name__,
                    "poll_failed": True,
                    **exc.metadata,
                },
            ),
            request_id=request_id,
        )
    except Exception as exc:
        return await update_media_generation_job_status(
            session,
            principal,
            job_id,
            MediaGenerationJobStatusUpdate(
                status=MediaGenerationJobStatus.RUNNING,
                error_message=f"Media provider status poll failed: {exc.__class__.__name__}",
                metadata={
                    "executor": "agenthive_media_generation_poller",
                    "error_type": exc.__class__.__name__,
                    "poll_failed": True,
                },
            ),
            request_id=request_id,
        )

    result.metadata = {
        "executor": "agenthive_media_generation_poller",
        "poll": {
            "external_job_id": job.external_job_id,
            "provider_type": job.provider_type,
            "provider_key": job.provider_key,
        },
        **result.metadata,
    }
    try:
        return await _apply_provider_result(
            session, principal, job_id, result, request_id=request_id
        )
    except MediaOutputArchiveError as exc:
        return await update_media_generation_job_status(
            session,
            principal,
            job_id,
            MediaGenerationJobStatusUpdate(
                status=MediaGenerationJobStatus.FAILED,
                error_message=str(exc),
                metadata={
                    "executor": "agenthive_media_generation_poller",
                    "error_type": exc.__class__.__name__,
                    "archive_failed": True,
                },
            ),
            request_id=request_id,
        )


async def _apply_provider_result(
    session: AsyncSession,
    principal: Principal,
    job_id: UUID,
    result: MediaProviderSubmitResult,
    *,
    request_id: str | None,
) -> MediaGenerationJobResponse:
    job = await session.get(MediaGenerationJob, job_id)
    if job is None:
        raise RuntimeError("Media generation job disappeared before provider result archival.")
    outputs, archive_metadata = await archive_media_outputs(job, result.outputs)
    return await update_media_generation_job_status(
        session,
        principal,
        job_id,
        MediaGenerationJobStatusUpdate(
            status=result.status,
            outputs=outputs,
            external_job_id=result.external_job_id,
            error_message=result.error_message,
            metadata={
                "executor": "agenthive_media_generation_executor",
                "output_archive": archive_metadata,
                **result.metadata,
            },
        ),
        request_id=request_id,
    )
