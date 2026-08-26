import { apiGet, apiPatch, apiPost } from "./core";

export type ChannelType = "wecom" | "dingtalk" | "feishu" | "web_widget" | "rest_api";
export type ChannelStatus = "active" | "disabled" | "testing" | "error";
export type ChannelMessageType = "text" | "image" | "file" | "audio" | "video" | "event" | "unknown";

export interface ChannelCreateRequest {
  name: string;
  channel_type: ChannelType;
  channel_key: string;
  agent_id?: string | null;
  status: ChannelStatus;
  config: Record<string, unknown>;
  secret?: string | null;
}

export interface ChannelResponse {
  id: string;
  tenant_id: string;
  name: string;
  channel_type: ChannelType;
  channel_key: string;
  agent_id: string | null;
  status: ChannelStatus;
  webhook_path: string;
  config: Record<string, unknown>;
  secret_configured: boolean;
  created_at: string;
  updated_at: string;
}

export interface ChannelListResponse {
  channels: ChannelResponse[];
}

export interface ChannelCreateResponse {
  channel: ChannelResponse;
  message: string;
}

export interface ChannelStatusUpdateRequest {
  status: ChannelStatus;
}

export interface ChannelProcessingResult {
  routed: boolean;
  agent_key: string | null;
  conversation_id: string | null;
  response_text: string | null;
  request_id: string | null;
  model_key: string | null;
  runtime_evidence: Record<string, unknown>;
  metadata: Record<string, unknown>;
  error: string | null;
}

export interface SignatureVerification {
  checked: boolean;
  valid: boolean;
  method: string | null;
  reason: string | null;
}

export interface InboundMessageResponse {
  tenant_id: string | null;
  channel_id: string | null;
  channel_type: ChannelType;
  channel_key: string | null;
  direction: "inbound";
  external_user_id: string | null;
  external_message_id: string | null;
  conversation_key: string;
  message_type: ChannelMessageType;
  text: string | null;
  attachments: Array<Record<string, unknown>>;
  raw_payload: Record<string, unknown>;
  signature: SignatureVerification;
  trace_id: string | null;
  request_id: string | null;
  received_at: string;
}

export interface ChannelTestRequest {
  text: string;
  external_user_id: string;
  conversation_key?: string | null;
  raw_payload: Record<string, unknown>;
}

export interface ChannelTestResponse {
  ok: boolean;
  channel_id: string;
  normalized_message: InboundMessageResponse;
  processing: ChannelProcessingResult | null;
  message: string;
}

export type ChannelPushMode = "direct" | "agent";

export interface OutboundDeliveryResult {
  attempted: boolean;
  delivered: boolean;
  mode: string;
  status_code: number | null;
  target: string | null;
  error: string | null;
  details: Record<string, unknown>;
}

export interface ChannelPushRequest {
  external_user_id: string;
  text: string;
  mode: ChannelPushMode;
  conversation_key?: string | null;
  agent_key?: string | null;
  model_key?: string | null;
  metadata?: Record<string, unknown>;
}

export interface ChannelPushResponse {
  channel_id: string;
  channel_type: ChannelType;
  channel_key: string;
  mode: ChannelPushMode;
  delivered: boolean;
  agent_invoked: boolean;
  agent_key: string | null;
  response_text: string | null;
  conversation_key: string;
  outbound_delivery: OutboundDeliveryResult | null;
  request_id: string | null;
  error: string | null;
  message: string;
}

export const channelsApi = {
  getChannels: () => apiGet<ChannelListResponse>("/api/v1/channels"),
  createChannel: (payload: ChannelCreateRequest) =>
    apiPost<ChannelCreateResponse, ChannelCreateRequest>("/api/v1/channels", payload),
  updateChannelStatus: (channelId: string, payload: ChannelStatusUpdateRequest) =>
    apiPatch<ChannelResponse, ChannelStatusUpdateRequest>(`/api/v1/channels/${channelId}/status`, payload),
  testChannel: (channelId: string, payload: ChannelTestRequest) =>
    apiPost<ChannelTestResponse, ChannelTestRequest>(`/api/v1/channels/${channelId}/test`, payload),
  pushToChannel: (channelId: string, payload: ChannelPushRequest) =>
    apiPost<ChannelPushResponse, ChannelPushRequest>(`/api/v1/channels/${channelId}/push`, payload),
};
