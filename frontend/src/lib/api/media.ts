import { apiDownloadBlob, apiGet, apiPatch, apiPost } from "./core";

export type MediaGenerationKind = "image" | "video";
export type MediaGenerationMode = "manual_prompt" | "natural_language" | "material_breakdown";
export type MediaAssetKind = "image" | "video";
export type MediaProviderType =
  | "openai_images"
  | "nano_banana"
  | "volcengine_seedance"
  | "openai_compatible_media"
  | "custom";
export type MediaGenerationJobStatus = "queued" | "running" | "succeeded" | "failed" | "canceled";

export interface MediaAssetRef {
  kind: MediaAssetKind;
  bucket?: string | null;
  object_key?: string | null;
  url?: string | null;
  mime_type?: string | null;
  metadata?: Record<string, unknown>;
}

export interface MediaModelCapability {
  provider_key: string;
  provider_type: MediaProviderType;
  model_key: string;
  routing_key: string;
  kind: MediaGenerationKind;
  display_name: string;
  capabilities: string[];
  default_parameters: Record<string, unknown>;
  price_unit: "output" | "second";
  price_usd: string;
  pricing_note?: string | null;
  status: "active" | "not_configured";
  configuration_issues: string[];
  configuration_hint?: string | null;
}

export interface MediaGenerationRequest {
  kind: MediaGenerationKind;
  mode?: MediaGenerationMode;
  prompt: string;
  negative_prompt?: string | null;
  model_key?: string | null;
  routing_key?: string | null;
  reference_assets?: MediaAssetRef[];
  image_count?: number;
  aspect_ratio?: string | null;
  resolution?: string | null;
  duration_seconds?: number | null;
  fps?: number | null;
  seed?: number | null;
  metadata?: Record<string, unknown>;
}

export interface MediaGenerationPlan {
  kind: MediaGenerationKind;
  provider_key: string;
  provider_type: MediaProviderType;
  model_key: string;
  routing_key: string;
  mode: MediaGenerationMode;
  prompt: string;
  estimated_output_count: number;
  estimated_cost_usd: string;
  pricing: Record<string, unknown>;
  normalized_parameters: Record<string, unknown>;
  reference_asset_count: number;
  output_storage: Record<string, unknown>;
  execution: Record<string, unknown>;
}

export interface MediaGenerationJobCreateRequest extends MediaGenerationRequest {
  agent_id?: string | null;
  department_id?: string | null;
  conversation_id?: string | null;
}

export interface MediaGenerationJobStatusUpdate {
  status: MediaGenerationJobStatus;
  outputs?: Record<string, unknown>[] | null;
  external_job_id?: string | null;
  error_message?: string | null;
  metadata?: Record<string, unknown>;
}

