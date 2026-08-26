import re
from decimal import Decimal
from typing import Any

from app.api.deps import Principal
from app.core.config import settings
from app.media.schemas import (
    MediaGenerationKind,
    MediaGenerationPlan,
    MediaGenerationRequest,
    MediaModelCapability,
    MediaProviderType,
)


MEDIA_MODEL_CATALOG: tuple[MediaModelCapability, ...] = (
    MediaModelCapability(
        provider_key="openai_images",
        provider_type=MediaProviderType.OPENAI_IMAGES,
        model_key="openai/gpt-image-2",
        routing_key="image-generation",
        kind=MediaGenerationKind.IMAGE,
        display_name="ChatGPT Images 2.0",
        capabilities=["prompt_to_image", "reference_image", "image_variants"],
        default_parameters={"image_count": 1, "resolution": "1024x1024"},
        price_unit="output",
        price_usd=Decimal("0.040000"),
        pricing_note="Built-in private-deployment estimate; override with customer provider pricing.",
    ),
    MediaModelCapability(
        provider_key="nano_banana",
        provider_type=MediaProviderType.NANO_BANANA,
        model_key="google/nano-banana",
        routing_key="image-generation",
        kind=MediaGenerationKind.IMAGE,
        display_name="Nano Banana",
        capabilities=["prompt_to_image", "reference_image", "style_transfer"],
        default_parameters={"image_count": 1, "resolution": "1024x1024"},
        price_unit="output",
        price_usd=Decimal("0.030000"),
        pricing_note="Built-in private-deployment estimate; override with customer provider pricing.",
    ),
    MediaModelCapability(
        provider_key="volcengine_seedance",
        provider_type=MediaProviderType.VOLCENGINE_SEEDANCE,
        model_key="volcengine/seedance-2.0",
        routing_key="video-generation",
        kind=MediaGenerationKind.VIDEO,
        display_name="Volcengine Seedance 2.0",
        capabilities=[
            "prompt_to_video",
            "reference_image_to_video",
            "reference_video",
            "async_job",
        ],
        default_parameters={"duration_seconds": 5, "fps": 24, "resolution": "1080p"},
        price_unit="second",
        price_usd=Decimal("0.080000"),
        pricing_note="Built-in private-deployment estimate per generated second; override with customer provider pricing.",
    ),
    MediaModelCapability(
        provider_key="openai_compatible_media",
        provider_type=MediaProviderType.OPENAI_COMPATIBLE_MEDIA,
        model_key="openai-compatible-image",
        routing_key="private-image-generation",
        kind=MediaGenerationKind.IMAGE,
        display_name="Private OpenAI-compatible Image Model",
        capabilities=["prompt_to_image", "reference_image"],
        default_parameters={"image_count": 1},
        price_unit="output",
        price_usd=Decimal("0.000000"),
        pricing_note="Default private endpoint estimate is zero until configured by the customer.",
    ),
    MediaModelCapability(
        provider_key="openai_compatible_media",
        provider_type=MediaProviderType.OPENAI_COMPATIBLE_MEDIA,
        model_key="openai-compatible-video",
        routing_key="private-video-generation",
        kind=MediaGenerationKind.VIDEO,
        display_name="Private OpenAI-compatible Video Model",
        capabilities=["prompt_to_video", "reference_image_to_video", "async_job"],
        default_parameters={"duration_seconds": 5, "fps": 24, "resolution": "720p"},
        price_unit="second",
        price_usd=Decimal("0.000000"),
        pricing_note="Default private endpoint estimate is zero until configured by the customer.",
    ),
)


def list_media_model_capabilities(
    provider_statuses: dict[MediaProviderType, bool] | None = None,
    provider_diagnostics: dict[MediaProviderType, list[str]] | None = None,
) -> list[MediaModelCapability]:
    diagnostics = provider_diagnostics or media_provider_diagnostics_from_settings()
    statuses = provider_statuses or {
        provider_type: not issues for provider_type, issues in diagnostics.items()
    }
    return [
        model.model_copy(
            update={
                "status": "active"
                if statuses.get(model.provider_type, False)
                else "not_configured",
                "configuration_issues": []
                if statuses.get(model.provider_type, False)
                else diagnostics[model.provider_type],
                "configuration_hint": None
                if statuses.get(model.provider_type, False)
                else _configuration_hint(diagnostics[model.provider_type]),
            }
        )
        for model in MEDIA_MODEL_CATALOG
    ]


