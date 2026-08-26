"""MCP (Model Context Protocol) server configuration model.

Stores per-tenant MCP server connections so Agents can discover and invoke
external tools via the open MCP protocol (HTTP JSON-RPC transport).
"""

from typing import Any
from uuid import UUID

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field

from app.models.base import TenantScopedMixin, TimestampMixin, UUIDMixin


class McpServerConfig(UUIDMixin, TenantScopedMixin, TimestampMixin, table=True):
    __tablename__ = "mcp_server_configs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "server_key", name="uq_mcp_servers_tenant_key"),
    )

    name: str = Field(max_length=120, nullable=False)
    server_key: str = Field(max_length=120, index=True, nullable=False)
    transport: str = Field(default="http", max_length=20, nullable=False)
    endpoint_url: str = Field(max_length=1024, nullable=False)
    # Encrypted blob (Fernet) holding auth headers / API key JSON. None = no auth.
    auth_ref: str | None = Field(default=None, max_length=4096)
    auth_configured: bool = Field(default=False, nullable=False)
    status: str = Field(default="active", max_length=30, index=True, nullable=False)
    timeout_seconds: float = Field(default=30.0, nullable=False)
    # Optional metadata: description, vendor, capabilities, icon, etc.
    metadata_: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSON, nullable=False),
        alias="metadata",
    )
    created_by: UUID | None = Field(default=None, foreign_key="users.id", index=True)
