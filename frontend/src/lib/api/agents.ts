import { apiDelete, apiGet, apiPatch, apiPost } from "./core";
import type { LLMUsageResponse } from "./models";

export interface AgentCatalogEntryResponse {
  agent_key: string;
  name: string;
  category: string;
  description: string;
  status: string;
  version: string;
  capabilities: string[];
  required_module: string;
  orchestration_runtime: string;
  orchestration_features: string[];
  licensed: boolean | null;
  installed: boolean | null;
  enabled: boolean | null;
  license_gate: string;
}

export interface AgentCatalogResponse {
  agents: AgentCatalogEntryResponse[];
}

export interface AgentInstanceCreateRequest {
  name: string;
  slug?: string | null;
  agent_key: string;
  description?: string | null;
  visibility?: "tenant" | "department" | "private";
  department_id?: string | null;
  owner_user_id?: string | null;
  model_routing_key?: string | null;
  model_key?: string | null;
  system_prompt?: string | null;
  config?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface AgentInstanceUpdateRequest {
  name?: string | null;
  description?: string | null;
  status?: "draft" | "active" | "disabled" | null;
  visibility?: "tenant" | "department" | "private" | null;
  department_id?: string | null;
  owner_user_id?: string | null;
  model_routing_key?: string | null;
  model_key?: string | null;
  system_prompt?: string | null;
  config?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
}

export interface AgentInstanceResponse {
  id: string;
  tenant_id: string;
  name: string;
  slug: string;
  agent_key: string;
  module_key: string;
  description: string | null;
  status: "draft" | "active" | "disabled";
  visibility: "tenant" | "department" | "private";
  department_id: string | null;
  owner_user_id: string | null;
  model_routing_key: string | null;
  model_key: string | null;
  system_prompt: string | null;
  config: Record<string, unknown>;
  metadata: Record<string, unknown>;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  runnable?: boolean;
  readiness?: "ready" | "needs_configuration" | string;
  readiness_reasons?: string[];
  model_available?: boolean;
  knowledge_base_count?: number;
  knowledge_enabled?: boolean;
}

export interface AgentInstanceListResponse {
  agents: AgentInstanceResponse[];
}

export interface WorkbenchAgentInstanceResponse {
  id: string;
  name: string;
  slug: string;
  agent_key: string;
  module_key: string;
  description: string | null;
  status: "active";
  visibility: "tenant" | "department" | "private";
  department_id: string | null;
  category?: string;
  workflow_profile?: string;
  runnable: boolean;
  readiness: "ready" | "needs_configuration" | string;
  readiness_reasons: string[];
  model_profile: string | null;
  model_policy: "configured" | "system_default" | string;
  model_available: boolean;
  knowledge_base_count: number;
  knowledge_enabled: boolean;
  knowledge_bases: WorkbenchAgentKnowledgeBaseSummary[];
}

export interface WorkbenchAgentKnowledgeBaseSummary {
  id: string;
  name: string;
  description: string | null;
  visibility: "tenant" | "department" | "private" | string;
  status: "active" | "archived" | string;
  document_count: number;
  tags: string[];
  updated_at: string;
}

export interface WorkbenchAgentInstanceListResponse {
  agents: WorkbenchAgentInstanceResponse[];
}

export interface AgentGovernanceTargetItem {
  id: string;
  label: string;
  description: string | null;
  metadata: Record<string, unknown>;
}

export interface AgentGovernanceTargetsResponse {
  departments: AgentGovernanceTargetItem[];
  users: AgentGovernanceTargetItem[];
  knowledge_bases: AgentGovernanceTargetItem[];
  model_deployments: AgentGovernanceTargetItem[];
}

export interface AgentRunRequest {
  input: string;
  context?: Record<string, unknown>;
  model_key?: string | null;
  routing_key?: string | null;
  max_tokens?: number | null;
}

export interface AgentRunResponse {
  answer: string;
  usage: LLMUsageResponse;
  model_key: string;
  request_id: string;
  sources: Array<Record<string, unknown>>;
  metadata: Record<string, unknown>;
}

export const agentsApi = {
  getAgentGovernanceTargets: () => apiGet<AgentGovernanceTargetsResponse>("/api/v1/agents/governance-targets"),
  getAgentInstances: () => apiGet<AgentInstanceListResponse>("/api/v1/agents/instances"),
  getWorkbenchAgentInstances: () => apiGet<WorkbenchAgentInstanceListResponse>("/api/v1/agents/workbench/instances"),
  createAgentInstance: (payload: AgentInstanceCreateRequest) =>
    apiPost<AgentInstanceResponse, AgentInstanceCreateRequest>("/api/v1/agents/instances", payload),
  updateAgentInstance: (agentId: string, payload: AgentInstanceUpdateRequest) =>
    apiPatch<AgentInstanceResponse, AgentInstanceUpdateRequest>(`/api/v1/agents/instances/${agentId}`, payload),
  getAgentCatalog: () => apiGet<AgentCatalogResponse>("/api/v1/agents/catalog"),
  runAgent: (agentKey: string, payload: AgentRunRequest) =>
    apiPost<AgentRunResponse, AgentRunRequest>(`/api/v1/agents/${agentKey}/run`, payload),
};

// Agent Assignments

export interface AgentAssignment {
  id: string;
  agent_id: string;
  user_id: string;
  user_email: string;
  user_full_name: string | null;
  user_username: string | null;
  role: string;
  created_at: string;
  updated_at: string;
}

export interface AgentAssignmentListResponse {
  assignments: AgentAssignment[];
  total: number;
}

export interface AgentAssignmentBulkRequest {
  users: Array<{ user_id: string; role: string }>;
}

export interface MyAgent {
  id: string;
  agent_id: string;
  agent_name: string;
  agent_key: string;
  agent_slug: string;
  role: string;
  assigned_at: string;
}

export interface MyAgentListResponse {
  agents: MyAgent[];
  total: number;
}

// Agent Assignments
export async function listAgentAssignments(agentId: string): Promise<AgentAssignment[]> {
  const response = await apiGet<AgentAssignmentListResponse>(`/api/v1/agent-assignments/agents/${agentId}/users`);
  return response.assignments;
}

export async function assignUsersToAgent(
  agentId: string,
  users: Array<{ user_id: string; role: string }>,
): Promise<AgentAssignment[]> {
  const response = await apiPost<AgentAssignmentListResponse, AgentAssignmentBulkRequest>(
    `/api/v1/agent-assignments/agents/${agentId}/users`,
    { users },
  );
  return response.assignments;
}

export async function removeAgentUser(agentId: string, userId: string): Promise<void> {
  await apiDelete<void>(`/api/v1/agent-assignments/agents/${agentId}/users/${userId}`);
}

export async function listMyAgents(): Promise<MyAgent[]> {
  const response = await apiGet<MyAgentListResponse>("/api/v1/agent-assignments/my-agents");
  return response.agents;
}