def build_media_generation_plan(
    request: MediaGenerationRequest,
    principal: Principal,
    *,
    agent_key: str | None = None,
    provider_statuses: dict[MediaProviderType, bool] | None = None,
) -> MediaGenerationPlan:
    model = _select_media_model(request, provider_statuses=provider_statuses)
    interpreted = _interpret_media_command(request)
    parameters = {
        **model.default_parameters,
        "image_count": interpreted.get("image_count", request.image_count),
        "aspect_ratio": interpreted.get("aspect_ratio", request.aspect_ratio),
        "resolution": interpreted.get(
            "resolution", request.resolution or model.default_parameters.get("resolution")
        ),
        "duration_seconds": interpreted.get("duration_seconds", request.duration_seconds),
        "fps": interpreted.get("fps", request.fps),
        "seed": request.seed,
    }
    estimated_output_count = (
        int(parameters.get("image_count") or request.image_count)
        if request.kind == MediaGenerationKind.IMAGE
        else 1
    )
    estimated_cost = _estimate_media_cost(
        model,
        estimated_output_count=estimated_output_count,
        duration_seconds=parameters.get("duration_seconds"),
    )
    reference_asset_summary = _reference_asset_summary(request)
    return MediaGenerationPlan(
        kind=request.kind,
        provider_key=model.provider_key,
        provider_type=model.provider_type,
        model_key=model.model_key,
        routing_key=model.routing_key,
        mode=request.mode,
        prompt=request.prompt.strip(),
        estimated_output_count=estimated_output_count,
        estimated_cost_usd=estimated_cost,
        pricing={
            "currency": "USD",
            "unit": model.price_unit,
            "unit_price_usd": str(model.price_usd),
            "source": "agenthive_builtin_estimate",
            "note": model.pricing_note,
        },
        normalized_parameters={
            **{key: value for key, value in parameters.items() if value is not None},
            **(
                {"command_interpretation": interpreted["command_interpretation"]}
                if interpreted
                else {}
            ),
            **(
                {"reference_assets": reference_asset_summary}
                if reference_asset_summary["count"]
                else {}
            ),
        },
        reference_asset_count=len(request.reference_assets),
        output_storage={
            "driver": "minio",
            "bucket_scope": "tenant",
            "tenant_id": str(principal.tenant_id),
            "prefix": f"generated/{agent_key or request.kind.value}",
        },
        execution={
            "mode": "async_job" if request.kind == MediaGenerationKind.VIDEO else "sync_or_async",
            "status": "planned",
            "external_call": False,
            "reference_asset_policy": reference_asset_summary["policy"],
        },
    )


def _select_media_model(
    request: MediaGenerationRequest,
    *,
    provider_statuses: dict[MediaProviderType, bool] | None = None,
) -> MediaModelCapability:
    candidates = [model for model in MEDIA_MODEL_CATALOG if model.kind == request.kind]
    if request.model_key:
        for model in candidates:
            if model.model_key == request.model_key:
                return model
    if request.routing_key:
        routed = [model for model in candidates if model.routing_key == request.routing_key]
        if provider_statuses:
            for model in routed:
                if provider_statuses.get(model.provider_type, False):
                    return model
        for model in candidates:
            if model.routing_key == request.routing_key:
                return model
    if provider_statuses:
        for model in candidates:
            if provider_statuses.get(model.provider_type, False):
                return model
    return candidates[0]


def _estimate_media_cost(
    model: MediaModelCapability,
    *,
    estimated_output_count: int,
    duration_seconds: object,
) -> Decimal:
    if model.price_unit == "second":
        seconds = Decimal(str(duration_seconds or 0))
        return (seconds * model.price_usd).quantize(Decimal("0.000001"))
    return (Decimal(estimated_output_count) * model.price_usd).quantize(Decimal("0.000001"))


