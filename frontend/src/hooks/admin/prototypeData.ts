import type {
  AgentCatalogEntryResponse,
  AgentInstanceCreateRequest,
  AgentInstanceResponse,
  AgentInstanceUpdateRequest,
  AgentModuleActionResponse,
  AgentModuleCatalogEntry,
  AgentModuleState,
  AgentRunRequest,
  AgentRunResponse,
  ChannelCreateRequest,
  ChannelCreateResponse,
  ChannelPushRequest,
  ChannelPushResponse,
  ChannelResponse,
  ChannelStatus,
  ChannelTestRequest,
  ChannelTestResponse,
  DocumentUploadCompleteResponse,
  KnowledgeBaseCreateRequest,
  KnowledgeBaseResponse,
  KnowledgeDeleteResponse,
  KnowledgeDocumentResponse,
  RetrievalTestRequest,
  RetrievalTestResponse,
} from "../../lib/api";

export const PROTOTYPE_NOW = "2026-01-01T00:00:00.000Z";
export const PROTOTYPE_TENANT_ID = "00000000-0000-4000-8000-000000000001";
export const PROTOTYPE_DEPARTMENT_ID = "00000000-0000-4000-8000-000000000301";
export const PROTOTYPE_ADMIN_USER_ID = "00000000-0000-4000-8000-000000000201";
export const PROTOTYPE_AGENT_OWNER_ID = "00000000-0000-4000-8000-000000000202";
export const PROTOTYPE_AGENT_INSTANCE_ID = "00000000-0000-4000-8000-000000000701";
export const PROTOTYPE_HR_AGENT_INSTANCE_ID = "00000000-0000-4000-8000-000000000702";
export const PROTOTYPE_WEB_CHANNEL_ID = "00000000-0000-4000-8000-000000000801";
export const PROTOTYPE_WECOM_CHANNEL_ID = "00000000-0000-4000-8000-000000000802";
export const PROTOTYPE_AFTER_SALES_KB_ID = "kb-after-sales";
const PROTOTYPE_ENABLED_MODULE_IDS = new Set(["agent.customer_service", "agent.hr_screening"]);

