import type {
  MediaAssetKind,
  MediaGenerationJobResponse,
  MediaGenerationJobStatus,
  MediaGenerationKind,
  MediaGenerationMode,
  MediaGenerationPlan,
  MediaGenerationRequest,
  MediaModelCapability,
} from "../../lib/api";

export interface MediaJobFormState {
  kind: MediaGenerationKind;
  mode: MediaGenerationMode;
  prompt: string;
  negativePrompt: string;
  modelKey: string;
  routingKey: string;
  referenceUrl: string;
  referenceKind: MediaAssetKind;
  imageCount: number;
  aspectRatio: string;
  resolution: string;
  durationSeconds: number;
  fps: number;
  seed: string;
}

export const defaultMediaJobForm: MediaJobFormState = {
  kind: "image",
  mode: "manual_prompt",
  prompt: "",
  negativePrompt: "",
  modelKey: "",
  routingKey: "",
  referenceUrl: "",
  referenceKind: "image",
  imageCount: 1,
  aspectRatio: "1:1",
  resolution: "1024x1024",
  durationSeconds: 5,
  fps: 24,
  seed: "",
};

export function defaultRoutingKeyForKind(kind: MediaGenerationKind) {
  return kind === "video" ? "video-generation" : "image-generation";
}

export function mediaGenerationRequestFromForm(form: MediaJobFormState): MediaGenerationRequest {
  return {
    kind: form.kind,
    mode: form.mode,
    prompt: form.prompt.trim(),
    negative_prompt: form.negativePrompt.trim() || null,
    model_key: form.modelKey || null,
    routing_key: form.routingKey || null,
    reference_assets: referenceAssets(form),
    image_count: form.kind === "image" ? form.imageCount : 1,
    aspect_ratio: form.kind === "image" ? form.aspectRatio || null : null,
    resolution: form.resolution || null,
    duration_seconds: form.kind === "video" ? form.durationSeconds : null,
    fps: form.kind === "video" ? form.fps : null,
    seed: form.seed ? Number(form.seed) : null,
    metadata: { source: "agenthive_console" },
  };
}

export function referenceAssets(form: MediaJobFormState) {
  const url = form.referenceUrl.trim();
  if (!url) {
    return [];
  }
  return [
    {
      kind: form.referenceKind as MediaAssetKind,
      url,
      metadata: { source: "console_reference_url" },
    },
  ];
}

export const prototypeMediaModels: MediaModelCapability[] = [
  {
    provider_key: "google",
    provider_type: "nano_banana",
    model_key: "google/nano-banana",
    routing_key: "image-generation",
    kind: "image",
    display_name: "Nano Banana",
    capabilities: ["prompt_to_image", "reference_image", "style_transfer"],
    default_parameters: { image_count: 1, resolution: "1024x1024" },
    price_unit: "output",
    price_usd: "0.030000",
    pricing_note: "Built-in estimate.",
    status: "active",
    configuration_issues: [],
    configuration_hint: null,
  },
  {
    provider_key: "volcengine",
    provider_type: "volcengine_seedance",
    model_key: "volcengine/seedance-2.0",
    routing_key: "video-generation",
    kind: "video",
    display_name: "Volcengine Seedance 2.0",
    capabilities: ["prompt_to_video", "reference_image_to_video", "reference_video", "async_job"],
    default_parameters: { duration_seconds: 5, fps: 24, resolution: "1080p" },
    price_unit: "second",
    price_usd: "0.080000",
    pricing_note: "Built-in estimate.",
    status: "active",
    configuration_issues: [],
    configuration_hint: null,
  },
];

