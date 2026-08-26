import { apiGet, apiPost } from "./core";

export type LicenseStatus = "inactive" | "active" | "expired" | "revoked" | "mismatch";

export type AgentModuleState = "not_installed" | "installed" | "enabled" | "disabled" | "expired" | "not_licensed";

export interface LicenseStatusResponse {
  status: LicenseStatus;
  license_type: string;
  customer_name: string;
  deployment_id: string;
  install_id: string;
  machine_fingerprint_hash: string;
  runtime_deployment_id: string | null;
  runtime_install_id: string | null;
  runtime_machine_fingerprint_hash: string | null;
  verification_issues: string[];
  allowed_modules: string[];
  allowed_features: string[];
  maintenance_until: string | null;
  expires_at: string | null;
  activated_at: string | null;
  max_users: number | null;
  max_agents: number | null;
  max_kb_size_gb: number | string | null;
  module_count: number;
  feature_count: number;
}

export interface AuthorizedModule {
  id: string;
  name: string;
  state: AgentModuleState;
  licensed: boolean;
  installed: boolean;
  enabled: boolean;
}

export interface AuthorizedFeature {
  id: string;
  name: string;
  enabled: boolean;
}

export interface LicenseModulesResponse {
  modules: AuthorizedModule[];
  features: AuthorizedFeature[];
}

export interface ActivationRequestResponse {
  product: string;
  tenant_id: string;
  deployment_id: string;
  install_id: string;
  machine_fingerprint_hash: string;
  fingerprint_algorithm: string;
  generated_at: string;
  request_id: string;
  request_code: string;
  request_hash: string;
  request_format: string;
  [key: string]: unknown;
}

export interface LicenseActivationRequest {
  license_key: string;
  activation_code?: string | null;
}

export interface LicenseVerificationResponse {
  mode: string;
  valid: boolean;
  status: LicenseStatus;
  reason: string;
  signature_alg: string | null;
  license_id: string | null;
}

export interface LicenseActivationResponse {
  status: LicenseStatus;
  message: string;
  license: LicenseStatusResponse;
  verification: LicenseVerificationResponse | null;
}

export interface LicenseDeactivateResponse {
  status: LicenseStatus;
  message: string;
  deactivated_at: string;
}

export interface AgentModuleCatalogEntry {
  id: string;
  name: string;
  scenario: string;
  priority: string;
  description: string;
  version: string;
  state: AgentModuleState;
  licensed: boolean;
  installed: boolean;
  enabled: boolean;
  required_features: string[];
  missing_features: string[];
  dependencies: string[];
  missing_dependencies: string[];
}

export interface AgentModuleListResponse {
  modules: AgentModuleCatalogEntry[];
}

export interface AgentModuleActionResponse {
  module_id: string;
  state: AgentModuleState;
  message: string;
}

export const licenseApi = {
  getLicenseStatus: () => apiGet<LicenseStatusResponse>("/api/v1/admin/license/status"),
  getLicenseModules: () => apiGet<LicenseModulesResponse>("/api/v1/admin/license/modules"),
  getLicenseActivationRequest: () => apiGet<ActivationRequestResponse>("/api/v1/admin/license/activation-request"),
  activateLicense: (payload: LicenseActivationRequest) =>
    apiPost<LicenseActivationResponse, LicenseActivationRequest>("/api/v1/admin/license/activate", payload),
  deactivateLicense: () =>
    apiPost<LicenseDeactivateResponse, Record<string, never>>("/api/v1/admin/license/deactivate", {}),
};

export const agentModulesApi = {
  getAgentModules: () => apiGet<AgentModuleListResponse>("/api/v1/agent-modules"),
  installAgentModule: (moduleId: string) =>
    apiPost<AgentModuleActionResponse, Record<string, never>>(`/api/v1/agent-modules/${moduleId}/install`, {}),
  enableAgentModule: (moduleId: string) =>
    apiPost<AgentModuleActionResponse, Record<string, never>>(`/api/v1/agent-modules/${moduleId}/enable`, {}),
  disableAgentModule: (moduleId: string) =>
    apiPost<AgentModuleActionResponse, Record<string, never>>(`/api/v1/agent-modules/${moduleId}/disable`, {}),
};
