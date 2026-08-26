"""MCP (Model Context Protocol) server schemas.

Covers CRUD, tool discovery, tool invocation, and audit-friendly responses.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class McpTransport(StrEnum):
    HTTP = "http"
    SSE = "sse"


class McpServerStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"


class McpServerCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    server_key: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    transport: McpTransport = Field(default=McpTransport.HTTP)
    endpoint_url: str = Field(min_length=1, max_length=1024)
    auth_headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float = Field(default=30.0, ge=1.0, le=300.0)
    status: McpServerStatus = Field(default=McpServerStatus.ACTIVE)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_endpoint(self) -> "McpServerCreateRequest":
        if not self.endpoint_url.startswith(("http://", "https://")):
            raise ValueError("endpoint_url must use http or https scheme")
        return self


class McpServerUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    transport: McpTransport | None = None
    endpoint_url: str | None = Field(default=None, min_length=1, max_length=1024)
    auth_headers: dict[str, str] | None = None
    timeout_seconds: float | None = Field(default=None, ge=1.0, le=300.0)
    status: McpServerStatus | None = None
    metadata: dict[str, Any] | None = None


class McpServerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    server_key: str
    transport: McpTransport
    endpoint_url: str
    auth_configured: bool
    status: McpServerStatus
    timeout_seconds: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime


class McpServerListResponse(BaseModel):
    servers: list[McpServerResponse]


class McpToolSchema(BaseModel):
    """JSON-Schema description of a tool's arguments."""

    type: str = "object"
    properties: dict[str, Any] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)


class McpToolInfo(BaseModel):
    name: str
    description: str | None = None
    input_schema: McpToolSchema = Field(default_factory=McpToolSchema)


class McpToolsListResponse(BaseModel):
    server_id: UUID
    server_key: str
    tools: list[McpToolInfo]


class McpToolInvokeRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


class McpToolInvokeResponse(BaseModel):
    server_id: UUID
    server_key: str
    tool_name: str
    ok: bool
    result: Any = None
    error: str | None = None
    latency_ms: int


class McpServerTestResponse(BaseModel):
    server_id: UUID
    server_key: str
    ok: bool
    reachable: bool
    tool_count: int
    tools: list[McpToolInfo]
    error: str | None = None
    latency_ms: int
