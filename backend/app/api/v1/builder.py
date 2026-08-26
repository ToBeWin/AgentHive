"""Low-code Agent Builder — admin API endpoints.

These endpoints sit on top of the existing AgentInstance CRUD: they accept a
Builder config, validate it through the policy engine, render it, and persist
the result inside ``AgentInstance.config["builder_config"]``. Operators
still use the regular ``/agents/instances`` endpoints to read / list / delete
the resulting instances.

Endpoints:
- ``POST /agents/builder/validate`` — dry-run validation, returns the issue report.
- ``POST /agents/builder/preview`` — validate + render, returns the rendered
  prompts and metadata without persisting.
- ``POST /agents/builder/instances`` — create a new AgentInstance from a
  Builder config (validated + compiled + persisted).
- ``PATCH /agents/builder/instances/{agent_id}`` — update an existing
  Builder-backed AgentInstance with a new config.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.builder import (
    AgentBuilderConfig,
    AgentBuilderPreviewRequest,
    AgentBuilderRenderOutput,
    AgentBuilderValidationReport,
    BuilderValidationError,
    compile_builder_config,
    preview_builder_config,
    validate_builder_config,
)
from app.agents.builder.engine import builder_config_to_instance_metadata
from app.api.deps import Principal, require_permission
from app.core.database import get_session
from app.core.security import Permission
from app.schemas.agents import (
    AgentInstanceCreateRequest,
    AgentInstanceResponse,
    AgentInstanceUpdateRequest,
)
from app.services.agent_runtime_service import (
    create_agent_instance,
    update_agent_instance,
)

router = APIRouter(prefix="/agents/builder", tags=["agents"])


class BuilderValidateResponse(AgentBuilderValidationReport):
    pass


class BuilderPreviewResponse(AgentBuilderValidationReport):
    rendered: AgentBuilderRenderOutput


@router.post("/validate", response_model=BuilderValidateResponse)
async def validate_builder(
    config: AgentBuilderConfig,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AGENTS_WRITE))],
) -> BuilderValidateResponse:
    report = await validate_builder_config(session, principal, config)
    return BuilderValidateResponse(**report.model_dump())


@router.post("/preview", response_model=BuilderPreviewResponse)
async def preview_builder(
    request: AgentBuilderPreviewRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AGENTS_WRITE))],
) -> BuilderPreviewResponse:
    rendered, report = await preview_builder_config(session, principal, request)
    return BuilderPreviewResponse(**report.model_dump(), rendered=rendered)


@router.post("/instances", response_model=AgentInstanceResponse)
async def create_builder_instance(
    config: AgentBuilderConfig,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AGENTS_WRITE))],
) -> AgentInstanceResponse:
    try:
        rendered = await compile_builder_config(session, principal, config)
    except BuilderValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "builder_validation_failed",
                "issues": [issue.model_dump(mode="json") for issue in exc.report.issues],
            },
        ) from exc
    builder_metadata = builder_config_to_instance_metadata(config, rendered)
    instance_payload = AgentInstanceCreateRequest(
        name=config.name,
        slug=None,  # let the service slugify the name
        agent_key="custom_builder",
        description=config.description,
        visibility="tenant",
        model_key=config.model_key,
        model_routing_key=config.routing_key,
        system_prompt=rendered.system_prompt,
        config={
            "builder_config": builder_metadata,
            "knowledge_base_ids": [str(kb_id) for kb_id in config.knowledge_base_ids],
            "mcp_server_keys": list(config.mcp_server_keys),
        },
        metadata={
            "source": "low_code_builder",
            "builder_config_name": config.name,
        },
    )
    return await create_agent_instance(
        session,
        principal,
        instance_payload,
        request_id=getattr(request.state, "request_id", None),
    )


@router.patch("/instances/{agent_id}", response_model=AgentInstanceResponse)
async def update_builder_instance(
    agent_id: UUID,
    config: AgentBuilderConfig,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AGENTS_WRITE))],
) -> AgentInstanceResponse:
    try:
        rendered = await compile_builder_config(session, principal, config)
    except BuilderValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "builder_validation_failed",
                "issues": [issue.model_dump(mode="json") for issue in exc.report.issues],
            },
        ) from exc
    builder_metadata = builder_config_to_instance_metadata(config, rendered)
    update_payload = AgentInstanceUpdateRequest(
        name=config.name,
        description=config.description,
        model_key=config.model_key,
        model_routing_key=config.routing_key,
        system_prompt=rendered.system_prompt,
        config={
            "builder_config": builder_metadata,
            "knowledge_base_ids": [str(kb_id) for kb_id in config.knowledge_base_ids],
            "mcp_server_keys": list(config.mcp_server_keys),
        },
        metadata={
            "source": "low_code_builder",
            "builder_config_name": config.name,
        },
    )
    return await update_agent_instance(
        session,
        principal,
        agent_id,
        update_payload,
        request_id=getattr(request.state, "request_id", None),
    )