export const PROTOTYPE_AGENT_MODULES: AgentModuleCatalogEntry[] = [
  moduleEntry({
    description: "Knowledge-grounded support Agent for ecommerce pre-sales and after-sales workflows.",
    enabled: true,
    id: "agent.customer_service",
    installed: true,
    licensed: true,
    name: "E-commerce Customer Service Assistant",
    priority: "P0",
    scenario: "Customer support answers, policy lookup, source citation",
    state: "enabled",
  }),
  moduleEntry({
    description: "Parses resumes, scores job fit, and drafts structured screening summaries.",
    enabled: true,
    id: "agent.hr_screening",
    installed: true,
    licensed: true,
    name: "HR Resume Screening Assistant",
    priority: "P0",
    scenario: "HR resume parsing and candidate matching",
    state: "enabled",
  }),
  moduleEntry({
    description: "Generates channel-specific copy for Xiaohongshu, Douyin, WeChat Moments, and stores.",
    enabled: false,
    id: "agent.copywriting",
    installed: true,
    licensed: true,
    name: "Copywriting Assistant",
    priority: "P0",
    scenario: "Marketing copy and platform adaptation",
    state: "installed",
  }),
  moduleEntry({
    description: "Plans product images, poster variants, reference-image edits, and brand-safe visual prompts.",
    enabled: false,
    id: "agent.image_generation",
    installed: false,
    licensed: true,
    name: "Product Image Generation Assistant",
    priority: "P0",
    required_features: ["feature.agent_catalog", "feature.media_generation", "feature.model_budget"],
    scenario: "Product image generation and reference image editing",
    state: "not_installed",
  }),
  moduleEntry({
    description: "Plans product videos from prompts, reference images, reference videos, and uploaded raw material.",
    enabled: false,
    id: "agent.video_generation",
    installed: false,
    licensed: true,
    name: "Short Video Generation Assistant",
    priority: "P0",
    required_features: ["feature.agent_catalog", "feature.media_generation", "feature.model_budget"],
    scenario: "Product video generation and material breakdown",
    state: "not_installed",
  }),
  moduleEntry({
    dependencies: ["agent.copywriting"],
    description: "Breaks down viral hooks, structure, rhythm, and reusable content patterns.",
    enabled: false,
    id: "agent.content_analysis",
    installed: false,
    licensed: false,
    name: "Viral Content Analysis Assistant",
    priority: "P1",
    scenario: "Content and video performance analysis",
    state: "not_licensed",
  }),
  moduleEntry({
    description: "Turns project facts into weekly reports, monthly reports, and executive summaries.",
    enabled: false,
    id: "agent.report_writer",
    installed: false,
    licensed: true,
    name: "Project Report Assistant",
    priority: "P1",
    scenario: "Project updates and management reporting",
    state: "not_installed",
  }),
  moduleEntry({
    description: "Creates product ideas, selling point briefs, and launch material directions.",
    enabled: false,
    id: "agent.product_design",
    installed: false,
    licensed: false,
    name: "New Product Design Assistant",
    priority: "P1",
    scenario: "Product ideas and selling point extraction",
    state: "not_licensed",
  }),
  moduleEntry({
    dependencies: ["agent.report_writer"],
    description: "Explains finance policies, reports, and common accounting workflows.",
    enabled: false,
    id: "agent.finance",
    installed: false,
    licensed: false,
    name: "Finance Efficiency Assistant",
    priority: "P2",
    required_features: ["feature.agent_catalog", "feature.model_budget"],
    scenario: "Finance Q&A and report interpretation",
    state: "not_licensed",
  }),
  moduleEntry({
    dependencies: ["agent.customer_service"],
    description: "Optimizes product titles, listings, promotion plans, and operating suggestions.",
    enabled: false,
    id: "agent.store_operations",
    installed: false,
    licensed: false,
    name: "Store Operations Assistant",
    priority: "P2",
    scenario: "Store operations and listing optimization",
    state: "not_licensed",
  }),
  moduleEntry({
    dependencies: ["agent.report_writer"],
    description: "Answers business metric questions, explains trends, and drafts data insights.",
    enabled: false,
    id: "agent.data_analyst",
    installed: false,
    licensed: false,
    name: "Data Analyst Assistant",
    priority: "P2",
    required_features: ["feature.agent_catalog", "feature.model_budget"],
    scenario: "Business data Q&A and trend analysis",
    state: "not_licensed",
  }),
];

export function prototypeAgentCatalogFromModules(modules: AgentModuleCatalogEntry[]): AgentCatalogEntryResponse[] {
  return modules.map((module) => ({
    agent_key: module.id.replace("agent.", ""),
    capabilities: capabilitiesForModule(module.id),
    category: module.priority,
    description: module.description,
    enabled: module.enabled,
    installed: module.installed,
    license_gate: "enforced",
    licensed: module.licensed,
    name: module.name,
    orchestration_features: orchestrationFeaturesForModule(module.id),
    orchestration_runtime: orchestrationRuntimeForModule(module.id),
    required_module: module.id,
    status: module.enabled ? "ready" : module.licensed ? "available" : "locked",
    version: module.version,
  }));
}

export const PROTOTYPE_AGENT_CATALOG: AgentCatalogEntryResponse[] =
  prototypeAgentCatalogFromModules(PROTOTYPE_AGENT_MODULES);

export const PROTOTYPE_KNOWLEDGE_BASES: KnowledgeBaseResponse[] = [
  {
    created_at: PROTOTYPE_NOW,
    department_ids: [PROTOTYPE_DEPARTMENT_ID],
    description: "Approved refund, exchange, shipping SLA, and escalation policies for customer-facing Agents.",
    document_count: 2,
    embedding_model_key: "bge-m3",
    id: PROTOTYPE_AFTER_SALES_KB_ID,
    metadata: { minio_bucket: "agenthive-knowledge", owner_department: "Customer Success" },
    name: "After-sales Policy",
    rag_engine: "pgvector",
    retrieval_config: {
      citation_required: true,
      metadata_filters: {},
      rerank_enabled: false,
      score_threshold: null,
      top_k: 5,
    },
    status: "active",
    tags: ["support", "refund", "exchange"],
    tenant_id: PROTOTYPE_TENANT_ID,
    updated_at: PROTOTYPE_NOW,
    visibility: "department",
  },
  {
    created_at: PROTOTYPE_NOW,
    department_ids: [],
    description: "Hiring criteria, role scorecards, and interview process notes for HR screening Agents.",
    document_count: 1,
    embedding_model_key: "bge-m3",
    id: "kb-hr-hiring",
    metadata: { minio_bucket: "agenthive-knowledge", owner_department: "Human Resources" },
    name: "HR Hiring Playbook",
    rag_engine: "pgvector",
    retrieval_config: {
      citation_required: true,
      metadata_filters: {},
      rerank_enabled: false,
      score_threshold: null,
      top_k: 5,
    },
    status: "active",
    tags: ["hr", "resume", "screening"],
    tenant_id: PROTOTYPE_TENANT_ID,
    updated_at: PROTOTYPE_NOW,
    visibility: "tenant",
  },
];

