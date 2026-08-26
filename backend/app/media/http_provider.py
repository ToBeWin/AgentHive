from collections.abc import Callable
from time import perf_counter
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import settings
from app.media.providers import (
    BaseMediaProviderAdapter,
    MediaProviderError,
    MediaProviderNotConfiguredError,
    MediaProviderProbeResult,
    MediaProviderSubmitResult,
)
from app.media.schemas import MediaGenerationJobStatus, MediaProviderType
from app.models.media import MediaGenerationJob

AsyncClientFactory = Callable[..., httpx.AsyncClient]


class HTTPMediaProviderAdapter(BaseMediaProviderAdapter):
    def __init__(
        self,
        *,
        provider_type: MediaProviderType,
        base_url: str | None,
        api_key: str,
        image_path: str = "/images/generations",
        video_path: str = "/videos/generations",
        status_path: str | None = None,
        timeout_seconds: float | None = None,
        callback_url: str | None = None,
        webhook_secret: str = "",
        client_factory: AsyncClientFactory | None = None,
    ) -> None:
        self.provider_type = provider_type
        self.base_url = base_url
        self.api_key = api_key
        self.image_path = image_path
        self.video_path = video_path
        self.status_path = status_path
        self.timeout_seconds = timeout_seconds or settings.media_provider_timeout_seconds
        self.callback_url = callback_url
        self.webhook_secret = webhook_secret
        self.client_factory = client_factory or httpx.AsyncClient

    async def probe(self, *, probe_path: str = "/models") -> MediaProviderProbeResult:
        if not self.base_url or not self.api_key:
            missing = _missing_config(self.base_url, self.api_key)
            return MediaProviderProbeResult(
                ok=False,
                latency_ms=0,
                message=f"Media provider is missing: {', '.join(missing)}.",
                metadata={
                    "live_network_call": False,
                    "missing": missing,
                    "probe_path": probe_path,
                },
            )
        started = perf_counter()
        path = probe_path if probe_path.startswith("/") else f"/{probe_path}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            async with self.client_factory(timeout=self.timeout_seconds) as client:
                response = await client.get(
                    f"{self.base_url.rstrip('/')}/{path.lstrip('/')}",
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            latency_ms = max(0, int((perf_counter() - started) * 1000))
            return MediaProviderProbeResult(
                ok=False,
                latency_ms=latency_ms,
                message=f"Media provider probe failed: {exc.__class__.__name__}.",
                metadata={
                    "live_network_call": True,
                    "error_type": exc.__class__.__name__,
                    "probe_path": path,
                },
            )

        latency_ms = max(0, int((perf_counter() - started) * 1000))
        ok = 200 <= response.status_code < 300
        return MediaProviderProbeResult(
            ok=ok,
            status_code=response.status_code,
            latency_ms=latency_ms,
            message=(
                "Media provider responded to a live probe."
                if ok
                else f"Media provider probe returned HTTP {response.status_code}."
            ),
            metadata={
                "live_network_call": True,
                "status_code": response.status_code,
                "probe_path": path,
            },
        )

    async def submit(self, job: MediaGenerationJob) -> MediaProviderSubmitResult:
        if not self.base_url or not self.api_key:
            raise MediaProviderNotConfiguredError(
                f"Media provider {job.provider_type} is not configured for live generation.",
                metadata={
                    "provider_key": job.provider_key,
                    "provider_type": job.provider_type,
                    "model_key": job.model_key,
                    "routing_key": job.routing_key,
                    "live_network_call": False,
                    "missing": _missing_config(self.base_url, self.api_key),
                },
            )
        path = self.video_path if job.kind == "video" else self.image_path
        payload = _provider_payload(
            job, callback_url=self.callback_url, webhook_secret=self.webhook_secret
        )
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            async with self.client_factory(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url.rstrip('/')}/{path.lstrip('/')}",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            raise MediaProviderError(
                f"Media provider returned HTTP {exc.response.status_code}.",
                metadata={
                    "provider_key": job.provider_key,
                    "provider_type": job.provider_type,
                    "live_network_call": True,
                    "status_code": exc.response.status_code,
                },
            ) from exc
        except httpx.HTTPError as exc:
            raise MediaProviderError(
                f"Media provider call failed: {exc.__class__.__name__}.",
                metadata={
                    "provider_key": job.provider_key,
                    "provider_type": job.provider_type,
                    "live_network_call": True,
                    "error_type": exc.__class__.__name__,
                },
            ) from exc
        if not isinstance(data, dict):
            raise MediaProviderError(
                "Media provider returned a non-object response.",
                metadata={
                    "provider_key": job.provider_key,
                    "provider_type": job.provider_type,
                    "live_network_call": True,
                    "response_type": type(data).__name__,
                },
            )
        return _submit_result(job, data)

    async def poll(self, job: MediaGenerationJob) -> MediaProviderSubmitResult:
        if not self.base_url or not self.api_key:
            raise MediaProviderNotConfiguredError(
                f"Media provider {job.provider_type} is not configured for status polling.",
                metadata={
                    "provider_key": job.provider_key,
                    "provider_type": job.provider_type,
                    "model_key": job.model_key,
                    "routing_key": job.routing_key,
                    "live_network_call": False,
                    "missing": _missing_config(self.base_url, self.api_key),
                },
            )
        if not self.status_path:
            raise MediaProviderError(
                f"Media provider {job.provider_type} does not support status polling.",
                metadata={
                    "provider_key": job.provider_key,
                    "provider_type": job.provider_type,
                    "model_key": job.model_key,
                    "routing_key": job.routing_key,
                    "external_job_id": job.external_job_id,
                    "live_network_call": False,
                    "poll_supported": False,
                },
            )
        if not job.external_job_id:
            raise MediaProviderError(
                "Media generation job has no external job id for status polling.",
                metadata={
                    "provider_key": job.provider_key,
                    "provider_type": job.provider_type,
                    "model_key": job.model_key,
                    "routing_key": job.routing_key,
                    "live_network_call": False,
                    "missing": ["external_job_id"],
                },
            )
        path = _status_path(self.status_path, job)
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            async with self.client_factory(timeout=self.timeout_seconds) as client:
                response = await client.get(
                    f"{self.base_url.rstrip('/')}/{path.lstrip('/')}",
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            raise MediaProviderError(
                f"Media provider status poll returned HTTP {exc.response.status_code}.",
                metadata={
                    "provider_key": job.provider_key,
                    "provider_type": job.provider_type,
                    "external_job_id": job.external_job_id,
                    "live_network_call": True,
                    "status_code": exc.response.status_code,
                },
            ) from exc
        except httpx.HTTPError as exc:
            raise MediaProviderError(
                f"Media provider status poll failed: {exc.__class__.__name__}.",
                metadata={
                    "provider_key": job.provider_key,
                    "provider_type": job.provider_type,
                    "external_job_id": job.external_job_id,
                    "live_network_call": True,
                    "error_type": exc.__class__.__name__,
                },
            ) from exc
        if not isinstance(data, dict):
            raise MediaProviderError(
                "Media provider status poll returned a non-object response.",
                metadata={
                    "provider_key": job.provider_key,
                    "provider_type": job.provider_type,
                    "external_job_id": job.external_job_id,
                    "live_network_call": True,
                    "response_type": type(data).__name__,
                },
            )
        result = _submit_result(job, data)
        result.metadata = {
            **result.metadata,
            "status_poll": True,
            "external_job_id": job.external_job_id,
        }
        return result


def _provider_payload(
    job: MediaGenerationJob,
    *,
    callback_url: str | None = None,
    webhook_secret: str = "",
) -> dict[str, Any]:
    parameters = dict(job.normalized_parameters)
    payload: dict[str, Any] = {
        "model": job.model_key,
        "prompt": job.prompt,
        "metadata": {
            "agenthive_job_id": str(job.id),
            "tenant_id": str(job.tenant_id),
            "routing_key": job.routing_key,
        },
    }
    if job.negative_prompt:
        payload["negative_prompt"] = job.negative_prompt
    if job.reference_assets:
        payload["reference_assets"] = list(job.reference_assets)
    if job.kind == "image":
        payload["n"] = int(parameters.get("image_count") or 1)
        if parameters.get("resolution"):
            payload["size"] = parameters["resolution"]
        if parameters.get("aspect_ratio"):
            payload["aspect_ratio"] = parameters["aspect_ratio"]
        if parameters.get("seed") is not None:
            payload["seed"] = parameters["seed"]
        payload["response_format"] = "url"
    else:
        if callback_url:
            payload["callback_url"] = callback_url
            payload["webhook"] = {
                "url": callback_url,
                "headers": _callback_headers(webhook_secret),
            }
        if parameters.get("duration_seconds") is not None:
            payload["duration_seconds"] = parameters["duration_seconds"]
        if parameters.get("fps") is not None:
            payload["fps"] = parameters["fps"]
        if parameters.get("resolution"):
            payload["resolution"] = parameters["resolution"]
        if parameters.get("seed") is not None:
            payload["seed"] = parameters["seed"]
    payload["parameters"] = parameters
    return payload


def _callback_headers(webhook_secret: str) -> dict[str, str]:
    if not webhook_secret:
        return {}
    return {"X-AgentHive-Media-Webhook-Secret": webhook_secret}


def _status_path(template: str, job: MediaGenerationJob) -> str:
    external_job_id = quote(str(job.external_job_id or ""), safe="")
    return (
        template.replace("{external_job_id}", external_job_id)
        .replace("{job_id}", quote(str(job.id), safe=""))
        .replace("{provider_key}", quote(job.provider_key, safe=""))
    )


def _submit_result(job: MediaGenerationJob, payload: dict[str, Any]) -> MediaProviderSubmitResult:
    provider_status = _normalize_provider_status(payload.get("status"))
    outputs = _extract_outputs(payload)
    external_job_id = _extract_external_job_id(payload)
    if provider_status is None:
        if outputs:
            provider_status = MediaGenerationJobStatus.SUCCEEDED
        elif job.kind == "video" and external_job_id:
            provider_status = MediaGenerationJobStatus.RUNNING
        else:
            provider_status = MediaGenerationJobStatus.FAILED
    error_message = _extract_error_message(payload)
    if provider_status == MediaGenerationJobStatus.FAILED and not error_message:
        error_message = "Media provider response did not include generated outputs."
    return MediaProviderSubmitResult(
        status=provider_status,
        outputs=outputs,
        external_job_id=external_job_id,
        error_message=error_message,
        metadata={
            "provider_status": payload.get("status"),
            "live_network_call": True,
            "response_id": payload.get("id"),
            "output_count": len(outputs),
        },
    )


def _normalize_provider_status(value: Any) -> MediaGenerationJobStatus | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in {"succeeded", "success", "completed", "complete", "done"}:
        return MediaGenerationJobStatus.SUCCEEDED
    if normalized in {"queued", "pending", "submitted", "running", "processing", "in_progress"}:
        return MediaGenerationJobStatus.RUNNING
    if normalized in {"failed", "error", "errored"}:
        return MediaGenerationJobStatus.FAILED
    if normalized in {"canceled", "cancelled"}:
        return MediaGenerationJobStatus.CANCELED
    return None


def _extract_outputs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for key in ("outputs", "data", "images", "videos"):
        candidates.extend(_output_candidates(payload.get(key)))
    result = payload.get("result")
    candidates.extend(_output_candidates(result))
    if isinstance(result, dict):
        for key in ("outputs", "data", "images", "videos"):
            candidates.extend(_output_candidates(result.get(key)))
    if not candidates and _has_media_output_fields(payload):
        candidates.append(payload)
    return [_normalize_output(item) for item in candidates]


def _output_candidates(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        if _has_media_output_fields(value):
            return [value]
        nested: list[dict[str, Any]] = []
        for key in ("outputs", "data", "images", "videos", "result"):
            nested.extend(_output_candidates(value.get(key)))
        return nested
    return []


def _has_media_output_fields(item: dict[str, Any]) -> bool:
    return any(
        item.get(key) is not None
        for key in (
            "bucket",
            "object_key",
            "url",
            "uri",
            "image_url",
            "video_url",
            "file_url",
            "download_url",
            "b64_json",
            "base64",
            "base64_json",
        )
    )


def _normalize_output(item: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key in (
        "bucket",
        "object_key",
        "url",
        "mime_type",
        "kind",
        "width",
        "height",
        "duration_seconds",
    ):
        if item.get(key) is not None:
            output[key] = item[key]
    url = _first_string(item, "url", "image_url", "video_url", "file_url", "download_url", "uri")
    if url:
        output["url"] = url
    if item.get("duration") is not None and output.get("duration_seconds") is None:
        output["duration_seconds"] = item["duration"]
    if item.get("b64_json"):
        output["b64_json"] = item["b64_json"]
        output["mime_type"] = output.get("mime_type") or "image/png"
    if item.get("base64_json") or item.get("base64"):
        output["b64_json"] = item.get("base64_json") or item["base64"]
        output["mime_type"] = output.get("mime_type") or "image/png"
    if output.get("url") and output.get("kind") is None:
        output["kind"] = _infer_output_kind(str(output["url"]), item)
    if item.get("revised_prompt"):
        output["revised_prompt"] = item["revised_prompt"]
    if item.get("id"):
        output["provider_output_id"] = item["id"]
    if not output:
        output["metadata"] = dict(item)
    return output


def _first_string(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _infer_output_kind(url: str, item: dict[str, Any]) -> str | None:
    mime_type = str(item.get("mime_type") or item.get("content_type") or "").lower()
    if mime_type.startswith("image/"):
        return "image"
    if mime_type.startswith("video/"):
        return "video"
    lowered_url = url.lower().split("?", 1)[0]
    if lowered_url.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif")):
        return "image"
    if lowered_url.endswith((".mp4", ".mov", ".webm", ".m4v", ".avi")):
        return "video"
    return None


def _extract_external_job_id(payload: dict[str, Any]) -> str | None:
    for key in ("job_id", "task_id", "request_id", "id"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _extract_error_message(payload: dict[str, Any]) -> str | None:
    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message:
            return message
    if isinstance(error, str) and error:
        return error
    message = payload.get("message")
    if isinstance(message, str) and message:
        return message
    return None


def _missing_config(base_url: str | None, api_key: str) -> list[str]:
    missing: list[str] = []
    if not base_url:
        missing.append("base_url")
    if not api_key:
        missing.append("api_key")
    return missing
