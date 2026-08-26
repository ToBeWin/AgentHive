import type { ChatMessageResponse } from "../../lib/api";

export interface ChatSourcePreview {
  id: string;
  knowledgeBaseName: string;
  sourceName: string;
  score: string;
  text: string;
}

export interface ChatKnowledgeBasePreview {
  id: string;
  name: string;
  engine: string;
  visibility: string;
  sourceCount: string;
  elapsedMs: string;
}

export interface ChatRuntimeRouteAttemptPreview {
  id: string;
  attempt: string;
  deploymentId: string;
  providerKey: string;
  modelKey: string;
  routingKey: string;
  status: string;
}

export interface ChatRunDetails {
  agentInstanceName: string;
  budgetCost: string;
  budgetEvent: string;
  budgetFallbackRequestId: string;
  budgetGuardStatus: string;
  budgetPolicyName: string;
  budgetReason: string;
  budgetReservationId: string;
  agentInstanceDetail: string;
  execution: string;
  knowledgeEnabled: boolean;
  knowledgeConfidence: string;
  knowledgeMaxScore: string;
  knowledgeReason: string;
  knowledgeRequiresReview: boolean;
  knowledgeReviewReason: string;
  knowledgeSourceCount: string;
  knowledgeTopK: string;
  licenseGate: string;
  licenseReason: string;
  message: ChatMessageResponse | null;
  modelKey: string;
  providerKey: string;
  requestId: string;
  runtimeCostUsd: string;
  runtimeErrorCode: string;
  runtimeErrorMessage: string;
  runtimeFallbackAttempts: string;
  runtimeFailureCandidateCount: string;
  runtimeFailureDetail: string;
  runtimeFailureOperation: string;
  runtimeHttpStatus: string;
  runtimeGatewayCalled: boolean;
  runtimeInputTokens: string;
  runtimeLocalResponse: string;
  runtimeMissingProviderKeys: string;
  runtimeMockAdapter: boolean;
  runtimeOutputTokens: string;
  runtimeRouteAttempts: string;
  runtimeSelectedRouteReason: string;
  runtimeSummaryMode: string;
  runtimeSummaryStatus: string;
  runtimeTotalTokens: string;
  routeAttempts: ChatRuntimeRouteAttemptPreview[];
  sources: ChatSourcePreview[];
  perBase: ChatKnowledgeBasePreview[];
}

export interface ChatMessageTraceSummary {
  confidence: string;
  execution: string;
  firstSourceName: string;
  maxScore: string;
  requiresReview: boolean;
  reviewReason: string;
  sourceCount: string;
}

const EMPTY_VALUE = "-";