export const PROTOTYPE_KNOWLEDGE_DOCUMENTS: KnowledgeDocumentResponse[] = [
  documentEntry({
    chunk_count: 12,
    filename: "refund-policy-2026.md",
    id: "doc-refund-policy",
    knowledge_base_id: PROTOTYPE_AFTER_SALES_KB_ID,
    size_bytes: 18432,
  }),
  documentEntry({
    chunk_count: 9,
    filename: "shipping-sla.md",
    id: "doc-shipping-sla",
    knowledge_base_id: PROTOTYPE_AFTER_SALES_KB_ID,
    size_bytes: 12980,
  }),
  documentEntry({
    chunk_count: 7,
    filename: "customer-success-scorecard.md",
    id: "doc-hr-scorecard",
    knowledge_base_id: "kb-hr-hiring",
    size_bytes: 10240,
  }),
];

export const PROTOTYPE_AGENT_INSTANCES: AgentInstanceResponse[] = [
  {
    agent_key: "customer_service",
    config: {
      channel_ready: true,
      knowledge_base_ids: [PROTOTYPE_AFTER_SALES_KB_ID],
      knowledge_top_k: 3,
      rag: "pgvector",
    },
    created_at: PROTOTYPE_NOW,
    created_by: PROTOTYPE_ADMIN_USER_ID,
    department_id: PROTOTYPE_DEPARTMENT_ID,
    description: "Customer-facing support Agent with knowledge base retrieval and model budget guardrails.",
    id: PROTOTYPE_AGENT_INSTANCE_ID,
    metadata: { demo: true, readiness: "ready" },
    model_key: "qwen-plus",
    model_routing_key: "cn-primary-chat",
    module_key: "agent.customer_service",
    name: "E-commerce Customer Service Agent",
    owner_user_id: PROTOTYPE_AGENT_OWNER_ID,
    slug: "ecommerce-customer-service",
    status: "active",
    system_prompt: "Answer with approved after-sales policy and cite knowledge sources.",
    tenant_id: PROTOTYPE_TENANT_ID,
    updated_at: PROTOTYPE_NOW,
    visibility: "department",
  },
  {
    agent_key: "hr_screening",
    config: {
      knowledge_base_ids: ["kb-hr-hiring"],
      knowledge_top_k: 3,
      screening_template: "scorecard",
    },
    created_at: PROTOTYPE_NOW,
    created_by: PROTOTYPE_ADMIN_USER_ID,
    department_id: null,
    description: "HR screening Agent with hiring playbook retrieval and structured candidate scorecards.",
    id: PROTOTYPE_HR_AGENT_INSTANCE_ID,
    metadata: { demo: true, readiness: "ready" },
    model_key: "qwen-plus",
    model_routing_key: "cn-hr-screening",
    module_key: "agent.hr_screening",
    name: "HR Resume Screening Agent",
    owner_user_id: PROTOTYPE_AGENT_OWNER_ID,
    slug: "hr-resume-screening",
    status: "active",
    system_prompt: "Score candidates against approved hiring criteria and flag items for HR review.",
    tenant_id: PROTOTYPE_TENANT_ID,
    updated_at: PROTOTYPE_NOW,
    visibility: "tenant",
  },
];

