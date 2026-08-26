import { ApiError, apiGet, apiPost, apiPostSse } from "./core";
import type { LLMUsageResponse } from "./models";

export interface ChatSessionCreateRequest {
  title?: string | null;
  agent_id?: string | null;
  channel_id?: string | null;
  department_id?: string | null;
  source: string;
  metadata?: Record<string, unknown>;
}

export interface ChatSessionResponse {
  id: string;
  tenant_id: string;
  title: string;
  agent_id: string | null;
  channel_id: string | null;
  user_id: string | null;
  department_id: string | null;
  source: string;
  status: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ChatSessionListResponse {
  sessions: ChatSessionResponse[];
  total: number;
  limit: number;
  offset: number;
}

export interface ChatMessageResponse {
  id: string;
  tenant_id: string;
  conversation_id: string;
  role: "system" | "user" | "assistant" | string;
  content: string;
  user_id: string | null;
  request_id: string | null;
  model_key: string | null;
  provider_key: string | null;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost_usd: string | number;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ChatMessageListResponse {
  messages: ChatMessageResponse[];
}

export interface ChatMessageCreateRequest {
  content: string;
  model_key?: string | null;
  routing_key?: string | null;
  temperature?: number | null;
  max_tokens?: number | null;
  metadata?: Record<string, unknown>;
}

export interface ChatMessageCreateResponse {
  user_message: ChatMessageResponse;
  assistant_message: ChatMessageResponse;
  request_id: string;
  provider_key: string;
  model_key: string;
  usage: LLMUsageResponse;
  metadata: Record<string, unknown>;
}

export interface ChatStreamMetadataResponse {
  user_message: ChatMessageResponse;
  request_id: string;
  provider_key: string;
  model_key: string;
  usage: LLMUsageResponse;
  metadata: Record<string, unknown>;
}

export interface ChatStreamDeltaResponse {
  content: string;
}

export interface ChatStreamStatusResponse {
  stage: "accepted" | "runtime" | "knowledge" | "persisted" | string;
  state: "started" | "completed" | "failed" | string;
  enabled?: boolean;
  source_count?: number;
  confidence_level?: string | null;
  message_id?: string;
  request_id?: string;
}

export interface ChatStreamDoneResponse {
  message_id: string;
}

export interface ChatStreamErrorResponse {
  status: number;
  detail: unknown;
  request_id?: string | null;
}

export interface ChatStreamCallbacks {
  onDelta?: (payload: ChatStreamDeltaResponse) => void;
  onDone?: (payload: ChatStreamDoneResponse) => void;
  onError?: (payload: ChatStreamErrorResponse) => void;
  onMetadata?: (payload: ChatStreamMetadataResponse) => void;
  onStatus?: (payload: ChatStreamStatusResponse) => void;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function asChatStreamMetadata(payload: unknown): ChatStreamMetadataResponse | null {
  if (!isRecord(payload) || !isRecord(payload.user_message)) {
    return null;
  }
  return payload as unknown as ChatStreamMetadataResponse;
}

function asChatStreamDelta(payload: unknown): ChatStreamDeltaResponse | null {
  if (!isRecord(payload) || typeof payload.content !== "string") {
    return null;
  }
  return { content: payload.content };
}

function asChatStreamStatus(payload: unknown): ChatStreamStatusResponse | null {
  if (!isRecord(payload) || typeof payload.stage !== "string" || typeof payload.state !== "string") {
    return null;
  }
  return payload as unknown as ChatStreamStatusResponse;
}

function asChatStreamDone(payload: unknown): ChatStreamDoneResponse | null {
  if (!isRecord(payload) || typeof payload.message_id !== "string") {
    return null;
  }
  return { message_id: payload.message_id };
}

function asChatStreamError(payload: unknown): ChatStreamErrorResponse | null {
  if (!isRecord(payload) || typeof payload.status !== "number") {
    return null;
  }
  return {
    detail: payload.detail,
    request_id: typeof payload.request_id === "string" ? payload.request_id : null,
    status: payload.status,
  };
}

export const chatApi = {
  getChatSessions: () => apiGet<ChatSessionListResponse>("/api/v1/chat/sessions?limit=20"),
  createChatSession: (payload: ChatSessionCreateRequest) =>
    apiPost<ChatSessionResponse, ChatSessionCreateRequest>("/api/v1/chat/sessions", payload),
  getChatMessages: (sessionId: string) =>
    apiGet<ChatMessageListResponse>(`/api/v1/chat/sessions/${sessionId}/messages`),
  sendChatMessage: (sessionId: string, payload: ChatMessageCreateRequest) =>
    apiPost<ChatMessageCreateResponse, ChatMessageCreateRequest>(
      `/api/v1/chat/sessions/${sessionId}/messages`,
      payload,
    ),
  streamChatMessage: (
    sessionId: string,
    payload: ChatMessageCreateRequest,
    callbacks: ChatStreamCallbacks,
    options?: { signal?: AbortSignal },
  ) =>
    apiPostSse<ChatMessageCreateRequest>(
      `/api/v1/chat/sessions/${sessionId}/messages/stream`,
      payload,
      {
        onEvent: (event, eventPayload) => {
          if (event === "metadata") {
            const metadata = asChatStreamMetadata(eventPayload);
            if (metadata) {
              callbacks.onMetadata?.(metadata);
            }
            return;
          }
          if (event === "delta") {
            const delta = asChatStreamDelta(eventPayload);
            if (delta) {
              callbacks.onDelta?.(delta);
            }
            return;
          }
          if (event === "status") {
            const status = asChatStreamStatus(eventPayload);
            if (status) {
              callbacks.onStatus?.(status);
            }
            return;
          }
          if (event === "done") {
            const done = asChatStreamDone(eventPayload);
            if (done) {
              callbacks.onDone?.(done);
            }
            return;
          }
          if (event === "error") {
            const streamError = asChatStreamError(eventPayload);
            if (streamError) {
              callbacks.onError?.(streamError);
              throw new ApiError(
                isRecord(streamError.detail) && typeof streamError.detail.message === "string"
                  ? streamError.detail.message
                  : `Request failed with status ${streamError.status}`,
                streamError.status,
                { detail: streamError.detail },
              );
            }
          }
        },
      },
      options ? { signal: options.signal } : undefined,
    ),
};
