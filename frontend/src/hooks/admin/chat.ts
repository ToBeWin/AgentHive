import { useCallback, useEffect, useRef, useState } from "react";
import { useLocale } from "../../i18n-context";
import {
  adminApi,
  type ChatMessageCreateRequest,
  type ChatMessageResponse,
  type ChatSessionCreateRequest,
  type ChatSessionResponse,
  type ChatStreamStatusResponse,
  getApiErrorDetail,
} from "../../lib/api";
import { type AsyncState, errorToMessage, pendingChatMessage, withRetry } from "./shared";

export function chatStreamStatusMessage(status: ChatStreamStatusResponse, t: (key: string) => string) {
  if (status.state === "failed") {
    return t("chatStreamFailed");
  }
  if (status.stage === "accepted") {
    return t("chatStreamAccepted");
  }
  if (status.stage === "runtime" && status.state === "started") {
    return t("chatStreamRuntimeStarted");
  }
  if (status.stage === "knowledge") {
    return status.enabled ? t("chatStreamKnowledgeCompleted") : t("chatStreamKnowledgeSkipped");
  }
  if (status.stage === "persisted") {
    return t("chatStreamPersisted");
  }
  return t("chatStreamWorking");
}

function chatErrorMessage(error: unknown, t: (key: string) => string) {
  const detail = getApiErrorDetail(error);
  if (detail?.code === "agent_concurrency_limited") {
    const retryAfterSeconds =
      typeof detail.retry_after_seconds === "number" && Number.isFinite(detail.retry_after_seconds)
        ? Math.max(1, Math.ceil(detail.retry_after_seconds))
        : 1;
    const scope = t(chatConcurrencyScopeKey(detail.scope));
    const message = t("chatConcurrencyLimited")
      .replace("{{seconds}}", String(retryAfterSeconds))
      .replace("{{scope}}", scope);
    if (!detail.request_id) {
      return message;
    }
    return `${message} ${t("chatConcurrencyRequestId").replace("{{requestId}}", detail.request_id)}`;
  }
  return errorToMessage(error);
}

function chatConcurrencyScopeKey(scope: string | undefined) {
  if (scope === "tenant") {
    return "chatConcurrencyScopeTenant";
  }
  if (scope === "user") {
    return "chatConcurrencyScopeUser";
  }
  if (scope === "agent") {
    return "chatConcurrencyScopeAgent";
  }
  return "chatConcurrencyScopeUnknown";
}