export function latestAssistantRunDetails(messages: ChatMessageResponse[]): ChatRunDetails {
  const message = [...messages].reverse().find((item) => item.role === "assistant") ?? null;
  const metadata = asRecord(message?.metadata) ?? {};
  const knowledge = asRecord(metadata.knowledge);
  const agentInstance = asRecord(metadata.agent_instance);
  const budgetGuard = asRecord(metadata.budget_guard);
  const runtime = asRecord(metadata.runtime_evidence);
  const runtimeSummary = asRecord(metadata.runtime_summary);
  const runtimeDetail = asRecord(runtime?.detail);
  const routeAttempts = asRecordArray(runtime?.route_attempts);
  const rawSources = asRecordArray(metadata.agent_sources ?? metadata.knowledge_sources);

  return {
    agentInstanceName:
      agentInstance?.enabled === true ? stringValue(agentInstance.name ?? agentInstance.slug) : EMPTY_VALUE,
    budgetCost: stringValue(budgetGuard?.actual_cost_usd ?? runtime?.cost_usd ?? message?.cost_usd),
    budgetEvent: stringValue(budgetGuard?.event_type),
    budgetFallbackRequestId: stringValue(budgetGuard?.fallback_request_id),
    budgetGuardStatus: stringValue(budgetGuard?.guard_status),
    budgetPolicyName: stringValue(budgetGuard?.policy_name ?? budgetGuard?.budget_id),
    budgetReason: stringValue(budgetGuard?.reason),
    budgetReservationId: stringValue(budgetGuard?.reservation_id),
    agentInstanceDetail:
      agentInstance?.enabled === true
        ? stringValue(agentInstance.visibility ?? agentInstance.agent_key ?? agentInstance.agent_id)
        : stringValue(agentInstance?.reason),
    execution: stringValue(
      runtime?.chat_execution ?? runtime?.execution ?? metadata.chat_execution ?? metadata.local_state,
    ),
    knowledgeEnabled: knowledge?.enabled === true,
    knowledgeConfidence: stringValue(knowledge?.confidence_level),
    knowledgeMaxScore: scoreValue(knowledge?.max_score),
    knowledgeReason: stringValue(knowledge?.reason),
    knowledgeRequiresReview: knowledge?.requires_human_review === true,
    knowledgeReviewReason: stringValue(knowledge?.review_reason),
    knowledgeSourceCount: stringValue(knowledge?.source_count ?? rawSources.length),
    knowledgeTopK: stringValue(knowledge?.top_k),
    licenseGate: stringValue(metadata.license_gate),
    licenseReason: stringValue(metadata.license_gate_reason ?? metadata.required_module),
    message,
    modelKey: stringValue(runtime?.model_key ?? message?.model_key),
    providerKey: stringValue(runtime?.provider_key ?? message?.provider_key),
    requestId: stringValue(runtime?.request_id ?? message?.request_id),
    runtimeCostUsd: stringValue(runtime?.cost_usd ?? message?.cost_usd),
    runtimeErrorCode: stringValue(runtime?.error_code ?? runtimeDetail?.code),
    runtimeErrorMessage: stringValue(runtime?.error_message ?? runtimeDetail?.message),
    runtimeFallbackAttempts: stringValue(runtime?.fallback_attempt_count ?? routeAttempts.length),
    runtimeFailureCandidateCount: stringValue(runtime?.candidate_count ?? runtimeDetail?.candidate_count),
    runtimeFailureDetail: routeFailureDetail(runtime, runtimeDetail),
    runtimeFailureOperation: stringValue(runtime?.operation),
    runtimeHttpStatus: stringValue(runtime?.http_status),
    runtimeGatewayCalled: runtime?.llm_gateway_called === true,
    runtimeInputTokens: stringValue(runtime?.input_tokens ?? message?.input_tokens),
    runtimeLocalResponse: stringValue(runtime?.local_response),
    runtimeMissingProviderKeys: missingProviderKeys(runtime, runtimeDetail),
    runtimeMockAdapter: runtime?.mock_adapter === true,
    runtimeOutputTokens: stringValue(runtime?.output_tokens ?? message?.output_tokens),
    runtimeRouteAttempts: stringValue(routeAttempts.length),
    runtimeSelectedRouteReason: stringValue(
      runtime?.selected_route_reason ?? runtime?.reason ?? runtime?.local_response,
    ),
    runtimeSummaryMode: stringValue(runtimeSummary?.adapter_mode),
    runtimeSummaryStatus: stringValue(runtimeSummary?.status),
    runtimeTotalTokens: stringValue(runtime?.total_tokens ?? message?.total_tokens),
    routeAttempts: routeAttempts.map(routeAttemptPreview),
    sources: rawSources.slice(0, 5).map(sourcePreview),
    perBase: asRecordArray(knowledge?.per_base).map(knowledgeBasePreview),
  };
}

