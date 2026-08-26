import type { AuditLogFilters, AuditLogItem, AuditLogListResponse } from "../../lib/api";

const TENANT_ID = "00000000-0000-4000-8000-000000000001";
const ADMIN_ID = "00000000-0000-4000-8000-000000000201";
const OPERATOR_ID = "00000000-0000-4000-8000-000000000202";
const AGENT_ID = "00000000-0000-4000-8000-000000000701";
const CHANNEL_ID = "00000000-0000-4000-8000-000000000801";
const DEPARTMENT_ID = "00000000-0000-4000-8000-000000000301";

const PROTOTYPE_AUDIT_LOGS: AuditLogItem[] = [
  auditEvent({
    action: "chat.message.send",
    actorId: OPERATOR_ID,
    actorType: "user",
    createdAt: "2026-01-01T09:12:12.000Z",
    details: {
      model_key: "deepseek-v4-flash",
      provider_key: "deepseek",
      runtime: {
        deployment_id: "00000000-0000-4000-8000-000000100005",
        execution: "agent_runtime",
        fallback_attempt_count: 0,
        llm_gateway_called: true,
        route_attempts: [
          {
            attempt: 1,
            deployment_id: "00000000-0000-4000-8000-000000100005",
            model_key: "deepseek-v4-flash",
            provider_key: "deepseek",
            routing_key: "cost-chat",
            status: "success",
          },
        ],
        routing_key: "cost-chat",
        selected_route_reason: "priority_route",
      },
      runtime_summary: {
        adapter_mode: "live_gateway",
        execution: "agent_runtime",
        fallback_attempt_count: 0,
        gateway_called: true,
        model_key: "deepseek-v4-flash",
        provider_key: "deepseek",
        selected_route_reason: "priority_route",
        status: "real_model_call",
      },
      total_tokens: 20,
    },
    id: "00000000-0000-4000-8000-000000170010",
    requestId: "proto-run-010",
    resourceId: AGENT_ID,
    resourceType: "conversation",
    status: "success",
  }),
  auditEvent({
    action: "llm.chat.settle",
    actorId: OPERATOR_ID,
    actorType: "user",
    createdAt: "2026-01-01T09:11:31.000Z",
    details: {
      budget_event: "settle",
      cost_usd: "0.0064",
      model_key: "qwen-plus",
      provider_key: "qwen",
      routing_key: "cn-primary-chat",
      tokens: 1706,
    },
    id: "00000000-0000-4000-8000-000000170001",
    requestId: "proto-run-001",
    resourceId: AGENT_ID,
    resourceType: "agent",
    status: "success",
  }),
  auditEvent({
    action: "budget.guard.deny",
    actorId: OPERATOR_ID,
    actorType: "user",
    createdAt: "2026-01-01T09:09:20.000Z",
    details: {
      budget_policy: "Customer Service Agent route guard",
      denied_route: "premium-chat",
      fallback_route: "cost-chat",
      reason: "agent hard cap above threshold",
    },
    id: "00000000-0000-4000-8000-000000170002",
    requestId: "proto-run-002",
    resourceId: AGENT_ID,
    resourceType: "budget_policy",
    status: "denied",
  }),
  auditEvent({
    action: "llm.route.fallback",
    actorId: null,
    actorType: "system",
    createdAt: "2026-01-01T09:09:29.000Z",
    details: {
      fallback_from: "gpt-4o",
      fallback_to: "deepseek-v4-flash",
      reason: "budget guard selected cost route",
      selected_route: "cost-chat",
    },
    id: "00000000-0000-4000-8000-000000170003",
    requestId: "proto-run-003",
    resourceId: "00000000-0000-4000-8000-000000100005",
    resourceType: "model_deployment",
    status: "success",
  }),
  auditEvent({
    action: "knowledge.retrieve",
    actorId: OPERATOR_ID,
    actorType: "user",
    createdAt: "2026-01-01T09:11:28.000Z",
    details: {
      engine: "pgvector",
      knowledge_base: "After-sales Policy",
      source_count: 2,
      top_k: 3,
    },
    id: "00000000-0000-4000-8000-000000170004",
    requestId: "proto-run-001",
    resourceId: "kb-after-sales",
    resourceType: "knowledge_base",
    status: "success",
  }),
  auditEvent({
    action: "license.module.check",
    actorId: null,
    actorType: "system",
    createdAt: "2026-01-01T09:11:27.000Z",
    details: {
      allowed: true,
      module: "agent.customer_service",
      tenant_license: "enterprise",
    },
    id: "00000000-0000-4000-8000-000000170005",
    requestId: "proto-run-001",
    resourceId: "agent.customer_service",
    resourceType: "license_module",
    status: "success",
  }),
  auditEvent({
    action: "rbac.permission.check",
    actorId: ADMIN_ID,
    actorType: "user",
    createdAt: "2026-01-01T09:07:10.000Z",
    details: {
      decision: "allow",
      permission: "models:write",
      role: "Tenant Administrator",
    },
    id: "00000000-0000-4000-8000-000000170006",
    requestId: "req-model-policy-save",
    resourceId: "00000000-0000-4000-8000-000000110002",
    resourceType: "model_policy",
    status: "success",
  }),
  auditEvent({
    action: "model.policy.update",
    actorId: ADMIN_ID,
    actorType: "user",
    createdAt: "2026-01-01T09:07:12.000Z",
    details: {
      default_route: "cn-primary-chat",
      scope: "department",
      strategy: "explicit deny > user > agent > channel > department > tenant",
    },
    id: "00000000-0000-4000-8000-000000170007",
    requestId: "req-model-policy-save",
    resourceId: DEPARTMENT_ID,
    resourceType: "department",
    status: "success",
  }),
  auditEvent({
    action: "channel.message.ingest",
    actorId: null,
    actorType: "system",
    createdAt: "2026-01-01T09:11:25.000Z",
    details: {
      channel_key: "web-support-widget",
      normalized_message: true,
      signature_checked: true,
    },
    id: "00000000-0000-4000-8000-000000170008",
    requestId: "proto-run-001",
    resourceId: CHANNEL_ID,
    resourceType: "channel",
    status: "success",
  }),
  auditEvent({
    action: "diagnostics.export",
    actorId: ADMIN_ID,
    actorType: "user",
    createdAt: "2026-01-01T08:55:00.000Z",
    details: {
      redacted: true,
      support_bundle: "agenthive-support-bundle",
      target: "private deployment",
    },
    id: "00000000-0000-4000-8000-000000170009",
    requestId: "req-support-bundle",
    resourceId: TENANT_ID,
    resourceType: "tenant",
    status: "success",
  }),
];

