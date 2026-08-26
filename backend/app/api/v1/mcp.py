"""MCP (Model Context Protocol) admin API.

Endpoints for managing per-tenant MCP server configurations, discovering
tools, and invoking tools for testing. All operations require MCP permissions.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_permission
from app.core.database import get_session
from app.core.security import Permission
from app.schemas.mcp import (
    McpServerCreateRequest as McpServerCreatePayload,
    McpServerListResponse,
    McpServerResponse,
    McpServerTestResponse,
    McpServerUpdateRequest,
    McpToolInvokeRequest,
    McpToolInvokeResponse,
    McpToolsListResponse,
)
from app.services.mcp_service import (
    create_mcp_server_for_tenant,
    delete_mcp_server_for_tenant,
    invoke_tool_on_server,
    list_mcp_servers_for_tenant,
    list_tools_for_server,
    test_mcp_server,
    update_mcp_server_for_tenant,
)

router = APIRouter(prefix="/mcp", tags=["mcp"])


def _client_meta(request: Request) -> dict[str, str | None]:
    return {
        "request_id": getattr(request.state, "request_id", None),
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


@router.get("/servers", response_model=McpServerListResponse)
async def list_mcp_servers(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.MCP_READ))],
) -> McpServerListResponse:
    return await list_mcp_servers_for_tenant(session, tenant_id=principal.tenant_id)


@router.post("/servers", response_model=McpServerResponse, status_code=status.HTTP_201_CREATED)
async def create_mcp_server(
    request: Request,
    payload: McpServerCreatePayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.MCP_WRITE))],
) -> McpServerResponse:
    meta = _client_meta(request)
    return await create_mcp_server_for_tenant(
        session,
        tenant_id=principal.tenant_id,
        request=payload,
        actor_id=principal.user_id,
        request_id=meta["request_id"],
    )


@router.patch("/servers/{server_id}", response_model=McpServerResponse)
async def update_mcp_server(
    request: Request,
    server_id: UUID,
    payload: McpServerUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.MCP_WRITE))],
) -> McpServerResponse:
    meta = _client_meta(request)
    return await update_mcp_server_for_tenant(
        session,
        tenant_id=principal.tenant_id,
        server_id=server_id,
        request=payload,
        actor_id=principal.user_id,
        request_id=meta["request_id"],
    )


@router.delete("/servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mcp_server(
    request: Request,
    server_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.MCP_WRITE))],
) -> None:
    meta = _client_meta(request)
    await delete_mcp_server_for_tenant(
        session,
        tenant_id=principal.tenant_id,
        server_id=server_id,
        actor_id=principal.user_id,
        request_id=meta["request_id"],
    )


@router.get("/servers/{server_id}/tools", response_model=McpToolsListResponse)
async def list_server_tools(
    request: Request,
    server_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.MCP_READ))],
) -> McpToolsListResponse:
    meta = _client_meta(request)
    return await list_tools_for_server(
        session,
        tenant_id=principal.tenant_id,
        server_id=server_id,
        actor_id=principal.user_id,
        request_id=meta["request_id"],
        ip_address=meta["ip_address"],
        user_agent=meta["user_agent"],
    )


@router.post("/servers/{server_id}/test", response_model=McpServerTestResponse)
async def test_mcp_server_endpoint(
    request: Request,
    server_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.MCP_WRITE))],
) -> McpServerTestResponse:
    meta = _client_meta(request)
    return await test_mcp_server(
        session,
        tenant_id=principal.tenant_id,
        server_id=server_id,
        actor_id=principal.user_id,
        request_id=meta["request_id"],
        ip_address=meta["ip_address"],
        user_agent=meta["user_agent"],
    )


@router.post(
    "/servers/{server_id}/tools/{tool_name}/invoke",
    response_model=McpToolInvokeResponse,
)
async def invoke_mcp_tool(
    request: Request,
    server_id: UUID,
    tool_name: str,
    payload: McpToolInvokeRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.MCP_INVOKE))],
) -> McpToolInvokeResponse:
    meta = _client_meta(request)
    return await invoke_tool_on_server(
        session,
        tenant_id=principal.tenant_id,
        server_id=server_id,
        tool_name=tool_name,
        request=payload,
        principal=principal,
        request_id=meta["request_id"],
        ip_address=meta["ip_address"],
        user_agent=meta["user_agent"],
    )