export function chatMessageTraceSummary(message: ChatMessageResponse): ChatMessageTraceSummary | null {
  if (message.role !== "assistant") {
    return null;
  }
  const metadata = asRecord(message.metadata) ?? {};
  const knowledge = asRecord(metadata.knowledge);
  const runtime = asRecord(metadata.runtime_evidence);
  const rawSources = asRecordArray(metadata.agent_sources ?? metadata.knowledge_sources);
  if (!knowledge?.enabled && rawSources.length === 0 && !metadata.chat_execution && !runtime) {
    return null;
  }
  const firstSource = rawSources[0];
  return {
    confidence: stringValue(knowledge?.confidence_level),
    execution: stringValue(
      runtime?.chat_execution ?? runtime?.execution ?? metadata.chat_execution ?? metadata.local_state,
    ),
    firstSourceName: firstSource ? stringValue(firstSource.source_name ?? firstSource.document_id) : EMPTY_VALUE,
    maxScore: scoreValue(knowledge?.max_score ?? firstSource?.score),
    requiresReview: knowledge?.requires_human_review === true,
    reviewReason: stringValue(knowledge?.review_reason ?? knowledge?.reason),
    sourceCount: stringValue(knowledge?.source_count ?? rawSources.length),
  };
}

export function chatConfidenceLabelKey(confidence: string) {
  return (
    {
      high: "chatRunConfidenceHigh",
      low: "chatRunConfidenceLow",
      medium: "chatRunConfidenceMedium",
      no_match: "chatRunConfidenceNoMatch",
      unscored: "chatRunConfidenceUnscored",
    }[confidence] ?? "chatRunConfidenceUnknown"
  );
}

function sourcePreview(source: Record<string, unknown>, index: number): ChatSourcePreview {
  return {
    id: stringValue(source.chunk_id ?? source.document_id ?? `${index}`),
    knowledgeBaseName: stringValue(source.knowledge_base_name),
    score: scoreValue(source.score),
    sourceName: stringValue(source.source_name ?? source.document_id ?? source.chunk_id),
    text: stringValue(source.text),
  };
}

function knowledgeBasePreview(item: Record<string, unknown>): ChatKnowledgeBasePreview {
  return {
    elapsedMs: stringValue(item.elapsed_ms),
    engine: stringValue(item.engine),
    id: stringValue(item.knowledge_base_id),
    name: stringValue(item.knowledge_base_name ?? item.knowledge_base_id),
    sourceCount: stringValue(item.source_count),
    visibility: stringValue(item.knowledge_base_visibility),
  };
}

function routeAttemptPreview(item: Record<string, unknown>, index: number): ChatRuntimeRouteAttemptPreview {
  return {
    id: stringValue(item.request_id ?? item.deployment_id ?? `${index}`),
    attempt: stringValue(item.attempt ?? index + 1),
    deploymentId: stringValue(item.deployment_id),
    providerKey: stringValue(item.provider_key),
    modelKey: stringValue(item.model_key ?? item.model),
    routingKey: stringValue(item.routing_key),
    status: stringValue(item.status),
  };
}

function routeFailureDetail(runtime: Record<string, unknown> | null, detail: Record<string, unknown> | null) {
  const requestModel = stringValue(detail?.request_model_key ?? runtime?.request_model_key);
  const requestRoute = stringValue(detail?.request_routing_key ?? runtime?.request_routing_key);
  const policyRoute = stringValue(detail?.policy_routing_key ?? runtime?.policy_routing_key);
  const parts = [
    requestModel !== EMPTY_VALUE ? `model=${requestModel}` : null,
    requestRoute !== EMPTY_VALUE ? `route=${requestRoute}` : null,
    policyRoute !== EMPTY_VALUE ? `policy_route=${policyRoute}` : null,
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : EMPTY_VALUE;
}

function missingProviderKeys(runtime: Record<string, unknown> | null, detail: Record<string, unknown> | null) {
  const keys = arrayStringValue(detail?.missing_provider_keys ?? runtime?.missing_provider_keys);
  return keys.length ? keys.join(", ") : EMPTY_VALUE;
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

function arrayStringValue(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => stringValue(item)).filter((item) => item !== EMPTY_VALUE);
}

function scoreValue(value: unknown): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return EMPTY_VALUE;
  }
  return parsed <= 1 ? parsed.toFixed(3) : parsed.toFixed(1);
}