export function useChatConsole(options: { fallbackOnError?: boolean } = {}) {
  const { t } = useLocale();
  const fallbackOnError = options.fallbackOnError === true;
  const [sessions, setSessions] = useState<AsyncState<ChatSessionResponse[]>>({
    data: null,
    error: null,
    loading: true,
  });
  const [messages, setMessages] = useState<ChatMessageResponse[]>([]);
  const [activeSession, setActiveSession] = useState<ChatSessionResponse | null>(null);
  const [sending, setSending] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const loadSessions = useCallback(async () => {
    setSessions((current) => ({ ...current, error: null, loading: true }));
    if (fallbackOnError) {
      const prototypeSession = prototypeChatSession(t);
      setSessions({ data: [prototypeSession], error: null, loading: false });
      setActiveSession((current) => current ?? prototypeSession);
      setMessages(prototypeChatMessages(prototypeSession, t));
      return;
    }
    try {
      const data = await withRetry(() => adminApi.getChatSessions());
      setSessions({ data: data.sessions, error: null, loading: false });
      setActiveSession((current) => current ?? data.sessions[0] ?? null);
    } catch (error) {
      setSessions({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [fallbackOnError, t]);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    let cancelled = false;
    async function loadMessages() {
      if (!activeSession) {
        setMessages([]);
        return;
      }
      if (fallbackOnError) {
        setMessages(prototypeChatMessages(activeSession, t));
        return;
      }
      try {
        const response = await withRetry(() => adminApi.getChatMessages(activeSession.id));
        if (!cancelled) {
          setMessages(response.messages);
        }
      } catch {
        if (!cancelled) {
          setMessages(fallbackOnError ? prototypeChatMessages(activeSession, t) : []);
        }
      }
    }
    void loadMessages();
    return () => {
      cancelled = true;
    };
  }, [activeSession, fallbackOnError, t]);

  const ensureSession = useCallback(async () => {
    if (activeSession) {
      return activeSession;
    }
    const created = await adminApi.createChatSession({
      source: "chat_console",
      title: t("chatNewConversation"),
      metadata: { ui: "admin_console" },
    });
    setActiveSession(created);
    setSessions((current) => ({
      data: [created, ...(current.data ?? [])],
      error: null,
      loading: false,
    }));
    return created;
  }, [activeSession, t]);

  const createSession = useCallback(
    async (payload?: Partial<ChatSessionCreateRequest>) => {
      setActionError(null);
      if (fallbackOnError) {
        const created = prototypeChatSession(t, payload);
        setActiveSession(created);
        setMessages([]);
        setSessions((current) => ({
          data: [created, ...(current.data ?? []).filter((item) => item.id !== created.id)],
          error: null,
          loading: false,
        }));
        return created;
      }
      try {
        const created = await adminApi.createChatSession({
          ...payload,
          agent_id: payload?.agent_id ?? null,
          metadata: { ui: "admin_console", ...(payload?.metadata ?? {}) },
          source: payload?.source ?? "chat_console",
          title: payload?.title ?? t("chatNewConversation"),
        });
        setActiveSession(created);
        setMessages([]);
        setSessions((current) => ({
          data: [created, ...(current.data ?? [])],
          error: null,
          loading: false,
        }));
        return created;
      } catch (error) {
        setActionError(chatErrorMessage(error, t));
        return null;
      }
    },
    [fallbackOnError, t],
  );

  const sendMessage = useCallback(
    async (payload: ChatMessageCreateRequest, options?: { session?: ChatSessionResponse }) => {
      setSending(true);
      setActionError(null);
      if (fallbackOnError) {
        const session = options?.session ?? activeSession ?? prototypeChatSession(t);
        if (!activeSession) {
          setActiveSession(session);
          setSessions((current) => ({ data: [session, ...(current.data ?? [])], error: null, loading: false }));
        }
        const now = new Date().toISOString();
        setMessages((current) => [
          ...current,
          prototypeUserMessage(session, payload.content, now),
          prototypeAssistantMessage(session, t("chatPrototypeAnswer"), now),
        ]);
        setSending(false);
        return null;
      }
      const clientMessageId = `client-${crypto.randomUUID()}`;
      const streamMessageId = `stream-${crypto.randomUUID()}`;
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        const session = options?.session ?? (await ensureSession());
        setMessages((current) => [
          ...current,
          pendingChatMessage({
            content: payload.content,
            id: clientMessageId,
            role: "user",
            session,
          }),
          pendingChatMessage({
            content: "",
            id: streamMessageId,
            role: "assistant",
            session,
          }),
        ]);
        await adminApi.streamChatMessage(
          session.id,
          payload,
          {
            onMetadata: (metadata) => {
              setMessages((current) =>
                current.map((item) => {
                  if (item.id === clientMessageId) {
                    return metadata.user_message;
                  }
                  if (item.id === streamMessageId) {
                    return {
                      ...item,
                      model_key: metadata.model_key,
                      provider_key: metadata.provider_key,
                      request_id: metadata.request_id,
                      input_tokens: metadata.usage.input_tokens,
                      output_tokens: metadata.usage.output_tokens,
                      total_tokens: metadata.usage.total_tokens,
                      cost_usd: metadata.usage.cost_usd,
                      metadata: {
                        ...metadata.metadata,
                        local_state: item.metadata.local_state,
                        stream_status: item.metadata.stream_status,
                      },
                    };
                  }
                  return item;
                }),
              );
            },
            onStatus: (status) => {
              setMessages((current) =>
                current.map((item) =>
                  item.id === streamMessageId
                    ? {
                        ...item,
                        // Keep content untouched; status text is surfaced via metadata.stream_status
                        // so the UI can render it separately without overwriting real content.
                        metadata: { ...item.metadata, local_state: "stream_status", stream_status: status },
                      }
                    : item,
                ),
              );
            },
            onDelta: (delta) => {
              setMessages((current) =>
                current.map((item) =>
                  item.id === streamMessageId
                    ? {
                        ...item,
                        content: `${item.content}${delta.content}`,
                        metadata: { ...item.metadata, local_state: "streaming_response" },
                      }
                    : item,
                ),
              );
            },
            onDone: (done) => {
              setMessages((current) =>
                current.map((item) => (item.id === streamMessageId ? { ...item, id: done.message_id } : item)),
              );
            },
          },
          { signal: controller.signal },
        );
        const refreshed = await adminApi.getChatMessages(session.id);
        setMessages(refreshed.messages);
        await loadSessions();
        return null;
      } catch (error) {
        // User aborted: keep the partial assistant content (if any) instead of
        // discarding it, and don't surface a noisy error banner.
        if (controller.signal.aborted) {
          setMessages((current) =>
            current
              .map((item) =>
                item.id === streamMessageId && !item.content
                  ? { ...item, content: t("chatStopped"), metadata: { ...item.metadata, local_state: "stopped" } }
                  : item,
              )
              .filter((item) => item.id !== clientMessageId || item.content),
          );
          // Try to persist whatever the server already saved.
          if (activeSession) {
            try {
              const refreshed = await adminApi.getChatMessages(activeSession.id);
              setMessages(refreshed.messages);
            } catch {
              // ignore: best-effort refresh
            }
          }
          return null;
        }
        setMessages((current) => current.filter((item) => item.id !== clientMessageId && item.id !== streamMessageId));
        setActionError(chatErrorMessage(error, t));
        return null;
      } finally {
        abortRef.current = null;
        setSending(false);
      }
    },
    [activeSession, ensureSession, fallbackOnError, loadSessions, t],
  );

  const stopGeneration = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
    }
  }, []);

  return {
    actionError,
    activeSession,
    createSession,
    messages,
    refetchSessions: loadSessions,
    sending,
    sessions,
    setActiveSession,
    sendMessage,
    stopGeneration,
  };
}

