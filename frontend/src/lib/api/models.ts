import { apiGet, apiPatch, apiPost, apiPut } from "./core";

export type LLMAdapterType = "litellm" | "openai_compatible" | "anthropic_compatible";
export type LLMProviderStatus = "active" | "inactive" | "not_configured";
export type LLMDeploymentStatus = "active" | "inactive";
export type LLMPolicyScope = "tenant" | "department" | "cost_center" | "user" | "agent" | "channel";
export type LLMPolicyEffect = "allow" | "deny";
export type LLMPolicyStatus = "active" | "inactive";

export interface LLMProviderResponse {
  provider_key: string;
  name: string;
  adapter_type: LLMAdapterType;
  base_url: string | null;
  region: string | null;
  status: LLMProviderStatus;
  capabilities: string[];
  credential_configured: boolean;
  metadata: Record<string, unknown>;
}

export interface LLMProviderListResponse {
  providers: LLMProviderResponse[];
}

export interface LLMDeploymentResponse {
  id: string;
  provider_key: string;
  provider_name: string;
  adapter_type: LLMAdapterType;
  model_key: string;
  display_name: string;
  deployment_name: string;
  routing_key: string;
  status: LLMDeploymentStatus;
  context_window: number | null;
  capabilities: string[];
  priority: number;
  config: Record<string, unknown>;
}

export interface LLMDeploymentListResponse {
  deployments: LLMDeploymentResponse[];
}

export interface LLMDeploymentReadinessResponse {
  deployment_id: string;
  provider_key: string;
  provider_name: string;
  model_key: string;
  display_name: string;
  routing_key: string;
  deployment_name: string;
  readiness: "ready" | "warning" | "blocked" | string;
  credential_configured: boolean;
  deployment_active: boolean;
  live_probe_ok: boolean;
  live_probe_checked_at: string | null;
  last_probe_message: string | null;
  pricing_configured: boolean;
  policy_referenced: boolean;
  fallback_configured: boolean;
  blockers: string[];
  warnings: string[];
  evidence: Record<string, unknown>;
}

export interface LLMReadinessResponse {
  generated_at: string;
  summary: Record<string, number>;
  deployments: LLMDeploymentReadinessResponse[];
}

export interface LLMModelPriceResponse {
  id: string;
  model_id: string;
  provider_key: string;
  model_key: string;
  display_name: string;
  currency: string;
  input_per_1k_tokens: string | number;
  output_per_1k_tokens: string | number;
  effective_from: string;
  effective_to: string | null;
}

export interface LLMModelPriceListResponse {
  prices: LLMModelPriceResponse[];
}

export interface LLMModelPriceUpsertRequest {
  provider_key: string;
  model_key: string;
  display_name?: string | null;
  currency?: string;
  input_per_1k_tokens: string | number;
  output_per_1k_tokens: string | number;
  effective_from?: string | null;
  effective_to?: string | null;
}