export const PROTOTYPE_CHANNELS: ChannelResponse[] = [
  {
    agent_id: PROTOTYPE_AGENT_INSTANCE_ID,
    channel_key: "web-support-widget",
    channel_type: "web_widget",
    config: { allowed_origins: ["https://shop.example.com"], streaming: true },
    created_at: PROTOTYPE_NOW,
    id: PROTOTYPE_WEB_CHANNEL_ID,
    name: "Support Web Widget",
    secret_configured: true,
    status: "active",
    tenant_id: PROTOTYPE_TENANT_ID,
    updated_at: PROTOTYPE_NOW,
    webhook_path: "/api/v1/channels/webhook/web_widget/web-support-widget",
  },
  {
    agent_id: PROTOTYPE_AGENT_INSTANCE_ID,
    channel_key: "wecom-customer-service",
    channel_type: "wecom",
    config: { corp_id_configured: true, aes_key_configured: true },
    created_at: PROTOTYPE_NOW,
    id: PROTOTYPE_WECOM_CHANNEL_ID,
    name: "WeCom Customer Service",
    secret_configured: true,
    status: "testing",
    tenant_id: PROTOTYPE_TENANT_ID,
    updated_at: PROTOTYPE_NOW,
    webhook_path: "/api/v1/channels/webhook/wecom/wecom-customer-service",
  },
];

export function prototypeAgentInstance(payload: AgentInstanceCreateRequest): AgentInstanceResponse {
  const catalog = PROTOTYPE_AGENT_CATALOG.find((agent) => agent.agent_key === payload.agent_key);
  const now = new Date().toISOString();
  return {
    agent_key: payload.agent_key,
    config: payload.config ?? {},
    created_at: now,
    created_by: PROTOTYPE_ADMIN_USER_ID,
    department_id: payload.department_id ?? PROTOTYPE_DEPARTMENT_ID,
    description: payload.description ?? catalog?.description ?? null,
    id: crypto.randomUUID(),
    metadata: { prototype: true, ...(payload.metadata ?? {}) },
    model_key: payload.model_key ?? null,
    model_routing_key: payload.model_routing_key ?? null,
    module_key: catalog?.required_module ?? `agent.${payload.agent_key}`,
    name: payload.name,
    owner_user_id: payload.owner_user_id ?? null,
    slug:
      payload.slug ??
      payload.name
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/(^-|-$)/g, ""),
    status: "active",
    system_prompt: payload.system_prompt ?? null,
    tenant_id: PROTOTYPE_TENANT_ID,
    updated_at: now,
    visibility: payload.visibility ?? "tenant",
  };
}

export function prototypeUpdatedAgentInstance(
  agentId: string,
  payload: AgentInstanceUpdateRequest,
): AgentInstanceResponse {
  const current = PROTOTYPE_AGENT_INSTANCES.find((agent) => agent.id === agentId) ?? PROTOTYPE_AGENT_INSTANCES[0];
  return {
    ...current,
    config: payload.config ?? current.config,
    department_id: payload.department_id ?? current.department_id,
    description: payload.description ?? current.description,
    metadata: payload.metadata ?? current.metadata,
    model_key: payload.model_key ?? current.model_key,
    model_routing_key: payload.model_routing_key ?? current.model_routing_key,
    name: payload.name ?? current.name,
    owner_user_id: payload.owner_user_id ?? current.owner_user_id,
    status: payload.status ?? current.status,
    system_prompt: payload.system_prompt ?? current.system_prompt,
    updated_at: new Date().toISOString(),
    visibility: payload.visibility ?? current.visibility,
  };
}