const PROTOTYPE_NOW = "2026-01-01T00:00:00.000Z";
const PROTOTYPE_TENANT_ID = "00000000-0000-4000-8000-000000000001";
const PROTOTYPE_SESSION_ID = "00000000-0000-4000-8000-000000000901";
const PROTOTYPE_AGENT_ID = "00000000-0000-4000-8000-000000000701";
const PROTOTYPE_DEPARTMENT_ID = "00000000-0000-4000-8000-000000000301";

function prototypeChatSession(
  t: (key: string) => string,
  payload?: Partial<ChatSessionCreateRequest>,
): ChatSessionResponse {
  return {
    agent_id: payload?.agent_id ?? PROTOTYPE_AGENT_ID,
    channel_id: payload?.channel_id ?? null,
    created_at: PROTOTYPE_NOW,
    department_id: payload?.department_id ?? PROTOTYPE_DEPARTMENT_ID,
    id: payload?.title ? crypto.randomUUID() : PROTOTYPE_SESSION_ID,
    metadata: {
      agent_key: "customer_service",
      ui: "prototype",
      ...(payload?.metadata ?? {}),
    },
    source: payload?.source ?? "chat_console",
    status: "active",
    tenant_id: PROTOTYPE_TENANT_ID,
    title: payload?.title ?? t("chatPrototypeSessionTitle"),
    updated_at: PROTOTYPE_NOW,
    user_id: "00000000-0000-4000-8000-000000000201",
  };
}

