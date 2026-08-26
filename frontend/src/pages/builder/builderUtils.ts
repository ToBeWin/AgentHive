import type { AgentBuilderConfig, BuilderResponseStyle, BuilderSupportedLanguage } from "../../lib/api";

export interface AgentModelDeploymentOption {
  id: string;
  label: string;
  routing_key: string;
}

export interface AgentKnowledgeBaseOption {
  id: string;
  name: string;
  rag_engine: string;
}

export interface AgentMcpServerOption {
  id: string;
  name: string;
  server_key: string;
  status: string;
}

export interface BuilderFormState {
  name: string;
  description: string;
  avatar_url: string;
  deployment_id: string;
  fallback_deployment_ids: string[];
  model_key: string;
  routing_key: string;
  temperature: string; // string for input control; converted on submit
  max_tokens: string;
  max_cost_per_request: string;
  system_prompt: string;
  response_style: BuilderResponseStyle;
  language: BuilderSupportedLanguage;
  knowledge_base_ids: string[];
  mcp_server_keys: string[];
  confidence_threshold: string;
  escalation_message: string;
  greeting_message: string;
  fallback_message: string;
}

export const emptyBuilderForm: BuilderFormState = {
  name: "",
  description: "",
  avatar_url: "",
  deployment_id: "",
  fallback_deployment_ids: [],
  model_key: "",
  routing_key: "",
  temperature: "0.7",
  max_tokens: "1024",
  max_cost_per_request: "",
  system_prompt: "",
  response_style: "formal",
  language: "auto",
  knowledge_base_ids: [],
  mcp_server_keys: [],
  confidence_threshold: "0.5",
  escalation_message: "",
  greeting_message: "",
  fallback_message: "",
};

/**
 * Convert a form state (strings for input friendliness) to the API payload
 * (typed numbers / nulls). Empty strings become null/undefined.
 */
export function formToConfig(form: BuilderFormState): AgentBuilderConfig {
  const config: AgentBuilderConfig = {
    name: form.name.trim(),
    system_prompt: form.system_prompt,
    response_style: form.response_style,
    language: form.language,
  };
  if (form.description.trim()) config.description = form.description.trim();
  if (form.avatar_url.trim()) config.avatar_url = form.avatar_url.trim();
  if (form.deployment_id.trim()) config.deployment_id = form.deployment_id.trim();
  if (form.fallback_deployment_ids.length) {
    config.fallback_deployment_ids = form.fallback_deployment_ids.filter((id) => id.trim());
  }
  if (form.model_key.trim()) config.model_key = form.model_key.trim();
  if (form.routing_key.trim()) config.routing_key = form.routing_key.trim();
  const temperature = parseFloat(form.temperature);
  if (!Number.isNaN(temperature)) config.temperature = temperature;
  const maxTokens = parseInt(form.max_tokens, 10);
  if (!Number.isNaN(maxTokens)) config.max_tokens = maxTokens;
  const maxCost = parseFloat(form.max_cost_per_request);
  if (!Number.isNaN(maxCost)) config.max_cost_per_request = maxCost;
  if (form.knowledge_base_ids.length) config.knowledge_base_ids = form.knowledge_base_ids;
  if (form.mcp_server_keys.length) config.mcp_server_keys = form.mcp_server_keys;
  const confidence = parseFloat(form.confidence_threshold);
  if (!Number.isNaN(confidence)) {
    config.confidence_threshold = confidence;
    if (form.escalation_message.trim()) {
      config.escalation_message = form.escalation_message.trim();
    }
  }
  if (form.greeting_message.trim()) config.greeting_message = form.greeting_message.trim();
  if (form.fallback_message.trim()) config.fallback_message = form.fallback_message.trim();
  return config;
}

export function configToForm(config: AgentBuilderConfig): BuilderFormState {
  return {
    name: config.name ?? "",
    description: config.description ?? "",
    avatar_url: config.avatar_url ?? "",
    deployment_id: config.deployment_id ?? "",
    fallback_deployment_ids: config.fallback_deployment_ids ?? [],
    model_key: config.model_key ?? "",
    routing_key: config.routing_key ?? "",
    temperature: config.temperature != null ? String(config.temperature) : "",
    max_tokens: config.max_tokens != null ? String(config.max_tokens) : "",
    max_cost_per_request: config.max_cost_per_request != null ? String(config.max_cost_per_request) : "",
    system_prompt: config.system_prompt ?? "",
    response_style: config.response_style ?? "formal",
    language: config.language ?? "auto",
    knowledge_base_ids: config.knowledge_base_ids ?? [],
    mcp_server_keys: config.mcp_server_keys ?? [],
    confidence_threshold: config.confidence_threshold != null ? String(config.confidence_threshold) : "",
    escalation_message: config.escalation_message ?? "",
    greeting_message: config.greeting_message ?? "",
    fallback_message: config.fallback_message ?? "",
  };
}

export function issueSeverityLabel(severity: "error" | "warning", locale: "en-US" | "zh-CN"): string {
  if (locale === "zh-CN") return severity === "error" ? "错误" : "警告";
  return severity === "error" ? "Error" : "Warning";
}

/**
 * Real-time hints derived purely from form state (without contacting the backend).
 * Mirrors the cross-field validators declared in the backend AgentBuilderConfig
 * model so users see guidance before clicking Validate.
 */
export function deriveRuntimeHints(
  form: BuilderFormState,
  locale: "en-US" | "zh-CN",
): Array<{ field: string; message: string }> {
  const hints: Array<{ field: string; message: string }> = [];
  const zh = locale === "zh-CN";

  // Backend _ensure_routing_target: at least one of deployment_id / model_key / routing_key
  if (!form.deployment_id.trim() && !form.model_key.trim() && !form.routing_key.trim()) {
    hints.push({
      field: "deployment_id",
      message: zh
        ? "至少需要填写 deployment_id、model_key 或 routing_key 中的一项"
        : "At least one of deployment_id, model_key, or routing_key is required",
    });
  }

  // Backend: escalation_message required when confidence_threshold is set
  const confidence = parseFloat(form.confidence_threshold);
  if (!Number.isNaN(confidence) && !form.escalation_message.trim()) {
    hints.push({
      field: "escalation_message",
      message: zh
        ? "设置了 confidence_threshold 时必须填写转人工消息"
        : "escalation_message is required when confidence_threshold is set",
    });
  }

  // Range guards — surface as hints so the user sees the boundary before backend rejects.
  if (!Number.isNaN(confidence) && (confidence < 0 || confidence > 1)) {
    hints.push({
      field: "confidence_threshold",
      message: zh ? "取值范围为 0–1" : "Must be between 0 and 1",
    });
  }
  const temperature = parseFloat(form.temperature);
  if (!Number.isNaN(temperature) && (temperature < 0 || temperature > 2)) {
    hints.push({
      field: "temperature",
      message: zh ? "取值范围为 0–2" : "Must be between 0 and 2",
    });
  }
  const maxTokens = parseInt(form.max_tokens, 10);
  if (!Number.isNaN(maxTokens) && (maxTokens < 1 || maxTokens > 8192)) {
    hints.push({
      field: "max_tokens",
      message: zh ? "取值范围为 1–8192" : "Must be between 1 and 8192",
    });
  }

  return hints;
}
