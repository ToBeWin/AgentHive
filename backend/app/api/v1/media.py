from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi import Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_any_permission, require_permission
from app.core.config import settings
from app.core.database import get_session
from app.core.security import Permission
from app.media.gateway import build_media_generation_plan, list_media_model_capabilities
from app.media.schemas import (
    MediaGenerationJobCreateRequest,
    MediaGenerationJobEnqueueResponse,
    MediaGenerationJobEventsResponse,
    MediaGenerationJobListResponse,
    MediaGenerationJobResponse,
    MediaGenerationJobStatus,
    MediaGenerationJobStatusUpdate,
    MediaGenerationKind,
    MediaGenerationPollBatchResponse,
    MediaGenerationProviderCallback,
    MediaGenerationPlan,
    MediaGenerationRequest,
    MediaModelCapability,
)
from app.services.media_generation_service import (
    cancel_media_generation_job,
    create_media_generation_job,
    get_media_generation_job,
    list_media_generation_job_events,
    list_media_generation_jobs,
    retry_media_generation_job,
    update_media_generation_job_status,
)
from app.services.media_generation_license_service import ensure_media_generation_module_runnable
from app.services.media_generation_policy_service import enforce_media_generation_model_policy
from app.services.media_generation_execution_service import (
    execute_media_generation_job,
    poll_media_generation_job,
)
from app.services.media_generation_queue_service import (
    enqueue_media_generation_job_for_worker,
    enqueue_media_generation_poll_for_worker,
    enqueue_running_media_generation_polls_for_worker,
)
from app.services.media_generation_webhook_service import (
    assert_media_webhook_secret,
    handle_media_generation_provider_callback,
)
from app.services.media_output_download_service import download_media_generation_output
from app.services.media_provider_config_service import (
    ensure_media_provider_configured,
    media_provider_diagnostics,
)

router = APIRouter(prefix="/media", tags=["media"])


@router.get("/models", response_model=list[MediaModelCapability])
async def read_media_models(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[
        Principal,
        Depends(
            require_any_permission(
                Permission.MODELS_READ, Permission.AGENTS_READ, Permission.CHAT_WRITE
            )
        ),
    ],
) -> list[MediaModelCapability]:
    diagnostics = await media_provider_diagnostics(session, principal)
    models = list_media_model_capabilities(provider_diagnostics=diagnostics)
    if _can_view_media_model_diagnostics(principal):
        return models
    return [
        model.model_copy(update={"configuration_issues": [], "configuration_hint": None})
        for model in models
        if model.status == "active"
    ]


def _can_view_media_model_diagnostics(principal: Principal) -> bool:
    return principal.has_any_permission(
        {
            Permission.MODELS_READ,
            Permission.MODELS_WRITE,
            Permission.SYSTEM_DIAGNOSTICS,
        }
    )


@router.post("/generations/plan", response_model=MediaGenerationPlan)
async def plan_media_generation(
    payload: MediaGenerationRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[
        Principal,
        Depends(require_any_permission(Permission.AGENTS_WRITE, Permission.CHAT_WRITE)),
    ],
) -> MediaGenerationPlan:
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
        session, principal, plan.provider_type, user_id=principal.user_id
    )
    await enforce_media_generation_model_policy(
        session,
        principal,
        plan,
        request_id=getattr(request.state, "request_id", None),
    )
    return plan


@router.post("/generations", response_model=MediaGenerationJobResponse)
async def create_generation_job(
    payload: MediaGenerationJobCreateRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[
        Principal,
        Depends(require_any_permission(Permission.AGENTS_WRITE, Permission.CHAT_WRITE)),
    ],
) -> MediaGenerationJobResponse:
    return await create_media_generation_job(
        session,
        principal,
        payload,
        request_id=getattr(request.state, "request_id", None),
    )


