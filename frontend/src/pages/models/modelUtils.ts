import {
  Boxes,
  Brain,
  Cloud,
  Database,
  KeyRound,
  Layers3,
  type LucideIcon,
  Network,
  Scale,
  Server,
  Sparkles,
} from "lucide-react";
import type { LLMPolicyScope, LLMProviderResponse } from "../../lib/api";

export type CredentialOwnerType = "tenant" | "department" | "user";

export interface CredentialFormState {
  apiKey: string;
  baseUrl: string;
  deploymentName: string;
  displayName: string;
  modelKey: string;
  ownerId: string;
  ownerType: CredentialOwnerType;
  probePath: string;
  routingKey: string;
}

export interface ModelPolicyFormState {
  allowedModels: string;
  allowedRoutingKeys: string;
  defaultModelKey: string;
  defaultRoutingKey: string;
  effect: "allow" | "deny";
  maxTokens: string;
  name: string;
  priority: string;
  scopeId: string;
  scopeType: LLMPolicyScope;
  status: "active" | "inactive";
}

export function defaultModelPolicyForm(): ModelPolicyFormState {
  return {
    allowedModels: "gpt-4o-mini",
    allowedRoutingKeys: "default-chat",
    defaultModelKey: "",
    defaultRoutingKey: "default-chat",
    effect: "allow",
    maxTokens: "2048",
    name: "Tenant default model policy",
    priority: "100",
    scopeId: "",
    scopeType: "tenant",
    status: "active",
  };
}

export function modelPolicyValidationKey(
  form: ModelPolicyFormState,
  options: { scopeTargetOptions?: Array<{ id: string }>; scopeTargetLoading?: boolean } = {},
) {
  const allowedModels = splitPolicyList(form.allowedModels);
  const allowedRoutes = splitPolicyList(form.allowedRoutingKeys);
  const defaultModelKey = form.defaultModelKey.trim();
  const defaultRoutingKey = form.defaultRoutingKey.trim();

  if (!form.name.trim()) {
    return "modelsPolicyNameRequired";
  }
  if (form.name.trim().length > 120 || hasControlCharacters(form.name)) {
    return "modelsPolicyNameInvalid";
  }
  if (form.scopeType !== "tenant") {
    if (options.scopeTargetLoading) {
      return "modelsPolicyScopeTargetsLoading";
    }
    const scopeId = form.scopeId.trim();
    if (!scopeId) {
      return "modelsPolicyScopeTargetRequired";
    }
    if (options.scopeTargetOptions?.length && !options.scopeTargetOptions.some((option) => option.id === scopeId)) {
      return "modelsPolicyScopeTargetInvalid";
    }
  }
  if (!isOptionalPositiveInteger(form.maxTokens)) {
    return "modelsPolicyMaxTokensInvalid";
  }
  if (!isRequiredPositiveInteger(form.priority)) {
    return "modelsPolicyPriorityInvalid";
  }
  if (!allowedModels.length && !allowedRoutes.length && !defaultModelKey && !defaultRoutingKey) {
    return "modelsPolicyRouteOrModelRequired";
  }
  if (
    allowedModels.some((item) => !isPolicyModelKey(item)) ||
    (defaultModelKey && !isPolicyModelKey(defaultModelKey))
  ) {
    return "modelsPolicyModelKeyInvalid";
  }
  if (
    allowedRoutes.some((item) => !isPolicyRoutingKey(item)) ||
    (defaultRoutingKey && !isPolicyRoutingKey(defaultRoutingKey))
  ) {
    return "modelsPolicyRoutingKeyInvalid";
  }
  if (defaultModelKey && allowedModels.length && !allowedModels.includes(defaultModelKey)) {
    return "modelsPolicyDefaultModelNotAllowed";
  }
  if (defaultRoutingKey && allowedRoutes.length && !allowedRoutes.includes(defaultRoutingKey)) {
    return "modelsPolicyDefaultRouteNotAllowed";
  }
  return null;
}

function isOptionalPositiveInteger(value: string) {
  const trimmed = value.trim();
  return !trimmed || isRequiredPositiveInteger(trimmed);
}

function isRequiredPositiveInteger(value: string) {
  const numeric = Number(value.trim());
  return Number.isSafeInteger(numeric) && numeric > 0 && numeric <= 10_000_000;
}

