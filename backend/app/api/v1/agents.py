from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_any_permission, require_permission
from app.core.database import get_session
from app.core.security import Permission
from app.schemas.agents import (
    AgentCatalogResponse,
    AgentGovernanceTargetsResponse,
    AgentInstanceCreateRequest,
    AgentInstanceListResponse,
    AgentInstanceResponse,
    AgentInstanceUpdateRequest,
    AgentRunRequest,
    AgentRunResponse,
    WorkbenchAgentInstanceListResponse,
)
from app.services.agent_runtime_service import (
    create_agent_instance,
    get_agent_instance,
    list_agent_governance_targets,
    list_agent_catalog,
    list_agent_instances,
    list_workbench_agent_instances,
    run_agent,
    update_agent_instance,
)

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/catalog", response_model=AgentCatalogResponse)
async def read_agent_catalog(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AGENTS_WRITE))],
) -> AgentCatalogResponse:
    return await list_agent_catalog(session, principal)


@router.get("/instances", response_model=AgentInstanceListResponse)
async def read_agent_instances(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AGENTS_WRITE))],
) -> AgentInstanceListResponse:
    return await list_agent_instances(session, principal)


@router.get("/workbench/instances", response_model=WorkbenchAgentInstanceListResponse)
async def read_workbench_agent_instances(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[
        Principal,
        Depends(
            require_any_permission(
                Permission.CHAT_READ, Permission.CHAT_WRITE, Permission.AGENTS_READ
            )
        ),
    ],
) -> WorkbenchAgentInstanceListResponse:
    return await list_workbench_agent_instances(session, principal)


@router.get("/governance-targets", response_model=AgentGovernanceTargetsResponse)
async def read_agent_governance_targets(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AGENTS_WRITE))],
) -> AgentGovernanceTargetsResponse:
    return await list_agent_governance_targets(session, principal)


@router.post("/instances", response_model=AgentInstanceResponse)
async def create_agent(
    payload: AgentInstanceCreateRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AGENTS_WRITE))],
) -> AgentInstanceResponse:
    return await create_agent_instance(
        session,
        principal,
        payload,
        request_id=getattr(request.state, "request_id", None),
    )


@router.get("/instances/{agent_id}", response_model=AgentInstanceResponse)
async def read_agent_instance(
    agent_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AGENTS_WRITE))],
) -> AgentInstanceResponse:
    return await get_agent_instance(session, principal, agent_id)


@router.patch("/instances/{agent_id}", response_model=AgentInstanceResponse)
async def update_agent(
    agent_id: UUID,
    payload: AgentInstanceUpdateRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AGENTS_WRITE))],
) -> AgentInstanceResponse:
    return await update_agent_instance(
        session,
        principal,
        agent_id,
        payload,
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/{agent_key}/run", response_model=AgentRunResponse)
async def run_official_agent(
    agent_key: str,
    payload: AgentRunRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AGENTS_WRITE))],
) -> AgentRunResponse:
    response = await run_agent(
        session,
        agent_key,
        payload,
        principal,
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()
    return response