@router.get("/generations", response_model=MediaGenerationJobListResponse)
async def read_generation_jobs(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AGENTS_READ))],
    kind: Annotated[MediaGenerationKind | None, Query()] = None,
    status_filter: Annotated[MediaGenerationJobStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> MediaGenerationJobListResponse:
    return await list_media_generation_jobs(
        session,
        principal,
        kind=kind,
        status_filter=status_filter,
        limit=limit,
    )


@router.post("/generations/poll/enqueue", response_model=MediaGenerationPollBatchResponse)
async def enqueue_running_generation_polls(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AGENTS_WRITE))],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> MediaGenerationPollBatchResponse:
    return await enqueue_running_media_generation_polls_for_worker(
        session,
        principal,
        limit=limit,
        request_id=getattr(request.state, "request_id", None),
    )


@router.get("/generations/{job_id}", response_model=MediaGenerationJobResponse)
async def read_generation_job(
    job_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AGENTS_READ))],
) -> MediaGenerationJobResponse:
    return await get_media_generation_job(session, principal, job_id)


@router.get("/generations/{job_id}/events", response_model=MediaGenerationJobEventsResponse)
async def read_generation_job_events(
    job_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AGENTS_READ))],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> MediaGenerationJobEventsResponse:
    return await list_media_generation_job_events(session, principal, job_id, limit=limit)


@router.get("/generations/{job_id}/outputs/{output_index}/download")
async def download_generation_output(
    job_id: UUID,
    output_index: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AGENTS_READ))],
) -> Response:
    output = await download_media_generation_output(
        session,
        principal,
        job_id,
        output_index,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return Response(
        content=output.data,
        media_type=output.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{output.filename}"',
            "Content-Length": str(output.size_bytes),
        },
    )


@router.patch("/generations/{job_id}/status", response_model=MediaGenerationJobResponse)
async def update_generation_job_status(
    job_id: UUID,
    payload: MediaGenerationJobStatusUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AGENTS_WRITE))],
) -> MediaGenerationJobResponse:
    return await update_media_generation_job_status(
        session,
        principal,
        job_id,
        payload,
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/generations/{job_id}/run", response_model=MediaGenerationJobResponse)
async def run_generation_job(
    job_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AGENTS_WRITE))],
) -> MediaGenerationJobResponse:
    return await execute_media_generation_job(
        session,
        principal,
        job_id,
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/generations/{job_id}/retry", response_model=MediaGenerationJobResponse)
async def retry_generation_job(
    job_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AGENTS_WRITE))],
) -> MediaGenerationJobResponse:
    return await retry_media_generation_job(
        session,
        principal,
        job_id,
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/generations/{job_id}/poll", response_model=MediaGenerationJobResponse)
async def poll_generation_job(
    job_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AGENTS_WRITE))],
) -> MediaGenerationJobResponse:
    return await poll_media_generation_job(
        session,
        principal,
        job_id,
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/generations/{job_id}/poll/enqueue", response_model=MediaGenerationJobEnqueueResponse)
async def enqueue_generation_poll(
    job_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AGENTS_WRITE))],
) -> MediaGenerationJobEnqueueResponse:
    return await enqueue_media_generation_poll_for_worker(
        session,
        principal,
        job_id,
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/generations/{job_id}/cancel", response_model=MediaGenerationJobResponse)
async def cancel_generation_job(
    job_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AGENTS_WRITE))],
) -> MediaGenerationJobResponse:
    return await cancel_media_generation_job(
        session,
        principal,
        job_id,
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/generations/{job_id}/enqueue", response_model=MediaGenerationJobEnqueueResponse)
async def enqueue_generation_job(
    job_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[
        Principal, Depends(require_any_permission(Permission.AGENTS_WRITE, Permission.CHAT_WRITE))
    ],
) -> MediaGenerationJobEnqueueResponse:
    return await enqueue_media_generation_job_for_worker(
        session,
        principal,
        job_id,
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/webhooks/provider", response_model=MediaGenerationJobResponse)
async def receive_media_provider_webhook(
    payload: MediaGenerationProviderCallback,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    webhook_secret: Annotated[str | None, Header(alias="X-AgentHive-Media-Webhook-Secret")] = None,
) -> MediaGenerationJobResponse:
    assert_media_webhook_secret(webhook_secret, settings.media_webhook_secret)
    return await handle_media_generation_provider_callback(
        session,
        payload,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
