"""MCP (Model Context Protocol) HTTP/SSE client.

Minimal client for the open MCP protocol over HTTP JSON-RPC 2.0:
- ``initialize`` (best-effort; many servers accept direct ``tools/list``)
- ``tools/list``
- ``tools/call``

Designed for private / on-prem deployments where MCP servers expose an
HTTP endpoint (e.g. ``http://localhost:9000/mcp``). Auth headers are
passed verbatim; SSE transport reuses the same JSON-RPC envelope.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, cast
from uuid import uuid4

import httpx

# Protocol constants — minimal subset of MCP 2024-11-05 spec.
_PROTOCOL_VERSION = "2024-11-05"
_CLIENT_NAME = "agenthive"
_CLIENT_VERSION = "1.0"


class McpClientError(RuntimeError):
    """Raised when an MCP server returns a JSON-RPC error or transport fails."""


@dataclass(frozen=True)
class McpEndpoint:
    """Resolved MCP server connection target."""

    server_id: str
    server_key: str
    transport: str  # "http" or "sse"
    endpoint_url: str
    auth_headers: dict[str, str]
    timeout_seconds: float


@dataclass(frozen=True)
class McpToolInfo:
    name: str
    description: str | None
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class McpToolCallResult:
    ok: bool
    result: Any
    error: str | None
    latency_ms: int


def _next_request_id() -> int:
    # JSON-RPC id must be unique per session; uuid4 int is safe and stateless.
    return abs(uuid4().int) % (1 << 31)


def _build_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": _PROTOCOL_VERSION,
    }
    if extra:
        headers.update({k: str(v) for k, v in extra.items() if v is not None})
    return headers


def _parse_jsonrpc_payload(response: httpx.Response) -> dict[str, Any]:
    """Extract the JSON-RPC payload from an HTTP/SSE response."""
    if response.status_code >= 400:
        raise McpClientError(
            f"MCP server returned HTTP {response.status_code}: {response.text[:200]}"
        )
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        return _parse_sse_payload(response.text)
    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise McpClientError(f"MCP server returned non-JSON response: {exc}") from exc
    if not isinstance(payload, dict):
        raise McpClientError("MCP server returned a non-object JSON-RPC payload.")
    return cast(dict[str, Any], payload)


def _parse_sse_payload(text: str) -> dict[str, Any]:
    """Parse a Server-Sent Events stream and return the first JSON data event."""
    for raw_event in text.split("\n\n"):
        data_lines = []
        for line in raw_event.splitlines():
            if line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())
        if not data_lines:
            continue
        try:
            payload = json.loads("\n".join(data_lines))
            if isinstance(payload, dict):
                return cast(dict[str, Any], payload)
        except json.JSONDecodeError:
            continue
    raise McpClientError("MCP SSE stream contained no parsable data event.")


def _raise_on_jsonrpc_error(payload: dict[str, Any], method: str) -> None:
    if "error" not in payload:
        return
    error = payload.get("error") or {}
    code = error.get("code")
    message = error.get("message") or "unknown MCP error"
    raise McpClientError(f"MCP '{method}' failed (code={code}): {message}")


async def _post_jsonrpc(
    endpoint: McpEndpoint,
    method: str,
    params: dict[str, Any] | None = None,
    *,
    initialize: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": _next_request_id(),
        "method": method,
    }
    if params is not None:
        payload["params"] = params
    headers = _build_headers(endpoint.auth_headers)
    try:
        async with httpx.AsyncClient(timeout=endpoint.timeout_seconds) as client:
            response = await client.post(endpoint.endpoint_url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        raise McpClientError(f"MCP HTTP transport error on '{method}': {exc}") from exc
    parsed = _parse_jsonrpc_payload(response)
    _raise_on_jsonrpc_error(parsed, method)
    return parsed


async def _ensure_initialised(endpoint: McpEndpoint) -> None:
    """Best-effort MCP initialize handshake.

    Many servers accept ``tools/list`` directly. We attempt initialize first
    and silently ignore failures so the platform degrades gracefully when
    talking to minimalist MCP implementations.
    """
    try:
        await _post_jsonrpc(
            endpoint,
            "initialize",
            {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {
                    "name": _CLIENT_NAME,
                    "version": _CLIENT_VERSION,
                },
            },
        )
        # Per spec, the server expects an `initialized` notification afterwards.
        # Notifications have no id and expect no response.
        try:
            async with httpx.AsyncClient(timeout=endpoint.timeout_seconds) as client:
                await client.post(
                    endpoint.endpoint_url,
                    json={
                        "jsonrpc": "2.0",
                        "method": "notifications/initialized",
                    },
                    headers=_build_headers(endpoint.auth_headers),
                )
        except httpx.HTTPError:
            pass
    except McpClientError:
        # Tolerate servers that do not implement initialize.
        return


def _coerce_tool_info(raw: dict[str, Any]) -> McpToolInfo:
    return McpToolInfo(
        name=str(raw.get("name") or ""),
        description=raw.get("description"),
        input_schema=raw.get("inputSchema") or {"type": "object", "properties": {}},
    )


async def list_tools(endpoint: McpEndpoint) -> list[McpToolInfo]:
    """Discover tools exposed by an MCP server."""
    await _ensure_initialised(endpoint)
    payload = await _post_jsonrpc(endpoint, "tools/list")
    result = payload.get("result") or {}
    tools_raw = result.get("tools") or []
    if not isinstance(tools_raw, list):
        raise McpClientError("MCP 'tools/list' returned non-list tools field.")
    return [_coerce_tool_info(item) for item in tools_raw if isinstance(item, dict)]


async def call_tool(
    endpoint: McpEndpoint,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> McpToolCallResult:
    """Invoke an MCP tool by name with JSON arguments."""
    await _ensure_initialised(endpoint)
    payload = await _post_jsonrpc(
        endpoint,
        "tools/call",
        {
            "name": tool_name,
            "arguments": arguments or {},
        },
    )
    result = payload.get("result")
    # MCP returns content blocks; we surface the raw result for callers to
    # interpret (text/image/etc. per spec).
    return McpToolCallResult(
        ok=True,
        result=result,
        error=None,
        latency_ms=0,  # set by caller with perf_counter
    )


async def probe(endpoint: McpEndpoint) -> tuple[bool, list[McpToolInfo], str | None]:
    """Lightweight reachability + tool-discovery probe used by connection tests."""
    try:
        tools = await list_tools(endpoint)
        return True, tools, None
    except McpClientError as exc:
        return False, [], str(exc)
    except Exception as exc:  # defensive: surface unexpected transport issues
        return False, [], f"{type(exc).__name__}: {exc}"