export interface LLMPolicyResponse {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  scope_type: LLMPolicyScope;
  scope_id: string | null;
  effect: LLMPolicyEffect;
  allowed_models: string[];
  allowed_routing_keys: string[];
  default_model_key: string | null;
  default_routing_key: string | null;
  max_tokens: number | null;
  priority: number;
  status: LLMPolicyStatus;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface LLMPolicyListResponse {
  policies: LLMPolicyResponse[];
}

export interface LLMPolicyUpsertRequest {
  id?: string | null;
  name: string;
  description?: string | null;
  scope_type: LLMPolicyScope;
  scope_id?: string | null;
  effect: LLMPolicyEffect;
  allowed_models: string[];
  allowed_routing_keys: string[];
  default_model_key?: string | null;
  default_routing_key?: string | null;
  max_tokens?: number | null;
  priority: number;
  status: LLMPolicyStatus;
  metadata?: Record<string, unknown>;
}

export interface LLMPolicyStatusUpdateRequest {
  status: LLMPolicyStatus;
}

export interface LLMCredentialUpsertRequest {
  display_name: string;
  api_key: string;
  base_url?: string | null;
  owner_type?: string;
  owner_id?: string | null;
  model_key?: string | null;
  deployment_name?: string | null;
  routing_key?: string | null;
  make_default?: boolean;
}

export interface LLMCredentialResponse {
  provider_key: string;
  display_name: string;
  masked_secret: string;
  credential_configured: boolean;
  base_url: string | null;
  owner_type: string;
  owner_id?: string | null;
  deployment_id?: string | null;
  routing_key?: string | null;
  model_key?: string | null;
}

export interface LLMConnectionTestRequest {
  adapter_type?: LLMAdapterType | null;
  api_key?: string | null;
  base_url?: string | null;
  deployment_id?: string | null;
  live_check?: boolean;
  model_key?: string | null;
  probe_path?: string | null;
  provider_key?: string | null;
  timeout_seconds?: number | null;
}

export interface LLMConnectionTestResponse {
  ok: boolean;
  provider_key: string | null;
  adapter_type: LLMAdapterType;
  model_key: string | null;
  latency_ms: number;
  checked_at: string;
  message: string;
  diagnostics: Record<string, unknown>;
}

export interface LLMConnectionTestHistoryItem {
  id: string;
  request_id: string | null;
  actor_id: string | null;
  status: string;
  ok: boolean;
  provider_key: string | null;
  provider_type: string | null;
  deployment_id: string | null;
  model_key: string | null;
  adapter_type: string | null;
  latency_ms: number | null;
  checked_at: string;
  message: string | null;
  operation: string | null;
  configuration_source: string | null;
  probe_path: string | null;
  status_code: number | null;
  fallback_attempt_count: number | null;
  selected_route_reason: string | null;
  temporary_api_key_provided: boolean;
  temporary_base_url_provided: boolean;
  live_network_call: boolean | null;
}

export interface LLMConnectionTestHistoryResponse {
  tests: LLMConnectionTestHistoryItem[];
}

export interface LLMGovernanceTargetItem {
  id: string;
  label: string;
  description: string | null;
  status: string | null;
  metadata: Record<string, unknown>;
}

export interface LLMGovernanceTargetsResponse {
  departments: LLMGovernanceTargetItem[];
  cost_centers: LLMGovernanceTargetItem[];
  users: LLMGovernanceTargetItem[];
  agents: LLMGovernanceTargetItem[];
  channels: LLMGovernanceTargetItem[];
}

export interface LLMUsageResponse {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost_usd: string | number;
}

export interface LLMDeploymentAcceptanceTestRequest {
  prompt?: string;
  max_tokens?: number;
}

export interface LLMDeploymentAcceptanceTestResponse {
  ok: boolean;
  request_id: string;
  deployment_id: string;
  provider_key: string;
  model_key: string;
  routing_key: string;
  content_preview: string;
  usage: LLMUsageResponse;
  route_attempts: Array<Record<string, unknown>>;
  live_network_call: boolean | null;
  mock: boolean | null;
  usage_recorded: boolean;
  audit_action: string;
  evidence: Record<string, unknown>;
}

export const modelsApi = {
  getModelProviders: () => apiGet<LLMProviderListResponse>("/api/v1/models/providers"),
  getModelDeployments: () => apiGet<LLMDeploymentListResponse>("/api/v1/models/deployments"),
  getModelReadiness: () => apiGet<LLMReadinessResponse>("/api/v1/models/readiness"),
  getModelPolicies: () => apiGet<LLMPolicyListResponse>("/api/v1/models/policies"),
  getModelPrices: () => apiGet<LLMModelPriceListResponse>("/api/v1/models/prices"),
  getModelConnectionTests: (limit = 20) =>
    apiGet<LLMConnectionTestHistoryResponse>(`/api/v1/models/connection-tests?limit=${limit}`),
  getModelGovernanceTargets: () => apiGet<LLMGovernanceTargetsResponse>("/api/v1/models/governance-targets"),
  saveModelPrice: (payload: LLMModelPriceUpsertRequest) =>
    apiPut<LLMModelPriceResponse, LLMModelPriceUpsertRequest>("/api/v1/models/prices", payload),
  saveModelPolicy: (payload: LLMPolicyUpsertRequest) =>
    apiPost<LLMPolicyResponse, LLMPolicyUpsertRequest>("/api/v1/models/policies", payload),
  updateModelPolicyStatus: (policyId: string, payload: LLMPolicyStatusUpdateRequest) =>
    apiPatch<LLMPolicyResponse, LLMPolicyStatusUpdateRequest>(`/api/v1/models/policies/${policyId}/status`, payload),
  saveModelCredential: (providerKey: string, payload: LLMCredentialUpsertRequest) =>
    apiPut<LLMCredentialResponse, LLMCredentialUpsertRequest>(
      `/api/v1/models/providers/${providerKey}/credential`,
      payload,
    ),
  testModelConnection: (payload: LLMConnectionTestRequest) =>
    apiPost<LLMConnectionTestResponse, LLMConnectionTestRequest>("/api/v1/models/test-connection", payload),
  runDeploymentAcceptanceTest: (deploymentId: string, payload: LLMDeploymentAcceptanceTestRequest = {}) =>
    apiPost<LLMDeploymentAcceptanceTestResponse, LLMDeploymentAcceptanceTestRequest>(
      `/api/v1/models/deployments/${deploymentId}/acceptance-test`,
      payload,
    ),
};