export interface MediaGenerationJobResponse {
  id: string;
  tenant_id: string;
  user_id: string | null;
  department_id: string | null;
  agent_id: string | null;
  conversation_id: string | null;
  request_id: string | null;
  kind: MediaGenerationKind;
  mode: MediaGenerationMode;
  status: MediaGenerationJobStatus;
  provider_key: string;
  provider_type: MediaProviderType;
  model_key: string;
  routing_key: string;
  prompt: string;
  negative_prompt: string | null;
  reference_assets: Record<string, unknown>[];
  request_parameters: Record<string, unknown>;
  normalized_parameters: Record<string, unknown>;
  output_storage: Record<string, unknown>;
  outputs: Record<string, unknown>[];
  external_job_id: string | null;
  error_message: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface MediaGenerationJobListResponse {
  jobs: MediaGenerationJobResponse[];
  total: number;
}

export interface MediaGenerationJobEnqueueResponse {
  job_id: string;
  task_id: string;
  queued: boolean;
}

export interface MediaGenerationPollBatchItem {
  job_id: string;
  external_job_id?: string | null;
  task_id?: string | null;
  queued: boolean;
  reason?: string | null;
}

export interface MediaGenerationPollBatchResponse {
  requested: number;
  queued: number;
  skipped: number;
  failed: number;
  items: MediaGenerationPollBatchItem[];
}

export interface MediaGenerationJobEvent {
  id: string;
  action: string;
  status: string;
  request_id: string | null;
  actor_id: string | null;
  actor_type: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface MediaGenerationJobEventsResponse {
  job_id: string;
  events: MediaGenerationJobEvent[];
  total: number;
}

export interface MediaGenerationJobListParams {
  kind?: MediaGenerationKind;
  status?: MediaGenerationJobStatus;
  limit?: number;
}

export const mediaApi = {
  getModels: () => apiGet<MediaModelCapability[]>("/api/v1/media/models"),
  planGeneration: (payload: MediaGenerationRequest) =>
    apiPost<MediaGenerationPlan, MediaGenerationRequest>("/api/v1/media/generations/plan", payload),
  createGenerationJob: (payload: MediaGenerationJobCreateRequest) =>
    apiPost<MediaGenerationJobResponse, MediaGenerationJobCreateRequest>("/api/v1/media/generations", payload),
  getGenerationJobs: (params: MediaGenerationJobListParams = {}) => {
    const query = new URLSearchParams();
    if (params.kind) {
      query.set("kind", params.kind);
    }
    if (params.status) {
      query.set("status", params.status);
    }
    if (params.limit) {
      query.set("limit", String(params.limit));
    }
    const suffix = query.size > 0 ? `?${query.toString()}` : "";
    return apiGet<MediaGenerationJobListResponse>(`/api/v1/media/generations${suffix}`);
  },
  getGenerationJob: (jobId: string) => apiGet<MediaGenerationJobResponse>(`/api/v1/media/generations/${jobId}`),
  getGenerationJobEvents: (jobId: string) =>
    apiGet<MediaGenerationJobEventsResponse>(`/api/v1/media/generations/${jobId}/events`),
  downloadGenerationOutput: (jobId: string, outputIndex: number) =>
    apiDownloadBlob(`/api/v1/media/generations/${jobId}/outputs/${outputIndex}/download`),
  enqueueGenerationJob: (jobId: string) =>
    apiPost<MediaGenerationJobEnqueueResponse, Record<string, never>>(`/api/v1/media/generations/${jobId}/enqueue`, {}),
  runGenerationJob: (jobId: string) =>
    apiPost<MediaGenerationJobResponse, Record<string, never>>(`/api/v1/media/generations/${jobId}/run`, {}),
  pollGenerationJob: (jobId: string) =>
    apiPost<MediaGenerationJobResponse, Record<string, never>>(`/api/v1/media/generations/${jobId}/poll`, {}),
  enqueueRunningGenerationPolls: (limit = 20) =>
    apiPost<MediaGenerationPollBatchResponse, Record<string, never>>(
      `/api/v1/media/generations/poll/enqueue?limit=${encodeURIComponent(String(limit))}`,
      {},
    ),
  enqueueGenerationPoll: (jobId: string) =>
    apiPost<MediaGenerationJobEnqueueResponse, Record<string, never>>(
      `/api/v1/media/generations/${jobId}/poll/enqueue`,
      {},
    ),
  retryGenerationJob: (jobId: string) =>
    apiPost<MediaGenerationJobResponse, Record<string, never>>(`/api/v1/media/generations/${jobId}/retry`, {}),
  cancelGenerationJob: (jobId: string) =>
    apiPost<MediaGenerationJobResponse, Record<string, never>>(`/api/v1/media/generations/${jobId}/cancel`, {}),
  updateGenerationJobStatus: (jobId: string, payload: MediaGenerationJobStatusUpdate) =>
    apiPatch<MediaGenerationJobResponse, MediaGenerationJobStatusUpdate>(
      `/api/v1/media/generations/${jobId}/status`,
      payload,
    ),
};