export function prototypeAgentRun(agentKey: string, payload: AgentRunRequest): AgentRunResponse {
  const selectedInstance =
    PROTOTYPE_AGENT_INSTANCES.find((instance) => instance.id === payload.context?.agent_id) ??
    PROTOTYPE_AGENT_INSTANCES.find((instance) => instance.agent_key === agentKey) ??
    null;
  const catalogAgent = PROTOTYPE_AGENT_CATALOG.find((agent) => agent.agent_key === agentKey) ?? null;
  const instanceKnowledgeBaseIds = knowledgeBaseIdsFromPrototypeConfig(selectedInstance?.config);
  const knowledgeBaseIds = Array.isArray(payload.context?.knowledge_base_ids)
    ? payload.context.knowledge_base_ids.map(String)
    : instanceKnowledgeBaseIds;
  const sources = knowledgeBaseIds.flatMap((id) =>
    retrievalSources(id).map((source) => ({ ...source, knowledge_base_id: id })),
  );
  const modelKey = payload.model_key || selectedInstance?.model_key || "qwen-plus";
  const requestId = `proto-run-${String(Math.floor(Date.now() % 1000)).padStart(3, "0")}`;
  const requiredModule = selectedInstance?.module_key ?? catalogAgent?.required_module ?? `agent.${agentKey}`;
  return {
    answer: prototypeAnswerForAgent(agentKey),
    metadata: {
      agent_instance: selectedInstance
        ? {
            enabled: true,
            id: selectedInstance.id,
            name: selectedInstance.name,
            slug: selectedInstance.slug,
            visibility: selectedInstance.visibility,
          }
        : { enabled: false },
      budget_guard: {
        actual_cost_usd: "0.0064",
        actual_tokens: 1706,
        guard_status: "settled",
        policy_name: "Customer Success model spend",
        reason: "Pre-call budget guard allowed cn-primary-chat and settled usage to department ledger.",
      },
      knowledge: {
        enabled: sources.length > 0,
        knowledge_base_ids: knowledgeBaseIds,
        per_base: knowledgeBaseIds.map((id) => {
          const base = PROTOTYPE_KNOWLEDGE_BASES.find((item) => item.id === id);
          return {
            elapsed_ms: 42,
            engine: base?.rag_engine ?? "pgvector",
            knowledge_base_id: id,
            knowledge_base_name: base?.name ?? id,
            knowledge_base_visibility: base?.visibility ?? "tenant",
            source_count: sources.filter((source) => source.knowledge_base_id === id).length,
          };
        }),
        reason: sources.length ? "sources_found" : "no_sources",
        source_count: sources.length,
        top_k: Number(payload.context?.knowledge_top_k ?? 3),
      },
      license_gate: "enforced",
      license_gate_reason: `${requiredModule} licensed and enabled`,
      required_module: requiredModule,
      routing_key: payload.routing_key ?? selectedInstance?.model_routing_key ?? "cn-primary-chat",
    },
    model_key: modelKey,
    request_id: requestId,
    sources,
    usage: {
      cost_usd: "0.0064",
      input_tokens: 1280,
      output_tokens: 426,
      total_tokens: 1706,
    },
  };
}

function knowledgeBaseIdsFromPrototypeConfig(config: Record<string, unknown> | undefined): string[] {
  const rawIds = config?.knowledge_base_ids;
  if (!Array.isArray(rawIds)) {
    return [];
  }
  return rawIds.filter((item): item is string => typeof item === "string" && item.length > 0);
}

function prototypeAnswerForAgent(agentKey: string): string {
  if (agentKey === "hr_screening") {
    return (
      "候选人摘要：候选人具备 3 年电商客服与售后 SOP 经验，熟悉退款、换货、物流异常处理。\n\n" +
      "匹配评分：82/100。匹配点在客服流程、沟通稳定性和数据记录习惯；待确认项是高峰期排班接受度与跨平台工具经验。\n\n" +
      "关键证据：简历中的售后工单处理、客户满意度维护和 SOP 更新经历，与 HR Hiring Playbook 的岗位记分卡高度相关。\n\n" +
      "面试建议：重点追问复杂纠纷案例、平台规则边界意识、以及是否能按公司知识库输出标准话术。"
    );
  }

  return (
    "可以这样回复客户：您好，收到您反馈尺码偏小。根据售后政策，商品签收后 7 天内、未穿着且吊牌和包装完整的情况下支持换码。" +
    "请您先提供订单号和商品照片，我们会为您核验库存并发起换大一码流程。如当前尺码库存不足，我会同步给您可选方案。"
  );
}

export function prototypeAgentModuleAction(
  moduleId: string,
  action: "install" | "enable" | "disable",
): AgentModuleActionResponse {
  const state: AgentModuleState = action === "disable" ? "disabled" : action === "enable" ? "enabled" : "installed";
  return {
    message: `Prototype ${action} completed for ${moduleId}.`,
    module_id: moduleId,
    state,
  };
}