def _reference_asset_summary(request: MediaGenerationRequest) -> dict[str, Any]:
    locations: dict[str, int] = {}
    kinds: dict[str, int] = {}
    for asset in request.reference_assets:
        kinds[asset.kind.value] = kinds.get(asset.kind.value, 0) + 1
        location = "url" if asset.url else "minio"
        locations[location] = locations.get(location, 0) + 1
    return {
        "count": len(request.reference_assets),
        "by_kind": kinds,
        "locations": locations,
        "material_breakdown": request.mode.value == "material_breakdown",
        "policy": {
            "external_urls_allowed": True,
            "external_url_networks": "public_http_https_only",
            "internal_assets": "minio_bucket_object_key",
            "provider_fetch": bool(locations.get("url")),
        },
    }


def _interpret_media_command(request: MediaGenerationRequest) -> dict[str, Any]:
    if request.mode == "manual_prompt":
        return {}
    prompt = request.prompt.strip()
    if not prompt:
        return {}
    inferred: dict[str, Any] = {}
    details: dict[str, Any] = {
        "source": "agenthive_rule_parser_v1",
        "mode": request.mode.value,
        "inferred_fields": [],
        "ignored_fields": [],
    }

    if _should_infer_field(request, "aspect_ratio"):
        aspect_ratio = _infer_aspect_ratio(prompt)
        if aspect_ratio:
            inferred["aspect_ratio"] = aspect_ratio
            details["inferred_fields"].append("aspect_ratio")

    if _should_infer_field(request, "resolution"):
        resolution = _infer_resolution(prompt)
        if resolution:
            inferred["resolution"] = resolution
            details["inferred_fields"].append("resolution")

    if request.kind == MediaGenerationKind.IMAGE:
        if _should_infer_field(request, "image_count"):
            image_count = _infer_image_count(prompt)
            if image_count is not None:
                inferred["image_count"] = image_count
                details["inferred_fields"].append("image_count")
    else:
        if _should_infer_field(request, "duration_seconds"):
            duration_seconds = _infer_duration_seconds(prompt)
            if duration_seconds is not None:
                inferred["duration_seconds"] = duration_seconds
                details["inferred_fields"].append("duration_seconds")
        if _should_infer_field(request, "fps"):
            fps = _infer_fps(prompt)
            if fps is not None:
                inferred["fps"] = fps
                details["inferred_fields"].append("fps")

    if not inferred:
        return {}
    return {**inferred, "command_interpretation": details}


def _should_infer_field(request: MediaGenerationRequest, field_name: str) -> bool:
    if field_name not in request.model_fields_set:
        return True
    value = getattr(request, field_name)
    default_like_values: dict[str, set[Any]] = {
        "image_count": {1},
        "aspect_ratio": {None, "", "1:1"},
        "resolution": {None, "", "1024x1024", "1080p"},
        "duration_seconds": {None, 5, 5.0},
        "fps": {None, 24},
    }
    return value in default_like_values.get(field_name, set())


def _infer_aspect_ratio(prompt: str) -> str | None:
    match = re.search(r"(?<!\d)(\d{1,2})\s*[:：]\s*(\d{1,2})(?!\d)", prompt)
    if not match:
        return None
    width, height = int(match.group(1)), int(match.group(2))
    if width <= 0 or height <= 0 or width > 32 or height > 32:
        return None
    return f"{width}:{height}"


def _infer_resolution(prompt: str) -> str | None:
    pixel_match = re.search(r"(?<!\d)(\d{3,5})\s*[xX×]\s*(\d{3,5})(?!\d)", prompt)
    if pixel_match:
        width, height = int(pixel_match.group(1)), int(pixel_match.group(2))
        if 256 <= width <= 8192 and 256 <= height <= 8192:
            return f"{width}x{height}"

    normalized = prompt.lower()
    for pattern, resolution in (
        (r"\b8k\b", "4320p"),
        (r"\b4k\b|超清", "2160p"),
        (r"\b2k\b", "1440p"),
        (r"\b1080p\b|1080\s*分辨率|高清", "1080p"),
        (r"\b720p\b|720\s*分辨率", "720p"),
    ):
        if re.search(pattern, normalized):
            return resolution
    return None