function prototypeChatMessages(session: ChatSessionResponse, t: (key: string) => string): ChatMessageResponse[] {
  return [
    prototypeUserMessage(session, t("chatPrototypeQuestion"), PROTOTYPE_NOW),
    prototypeAssistantMessage(session, t("chatPrototypeAnswer"), PROTOTYPE_NOW),
  ];
}

function prototypeUserMessage(session: ChatSessionResponse, content: string, createdAt: string): ChatMessageResponse {
  return {
    content,
    conversation_id: session.id,
    cost_usd: 0,
    created_at: createdAt,
    id: crypto.randomUUID(),
    input_tokens: 0,
    metadata: { surface: "prototype" },
    model_key: null,
    output_tokens: 0,
    provider_key: null,
    request_id: "proto-run-001",
    role: "user",
    tenant_id: session.tenant_id,
    total_tokens: 0,
    updated_at: createdAt,
    user_id: session.user_id,
  };
}

function prototypeAssistantMessage(
  session: ChatSessionResponse,
  content: string,
  createdAt: string,
): ChatMessageResponse {
  return {
    content,
    conversation_id: session.id,
    cost_usd: "0.0064",
    created_at: createdAt,
    id: crypto.randomUUID(),
    input_tokens: 1280,
    metadata: {
      agent_instance: {
        agent_id: session.agent_id,
        enabled: true,
        name: "E-commerce Customer Service Assistant",
        slug: "ecommerce-cs",
        visibility: "department",
      },
      agent_sources: [
        {
          chunk_id: "chunk-refund-001",
          document_id: "doc-refund-policy",
          knowledge_base_id: "kb-after-sales",
          knowledge_base_name: "After-sales Policy",
          rank: 1,
          score: 0.913,
          source_name: "refund-policy-2026.md",
          text: "Refund requests within seven days should be verified against order status, logistics receipt, and product category exclusions.",
        },
        {
          chunk_id: "chunk-shipping-004",
          document_id: "doc-shipping-sla",
          knowledge_base_id: "kb-after-sales",
          knowledge_base_name: "After-sales Policy",
          rank: 2,
          score: 0.872,
          source_name: "shipping-sla.md",
          text: "Delayed shipments require an apology, an expected delivery window, and escalation when the SLA breach is confirmed.",
        },
      ],
      chat_execution: "agent_runtime",
      budget_guard: {
        actual_cost_usd: "0.0064",
        actual_tokens: 1706,
        budget_id: "00000000-0000-4000-8000-000000140002",
        currency: "USD",
        event_type: "settle",
        fallback_request_id: "proto-run-003",
        guard_status: "settled",
        policy_name: "Customer Success model spend",
        premium_route_denied_request_id: "proto-run-002",
        reason: "Pre-call budget guard allowed cn-primary-chat and settled usage to department ledger.",
        reservation_id: "reserve-proto-run-001",
      },
      knowledge: {
        confidence_level: "high",
        enabled: true,
        knowledge_base_ids: ["kb-after-sales"],
        max_score: 0.913,
        min_score: 0.872,
        per_base: [
          {
            elapsed_ms: 42,
            engine: "pgvector",
            knowledge_base_id: "kb-after-sales",
            knowledge_base_name: "After-sales Policy",
            knowledge_base_visibility: "department",
            source_count: 2,
          },
        ],
        reason: "sources_found",
        requires_human_review: false,
        review_reason: "strong_source_match",
        source_count: 2,
        top_k: 3,
      },
      license_gate: "enforced",
      license_gate_reason: "agent.customer_service licensed and enabled",
      required_module: "agent.customer_service",
    },
    model_key: "qwen-plus",
    output_tokens: 426,
    provider_key: "qwen",
    request_id: "proto-run-001",
    role: "assistant",
    tenant_id: session.tenant_id,
    total_tokens: 1706,
    updated_at: createdAt,
    user_id: null,
  };
}
