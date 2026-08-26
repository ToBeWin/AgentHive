import type { AuditLogFilters, AuditLogItem } from "../../lib/api";

export type AuditFilterState = {
  action: string;
  actor_id: string;
  created_from: string;
  created_to: string;
  request_id: string;
  resource_type: string;
  status: string;
};

export interface AuditRuntimeAttemptPreview {
  attempt: string;
  deploymentId: string;
  errorCode: string;
  modelKey: string;
  providerKey: string;
  routingKey: string;
  status: string;
}

export interface AuditRuntimeSummary {
  adapterMode: string;
  deploymentId: string;
  execution: string;
  fallbackAttemptCount: string;
  gatewayCalled: boolean;
  modelKey: string;
  providerKey: string;
  routeAttempts: AuditRuntimeAttemptPreview[];
  routingKey: string;
  selectedRouteReason: string;
  status: string;
}

const EMPTY_VALUE = "-";

export const emptyAuditFilters: AuditFilterState = {
  action: "",
  actor_id: "",
  created_from: "",
  created_to: "",
  request_id: "",
  resource_type: "",
  status: "",
};

export function auditSummary(rows: AuditLogItem[]) {
  const actors = new Set(rows.map((row) => row.actor_id ?? row.actor_type).filter(Boolean));
  return {
    actorCount: actors.size,
    failures: rows.filter((row) => row.status !== "success").length,
    systemEvents: rows.filter((row) => row.actor_type === "system").length,
  };
}

export function compactResource(row: AuditLogItem, systemLabel: string) {
  const resource = row.resource_type ?? systemLabel;
  return `${resource}${row.resource_id ? `:${compactIdentifier(row.resource_id)}` : ""}`;
}

export function compactIdentifier(value: string | null | undefined) {
  if (!value) {
    return "";
  }
  if (value.length <= 18) {
    return value;
  }
  return `${value.slice(0, 8)}...${value.slice(-4)}`;
}

export function compactDetails(details: Record<string, unknown>, emptyLabel: string) {
  const runtime = auditRuntimeSummary(details);
  if (runtime) {
    const modelKey = stringValue(details.model_key ?? runtime.modelKey);
    const providerKey = stringValue(details.provider_key ?? runtime.providerKey);
    const modelPair =
      modelKey !== EMPTY_VALUE || providerKey !== EMPTY_VALUE ? `${providerKey}/${modelKey}` : EMPTY_VALUE;
    return [
      modelPair !== EMPTY_VALUE ? `model: ${modelPair}` : null,
      runtime.routingKey !== EMPTY_VALUE ? `route: ${runtime.routingKey}` : null,
      runtime.deploymentId !== EMPTY_VALUE ? `deployment: ${compactIdentifier(runtime.deploymentId)}` : null,
    ]
      .filter(Boolean)
      .join(" · ");
  }
  const entries = Object.entries(details);
  if (!entries.length) {
    return emptyLabel;
  }
  return entries
    .slice(0, 2)
    .map(([key, value]) => `${key}: ${compactDetailValue(value)}`)
    .join(" · ");
}

export function auditRuntimeSummary(details: Record<string, unknown>): AuditRuntimeSummary | null {
  const runtime = asRecord(details.runtime);
  const runtimeSummary = asRecord(details.runtime_summary);
  if (!runtime && !runtimeSummary) {
    return null;
  }
  const attempts = asRecordArray(runtime?.route_attempts).map(auditRuntimeAttemptPreview);
  const selectedAttempt = attempts.find((attempt) => attempt.status === "success") ?? attempts[0];
  return {
    adapterMode: stringValue(runtimeSummary?.adapter_mode),
    deploymentId: stringValue(runtime?.deployment_id ?? selectedAttempt?.deploymentId),
    execution: stringValue(runtimeSummary?.execution ?? runtime?.execution),
    fallbackAttemptCount: stringValue(runtimeSummary?.fallback_attempt_count ?? runtime?.fallback_attempt_count),
    gatewayCalled: runtimeSummary?.gateway_called === true || runtime?.llm_gateway_called === true,
    modelKey: stringValue(runtimeSummary?.model_key ?? details.model_key ?? selectedAttempt?.modelKey),
    providerKey: stringValue(runtimeSummary?.provider_key ?? details.provider_key ?? selectedAttempt?.providerKey),
    routeAttempts: attempts,
    routingKey: stringValue(runtime?.routing_key ?? selectedAttempt?.routingKey),
    selectedRouteReason: stringValue(runtimeSummary?.selected_route_reason ?? runtime?.selected_route_reason),
    status: stringValue(runtimeSummary?.status),
  };
}

function auditRuntimeAttemptPreview(item: Record<string, unknown>): AuditRuntimeAttemptPreview {
  return {
    attempt: stringValue(item.attempt),
    deploymentId: stringValue(item.deployment_id),
    errorCode: stringValue(item.error_code),
    modelKey: stringValue(item.model_key),
    providerKey: stringValue(item.provider_key),
    routingKey: stringValue(item.routing_key),
    status: stringValue(item.status),
  };
}

export function auditStatusLabel(status: string, t: (key: string) => string) {
  if (status === "success") {
    return t("auditStatusSuccess");
  }
  if (status === "failed") {
    return t("auditStatusFailed");
  }
  if (status === "denied") {
    return t("auditStatusDenied");
  }
  if (status === "error") {
    return t("auditStatusError");
  }
  return status || "-";
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function asRecordArray(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is Record<string, unknown> => Boolean(asRecord(item)));
}

function stringValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return EMPTY_VALUE;
  }
  return String(value);
}

function compactDetailValue(value: unknown): string {
  if (value && typeof value === "object") {
    return Array.isArray(value) ? `[${value.length}]` : "{...}";
  }
  return String(value);
}

export function toAuditQueryFilters(
  filters: AuditFilterState,
  pagination: { limit?: number; offset?: number } = {},
): AuditLogFilters {
  return {
    action: filters.action.trim() || undefined,
    actor_id: filters.actor_id.trim() || undefined,
    created_from: toIsoDateTime(filters.created_from),
    created_to: toIsoDateTime(filters.created_to),
    limit: pagination.limit ?? 50,
    offset: pagination.offset ?? 0,
    request_id: filters.request_id.trim() || undefined,
    resource_type: filters.resource_type.trim() || undefined,
    status: filters.status.trim() || undefined,
  };
}

function toIsoDateTime(value: string) {
  if (!value.trim()) {
    return undefined;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return undefined;
  }
  return date.toISOString();
}