def _infer_image_count(prompt: str) -> int | None:
    match = re.search(
        r"(?<!\d)(\d{1,2})\s*(?:张|幅|个|images?|pics?|pictures?)(?![a-zA-Z])", prompt, re.I
    )
    if match:
        return _bounded_int(int(match.group(1)), minimum=1, maximum=8)
    for phrase, count in {
        "一张": 1,
        "两张": 2,
        "二张": 2,
        "三张": 3,
        "四张": 4,
        "五张": 5,
        "六张": 6,
        "七张": 7,
        "八张": 8,
    }.items():
        if phrase in prompt:
            return count
    return None


def _infer_duration_seconds(prompt: str) -> float | None:
    match = re.search(
        r"(?<!\d)(\d+(?:\.\d+)?)\s*(?:秒|s|sec|secs|second|seconds)(?![a-zA-Z])",
        prompt,
        re.I,
    )
    if not match:
        return None
    seconds = float(match.group(1))
    if seconds <= 0:
        return None
    return min(seconds, 60.0)


def _infer_fps(prompt: str) -> int | None:
    match = re.search(r"(?<!\d)(\d{1,3})\s*(?:fps|帧率|帧)(?![a-zA-Z])", prompt, re.I)
    if not match:
        return None
    fps = int(match.group(1))
    if fps not in {16, 24, 25, 30, 50, 60}:
        return None
    return fps


def _bounded_int(value: int, *, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def _provider_statuses_from_settings() -> dict[MediaProviderType, bool]:
    return {
        provider_type: not issues
        for provider_type, issues in media_provider_diagnostics_from_settings().items()
    }


def media_provider_diagnostics_from_settings() -> dict[MediaProviderType, list[str]]:
    return {
        MediaProviderType.OPENAI_IMAGES: _missing_media_provider_config(
            base_url=settings.openai_images_base_url,
            api_key=settings.openai_images_api_key,
            base_url_name="OPENAI_IMAGES_BASE_URL",
            api_key_name="OPENAI_IMAGES_API_KEY",
        ),
        MediaProviderType.NANO_BANANA: _missing_media_provider_config(
            base_url=settings.nano_banana_base_url,
            api_key=settings.nano_banana_api_key,
            base_url_name="NANO_BANANA_BASE_URL",
            api_key_name="NANO_BANANA_API_KEY",
        ),
        MediaProviderType.VOLCENGINE_SEEDANCE: _missing_media_provider_config(
            base_url=settings.volcengine_seedance_base_url,
            api_key=settings.volcengine_seedance_api_key,
            base_url_name="VOLCENGINE_SEEDANCE_BASE_URL",
            api_key_name="VOLCENGINE_SEEDANCE_API_KEY",
        ),
        MediaProviderType.OPENAI_COMPATIBLE_MEDIA: _missing_media_provider_config(
            base_url=settings.media_openai_compatible_base_url,
            api_key=settings.media_openai_compatible_api_key,
            base_url_name="MEDIA_OPENAI_COMPATIBLE_BASE_URL",
            api_key_name="MEDIA_OPENAI_COMPATIBLE_API_KEY",
        ),
        MediaProviderType.CUSTOM: ["custom_media_provider_adapter"],
    }


def _missing_media_provider_config(
    *,
    base_url: str | None,
    api_key: str,
    base_url_name: str,
    api_key_name: str,
) -> list[str]:
    missing = []
    if not base_url:
        missing.append(base_url_name)
    if not api_key:
        missing.append(api_key_name)
    return missing


def _configuration_hint(configuration_issues: list[str]) -> str | None:
    if not configuration_issues:
        return None
    return "Missing media provider configuration: " + ", ".join(configuration_issues) + "."
