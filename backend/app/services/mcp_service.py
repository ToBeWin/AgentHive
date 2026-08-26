"""MCP server configuration service.

Manages per-tenant MCP server configurations: CRUD, status transitions,
tool discovery and tool invocation. All mutations emit audit events.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, cast
from uuid import UUID, uuid4

from cryptography.fernet import InvalidToken
from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.deps import Principal
from app.core.secrets import decrypt_secret, encrypt_secret
from app.mcp.client import (
    McpClientError,
    McpEndpoint,
    McpToolCallResult,
    McpToolInfo,
    call_tool as mcp_call_tool,
    list_tools as mcp_list_tools,
    probe as mcp_probe,
)
from app.models.mcp import McpServerConfig
from app.schemas.mcp import (
    McpServerCreateRequest,
    McpServerListResponse,
    McpServerResponse,
    McpServerStatus,
    McpServerTestResponse,
    McpServerUpdateRequest,
    McpToolInfo as McpToolInfoSchema,
    McpToolInvokeRequest,
    McpToolInvokeResponse,
    McpToolSchema,
    McpToolsListResponse,
    McpTransport,
)
from app.services.audit_service import record_audit_event


@dataclass(frozen=True)
class McpServerRecord:
    """Memory representation used for cache + transport."""

    id: UUID
    tenant_id: UUID
    name: str
    server_key: str
    transport: McpTransport
    endpoint_url: str
    auth_headers: dict[str, str]
    status: McpServerStatus
    timeout_seconds: float
    metadata: dict[str, Any]
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    auth_configured: bool

    def to_endpoint(self) -> McpEndpoint:
        return McpEndpoint(
            server_id=str(self.id),
            server_key=self.server_key,
            transport=self.transport.value,
            endpoint_url=self.endpoint_url,
            auth_headers=dict(self.auth_headers),
            timeout_seconds=self.timeout_seconds,
        )


_servers_by_tenant: dict[UUID, dict[UUID, McpServerRecord]] = {}


def _cache_server(record: McpServerRecord) -> None:
    _servers_by_tenant.setdefault(record.tenant_id, {})[record.id] = record


def _evict_server(tenant_id: UUID, server_id: UUID) -> None:
    _servers_by_tenant.get(tenant_id, {}).pop(server_id, None)


def _decrypt_auth_headers(auth_ref: str | None) -> dict[str, str]:
    if not auth_ref:
        return {}
    try:
        decoded = decrypt_secret(auth_ref)
    except (InvalidToken, ValueError):
        return {}
    try:
        parsed = json.loads(decoded)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(k): str(v) for k, v in parsed.items()}


def _encrypt_auth_headers(headers: dict[str, str]) -> str | None:
    if not headers:
        return None
    return encrypt_secret(json.dumps(headers, separators=(",", ":")))


def _record_from_row(row: McpServerConfig) -> McpServerRecord:
    return McpServerRecord(
        id=row.id,
        tenant_id=row.tenant_id,
        name=row.name,
        server_key=row.server_key,
        transport=McpTransport(row.transport),
        endpoint_url=row.endpoint_url,
        auth_headers=_decrypt_auth_headers(row.auth_ref),
        status=McpServerStatus(row.status),
        timeout_seconds=float(row.timeout_seconds),
        metadata=dict(row.metadata_ or {}),
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
        auth_configured=bool(row.auth_configured),
    )


def _to_response(record: McpServerRecord) -> McpServerResponse:
    return McpServerResponse(
        id=record.id,
        tenant_id=record.tenant_id,
        name=record.name,
        server_key=record.server_key,
        transport=record.transport,
        endpoint_url=record.endpoint_url,
        auth_configured=record.auth_configured,
        status=record.status,
        timeout_seconds=record.timeout_seconds,
        metadata=dict(record.metadata),
        created_by=record.created_by,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _tool_info_to_schema(tool: McpToolInfo) -> McpToolInfoSchema:
    return McpToolInfoSchema(
        name=tool.name,
        description=tool.description,
        input_schema=McpToolSchema(
            type=str(tool.input_schema.get("type") or "object"),
            properties=tool.input_schema.get("properties") or {},
            required=list(tool.input_schema.get("required") or []),
        ),
    )


async def list_mcp_servers_for_tenant(
    session: AsyncSession,
    *,
    tenant_id: UUID,
) -> McpServerListResponse:
    records: list[McpServerRecord] = []
    try:
        result = await session.execute(
            select(McpServerConfig)
            .where(McpServerConfig.tenant_id == tenant_id)
            .order_by(cast(Any, McpServerConfig.created_at))
        )
        records = [_record_from_row(row) for row in result.scalars().all()]
        for record in records:
            _cache_server(record)
    except (OSError, SQLAlchemyError):
        records = []
    # Resilience fallback: if the DB returned no rows but the in-memory cache
    # has entries for this tenant (e.g. DB unavailable, or read replica lag),
    # serve from cache so operators can still inspect configurations.
    if not records:
        records = sorted(
            _servers_by_tenant.get(tenant_id, {}).values(),
            key=lambda server: server.created_at,
        )
    return McpServerListResponse(servers=[_to_response(record) for record in records])


async def get_mcp_server_for_tenant(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    server_id: UUID,
) -> McpServerRecord:
    try:
        result = await session.execute(
            select(McpServerConfig).where(
                McpServerConfig.tenant_id == tenant_id,
                McpServerConfig.id == server_id,
            )
        )
        row = result.scalar_one_or_none()
    except (OSError, SQLAlchemyError):
        row = None
    if row is None:
        cached = _servers_by_tenant.get(tenant_id, {}).get(server_id)
        if cached is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="MCP server not found for this tenant.",
            )
        return cached
    record = _record_from_row(row)
    _cache_server(record)
    return record


async def create_mcp_server_for_tenant(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    request: McpServerCreateRequest,
    actor_id: UUID | None,
    request_id: str | None = None,
) -> McpServerResponse:
    # Reject duplicate server_key within the same tenant.
    try:
        existing = await session.execute(
            select(McpServerConfig.id).where(
                McpServerConfig.tenant_id == tenant_id,
                McpServerConfig.server_key == request.server_key,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="MCP server_key already exists for this tenant.",
            )
    except SQLAlchemyError:
        await session.rollback()

    now = datetime.now(timezone.utc)
    auth_ref = _encrypt_auth_headers(request.auth_headers)
    record_id = uuid4()
    try:
        row = McpServerConfig(
            id=record_id,
            tenant_id=tenant_id,
            name=request.name,
            server_key=request.server_key,
            transport=request.transport.value,
            endpoint_url=request.endpoint_url,
            auth_ref=auth_ref,
            auth_configured=bool(request.auth_headers),
            status=request.status.value,
            timeout_seconds=float(request.timeout_seconds),
            metadata_=dict(request.metadata),
            created_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        await session.flush()
    except SQLAlchemyError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist MCP server configuration.",
        ) from exc

    record = McpServerRecord(
        id=record_id,
        tenant_id=tenant_id,
        name=request.name,
        server_key=request.server_key,
        transport=request.transport,
        endpoint_url=request.endpoint_url,
        auth_headers=dict(request.auth_headers),
        status=request.status,
        timeout_seconds=float(request.timeout_seconds),
        metadata=dict(request.metadata),
        created_by=actor_id,
        created_at=now,
        updated_at=now,
        auth_configured=bool(request.auth_headers),
    )
    _cache_server(record)

    await record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        request_id=request_id,
        action="mcp.server.create",
        resource_type="mcp_server",
        resource_id=record.id,
        details={
            "server_key": record.server_key,
            "name": record.name,
            "transport": record.transport.value,
            "endpoint_url": record.endpoint_url,
            "auth_configured": record.auth_configured,
            "status": record.status.value,
        },
    )
    await session.commit()
    return _to_response(record)


async def update_mcp_server_for_tenant(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    server_id: UUID,
    request: McpServerUpdateRequest,
    actor_id: UUID | None,
    request_id: str | None = None,
) -> McpServerResponse:
    record = await get_mcp_server_for_tenant(session, tenant_id=tenant_id, server_id=server_id)
    changes: dict[str, Any] = {}
    try:
        result = await session.execute(
            select(McpServerConfig).where(
                McpServerConfig.tenant_id == tenant_id,
                McpServerConfig.id == server_id,
            )
        )
        row = result.scalar_one_or_none()
    except SQLAlchemyError:
        row = None
    if row is not None:
        if request.name is not None and request.name != row.name:
            row.name = request.name
            changes["name"] = request.name
        if request.transport is not None and request.transport.value != row.transport:
            row.transport = request.transport.value
            changes["transport"] = request.transport.value
        if request.endpoint_url is not None and request.endpoint_url != row.endpoint_url:
            row.endpoint_url = request.endpoint_url
            changes["endpoint_url"] = request.endpoint_url
        if request.auth_headers is not None:
            new_auth_ref = _encrypt_auth_headers(request.auth_headers)
            row.auth_ref = new_auth_ref
            row.auth_configured = bool(request.auth_headers)
            changes["auth_configured"] = bool(request.auth_headers)
        if (
            request.timeout_seconds is not None
            and abs(request.timeout_seconds - float(row.timeout_seconds)) > 1e-9
        ):
            row.timeout_seconds = float(request.timeout_seconds)
            changes["timeout_seconds"] = float(request.timeout_seconds)
        if request.status is not None and request.status.value != row.status:
            row.status = request.status.value
            changes["status"] = request.status.value
        if request.metadata is not None:
            row.metadata_ = dict(request.metadata)
            changes["metadata"] = dict(request.metadata)
        if changes:
            row.updated_at = datetime.now(timezone.utc)
            await session.flush()
    else:
        # Cached-only fallback: surface a 404 to nudge caller to recreate.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCP server configuration unavailable; cache-only fallback.",
        )

    updated = _record_from_row(row) if row is not None else record
    _cache_server(updated)

    if changes:
        await record_audit_event(
            session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            request_id=request_id,
            action="mcp.server.update",
            resource_type="mcp_server",
            resource_id=updated.id,
            details={
                "server_key": updated.server_key,
                "changes": changes,
            },
        )
        await session.commit()
    return _to_response(updated)


async def delete_mcp_server_for_tenant(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    server_id: UUID,
    actor_id: UUID | None,
    request_id: str | None = None,
) -> None:
    record = await get_mcp_server_for_tenant(session, tenant_id=tenant_id, server_id=server_id)
    try:
        result = await session.execute(
            select(McpServerConfig).where(
                McpServerConfig.tenant_id == tenant_id,
                McpServerConfig.id == server_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is not None:
            await session.delete(row)
            await session.flush()
    except SQLAlchemyError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete MCP server configuration.",
        ) from exc

    _evict_server(tenant_id, server_id)
    await record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        request_id=request_id,
        action="mcp.server.delete",
        resource_type="mcp_server",
        resource_id=record.id,
        details={
            "server_key": record.server_key,
            "name": record.name,
        },
    )
    await session.commit()


async def list_tools_for_server(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    server_id: UUID,
    actor_id: UUID | None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> McpToolsListResponse:
    record = await get_mcp_server_for_tenant(session, tenant_id=tenant_id, server_id=server_id)
    if record.status != McpServerStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="MCP server is not active; cannot list tools.",
        )
    tools = await mcp_list_tools(record.to_endpoint())
    await record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        request_id=request_id,
        action="mcp.tools.list",
        resource_type="mcp_server",
        resource_id=record.id,
        ip_address=ip_address,
        user_agent=user_agent,
        details={
            "server_key": record.server_key,
            "tool_count": len(tools),
            "tool_names": [t.name for t in tools],
        },
    )
    await session.commit()
    return McpToolsListResponse(
        server_id=record.id,
        server_key=record.server_key,
        tools=[_tool_info_to_schema(tool) for tool in tools],
    )


async def invoke_tool_on_server(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    server_id: UUID,
    tool_name: str,
    request: McpToolInvokeRequest,
    principal: Principal,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> McpToolInvokeResponse:
    record = await get_mcp_server_for_tenant(session, tenant_id=tenant_id, server_id=server_id)
    if record.status != McpServerStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="MCP server is not active; cannot invoke tools.",
        )
    started = datetime.now(timezone.utc)
    error_message: str | None = None
    result_value: Any = None
    ok = False
    try:
        call_result: McpToolCallResult = await mcp_call_tool(
            record.to_endpoint(),
            tool_name,
            request.arguments,
        )
        ok = call_result.ok
        result_value = call_result.result
    except McpClientError as exc:
        error_message = str(exc)
    except Exception as exc:  # defensive surface for unexpected transport errors
        error_message = f"{type(exc).__name__}: {exc}"
    latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)

    await record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=principal.user_id,
        request_id=request_id,
        action="mcp.tool.invoke",
        resource_type="mcp_server",
        resource_id=record.id,
        ip_address=ip_address,
        user_agent=user_agent,
        details={
            "server_key": record.server_key,
            "tool_name": tool_name,
            "ok": ok,
            "latency_ms": latency_ms,
            "error": error_message,
            "arguments_keys": sorted(request.arguments.keys()),
        },
    )
    await session.commit()
    return McpToolInvokeResponse(
        server_id=record.id,
        server_key=record.server_key,
        tool_name=tool_name,
        ok=ok,
        result=result_value,
        error=error_message,
        latency_ms=latency_ms,
    )


async def test_mcp_server(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    server_id: UUID,
    actor_id: UUID | None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> McpServerTestResponse:
    record = await get_mcp_server_for_tenant(session, tenant_id=tenant_id, server_id=server_id)
    started = datetime.now(timezone.utc)
    reachable, tools, error = await mcp_probe(record.to_endpoint())
    latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    await record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        request_id=request_id,
        action="mcp.server.test",
        resource_type="mcp_server",
        resource_id=record.id,
        ip_address=ip_address,
        user_agent=user_agent,
        details={
            "server_key": record.server_key,
            "reachable": reachable,
            "tool_count": len(tools),
            "latency_ms": latency_ms,
            "error": error,
        },
    )
    await session.commit()
    return McpServerTestResponse(
        server_id=record.id,
        server_key=record.server_key,
        ok=reachable,
        reachable=reachable,
        tool_count=len(tools),
        tools=[_tool_info_to_schema(tool) for tool in tools],
        error=error,
        latency_ms=latency_ms,
    )


def get_active_mcp_endpoints_for_tenant(
    tenant_id: UUID,
    *,
    server_keys: list[str] | None = None,
) -> list[McpEndpoint]:
    """Return endpoints for active MCP servers in the tenant.

    Used by Agent runtime to mount MCP tools for a given run. If
    ``server_keys`` is None, all active servers are returned; otherwise only
    servers whose ``server_key`` is in the list are included.
    """
    cache = _servers_by_tenant.get(tenant_id, {})
    endpoints: list[McpEndpoint] = []
    wanted = set(server_keys) if server_keys else None
    for record in cache.values():
        if record.status != McpServerStatus.ACTIVE:
            continue
        if wanted is not None and record.server_key not in wanted:
            continue
        endpoints.append(record.to_endpoint())
    return endpoints


async def refresh_cache_for_tenant(session: AsyncSession, *, tenant_id: UUID) -> None:
    """Reload MCP server configs from the database into the in-memory cache."""
    try:
        result = await session.execute(
            select(McpServerConfig).where(McpServerConfig.tenant_id == tenant_id)
        )
        records = [_record_from_row(row) for row in result.scalars().all()]
    except (OSError, SQLAlchemyError):
        return
    cache: dict[UUID, McpServerRecord] = {record.id: record for record in records}
    _servers_by_tenant[tenant_id] = cache
