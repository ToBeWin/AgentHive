import { ApiError, apiDownloadBlob, apiGet } from "./core";

export type SystemComponentStatus =
  | "healthy"
  | "degraded"
  | "unhealthy"
  | "configured"
  | "not_configured"
  | "error"
  | string;

export interface SystemComponentReport {
  status: SystemComponentStatus;
  message?: string;
  details?: Record<string, unknown>;
  remediation?: SystemComponentRemediation;
  checked_at?: string;
  component?: string;
  migrations?: Record<string, unknown>;
}

export interface SystemComponentRemediation {
  summary?: string;
  action?: string;
  docs_anchor?: string;
}

export type DeliverySeverity = "pass" | "warning" | "blocker" | string;
export type DeliveryStatus = "ready" | "ready_with_warnings" | "blocked" | string;

export interface DeliveryCheck {
  id: string;
  label: string;
  component: string;
  status: SystemComponentStatus;
  severity: DeliverySeverity;
  message?: string;
  remediation?: SystemComponentRemediation | null;
}

export interface DeliveryAssessment {
  status: DeliveryStatus;
  summary: string;
  blocker_count: number;
  warning_count: number;
  blockers: DeliveryCheck[];
  warnings: DeliveryCheck[];
  checks: DeliveryCheck[];
}

export interface SystemHealthReport {
  status: SystemComponentStatus;
  service: string;
  version: string;
  environment: string;
  checked_at: string;
  components: Record<string, SystemComponentReport>;
  delivery?: DeliveryAssessment;
}

export interface SystemInfoResponse {
  name: string;
  edition: string;
  version: string;
}

export interface SystemDiagnosticsReport {
  product: "AgentHive" | string;
  report_type: "deployment_diagnostics" | string;
  schema_version: string;
  generated_at: string;
  redacted: boolean;
  delivery?: DeliveryAssessment | null;
  diagnostics: {
    health: SystemHealthReport;
    readiness: SystemHealthReport;
    info: SystemInfoResponse;
    [key: string]: unknown;
  };
}

export interface ConnectionAcceptanceEvidenceItem {
  provider_key?: string | null;
  provider_type?: string | null;
  model_key?: string | null;
  operation?: string | null;
  ok?: boolean | null;
  status?: string | null;
  checked_at?: string | null;
  latency_ms?: number | null;
  live_network_call?: boolean | null;
  status_code?: number | null;
  probe_path?: string | null;
  configuration_source?: string | null;
  selected_route_reason?: string | null;
}

export interface ConnectionAcceptanceEvidence {
  status: string;
  summary: string;
  recent_test_count: number;
  live_network_call_count: number;
  media_live_probe_count: number;
  failed_recent_count: number;
  providers: string[];
  latest_live_probe?: ConnectionAcceptanceEvidenceItem | null;
  latest_media_live_probe?: ConnectionAcceptanceEvidenceItem | null;
  recent_tests: ConnectionAcceptanceEvidenceItem[];
}

export interface KnowledgeAcceptanceEvidenceItem {
  agent_key?: string | null;
  agent_instance_id?: string | null;
  agent_instance_name?: string | null;
  required_module?: string | null;
  model_key?: string | null;
  routing_key?: string | null;
  department_id?: string | null;
  channel_id?: string | null;
  checked_at?: string | null;
  status?: string | null;
  knowledge_enabled?: boolean | null;
  knowledge_base_ids?: string[];
  source_count?: number | null;
  confidence_level?: string | null;
  max_score?: number | null;
  min_score?: number | null;
  requires_human_review?: boolean | null;
  review_reason?: string | null;
  guardrail_mode?: string | null;
  guardrail_triggered?: boolean | null;
  skipped_model_call?: boolean | null;
}

export interface KnowledgeAcceptanceEvidence {
  status: string;
  summary: string;
  recent_run_count: number;
  knowledge_enabled_run_count: number;
  runs_with_sources_count: number;
  human_review_required_count: number;
  guardrail_triggered_count: number;
  agents: string[];
  latest_knowledge_run?: KnowledgeAcceptanceEvidenceItem | null;
  recent_runs: KnowledgeAcceptanceEvidenceItem[];
}

function isHealthReport(value: unknown): value is SystemHealthReport {
  return Boolean(
    value && typeof value === "object" && "status" in value && "service" in value && "components" in value,
  );
}

export const systemApi = {
  getHealth: () => apiGet<SystemHealthReport>("/api/v1/health"),
  getInfo: () => apiGet<SystemInfoResponse>("/api/v1/system/info"),
  getDiagnostics: () => apiGet<SystemDiagnosticsReport>("/api/v1/system/diagnostics"),
  getSupportBundle: () => apiDownloadBlob("/api/v1/system/support-bundle"),
  getReadiness: async () => {
    try {
      return await apiGet<SystemHealthReport>("/api/v1/health/readiness");
    } catch (error) {
      if (error instanceof ApiError && isHealthReport(error.details)) {
        return error.details;
      }
      throw error;
    }
  },
};