export const prototypeMediaJobs: MediaGenerationJobResponse[] = [
  {
    id: "proto-media-job-1",
    tenant_id: "proto-tenant",
    user_id: "proto-user",
    department_id: null,
    agent_id: null,
    conversation_id: null,
    request_id: "proto-media-request",
    kind: "image",
    mode: "manual_prompt",
    status: "queued",
    provider_key: "google",
    provider_type: "nano_banana",
    model_key: "google/nano-banana",
    routing_key: "image-generation",
    prompt: "Generate a clean white-background sneaker product image.",
    negative_prompt: null,
    reference_assets: [],
    request_parameters: { image_count: 2, aspect_ratio: "1:1" },
    normalized_parameters: { image_count: 2, aspect_ratio: "1:1", resolution: "1024x1024" },
    output_storage: { driver: "minio", prefix: "generated/image_generation" },
    outputs: [],
    external_job_id: null,
    error_message: null,
    metadata: {
      estimated_output_count: 2,
      estimated_cost_usd: "0.060000",
      pricing: { currency: "USD", unit: "output", unit_price_usd: "0.030000" },
      reference_asset_count: 0,
    },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    started_at: null,
    completed_at: null,
  },
  {
    id: "proto-media-job-2",
    tenant_id: "proto-tenant",
    user_id: "proto-user",
    department_id: null,
    agent_id: null,
    conversation_id: null,
    request_id: "proto-media-request-video",
    kind: "video",
    mode: "natural_language",
    status: "running",
    provider_key: "volcengine",
    provider_type: "volcengine_seedance",
    model_key: "volcengine/seedance-2.0",
    routing_key: "video-generation",
    prompt: "用参考图生成一条 8 秒 16:9 的电商卖点短视频。",
    negative_prompt: null,
    reference_assets: [{ kind: "image", url: "https://cdn.example.com/ref/shoe.png" }],
    request_parameters: { duration_seconds: 8, fps: 24, resolution: "1080p" },
    normalized_parameters: { duration_seconds: 8, fps: 24, resolution: "1080p", aspect_ratio: "16:9" },
    output_storage: { driver: "minio", prefix: "generated/video_generation" },
    outputs: [],
    external_job_id: "seedance-task-proto-42",
    error_message: null,
    metadata: {
      estimated_output_count: 1,
      estimated_cost_usd: "0.640000",
      pricing: { currency: "USD", unit: "second", unit_price_usd: "0.080000" },
      reference_asset_count: 1,
      poll: { provider_type: "volcengine_seedance", external_job_id: "seedance-task-proto-42" },
    },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    started_at: new Date().toISOString(),
    completed_at: null,
  },
];

export function statusLabelKey(status: MediaGenerationJobStatus) {
  const suffix = status
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join("");
  return `mediaStatus${suffix}`;
}

export function modeLabelKey(mode: MediaGenerationMode) {
  if (mode === "manual_prompt") {
    return "mediaModeManualPrompt";
  }
  if (mode === "material_breakdown") {
    return "mediaModeMaterialBreakdown";
  }
  return "mediaModeNaturalLanguage";
}

export function kindLabelKey(kind: MediaGenerationKind) {
  return kind === "video" ? "mediaKindVideo" : "mediaKindImage";
}

export function hasActiveMediaJobs(jobs: MediaGenerationJobResponse[]) {
  return jobs.some((job) => job.status === "queued" || job.status === "running");
}

export function formatDateTime(value: string | null) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit",
  }).format(date);
}

export function shortId(value: string | null) {
  if (!value) {
    return "-";
  }
  if (value.startsWith("proto-")) {
    return value;
  }
  return value.slice(0, 8);
}

export function safeJson(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2);
}

export function prototypePlanFromRequest(
  request: MediaGenerationRequest,
  models: MediaModelCapability[] = prototypeMediaModels,
): MediaGenerationPlan {
  const model = pickPrototypeModel(request, models);
  const normalized = prototypeNormalizedParameters(request);
  const estimatedOutputCount =
    request.kind === "video" ? Number(normalized.duration_seconds ?? 5) : Number(normalized.image_count ?? 1);
  const price = Number(model.price_usd);
  return {
    kind: request.kind,
    provider_key: model.provider_key,
    provider_type: model.provider_type,
    model_key: model.model_key,
    routing_key: request.routing_key || model.routing_key,
    mode: request.mode ?? "manual_prompt",
    prompt: request.prompt,
    estimated_output_count: estimatedOutputCount,
    estimated_cost_usd: (price * estimatedOutputCount).toFixed(6),
    pricing: { currency: "USD", unit: model.price_unit, unit_price_usd: model.price_usd },
    normalized_parameters: normalized,
    reference_asset_count: request.reference_assets?.length ?? 0,
    output_storage: { driver: "minio", prefix: `generated/${request.kind}_generation` },
    execution: {
      mode: request.kind === "video" ? "async_provider_job" : "sync_provider_job",
      prototype: true,
      governed_by: ["license", "budget", "policy", "audit"],
    },
  };
}

export function prototypeJobFromRequest(
  request: MediaGenerationRequest,
  models: MediaModelCapability[] = prototypeMediaModels,
): MediaGenerationJobResponse {
  const plan = prototypePlanFromRequest(request, models);
  const now = new Date().toISOString();
  return {
    id: `proto-media-job-${Date.now()}`,
    tenant_id: "proto-tenant",
    user_id: "proto-user",
    department_id: null,
    agent_id: null,
    conversation_id: null,
    request_id: `proto-media-request-${Date.now()}`,
    kind: request.kind,
    mode: plan.mode,
    status: "queued",
    provider_key: plan.provider_key,
    provider_type: plan.provider_type,
    model_key: plan.model_key,
    routing_key: plan.routing_key,
    prompt: request.prompt,
    negative_prompt: request.negative_prompt ?? null,
    reference_assets: (request.reference_assets ?? []).map((asset) => ({ ...asset })),
    request_parameters: { ...request },
    normalized_parameters: plan.normalized_parameters,
    output_storage: plan.output_storage,
    outputs: [],
    external_job_id: null,
    error_message: null,
    metadata: {
      estimated_output_count: plan.estimated_output_count,
      estimated_cost_usd: plan.estimated_cost_usd,
      pricing: plan.pricing,
      reference_asset_count: plan.reference_asset_count,
      prototype: true,
    },
    created_at: now,
    updated_at: now,
    started_at: null,
    completed_at: null,
  };
}