function hasControlCharacters(value: string) {
  return Array.from(value).some((character) => {
    const code = character.charCodeAt(0);
    return code <= 31 || code === 127;
  });
}

function isPolicyModelKey(value: string) {
  return value.length <= 160 && /^[A-Za-z0-9._:/-]+$/.test(value);
}

function isPolicyRoutingKey(value: string) {
  return value.length <= 96 && /^[A-Za-z0-9._-]+$/.test(value);
}

export interface ModelPriceFormState {
  currency: string;
  displayName: string;
  inputPer1k: string;
  modelKey: string;
  outputPer1k: string;
  providerKey: string;
}

const providerIconMap: Record<string, LucideIcon> = {
  anthropic: Brain,
  anthropic_compatible: Brain,
  ai302: Layers3,
  azure_openai: Cloud,
  baidu_qianfan: Brain,
  bedrock: Cloud,
  cohere: Brain,
  deepseek: Scale,
  doubao: Sparkles,
  fireworks: Layers3,
  gemini: KeyRound,
  glm: Brain,
  groq: Layers3,
  hunyuan: Brain,
  kimi: Sparkles,
  litellm: Layers3,
  lmstudio: Server,
  localai: Server,
  mimo: Brain,
  minimax: Sparkles,
  mistral: Brain,
  novita: Layers3,
  ollama: Server,
  openai: Sparkles,
  openai_images: Sparkles,
  openai_compatible: Layers3,
  openai_compatible_media: Layers3,
  openrouter: Network,
  qwen: Brain,
  nano_banana: Sparkles,
  sglang: Server,
  siliconflow: Layers3,
  spark: Brain,
  together: Layers3,
  vertex_ai: Cloud,
  volcengine_seedance: Sparkles,
  vllm: Database,
  xai: Brain,
  xinference: Server,
};

export interface ModelCoverageGroup {
  key: "international" | "china" | "aggregators" | "private" | "media";
  providerKeys: string[];
}

export interface ModelProtocolCoverage {
  key: "litellm" | "openaiCompatible" | "anthropicCompatible" | "mediaCompatible";
  providerKeys: string[];
}

export const modelProtocolCoverage: ModelProtocolCoverage[] = [
  {
    key: "litellm",
    providerKeys: ["litellm"],
  },
  {
    key: "openaiCompatible",
    providerKeys: [
      "openai_compatible",
      "qwen",
      "deepseek",
      "kimi",
      "minimax",
      "mimo",
      "glm",
      "doubao",
      "baidu_qianfan",
      "hunyuan",
      "spark",
      "siliconflow",
      "ai302",
    ],
  },
  {
    key: "anthropicCompatible",
    providerKeys: ["anthropic_compatible", "bedrock"],
  },
  {
    key: "mediaCompatible",
    providerKeys: ["openai_compatible_media", "openai_images", "nano_banana", "volcengine_seedance"],
  },
];

export const modelCoverageGroups: ModelCoverageGroup[] = [
  {
    key: "international",
    providerKeys: [
      "openai",
      "anthropic",
      "anthropic_compatible",
      "gemini",
      "azure_openai",
      "bedrock",
      "vertex_ai",
      "mistral",
      "cohere",
      "xai",
    ],
  },
  {
    key: "china",
    providerKeys: ["qwen", "deepseek", "kimi", "minimax", "mimo", "glm", "doubao", "baidu_qianfan", "hunyuan", "spark"],
  },
  {
    key: "aggregators",
    providerKeys: ["litellm", "openrouter", "together", "fireworks", "groq", "novita", "siliconflow", "ai302"],
  },
  {
    key: "private",
    providerKeys: ["openai_compatible", "ollama", "vllm", "sglang", "lmstudio", "xinference", "localai"],
  },
  {
    key: "media",
    providerKeys: ["openai_images", "nano_banana", "volcengine_seedance", "openai_compatible_media"],
  },
];

