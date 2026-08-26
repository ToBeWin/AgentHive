"""MCP (Model Context Protocol) integration package.

Provides AgentHive Agents with external tool discovery and invocation via
the open MCP protocol. HTTP JSON-RPC transport is the primary mode for
private / on-prem deployments.
"""

from app.mcp.client import (
    McpClientError,
    McpEndpoint,
    McpToolCallResult,
    McpToolInfo,
    call_tool,
    list_tools,
    probe,
)

__all__ = [
    "McpClientError",
    "McpEndpoint",
    "McpToolCallResult",
    "McpToolInfo",
    "call_tool",
    "list_tools",
    "probe",
]
