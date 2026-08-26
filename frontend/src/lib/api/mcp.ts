import { apiGet } from "./core";

export type McpTransport = "stdio" | "http" | "sse";
export type McpServerStatus = "active" | "inactive" | "error";

export interface McpServerResponse {
  id: string;
  tenant_id: string;
  name: string;
  server_key: string;
  transport: McpTransport;
  endpoint_url: string;
  auth_configured: boolean;
  status: McpServerStatus;
  timeout_seconds: number;
  metadata: Record<string, unknown>;
  created_by: string | null;
  created_at: string;
}

export interface McpServerListResponse {
  servers: McpServerResponse[];
}

export const mcpApi = {
  listServers: () => apiGet<McpServerListResponse>("/api/v1/mcp/servers"),
};
