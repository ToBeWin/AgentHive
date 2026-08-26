from uuid import uuid4

from app.models.llm import LLMCredential, LLMDeployment, LLMProvider
from scripts.demo_seed.llm import (
    _DEMO_MODEL_CATALOG,
    _demo_allowed_models,
    _demo_allowed_routing_keys,
    _is_live_deployment_config,
    _is_preferred_live_deployment,
)


def test_demo_seed_includes_mainstream_china_model_catalog() -> None:
    model_keys = {item.model_key for item in _DEMO_MODEL_CATALOG}

    assert {
        "qwen-plus",
        "deepseek-v4-flash",
        "moonshot-v1-128k",
        "mimo-chat",
        "mimo-v2.5-pro",
        "abab6.5s-chat",
        "glm-4-plus",
        "doubao-pro-32k",
    }.issubset(model_keys)


def test_demo_default_policy_allows_seeded_model_routes() -> None:
    allowed_models = set(_demo_allowed_models("qwen-plus"))
    allowed_routes = set(_demo_allowed_routing_keys("cn-primary-chat"))

    assert {
        "deepseek-v4-flash",
        "mimo-chat",
        "mimo-v2.5-pro",
        "abab6.5s-chat",
        "glm-4-plus",
    }.issubset(allowed_models)
    assert {
        "deepseek-chat",
        "mimo-chat",
        "minimax-chat",
        "glm-chat",
        "doubao-chat",
    }.issubset(allowed_routes)


def test_demo_seed_can_prefer_live_customer_service_model_route() -> None:
    assert _is_live_deployment_config({"live_network_call": True, "mock": False})
    assert not _is_live_deployment_config({"live_network_call": False, "mock": True})
    assert not _is_live_deployment_config({"live_network_call": True, "mock": True})

    tenant_id = uuid4()
    provider = LLMProvider(
        tenant_id=tenant_id,
        provider_key="mimo",
        name="MiMo",
        adapter_type="openai_compatible",
        base_url="https://mimo.example.test/v1",
        is_active=True,
    )
    credential = LLMCredential(
        tenant_id=tenant_id,
        provider_id=uuid4(),
        display_name="mimo-v2.5-pro",
        secret_ref="encrypted-secret",
        masked_secret="tp-...live",
        is_active=True,
    )
    deployment = LLMDeployment(
        tenant_id=tenant_id,
        provider_id=uuid4(),
        credential_id=uuid4(),
        model_id=uuid4(),
        deployment_name="mimo-v2.5-pro",
        routing_key="mimo-v2.5-pro",
        is_active=True,
        priority=10,
    )
    assert _is_preferred_live_deployment(provider, credential, deployment)

    provider.provider_key = "litellm"
    provider.config = {"demo_seed": True}
    credential.display_name = "Demo LiteLLM Virtual Key"
    assert not _is_preferred_live_deployment(provider, credential, deployment)