export const providerDisplayNames: Record<string, string> = {
  ai302: "302.AI",
  anthropic: "Claude",
  anthropic_compatible: "Anthropic-compatible",
  azure_openai: "Azure OpenAI",
  baidu_qianfan: "Baidu Qianfan",
  bedrock: "AWS Bedrock",
  cohere: "Cohere",
  deepseek: "DeepSeek",
  doubao: "Doubao",
  fireworks: "Fireworks",
  gemini: "Gemini",
  glm: "GLM",
  groq: "Groq",
  hunyuan: "Hunyuan",
  kimi: "Kimi",
  litellm: "LiteLLM",
  lmstudio: "LM Studio",
  localai: "LocalAI",
  mimo: "MiMo",
  minimax: "MiniMax",
  mistral: "Mistral",
  novita: "Novita",
  ollama: "Ollama",
  openai: "GPT",
  openai_images: "OpenAI Images",
  openai_compatible_media: "Private Media",
  openai_compatible: "OpenAI-compatible",
  openrouter: "OpenRouter",
  qwen: "Qwen",
  nano_banana: "Nano Banana",
  sglang: "SGLang",
  siliconflow: "SiliconFlow",
  spark: "Spark",
  together: "Together AI",
  vertex_ai: "Vertex AI",
  volcengine_seedance: "Seedance",
  vllm: "vLLM",
  xai: "xAI",
  xinference: "Xinference",
};

export function getProviderIcon(provider: LLMProviderResponse) {
  return providerIconMap[provider.provider_key] ?? Boxes;
}

export function formatProviderStatus(status: string, credentialConfigured: boolean) {
  if (credentialConfigured) {
    return "configured";
  }
  if (status === "active") {
    return "catalog-active";
  }
  if (status === "not_configured") {
    return "not-configured";
  }
  return status.replace(/_/g, "-").toLowerCase();
}

export function providerStatusLabelKey(status: string, credentialConfigured: boolean) {
  if (credentialConfigured) {
    return "modelsProviderStatusConfigured";
  }
  if (status === "active") {
    return "modelsProviderStatusCatalogActive";
  }
  if (status === "not_configured") {
    return "modelsProviderStatusNotConfigured";
  }
  return null;
}

export function formatAdapterDetail(provider: LLMProviderResponse) {
  if (provider.base_url) {
    return provider.base_url;
  }
  if (provider.adapter_type === "litellm") {
    return "LiteLLM adapter";
  }
  if (provider.adapter_type === "anthropic_compatible") {
    return "Anthropic-compatible adapter";
  }
  return "OpenAI-compatible adapter";
}

export function defaultModelKeyForProvider(providerKey: string) {
  const defaults: Record<string, string> = {
    ai302: "gpt-4o-mini",
    anthropic: "claude-3-5-sonnet",
    anthropic_compatible: "claude-compatible",
    azure_openai: "gpt-4o-mini",
    baidu_qianfan: "ernie-4.0-turbo-8k",
    bedrock: "anthropic.claude-3-5-sonnet-20240620-v1:0",
    cohere: "command-r-plus",
    deepseek: "deepseek-v4-flash",
    doubao: "doubao-pro-32k",
    fireworks: "accounts/fireworks/models/llama-v3p1-70b-instruct",
    gemini: "gemini-1.5-pro",
    glm: "glm-4-plus",
    groq: "llama-3.1-70b-versatile",
    hunyuan: "hunyuan-pro",
    kimi: "moonshot-v1-128k",
    litellm: "gpt-4o-mini",
    lmstudio: "local-model",
    localai: "local-chat",
    mimo: "mimo-chat",
    minimax: "abab6.5s-chat",
    mistral: "mistral-large-latest",
    novita: "meta-llama/llama-3.1-70b-instruct",
    ollama: "llama3.1",
    openai: "gpt-4o",
    openai_images: "openai/gpt-image-2",
    openai_compatible: "local-chat",
    openai_compatible_media: "openai-compatible-image",
    openrouter: "openai/gpt-4o-mini",
    qwen: "qwen-plus",
    nano_banana: "google/nano-banana",
    sglang: "local-chat",
    siliconflow: "deepseek-ai/DeepSeek-V3",
    spark: "spark-max",
    together: "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
    vertex_ai: "gemini-1.5-pro",
    volcengine_seedance: "volcengine/seedance-2.0",
    vllm: "local-chat",
    xai: "grok-2-latest",
    xinference: "local-chat",
  };
  return defaults[providerKey] ?? "chat-model";
}