export function prototypeKnowledgeBase(payload: KnowledgeBaseCreateRequest): KnowledgeBaseResponse {
  const now = new Date().toISOString();
  return {
    created_at: now,
    department_ids: payload.department_ids ?? [],
    description: payload.description ?? null,
    document_count: 0,
    embedding_model_key: payload.embedding_model_key ?? "bge-m3",
    id: crypto.randomUUID(),
    metadata: { prototype: true, ...(payload.metadata ?? {}) },
    name: payload.name,
    rag_engine: payload.rag_engine,
    retrieval_config:
      payload.retrieval_config ??
      ({
        citation_required: true,
        metadata_filters: {},
        rerank_enabled: false,
        score_threshold: null,
        top_k: 5,
      } satisfies KnowledgeBaseResponse["retrieval_config"]),
    status: "active",
    tags: payload.tags ?? [],
    tenant_id: PROTOTYPE_TENANT_ID,
    updated_at: now,
    visibility: payload.visibility,
  };
}

export function prototypeKnowledgeDocuments(baseId: string): KnowledgeDocumentResponse[] {
  return PROTOTYPE_KNOWLEDGE_DOCUMENTS.filter((document) => document.knowledge_base_id === baseId);
}

export function prototypeKnowledgeUpload(baseId: string, file: File): DocumentUploadCompleteResponse {
  const now = new Date().toISOString();
  return {
    auto_ingest: true,
    diagnostics: { engine: "pgvector", minio_bucket: "agenthive-knowledge", prototype: true },
    document: {
      checksum_sha256: "sha256:prototype",
      chunk_count: 4,
      content_type: file.type || "application/octet-stream",
      created_at: now,
      error_message: null,
      filename: file.name,
      id: crypto.randomUUID(),
      knowledge_base_id: baseId,
      metadata: { prototype_upload: true },
      rag_document_id: `rag-${crypto.randomUUID()}`,
      size_bytes: file.size,
      source: "api_upload",
      status: "indexed",
      storage_bucket: "agenthive-knowledge",
      storage_object_key: `${PROTOTYPE_TENANT_ID}/${baseId}/${file.name}`,
      tenant_id: PROTOTYPE_TENANT_ID,
      updated_at: now,
    },
    ingest_status: "indexed",
    message: `${file.name} indexed in Prototype Mode.`,
  };
}

export function prototypeKnowledgeDelete(id: string, target: "base" | "document"): KnowledgeDeleteResponse {
  return {
    deleted: true,
    diagnostics: { prototype: true, target },
    id,
    message: `Prototype ${target} deleted.`,
  };
}

export function prototypeRetrievalTest(baseId: string, payload: RetrievalTestRequest): RetrievalTestResponse {
  const base = PROTOTYPE_KNOWLEDGE_BASES.find((item) => item.id === baseId) ?? PROTOTYPE_KNOWLEDGE_BASES[0];
  const results = retrievalSources(base.id).slice(0, Math.max(1, Math.min(payload.top_k, 5)));
  return {
    checked_at: new Date().toISOString(),
    diagnostics: {
      adapter: "pgvector",
      fallback_available: true,
      filters: payload.filters ?? {},
      prototype: true,
      rerank: payload.rerank ?? false,
    },
    elapsed_ms: 42,
    engine: base.rag_engine,
    knowledge_base_id: base.id,
    query: payload.query,
    results,
  };
}

export function prototypeChannel(payload: ChannelCreateRequest): ChannelCreateResponse {
  const now = new Date().toISOString();
  const channel: ChannelResponse = {
    agent_id: payload.agent_id ?? PROTOTYPE_AGENT_INSTANCE_ID,
    channel_key: payload.channel_key,
    channel_type: payload.channel_type,
    config: payload.config,
    created_at: now,
    id: crypto.randomUUID(),
    name: payload.name,
    secret_configured: Boolean(payload.secret),
    status: payload.status,
    tenant_id: PROTOTYPE_TENANT_ID,
    updated_at: now,
    webhook_path: `/api/v1/channels/webhook/${payload.channel_type}/${payload.channel_key}`,
  };
  return {
    channel,
    message: `${payload.name} created in Prototype Mode.`,
  };
}

export function prototypeChannelStatus(channelId: string, status: ChannelStatus): ChannelResponse {
  const current = PROTOTYPE_CHANNELS.find((channel) => channel.id === channelId) ?? PROTOTYPE_CHANNELS[0];
  return {
    ...current,
    status,
    updated_at: new Date().toISOString(),
  };
}

