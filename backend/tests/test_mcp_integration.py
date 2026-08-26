"""Unit tests for MCP integration — client, service, runtime mounting.

Covers:
- MCP client JSON-RPC parsing (HTTP + SSE), error handling, tool discovery
- McpServerConfig model + schemas (validation, encryption of auth headers)
- Service CRUD + audit events + cache fallback
- Agent runtime mounting: ``_enrich_with_mcp_tools`` injects diagnostics
  into payload.context and tolerates unreachable servers.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import httpx

from app.mcp.client import (
    McpClientError,
    McpEndpoint,
    McpToolInfo,
    call_tool,
    list_tools,
    probe,
)
from app.schemas.agents import AgentRunRequest
from app.schemas.mcp import (
    McpServerCreateRequest,
    McpServerStatus,
    McpServerUpdateRequest,
    McpTransport,
)
from app.services import mcp_service
from app.services.mcp_service import (
    McpServerRecord,
    _cache_server,
    _decrypt_auth_headers,
    _encrypt_auth_headers,
    _servers_by_tenant,
    create_mcp_server_for_tenant,
    delete_mcp_server_for_tenant,
    get_active_mcp_endpoints_for_tenant,
    get_mcp_server_for_tenant,
    invoke_tool_on_server,
    list_mcp_servers_for_tenant,
    list_tools_for_server,
    test_mcp_server as probe_mcp_server,
    update_mcp_server_for_tenant,
)
from app.api.deps import Principal


_REAL_ASYNC_CLIENT = httpx.AsyncClient


def _async_client_factory(transport: httpx.MockTransport):
    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("transport", None)
        return _REAL_ASYNC_CLIENT(*args, **kwargs, transport=transport)

    return factory


def _endpoint(
    *,
    transport: str = "http",
    auth_headers: dict[str, str] | None = None,
    timeout: float = 5.0,
) -> McpEndpoint:
    return McpEndpoint(
        server_id=str(uuid4()),
        server_key="test-server",
        transport=transport,
        endpoint_url="http://localhost:9000/mcp",
        auth_headers=auth_headers or {},
        timeout_seconds=timeout,
    )


class _FakeScalars:
    def __init__(self, items: list[Any] | None = None) -> None:
        self._items = items or []

    def all(self):
        return self._items

    def first(self):
        return self._items[0] if self._items else None

    def one_or_none(self):
        if not self._items:
            return None
        if len(self._items) == 1:
            return self._items[0]
        raise Exception("multiple rows")


class _FakeResult:
    def __init__(self, items: list[Any] | None = None) -> None:
        self._scalars = _FakeScalars(items)

    def scalars(self):
        return self._scalars

    def scalar_one_or_none(self):
        items = self._scalars._items
        if not items:
            return None
        if len(items) == 1:
            return items[0]
        raise Exception("multiple rows")


class _FakeSession:
    """Minimal AsyncSession stub for service tests (no real DB needed)."""

    def __init__(self, *, rows: list[Any] | None = None) -> None:
        self._rows = rows or []
        self.added: list[Any] = []
        self.committed = 0
        self.rolled_back = 0
        self.flushed = 0
        self.deleted: list[Any] = []

    async def execute(self, *_args: Any, **_kwargs: Any) -> _FakeResult:
        return _FakeResult(self._rows)

    def add(self, value: Any) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        self.flushed += 1

    async def commit(self) -> None:
        self.committed += 1

    async def rollback(self) -> None:
        self.rolled_back += 1

    async def delete(self, value: Any) -> None:
        self.deleted.append(value)

    async def get(self, *_args: Any, **_kwargs: Any) -> None:
        return None


def _principal(*, tenant_id: UUID | None = None, user_id: UUID | None = None) -> Principal:
    from app.core.security import Permission

    class _P:
        def __init__(self) -> None:
            self.tenant_id = tenant_id or uuid4()
            self.user_id = user_id or uuid4()
            self.permissions = {Permission.MCP_READ, Permission.MCP_WRITE, Permission.MCP_INVOKE}
            self.is_tenant_admin = True
            self.role = "tenant_admin"

    return _P()  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Client tests
# ---------------------------------------------------------------------------


class McpClientHttpTests(unittest.IsolatedAsyncioTestCase):
    async def _patch_client(self, transport: httpx.MockTransport) -> Any:
        return patch(
            "app.mcp.client.httpx.AsyncClient",
            side_effect=_async_client_factory(transport),
        )

    async def test_list_tools_http_json_response(self) -> None:
        tools_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "tools": [
                    {
                        "name": "search_kb",
                        "description": "Search the knowledge base",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                            "required": ["query"],
                        },
                    },
                    {
                        "name": "echo",
                        "description": None,
                        "inputSchema": None,
                    },
                ]
            },
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=tools_payload)

        endpoint = _endpoint()
        with await self._patch_client(httpx.MockTransport(handler)) as _:
            # Stub initialize to skip the handshake's extra requests.
            with patch("app.mcp.client._ensure_initialised", new=AsyncMock()):
                tools = await list_tools(endpoint)

        self.assertEqual(len(tools), 2)
        self.assertEqual(tools[0].name, "search_kb")
        self.assertEqual(tools[0].description, "Search the knowledge base")
        self.assertEqual(tools[0].input_schema["required"], ["query"])
        self.assertEqual(tools[1].name, "echo")
        self.assertEqual(tools[1].input_schema["type"], "object")

    async def test_list_tools_sse_stream(self) -> None:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"tools": [{"name": "tool_a", "inputSchema": {}}]},
        }
        sse_text = f"event: message\ndata: {json.dumps(payload)}\n\n"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=sse_text,
                headers={"content-type": "text/event-stream"},
            )

        endpoint = _endpoint(transport="sse")
        with await self._patch_client(httpx.MockTransport(handler)):
            with patch("app.mcp.client._ensure_initialised", new=AsyncMock()):
                tools = await list_tools(endpoint)

        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].name, "tool_a")

    async def test_list_tools_raises_on_jsonrpc_error(self) -> None:
        error_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32601, "message": "Method not found"},
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=error_payload)

        endpoint = _endpoint()
        with await self._patch_client(httpx.MockTransport(handler)):
            with patch("app.mcp.client._ensure_initialised", new=AsyncMock()):
                with self.assertRaises(McpClientError) as ctx:
                    await list_tools(endpoint)
        self.assertIn("Method not found", str(ctx.exception))

    async def test_list_tools_raises_on_http_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="internal error")

        endpoint = _endpoint()
        with await self._patch_client(httpx.MockTransport(handler)):
            with patch("app.mcp.client._ensure_initialised", new=AsyncMock()):
                with self.assertRaises(McpClientError) as ctx:
                    await list_tools(endpoint)
        self.assertIn("HTTP 500", str(ctx.exception))

    async def test_call_tool_returns_result(self) -> None:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [{"type": "text", "text": "hello"}],
                "isError": False,
            },
        }

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert body["method"] == "tools/call"
            assert body["params"]["name"] == "search_kb"
            return httpx.Response(200, json=payload)

        endpoint = _endpoint()
        with await self._patch_client(httpx.MockTransport(handler)):
            with patch("app.mcp.client._ensure_initialised", new=AsyncMock()):
                result = await call_tool(endpoint, "search_kb", {"query": "x"})
        self.assertTrue(result.ok)
        self.assertEqual(result.result["content"][0]["text"], "hello")

    async def test_probe_returns_false_on_failure(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="unavailable")

        endpoint = _endpoint()
        with await self._patch_client(httpx.MockTransport(handler)):
            with patch("app.mcp.client._ensure_initialised", new=AsyncMock()):
                ok, tools, error = await probe(endpoint)
        self.assertFalse(ok)
        self.assertEqual(tools, [])
        self.assertIn("HTTP 503", error or "")


# ---------------------------------------------------------------------------
# Encryption + model tests
# ---------------------------------------------------------------------------


class McpAuthEncryptionTests(unittest.TestCase):
    def test_encrypt_decrypt_round_trip(self) -> None:
        headers = {"Authorization": "Bearer abc", "X-Tenant": "t1"}
        encrypted = _encrypt_auth_headers(headers)
        self.assertIsNotNone(encrypted)
        self.assertNotIn("Bearer", encrypted)
        decrypted = _decrypt_auth_headers(encrypted)
        self.assertEqual(decrypted, headers)

    def test_encrypt_none_returns_none(self) -> None:
        self.assertIsNone(_encrypt_auth_headers({}))

    def test_decrypt_invalid_returns_empty(self) -> None:
        self.assertEqual(_decrypt_auth_headers("not-a-valid-token"), {})
        self.assertEqual(_decrypt_auth_headers(None), {})


class McpSchemaTests(unittest.TestCase):
    def test_create_request_validates_endpoint_scheme(self) -> None:
        with self.assertRaises(ValueError):
            McpServerCreateRequest(
                name="bad",
                server_key="bad",
                endpoint_url="ftp://nope",
            )

    def test_create_request_server_key_pattern(self) -> None:
        with self.assertRaises(ValueError):
            McpServerCreateRequest(
                name="bad",
                server_key="Bad Key!",  # invalid chars
                endpoint_url="http://localhost:9000",
            )

    def test_create_request_defaults(self) -> None:
        req = McpServerCreateRequest(
            name="ok",
            server_key="ok-key_1",
            endpoint_url="http://localhost:9000/mcp",
        )
        self.assertEqual(req.transport, McpTransport.HTTP)
        self.assertEqual(req.status, McpServerStatus.ACTIVE)
        self.assertEqual(req.timeout_seconds, 30.0)
        self.assertEqual(req.auth_headers, {})


# ---------------------------------------------------------------------------
# Service CRUD + audit tests (with patched audit + DB session)
# ---------------------------------------------------------------------------


class McpServiceCrudTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        _servers_by_tenant.clear()
        self._audit_calls: list[dict[str, Any]] = []

        async def _fake_audit(session: Any, **kwargs: Any) -> None:
            self._audit_calls.append(kwargs)

        self._audit_patch = patch(
            "app.services.mcp_service.record_audit_event",
            new=_fake_audit,
        )
        self._audit_patch.start()

    async def asyncTearDown(self) -> None:
        self._audit_patch.stop()
        _servers_by_tenant.clear()

    async def test_create_then_list_returns_cached_record(self) -> None:
        tenant_id = uuid4()
        actor_id = uuid4()
        session = _FakeSession()
        req = McpServerCreateRequest(
            name="kb-search",
            server_key="kb-search",
            endpoint_url="http://localhost:9000/mcp",
            auth_headers={"Authorization": "Bearer tok"},
            timeout_seconds=15.0,
        )
        response = await create_mcp_server_for_tenant(
            session,
            tenant_id=tenant_id,
            request=req,
            actor_id=actor_id,
        )
        self.assertTrue(response.auth_configured)
        self.assertEqual(response.server_key, "kb-search")
        self.assertEqual(response.timeout_seconds, 15.0)
        self.assertEqual(session.committed, 1)
        # Audit recorded for create
        self.assertEqual(len(self._audit_calls), 1)
        self.assertEqual(self._audit_calls[0]["action"], "mcp.server.create")

        # List should pick up the cached record even with empty DB.
        list_response = await list_mcp_servers_for_tenant(_FakeSession(), tenant_id=tenant_id)
        self.assertEqual(len(list_response.servers), 1)
        self.assertEqual(list_response.servers[0].id, response.id)

    async def test_create_rejects_duplicate_server_key(self) -> None:
        tenant_id = uuid4()
        # First create succeeds and caches.
        session1 = _FakeSession()
        await create_mcp_server_for_tenant(
            session1,
            tenant_id=tenant_id,
            request=McpServerCreateRequest(
                name="s1",
                server_key="dup-key",
                endpoint_url="http://localhost:9000/mcp",
            ),
            actor_id=uuid4(),
        )
        # Second create with same key hits the cache lookup path (no DB rows
        # returned by _FakeSession) so the duplicate detection runs against
        # the cached record via the DB-exists check returning None — we
        # therefore assert that a duplicate-key create still surfaces a 409
        # when a DB row exists.
        from fastapi import HTTPException

        row = mcp_service.McpServerConfig(
            id=uuid4(),
            tenant_id=tenant_id,
            name="s1",
            server_key="dup-key",
            transport="http",
            endpoint_url="http://localhost:9000/mcp",
            auth_ref=None,
            auth_configured=False,
            status="active",
            timeout_seconds=30.0,
            metadata_={},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session2 = _FakeSession(rows=[row.id])  # exists check returns truthy
        with self.assertRaises(HTTPException) as ctx:
            await create_mcp_server_for_tenant(
                session2,
                tenant_id=tenant_id,
                request=McpServerCreateRequest(
                    name="s2",
                    server_key="dup-key",
                    endpoint_url="http://localhost:9000/mcp",
                ),
                actor_id=uuid4(),
            )
        self.assertEqual(ctx.exception.status_code, 409)

    async def test_update_changes_fields_and_audits(self) -> None:
        tenant_id = uuid4()
        actor_id = uuid4()
        session = _FakeSession()
        created = await create_mcp_server_for_tenant(
            session,
            tenant_id=tenant_id,
            request=McpServerCreateRequest(
                name="orig",
                server_key="orig-key",
                endpoint_url="http://localhost:9000/mcp",
            ),
            actor_id=actor_id,
        )
        # Simulate DB row existing for the update path.
        row = mcp_service.McpServerConfig(
            id=created.id,
            tenant_id=tenant_id,
            name="orig",
            server_key="orig-key",
            transport="http",
            endpoint_url="http://localhost:9000/mcp",
            auth_ref=None,
            auth_configured=False,
            status="active",
            timeout_seconds=30.0,
            metadata_={},
            created_at=created.created_at,
            updated_at=created.updated_at,
        )
        session_with_row = _FakeSession(rows=[row])
        updated = await update_mcp_server_for_tenant(
            session_with_row,
            tenant_id=tenant_id,
            server_id=created.id,
            request=McpServerUpdateRequest(
                name="renamed",
                status=McpServerStatus.DISABLED,
                timeout_seconds=60.0,
            ),
            actor_id=actor_id,
        )
        self.assertEqual(updated.name, "renamed")
        self.assertEqual(updated.status, McpServerStatus.DISABLED)
        self.assertEqual(updated.timeout_seconds, 60.0)
        # Audit recorded for update
        update_audits = [c for c in self._audit_calls if c["action"] == "mcp.server.update"]
        self.assertEqual(len(update_audits), 1)
        self.assertIn("name", update_audits[0]["details"]["changes"])

    async def test_delete_evicts_cache_and_audits(self) -> None:
        tenant_id = uuid4()
        actor_id = uuid4()
        session = _FakeSession()
        created = await create_mcp_server_for_tenant(
            session,
            tenant_id=tenant_id,
            request=McpServerCreateRequest(
                name="to-delete",
                server_key="del-key",
                endpoint_url="http://localhost:9000/mcp",
            ),
            actor_id=actor_id,
        )
        row = mcp_service.McpServerConfig(
            id=created.id,
            tenant_id=tenant_id,
            name="to-delete",
            server_key="del-key",
            transport="http",
            endpoint_url="http://localhost:9000/mcp",
            auth_ref=None,
            auth_configured=False,
            status="active",
            timeout_seconds=30.0,
            metadata_={},
            created_at=created.created_at,
            updated_at=created.updated_at,
        )
        session_with_row = _FakeSession(rows=[row])
        await delete_mcp_server_for_tenant(
            session_with_row,
            tenant_id=tenant_id,
            server_id=created.id,
            actor_id=actor_id,
        )
        # Cache evicted
        self.assertNotIn(created.id, _servers_by_tenant.get(tenant_id, {}))
        # Audit recorded for delete
        delete_audits = [c for c in self._audit_calls if c["action"] == "mcp.server.delete"]
        self.assertEqual(len(delete_audits), 1)

    async def test_get_mcp_server_404_when_missing(self) -> None:
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as ctx:
            await get_mcp_server_for_tenant(
                _FakeSession(),
                tenant_id=uuid4(),
                server_id=uuid4(),
            )
        self.assertEqual(ctx.exception.status_code, 404)


# ---------------------------------------------------------------------------
# Service tool discovery + invocation tests
# ---------------------------------------------------------------------------


class McpServiceToolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        _servers_by_tenant.clear()
        self._audit_calls: list[dict[str, Any]] = []

        async def _fake_audit(session: Any, **kwargs: Any) -> None:
            self._audit_calls.append(kwargs)

        self._audit_patch = patch(
            "app.services.mcp_service.record_audit_event",
            new=_fake_audit,
        )
        self._audit_patch.start()

    async def asyncTearDown(self) -> None:
        self._audit_patch.stop()
        _servers_by_tenant.clear()

    async def _seed_record(
        self, *, status: McpServerStatus = McpServerStatus.ACTIVE
    ) -> tuple[UUID, UUID, McpServerRecord]:
        tenant_id = uuid4()
        record = McpServerRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            name="seed",
            server_key="seed-key",
            transport=McpTransport.HTTP,
            endpoint_url="http://localhost:9000/mcp",
            auth_headers={},
            status=status,
            timeout_seconds=5.0,
            metadata={},
            created_by=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            auth_configured=False,
        )
        _cache_server(record)
        return tenant_id, record.id, record

    async def test_list_tools_invokes_client_and_audits(self) -> None:
        tenant_id, server_id, _ = await self._seed_record()
        tools = [McpToolInfo(name="t1", description="d", input_schema={})]

        with patch("app.services.mcp_service.mcp_list_tools", new=AsyncMock(return_value=tools)):
            response = await list_tools_for_server(
                _FakeSession(),
                tenant_id=tenant_id,
                server_id=server_id,
                actor_id=uuid4(),
            )
        self.assertEqual(response.server_id, server_id)
        self.assertEqual(len(response.tools), 1)
        self.assertEqual(response.tools[0].name, "t1")
        audits = [c for c in self._audit_calls if c["action"] == "mcp.tools.list"]
        self.assertEqual(len(audits), 1)
        self.assertEqual(audits[0]["details"]["tool_count"], 1)

    async def test_list_tools_rejects_disabled_server(self) -> None:
        from fastapi import HTTPException

        tenant_id, server_id, _ = await self._seed_record(status=McpServerStatus.DISABLED)
        with self.assertRaises(HTTPException) as ctx:
            await list_tools_for_server(
                _FakeSession(),
                tenant_id=tenant_id,
                server_id=server_id,
                actor_id=uuid4(),
            )
        self.assertEqual(ctx.exception.status_code, 409)

    async def test_invoke_tool_returns_error_on_client_failure(self) -> None:
        from app.schemas.mcp import McpToolInvokeRequest

        tenant_id, server_id, _ = await self._seed_record()
        principal = _principal(tenant_id=tenant_id)

        async def _fail(*_args: Any, **_kwargs: Any) -> Any:
            raise McpClientError("connection refused")

        with patch("app.services.mcp_service.mcp_call_tool", new=_fail):
            response = await invoke_tool_on_server(
                _FakeSession(),
                tenant_id=tenant_id,
                server_id=server_id,
                tool_name="search",
                request=McpToolInvokeRequest(arguments={"q": "x"}),
                principal=principal,  # type: ignore[arg-type]
            )
        self.assertFalse(response.ok)
        self.assertEqual(response.error, "connection refused")
        audits = [c for c in self._audit_calls if c["action"] == "mcp.tool.invoke"]
        self.assertEqual(len(audits), 1)
        self.assertFalse(audits[0]["details"]["ok"])

    async def test_test_server_probes_and_returns_tools(self) -> None:
        tenant_id, server_id, _ = await self._seed_record()
        tools = [McpToolInfo(name="t", description=None, input_schema={})]
        with patch(
            "app.services.mcp_service.mcp_probe",
            new=AsyncMock(return_value=(True, tools, None)),
        ):
            response = await probe_mcp_server(
                _FakeSession(),
                tenant_id=tenant_id,
                server_id=server_id,
                actor_id=uuid4(),
            )
        self.assertTrue(response.ok)
        self.assertTrue(response.reachable)
        self.assertEqual(response.tool_count, 1)


# ---------------------------------------------------------------------------
# Agent runtime mounting test
# ---------------------------------------------------------------------------


class AgentRuntimeMcpMountingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        _servers_by_tenant.clear()

    async def asyncTearDown(self) -> None:
        _servers_by_tenant.clear()

    async def test_enrich_with_mcp_tools_injects_diagnostics(self) -> None:
        from app.services.agent_runtime_service import _enrich_with_mcp_tools

        tenant_id = uuid4()
        record = McpServerRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            name="s",
            server_key="s-key",
            transport=McpTransport.HTTP,
            endpoint_url="http://localhost:9000/mcp",
            auth_headers={},
            status=McpServerStatus.ACTIVE,
            timeout_seconds=5.0,
            metadata={},
            created_by=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            auth_configured=False,
        )
        _cache_server(record)
        principal = _principal(tenant_id=tenant_id)
        payload = AgentRunRequest(input="hi")

        tools = [McpToolInfo(name="search", description="d", input_schema={})]
        with patch("app.mcp.client.list_tools", new=AsyncMock(return_value=tools)):
            enriched = await _enrich_with_mcp_tools(
                _FakeSession(),
                payload,
                principal,  # type: ignore[arg-type]
            )
        mcp = enriched.context["mcp"]
        self.assertEqual(mcp["total_tools"], 1)
        self.assertEqual(len(mcp["mounted"]), 1)
        self.assertEqual(mcp["mounted"][0]["server_key"], "s-key")
        self.assertEqual(mcp["mounted"][0]["tool_names"], ["search"])
        self.assertIsNone(mcp["mounted"][0]["error"])

    async def test_enrich_with_mcp_tools_tolerates_unreachable_server(self) -> None:
        from app.services.agent_runtime_service import _enrich_with_mcp_tools

        tenant_id = uuid4()
        record = McpServerRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            name="s",
            server_key="bad-key",
            transport=McpTransport.HTTP,
            endpoint_url="http://localhost:9999/mcp",
            auth_headers={},
            status=McpServerStatus.ACTIVE,
            timeout_seconds=5.0,
            metadata={},
            created_by=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            auth_configured=False,
        )
        _cache_server(record)
        principal = _principal(tenant_id=tenant_id)
        payload = AgentRunRequest(input="hi")

        async def _fail(*_args: Any, **_kwargs: Any) -> Any:
            raise McpClientError("connection refused")

        with patch("app.mcp.client.list_tools", new=_fail):
            enriched = await _enrich_with_mcp_tools(
                _FakeSession(),
                payload,
                principal,  # type: ignore[arg-type]
            )
        mcp = enriched.context["mcp"]
        self.assertEqual(mcp["total_tools"], 0)
        self.assertEqual(mcp["mounted"][0]["error"], "connection refused")
        self.assertEqual(mcp["mounted"][0]["tool_count"], 0)

    async def test_enrich_with_mcp_tools_respects_explicit_server_keys(self) -> None:
        from app.services.agent_runtime_service import _enrich_with_mcp_tools

        tenant_id = uuid4()
        for key in ("keep-key", "skip-key"):
            _cache_server(
                McpServerRecord(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    name=key,
                    server_key=key,
                    transport=McpTransport.HTTP,
                    endpoint_url=f"http://localhost:9000/{key}",
                    auth_headers={},
                    status=McpServerStatus.ACTIVE,
                    timeout_seconds=5.0,
                    metadata={},
                    created_by=None,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                    auth_configured=False,
                )
            )
        principal = _principal(tenant_id=tenant_id)
        payload = AgentRunRequest(input="hi", mcp_server_keys=["keep-key"])

        with patch(
            "app.mcp.client.list_tools",
            new=AsyncMock(return_value=[]),
        ):
            enriched = await _enrich_with_mcp_tools(
                _FakeSession(),
                payload,
                principal,  # type: ignore[arg-type]
            )
        mounted = enriched.context["mcp"]["mounted"]
        self.assertEqual(len(mounted), 1)
        self.assertEqual(mounted[0]["server_key"], "keep-key")

    async def test_get_active_endpoints_filters_by_keys(self) -> None:
        tenant_id = uuid4()
        for key in ("a", "b"):
            _cache_server(
                McpServerRecord(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    name=key,
                    server_key=key,
                    transport=McpTransport.HTTP,
                    endpoint_url=f"http://localhost:9000/{key}",
                    auth_headers={},
                    status=McpServerStatus.ACTIVE,
                    timeout_seconds=5.0,
                    metadata={},
                    created_by=None,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                    auth_configured=False,
                )
            )
        # Disabled server should be excluded.
        _cache_server(
            McpServerRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                name="disabled",
                server_key="disabled",
                transport=McpTransport.HTTP,
                endpoint_url="http://localhost:9000/disabled",
                auth_headers={},
                status=McpServerStatus.DISABLED,
                timeout_seconds=5.0,
                metadata={},
                created_by=None,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                auth_configured=False,
            )
        )
        endpoints = get_active_mcp_endpoints_for_tenant(tenant_id)
        self.assertEqual({e.server_key for e in endpoints}, {"a", "b"})

        filtered = get_active_mcp_endpoints_for_tenant(tenant_id, server_keys=["a"])
        self.assertEqual([e.server_key for e in filtered], ["a"])


if __name__ == "__main__":
    unittest.main()
