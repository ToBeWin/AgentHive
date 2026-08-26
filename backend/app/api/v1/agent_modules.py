from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_permission
from app.core.database import get_session
from app.core.security import Permission
from app.schemas.agent_modules import (
    AgentModuleActionResponse,
    AgentModuleDetailResponse,
    AgentModuleListResponse,
)
from app.services.agent_module_service import (
    disable_agent_module_for_tenant,
    enable_agent_module_for_tenant,
    get_agent_module_for_tenant,
    install_agent_module_for_tenant,
    list_agent_modules_for_tenant,
)

router = APIRouter(prefix="/agent-modules", tags=["agent-modules"])


@router.get("", response_model=AgentModuleListResponse)
async def read_agent_modules(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AGENTS_WRITE))],
) -> AgentModuleListResponse:
    return await list_agent_modules_for_tenant(session, tenant_id=principal.tenant_id)


@router.get("/{id}", response_model=AgentModuleDetailResponse)
async def read_agent_module(
    id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AGENTS_WRITE))],
) -> AgentModuleDetailResponse:
    return await get_agent_module_for_tenant(session, id, tenant_id=principal.tenant_id)


@router.post("/{id}/install", response_model=AgentModuleActionResponse)
async def install_module(
    request: Request,
    id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AGENTS_WRITE))],
) -> AgentModuleActionResponse:
    return await install_agent_module_for_tenant(
        session,
        id,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/{id}/enable", response_model=AgentModuleActionResponse)
async def enable_module(
    request: Request,
    id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AGENTS_WRITE))],
) -> AgentModuleActionResponse:
    return await enable_agent_module_for_tenant(
        session,
        id,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/{id}/disable", response_model=AgentModuleActionResponse)
async def disable_module(
    request: Request,
    id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.AGENTS_WRITE))],
) -> AgentModuleActionResponse:
    return await disable_agent_module_for_tenant(
        session,
        id,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        request_id=getattr(request.state, "request_id", None),
    )
