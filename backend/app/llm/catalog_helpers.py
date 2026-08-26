"""Pure catalog lookups shared by LLM service configuration paths."""

from collections.abc import Sequence
from typing import Protocol


class DeploymentCatalogEntry(Protocol):
    provider_key: str
    model_key: str
    context_window: int | None


def default_provider_routing_key(provider_key: str) -> str:
    if provider_key == "litellm":
        return "default-chat"
    if provider_key == "openai_compatible":
        return "private-chat"
    if provider_key == "anthropic_compatible":
        return "anthropic-private-chat"
    if provider_key in {"openai_images", "nano_banana"}:
        return f"{provider_key}-image"
    if provider_key == "volcengine_seedance":
        return "volcengine-seedance-video"
    if provider_key == "openai_compatible_media":
        return "private-media-generation"
    return f"{provider_key}-chat"


def default_model_key(provider_key: str, deployments: Sequence[DeploymentCatalogEntry]) -> str:
    for deployment in deployments:
        if deployment.provider_key == provider_key:
            return deployment.model_key
    return "chat-model"


def context_window_for(model_key: str, deployments: Sequence[DeploymentCatalogEntry]) -> int | None:
    for deployment in deployments:
        if deployment.model_key == model_key:
            return deployment.context_window
    return None


def model_type_for_capabilities(capabilities: list[str]) -> str:
    capability_set = set(capabilities)
    if "image_generation" in capability_set and "video_generation" in capability_set:
        return "media"
    if "video_generation" in capability_set:
        return "video"
    if "image_generation" in capability_set:
        return "image"
    return "chat"