export function prototypeAuditLogs(filters: AuditLogFilters = {}): AuditLogListResponse {
  const filtered = filterAuditLogs(PROTOTYPE_AUDIT_LOGS, filters);
  const offset = filters.offset ?? 0;
  const limit = filters.limit ?? 50;
  return {
    items: filtered.slice(offset, offset + limit),
    limit,
    offset,
    total: filtered.length,
  };
}

export function prototypeAuditExport(filters: AuditLogFilters = {}, format: "csv" | "json") {
  const rows = filterAuditLogs(PROTOTYPE_AUDIT_LOGS, filters);
  if (format === "json") {
    return JSON.stringify(rows, null, 2);
  }
  const headers = [
    "id",
    "created_at",
    "actor_type",
    "actor_id",
    "action",
    "resource_type",
    "resource_id",
    "status",
    "request_id",
    "details",
  ];
  return [
    headers.join(","),
    ...rows.map((row) =>
      headers
        .map((key) => {
          const value = key === "details" ? JSON.stringify(row.details) : row[key as keyof AuditLogItem];
          return JSON.stringify(value ?? "");
        })
        .join(","),
    ),
  ].join("\n");
}

function filterAuditLogs(rows: AuditLogItem[], filters: AuditLogFilters) {
  return rows.filter((row) => {
    if (filters.action && !row.action.includes(filters.action)) {
      return false;
    }
    if (filters.actor_id && row.actor_id !== filters.actor_id) {
      return false;
    }
    if (filters.resource_type && row.resource_type !== filters.resource_type) {
      return false;
    }
    if (filters.status && row.status !== filters.status) {
      return false;
    }
    if (filters.request_id && row.request_id !== filters.request_id) {
      return false;
    }
    if (filters.created_from && new Date(row.created_at) < new Date(filters.created_from)) {
      return false;
    }
    if (filters.created_to && new Date(row.created_at) > new Date(filters.created_to)) {
      return false;
    }
    return true;
  });
}

function auditEvent({
  action,
  actorId,
  actorType,
  createdAt,
  details,
  id,
  requestId,
  resourceId,
  resourceType,
  status,
}: {
  action: string;
  actorId: string | null;
  actorType: string;
  createdAt: string;
  details: Record<string, unknown>;
  id: string;
  requestId: string;
  resourceId: string;
  resourceType: string;
  status: string;
}): AuditLogItem {
  return {
    action,
    actor_id: actorId,
    actor_type: actorType,
    created_at: createdAt,
    details,
    id,
    ip_address: actorType === "system" ? "127.0.0.1" : "10.0.12.24",
    request_id: requestId,
    resource_id: resourceId,
    resource_type: resourceType,
    status,
    tenant_id: TENANT_ID,
    user_agent: actorType === "system" ? "AgentHive/System" : "AgentHive Admin Console",
  };
}
