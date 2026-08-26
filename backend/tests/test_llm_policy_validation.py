from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.llm.catalog_helpers import (
    context_window_for,
    default_model_key,
    default_provider_routing_key,
    model_type_for_capabilities,
)
from app.llm.policy_validation import (
    dedupe_text_list,
    normalize_and_validate_policy_payload,
    normalize_policy_key,
    validate_policy_scope,
)
from app.schemas.llm import LLMPolicyEffect, LLMPolicyScope, LLMPolicyUpsertRequest


def test_policy_payload_normalizes_in_place_and_preserves_list_order() -> None:
    payload = LLMPolicyUpsertRequest(
        name="  Default policy  ",
        description="  tenant scope  ",
        effect=LLMPolicyEffect.ALLOW,
        allowed_models=[" qwen-plus ", "qwen-plus", "deepseek-v4-flash"],
        allowed_routing_keys=[" default-chat ", "default-chat"],
        default_model_key=" qwen-plus ",
        default_routing_key=" default-chat ",
    )

    normalize_and_validate_policy_payload(payload)

    assert payload.name == "Default policy"
    assert payload.description == "tenant scope"
    assert payload.allowed_models == ["qwen-plus", "deepseek-v4-flash"]
    assert payload.allowed_routing_keys == ["default-chat"]
    assert payload.default_model_key == "qwen-plus"
    assert dedupe_text_list([" qwen ", "qwen", "", "deepseek"]) == ["qwen", "deepseek"]


def test_policy_validation_preserves_client_error_status_and_text() -> None:
    with pytest.raises(HTTPException, match="invalid model or routing key") as raised:
        normalize_policy_key("bad key", field_name="allowed_models", required=False)

    assert raised.value.status_code == 422


def test_tenant_scope_clears_scope_id_and_non_tenant_scope_requires_one() -> None:
    tenant_payload = LLMPolicyUpsertRequest(name="Tenant", scope_id=uuid4())
    validate_policy_scope(tenant_payload)
    assert tenant_payload.scope_id is None

    with pytest.raises(HTTPException, match="scope_id is required"):
        validate_policy_scope(
            LLMPolicyUpsertRequest(name="Department", scope_type=LLMPolicyScope.DEPARTMENT)
        )


def test_catalog_helpers_keep_default_and_capability_mappings() -> None:
    deployments = [
        SimpleNamespace(provider_key="qwen", model_key="qwen-plus", context_window=131072),
        SimpleNamespace(provider_key="nano_banana", model_key="google/nano-banana", context_window=None),
    ]

    assert default_provider_routing_key("openai_compatible") == "private-chat"
    assert default_model_key("qwen", deployments) == "qwen-plus"
    assert default_model_key("missing", deployments) == "chat-model"
    assert context_window_for("qwen-plus", deployments) == 131072
    assert model_type_for_capabilities(["image_generation", "video_generation"]) == "media"
