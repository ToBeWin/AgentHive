import type { AgentInstanceResponse } from "./agents";
import { apiPatch, apiPost } from "./core";

export type BuilderResponseStyle = "formal" | "friendly" | "concise";
export type BuilderSupportedLanguage = "zh" | "en" | "auto";
export type BuilderIssueSeverity = "error" | "warning";

export interface AgentBuilderConfig {
  name: string;
  description?: string | null;
  avatar_url?: string | null;
  deployment_id?: string | null;
  fallback_deployment_ids?: string[];
  model_key?: string | null;
  routing_key?: string | null;
  temperature?: number | null;
  max_tokens?: number | null;
  max_cost_per_request?: number | null;
  system_prompt: string;
  response_style: BuilderResponseStyle;
  language: BuilderSupportedLanguage;
  knowledge_base_ids?: string[];
  mcp_server_keys?: string[];
  confidence_threshold?: number | null;
  escalation_message?: string | null;
  greeting_message?: string | null;
  fallback_message?: string | null;
  metadata?: Record<string, unknown>;
}

export interface AgentBuilderConfigIssue {
  severity: BuilderIssueSeverity;
  code: string;
  message: string;
  field?: string | null;
}

export interface AgentBuilderValidationReport {
  ok: boolean;
  issues: AgentBuilderConfigIssue[];
}

export interface AgentBuilderRenderOutput {
  system_prompt: string;
  user_prompt_template: string;
  response_style: BuilderResponseStyle;
  language: BuilderSupportedLanguage;
  greeting_message: string | null;
  fallback_message: string;
  escalation_message: string | null;
  confidence_threshold: number | null;
  bound_knowledge_base_ids: string[];
  bound_mcp_server_keys: string[];
  runtime_metadata: Record<string, unknown>;
}

export interface BuilderPreviewRequest {
  config: AgentBuilderConfig;
}

export interface BuilderPreviewResponse extends AgentBuilderValidationReport {
  rendered: AgentBuilderRenderOutput;
}

export interface BuilderValidateResponse extends AgentBuilderValidationReport {}

export const builderApi = {
  validate: (config: AgentBuilderConfig) =>
    apiPost<BuilderValidateResponse, AgentBuilderConfig>("/api/v1/agents/builder/validate", config),
  preview: (request: BuilderPreviewRequest) =>
    apiPost<BuilderPreviewResponse, BuilderPreviewRequest>("/api/v1/agents/builder/preview", request),
  createInstance: (config: AgentBuilderConfig) =>
    apiPost<AgentInstanceResponse, AgentBuilderConfig>("/api/v1/agents/builder/instances", config),
  updateInstance: (agentId: string, config: AgentBuilderConfig) =>
    apiPatch<AgentInstanceResponse, AgentBuilderConfig>(`/api/v1/agents/builder/instances/${agentId}`, config),
};