export function prototypeMediaEvents(job: MediaGenerationJobResponse) {
  const created = job.created_at;
  const updated = job.updated_at;
  return [
    prototypeMediaEvent(job, "media.generation.create", "queued", created),
    ...(job.started_at ? [prototypeMediaEvent(job, "media.generation.enqueue", "running", job.started_at)] : []),
    ...(job.completed_at
      ? [prototypeMediaEvent(job, "media.generation.status_update", job.status, job.completed_at)]
      : updated !== created
        ? [prototypeMediaEvent(job, "media.generation.status_update", job.status, updated)]
        : []),
  ];
}

export function transitionPrototypeMediaJob(
  job: MediaGenerationJobResponse,
  action: "cancel" | "enqueue" | "enqueue_poll" | "poll" | "retry" | "run",
): MediaGenerationJobResponse {
  const now = new Date().toISOString();
  if (action === "enqueue") {
    return {
      ...job,
      status: "running",
      external_job_id: job.external_job_id ?? `proto-provider-${job.kind}-${Date.now()}`,
      metadata: { ...job.metadata, queue: prototypeQueueMetadata(now, job.status) },
      started_at: job.started_at ?? now,
      updated_at: now,
    };
  }
  if (action === "enqueue_poll") {
    return {
      ...job,
      metadata: { ...job.metadata, poll_queue: prototypeQueueMetadata(now, job.status) },
      updated_at: now,
    };
  }
  if (action === "retry") {
    return {
      ...job,
      status: "queued",
      error_message: null,
      outputs: [],
      metadata: { ...job.metadata, retry: { requested_at: now, prototype: true } },
      completed_at: null,
      updated_at: now,
    };
  }
  if (action === "cancel") {
    return {
      ...job,
      status: "canceled",
      metadata: { ...job.metadata, canceled: { at: now, prototype: true } },
      completed_at: now,
      updated_at: now,
    };
  }
  return {
    ...job,
    status: "succeeded",
    external_job_id: job.external_job_id ?? `proto-provider-${job.kind}-${Date.now()}`,
    outputs: prototypeOutputsForJob(job),
    metadata: { ...job.metadata, completed_by: action, prototype: true },
    started_at: job.started_at ?? now,
    completed_at: now,
    updated_at: now,
  };
}

function pickPrototypeModel(request: MediaGenerationRequest, models: MediaModelCapability[]) {
  return (
    models.find((model) => model.model_key === request.model_key && model.kind === request.kind) ??
    models.find((model) => model.kind === request.kind && model.status === "active") ??
    prototypeMediaModels.find((model) => model.kind === request.kind) ??
    prototypeMediaModels[0]
  );
}

function prototypeNormalizedParameters(request: MediaGenerationRequest) {
  if (request.kind === "video") {
    return {
      duration_seconds: request.duration_seconds ?? 5,
      fps: request.fps ?? 24,
      resolution: request.resolution ?? "1080p",
      aspect_ratio: request.aspect_ratio ?? "16:9",
      reference_assets: { count: request.reference_assets?.length ?? 0 },
    };
  }
  return {
    image_count: request.image_count ?? 1,
    aspect_ratio: request.aspect_ratio ?? "1:1",
    resolution: request.resolution ?? "1024x1024",
    seed: request.seed ?? null,
    reference_assets: { count: request.reference_assets?.length ?? 0 },
  };
}

function prototypeQueueMetadata(now: string, status: string) {
  return {
    task_id: `proto-task-${Date.now()}`,
    enqueued_at: now,
    actor_id: "proto-user",
    request_id: "proto-media-request",
    status_at_enqueue: status,
    prototype: true,
  };
}

function prototypeOutputsForJob(job: MediaGenerationJobResponse) {
  const extension = job.kind === "video" ? "mp4" : "png";
  const mime = job.kind === "video" ? "video/mp4" : "image/png";
  return [
    {
      bucket: "agenthive-media",
      object_key: `prototype/${job.id}/output.${extension}`,
      mime_type: mime,
      metadata: { prototype: true, provider_key: job.provider_key, model_key: job.model_key },
    },
  ];
}

function prototypeMediaEvent(job: MediaGenerationJobResponse, action: string, status: string, createdAt: string) {
  return {
    id: `${job.id}-${action}-${createdAt}`,
    action,
    status,
    request_id: job.request_id,
    actor_id: "proto-user",
    actor_type: "user",
    details: { prototype: true, model_key: job.model_key, routing_key: job.routing_key },
    created_at: createdAt,
  };
}