export function defaultModelDisplayNameForProvider(providerKey: string) {
  const defaults: Record<string, string> = {
    openai_images: "ChatGPT Images 2.0",
    nano_banana: "Nano Banana",
    volcengine_seedance: "Seedance 2.0 Video",
    openai_compatible_media: "Private Image/Video Model",
  };
  return defaults[providerKey] ?? defaultModelKeyForProvider(providerKey);
}

export function defaultRoutingKeyForProvider(providerKey: string) {
  if (providerKey === "litellm") {
    return "default-chat";
  }
  if (providerKey === "openai_compatible") {
    return "private-chat";
  }
  if (providerKey === "anthropic_compatible") {
    return "anthropic-private-chat";
  }
  if (providerKey === "openai_images" || providerKey === "nano_banana") {
    return `${providerKey}-image`;
  }
  if (providerKey === "volcengine_seedance") {
    return "volcengine-seedance-video";
  }
  if (providerKey === "openai_compatible_media") {
    return "private-media-generation";
  }
  return `${providerKey}-chat`;
}

export function providerProtocolLabelKey(provider: LLMProviderResponse) {
  if (provider.adapter_type === "litellm") {
    return "modelsProtocolLitellm";
  }
  if (provider.adapter_type === "anthropic_compatible") {
    return "modelsProtocolAnthropicCompatible";
  }
  if (provider.provider_key === "openai_compatible_media") {
    return "modelsProtocolMediaCompatible";
  }
  return "modelsProtocolOpenaiCompatible";
}

export function providerCredentialHintKey(provider: LLMProviderResponse) {
  if (provider.adapter_type === "litellm") {
    return "modelsCredentialHintLiteLlm";
  }
  if (provider.adapter_type === "anthropic_compatible") {
    return "modelsCredentialHintAnthropicCompatible";
  }
  if (provider.provider_key === "openai_compatible_media") {
    return "modelsCredentialHintMediaCompatible";
  }
  if (provider.provider_key === "deepseek") {
    return "modelsCredentialHintDeepSeek";
  }
  if (provider.provider_key === "mimo") {
    return "modelsCredentialHintMimo";
  }
  return "modelsCredentialHintOpenAiCompatible";
}

export function isMediaProvider(providerKey: string) {
  return ["openai_images", "nano_banana", "volcengine_seedance", "openai_compatible_media"].includes(providerKey);
}

export function defaultDeploymentNameForProvider(providerKey: string, providerName: string) {
  if (providerKey === "openai_images" || providerKey === "nano_banana") {
    return `${providerName} Default Image`;
  }
  if (providerKey === "volcengine_seedance") {
    return `${providerName} Default Video`;
  }
  if (providerKey === "openai_compatible_media") {
    return `${providerName} Default Media`;
  }
  return `${providerName} Default Chat`;
}

export function modelKeyPlaceholderForProvider(providerKey: string) {
  if (providerKey === "openai_images") {
    return "openai/gpt-image-2";
  }
  if (providerKey === "nano_banana") {
    return "google/nano-banana";
  }
  if (providerKey === "volcengine_seedance") {
    return "volcengine/seedance-2.0";
  }
  if (providerKey === "openai_compatible_media") {
    return "openai-compatible-image, openai-compatible-video";
  }
  if (providerKey === "mimo") {
    return "mimo-chat";
  }
  return "gpt-4o-mini, qwen-plus, deepseek-v4-flash...";
}

export function routingKeyPlaceholderForProvider(providerKey: string) {
  if (isMediaProvider(providerKey)) {
    return defaultRoutingKeyForProvider(providerKey);
  }
  return "default-chat";
}

export function defaultTokenPriceForProvider(providerKey: string) {
  if (isMediaProvider(providerKey)) {
    return { inputPer1k: "0", outputPer1k: "0" };
  }
  return { inputPer1k: "0.001", outputPer1k: "0.002" };
}

export function getConfiguredProviderKeys(providers: LLMProviderResponse[]) {
  return new Set(
    providers.filter((provider) => provider.credential_configured).map((provider) => provider.provider_key),
  );
}

export function splitPolicyList(value: string) {
  const items = value
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
  return Array.from(new Set(items));
}