export function prototypeChannelTest(channelId: string, payload: ChannelTestRequest): ChannelTestResponse {
  const channel = PROTOTYPE_CHANNELS.find((item) => item.id === channelId) ?? PROTOTYPE_CHANNELS[0];
  const now = new Date().toISOString();
  return {
    channel_id: channel.id,
    message: "Prototype channel test normalized and routed to customer_service.",
    normalized_message: {
      attachments: [],
      channel_id: channel.id,
      channel_key: channel.channel_key,
      channel_type: channel.channel_type,
      conversation_key: payload.conversation_key ?? `test:${channel.channel_key}`,
      direction: "inbound",
      external_message_id: "proto-message-001",
      external_user_id: payload.external_user_id,
      message_type: "text",
      raw_payload: payload.raw_payload,
      received_at: now,
      request_id: "proto-run-001",
      signature: {
        checked: true,
        method: "hmac-sha256",
        reason: null,
        valid: true,
      },
      tenant_id: PROTOTYPE_TENANT_ID,
      text: payload.text,
      trace_id: "trace-proto-channel-001",
    },
    ok: true,
    processing: {
      agent_key: "customer_service",
      conversation_id: "conversation-proto-channel-001",
      error: null,
      metadata: {
        provider_key: "qwen",
      },
      model_key: "qwen-plus",
      request_id: "proto-run-001",
      response_text: "已根据售后知识库生成回复，并记录到 Customer Success 成本中心。",
      routed: true,
      runtime_evidence: {
        agent_key: "customer_service",
        channel_execution: "channel_gateway",
        channel_id: channel.id,
        channel_key: channel.channel_key,
        channel_type: channel.channel_type,
        conversation_key: payload.conversation_key ?? `test:${channel.channel_key}`,
        llm_gateway_called: true,
        message_type: "text",
        model_key: "qwen-plus",
        provider_key: "qwen",
        request_id: "proto-run-001",
        routed: true,
        signature_checked: true,
        signature_method: "hmac-sha256",
        signature_valid: true,
      },
    },
  };
}

export function prototypeChannelPush(channelId: string, payload: ChannelPushRequest): ChannelPushResponse {
  const channel = PROTOTYPE_CHANNELS.find((item) => item.id === channelId) ?? PROTOTYPE_CHANNELS[0];
  const conversationKey =
    payload.conversation_key ?? `${channel.channel_type}:${channel.channel_key}:${payload.external_user_id}`;
  const invokedAgent = payload.mode === "agent";
  const responseText = invokedAgent ? "已根据售后知识库生成主动回复，并通过当前渠道下发。" : null;
  return {
    channel_id: channel.id,
    channel_type: channel.channel_type,
    channel_key: channel.channel_key,
    mode: payload.mode,
    delivered: true,
    agent_invoked: invokedAgent,
    agent_key: invokedAgent ? "customer_service" : null,
    response_text: responseText,
    conversation_key: conversationKey,
    outbound_delivery: {
      attempted: true,
      delivered: true,
      mode: "prototype",
      status_code: 200,
      target: payload.external_user_id,
      error: null,
      details: { prototype: true },
    },
    request_id: "proto-push-001",
    error: null,
    message: `Prototype push (${payload.mode}) delivered to ${payload.external_user_id}.`,
  };
}

type PrototypeModuleEntry = Omit<
  AgentModuleCatalogEntry,
  "dependencies" | "missing_dependencies" | "missing_features" | "required_features" | "version"
> & {
  dependencies?: string[];
  required_features?: string[];
};

function moduleEntry(entry: PrototypeModuleEntry): AgentModuleCatalogEntry {
  const dependencies = entry.dependencies ?? [];
  const requiredFeatures = entry.required_features ?? ["feature.agent_catalog"];
  return {
    dependencies,
    description: entry.description,
    enabled: entry.enabled,
    id: entry.id,
    installed: entry.installed,
    licensed: entry.licensed,
    missing_dependencies: dependencies.filter((dependency) => !isModuleEnabled(dependency)),
    missing_features: requiredFeatures.filter(
      (feature) =>
        feature !== "feature.agent_catalog" &&
        feature !== "feature.model_budget" &&
        feature !== "feature.media_generation",
    ),
    name: entry.name,
    priority: entry.priority,
    required_features: requiredFeatures,
    scenario: entry.scenario,
    state: entry.state,
    version: "0.1.0",
  };
}

function isModuleEnabled(moduleId: string) {
  return PROTOTYPE_ENABLED_MODULE_IDS.has(moduleId);
}

