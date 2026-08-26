import { apiDownloadText, apiGet } from "./core";

export interface AuditLogItem {
  id: string;
  tenant_id: string;
  request_id: string | null;
  actor_id: string | null;
  actor_type: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  status: string;
  ip_address: string | null;
  user_agent: string | null;
  details: Record<string, unknown>;
  created_at: string;
}

export interface AuditLogListResponse {
  items: AuditLogItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface AuditLogFilters {
  action?: string;
  actor_id?: string;
  resource_type?: string;
  status?: string;
  request_id?: string;
  created_from?: string;
  created_to?: string;
  limit?: number;
  offset?: number;
}

export const auditApi = {
  getAuditLogs: (filters: AuditLogFilters = {}) => {
    const params = auditLogParams(filters);
    return apiGet<AuditLogListResponse>(`/api/v1/audit/logs?${params.toString()}`);
  },
  exportAuditLogsCsv: (filters: AuditLogFilters = {}) => {
    const params = auditLogParams({ ...filters, limit: filters.limit ?? 5000 });
    params.delete("offset");
    return apiDownloadText(`/api/v1/audit/logs/export?${params.toString()}`);
  },
  exportAuditLogsJson: (filters: AuditLogFilters = {}) => {
    const params = auditLogParams({ ...filters, limit: filters.limit ?? 5000 });
    params.delete("offset");
    params.set("format", "json");
    return apiDownloadText(`/api/v1/audit/logs/export?${params.toString()}`);
  },
};

function auditLogParams(filters: AuditLogFilters) {
  const params = new URLSearchParams();
  params.set("limit", String(filters.limit ?? 50));
  params.set("offset", String(filters.offset ?? 0));
  for (const key of [
    "action",
    "actor_id",
    "resource_type",
    "status",
    "request_id",
    "created_from",
    "created_to",
  ] as const) {
    const value = filters[key]?.trim();
    if (value) {
      params.set(key, value);
    }
  }
  return params;
}