function capabilitiesForModule(moduleId: string) {
  const capabilities: Record<string, string[]> = {
    "agent.content_analysis": ["hook_analysis", "rewrite_brief", "content_breakdown"],
    "agent.copywriting": ["copy_generation", "tone_variants", "platform_adaptation"],
    "agent.customer_service": ["knowledge_retrieval", "reply_drafting", "source_citation", "budget_guard"],
    "agent.data_analyst": ["metric_qa", "trend_analysis", "insight_summary"],
    "agent.finance": ["finance_qa", "statement_interpretation", "policy_lookup"],
    "agent.hr_screening": ["resume_parse", "candidate_scoring", "screening_summary"],
    "agent.image_generation": ["prompt_to_image", "reference_image", "image_variants", "brand_style_control"],
    "agent.product_design": ["idea_generation", "selling_point_extraction", "persona_fit"],
    "agent.report_writer": ["report_outline", "progress_summary", "risk_summary"],
    "agent.store_operations": ["listing_optimization", "campaign_ideas", "operation_suggestions"],
    "agent.video_generation": [
      "prompt_to_video",
      "reference_image_to_video",
      "reference_video",
      "duration_fps_resolution_control",
    ],
  };
  return capabilities[moduleId] ?? [];
}

function orchestrationRuntimeForModule(moduleId: string) {
  if (moduleId === "customer_service" || moduleId === "agent.customer_service") {
    return "langgraph";
  }
  if (moduleId === "agent.image_generation" || moduleId === "agent.video_generation") {
    return "media_gateway";
  }
  return "langchain";
}

function orchestrationFeaturesForModule(moduleId: string) {
  if (moduleId === "agent.customer_service") {
    return ["state_graph", "typed_state", "checkpoint_ready", "knowledge_retrieval_node"];
  }
  if (moduleId === "agent.image_generation" || moduleId === "agent.video_generation") {
    return ["media_generation_plan", "reference_assets", "async_job_ready", "minio_output_contract"];
  }
  return ["prompt_template", "runnable_chain", "structured_output"];
}

function documentEntry({
  chunk_count,
  filename,
  id,
  knowledge_base_id,
  size_bytes,
}: {
  chunk_count: number;
  filename: string;
  id: string;
  knowledge_base_id: string;
  size_bytes: number;
}): KnowledgeDocumentResponse {
  return {
    checksum_sha256: "sha256:prototype",
    chunk_count,
    content_type: "text/markdown",
    created_at: PROTOTYPE_NOW,
    error_message: null,
    filename,
    id,
    knowledge_base_id,
    metadata: { language: "zh-CN", prototype: true },
    rag_document_id: `rag-${id}`,
    size_bytes,
    source: "api_upload",
    status: "indexed",
    storage_bucket: "agenthive-knowledge",
    storage_object_key: `${PROTOTYPE_TENANT_ID}/${knowledge_base_id}/${filename}`,
    tenant_id: PROTOTYPE_TENANT_ID,
    updated_at: PROTOTYPE_NOW,
  };
}

function retrievalSources(baseId: string): RetrievalTestResponse["results"] {
  if (baseId === "kb-hr-hiring") {
    return [
      {
        chunk_id: "chunk-hr-001",
        document_id: "doc-hr-scorecard",
        metadata: { section: "scorecard" },
        score: 0.903,
        source_name: "customer-success-scorecard.md",
        text: "Customer Success candidates should be scored on communication clarity, escalation judgment, and structured problem solving.",
      },
    ];
  }
  return [
    {
      chunk_id: "chunk-refund-002",
      document_id: "doc-refund-policy",
      metadata: { section: "exchange", visibility: "department" },
      score: 0.918,
      source_name: "refund-policy-2026.md",
      text: "Size exchanges are allowed within seven days after receipt when the item is unworn and packaging plus tags are intact.",
    },
    {
      chunk_id: "chunk-shipping-004",
      document_id: "doc-shipping-sla",
      metadata: { section: "sla", visibility: "department" },
      score: 0.872,
      source_name: "shipping-sla.md",
      text: "Delayed shipments require an apology, an expected delivery window, and escalation when the SLA breach is confirmed.",
    },
  ].map((source) => ({
    ...source,
    knowledge_base_id: PROTOTYPE_AFTER_SALES_KB_ID,
    knowledge_base_name: "After-sales Policy",
  }));
}
