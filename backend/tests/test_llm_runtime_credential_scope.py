from uuid import uuid4
import unittest
from unittest.mock import AsyncMock, patch

from app.api.deps import Principal
from app.core.secrets import encrypt_secret
from app.llm.policy import ModelPolicyRule
from app.llm.schemas import (
    DeploymentConfig,
    LLMAdapterType,
    LLMChatRequest,
    LLMDeploymentStatus,
    LLMRequestContext,
)
from app.models.llm import LLMCredential, LLMDeployment, LLMModel, LLMProvider
from app.services.llm_service import (
    _build_gateway,
    _policy_rules_matching_deployments,
    _runtime_deployments,
    _runtime_providers,
)


class FakeRowsResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeRuntimeProviderSession:
    def __init__(self, rows):
        self.rows = rows

    async def execute(self, _statement):
        return FakeRowsResult(self.rows)


def make_provider(*, tenant_id, provider_key="qwen") -> LLMProvider:
    return LLMProvider(
        tenant_id=tenant_id,
        provider_key=provider_key,
        name="Qwen",
        adapter_type="openai_compatible",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        is_active=True,
        config={"capabilities": ["chat", "stream"]},
    )


def make_credential(*, tenant_id, provider_id, owner_type, owner_id, secret) -> LLMCredential:
    return LLMCredential(
        tenant_id=tenant_id,
        provider_id=provider_id,
        owner_type=owner_type,
        owner_id=owner_id,
        display_name=f"{owner_type} key",
        secret_ref=encrypt_secret(secret),
        masked_secret="****",
        is_active=True,
    )


class FakeRuntimeDeploymentSession:
    def __init__(self, rows):
        self.rows = rows

    async def execute(self, _statement):
        return FakeRowsResult(self.rows)


def make_model(*, provider_key="litellm", model_key="qwen-plus") -> LLMModel:
    return LLMModel(
        provider_key=provider_key,
        model_key=model_key,
        display_name=model_key,
        model_type="chat",
        context_window=131072,
        capabilities=["chat", "stream"],
        is_global=True,
    )


def make_deployment(*, tenant_id, provider_id, model_id, credential_id) -> LLMDeployment:
    return LLMDeployment(
        tenant_id=tenant_id,
        provider_id=provider_id,
        model_id=model_id,
        credential_id=credential_id,
        deployment_name="Demo Chat",
        routing_key="default-chat",
        is_active=True,
        priority=10,
        config={"demo_seed": True},
    )


def _deployment_config(*, routing_key: str, model_key: str) -> DeploymentConfig:
    return DeploymentConfig(
        id=uuid4(),
        provider_key="litellm",
        provider_name="LiteLLM Proxy",
        adapter_type=LLMAdapterType.LITELLM,
        model_key=model_key,
        display_name=model_key,
        deployment_name="Default Chat",
        routing_key=routing_key,
        status=LLMDeploymentStatus.ACTIVE,
        context_window=128000,
        capabilities=["chat", "stream"],
        priority=10,
        base_url="http://127.0.0.1:14000",
        config={"mock": True},
    )


class LLMRuntimeCredentialScopeTests(unittest.IsolatedAsyncioTestCase):
    def test_policy_rules_drop_stale_allow_routes_that_do_not_match_active_deployments(self):
        stale_policy = ModelPolicyRule(
            id=uuid4(),
            name="Old CN route",
            scope_type="tenant",
            scope_id=None,
            effect="allow",
            allowed_models=(),
            allowed_routing_keys=("cn-primary-chat",),
            default_model_key=None,
            default_routing_key="cn-primary-chat",
            max_tokens=1024,
            priority=10,
        )

        rules = _policy_rules_matching_deployments(
            [stale_policy],
            [_deployment_config(routing_key="default-chat", model_key="gpt-4o-mini")],
        )

        self.assertEqual([], rules)

    def test_policy_rules_keep_deny_all_even_when_routes_drift(self):
        deny_all = ModelPolicyRule(
            id=uuid4(),
            name="Deny tenant",
            scope_type="tenant",
            scope_id=None,
            effect="deny",
            allowed_models=(),
            allowed_routing_keys=(),
            default_model_key=None,
            default_routing_key=None,
            max_tokens=None,
            priority=1,
        )

        rules = _policy_rules_matching_deployments(
            [deny_all],
            [_deployment_config(routing_key="default-chat", model_key="gpt-4o-mini")],
        )

        self.assertEqual([deny_all], rules)

    async def test_gateway_falls_back_to_static_policy_when_runtime_credentials_are_unusable(self):
        tenant_id = uuid4()
        user_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=user_id, permissions={"models:read"})

        with (
            patch("app.services.llm_service._runtime_providers", AsyncMock(return_value=[])),
            patch("app.services.llm_service._runtime_deployments", AsyncMock(return_value=[])),
            patch(
                "app.services.llm_service._runtime_policy_rules",
                AsyncMock(side_effect=AssertionError("runtime policy should not be loaded")),
            ),
            patch(
                "app.services.llm_service._runtime_pricing_rules",
                AsyncMock(side_effect=AssertionError("runtime pricing should not be loaded")),
            ),
        ):
            gateway = await _build_gateway(object(), principal)

        request = LLMChatRequest(messages=[{"role": "user", "content": "ping"}])
        context = LLMRequestContext(tenant_id=tenant_id, user_id=user_id)
        decision = await gateway.policy.evaluate(request, context)
        routes = await gateway.router.plan(
            request.model_copy(update={"routing_key": decision.routing_key}),
            decision,
        )

        self.assertEqual("default_route", decision.reason)
        self.assertEqual("default-chat", decision.routing_key)
        self.assertEqual("default-chat", routes[0].deployment.routing_key)

    async def test_runtime_provider_prefers_user_then_department_then_tenant_credentials(self):
        tenant_id = uuid4()
        user_id = uuid4()
        department_id = uuid4()
        other_department_id = uuid4()
        provider = make_provider(tenant_id=tenant_id)
        rows = [
            (
                provider,
                make_credential(
                    tenant_id=tenant_id,
                    provider_id=provider.id,
                    owner_type="tenant",
                    owner_id=None,
                    secret="sk-tenant",
                ),
            ),
            (
                provider,
                make_credential(
                    tenant_id=tenant_id,
                    provider_id=provider.id,
                    owner_type="department",
                    owner_id=department_id,
                    secret="sk-department",
                ),
            ),
            (
                provider,
                make_credential(
                    tenant_id=tenant_id,
                    provider_id=provider.id,
                    owner_type="department",
                    owner_id=other_department_id,
                    secret="sk-other-department",
                ),
            ),
            (
                provider,
                make_credential(
                    tenant_id=tenant_id,
                    provider_id=provider.id,
                    owner_type="user",
                    owner_id=user_id,
                    secret="sk-user",
                ),
            ),
        ]

        providers = await _runtime_providers(
            FakeRuntimeProviderSession(rows),
            Principal(tenant_id=tenant_id, user_id=user_id, permissions={"models:read"}),
            department_id=department_id,
            user_id=user_id,
        )

        self.assertEqual(1, len(providers))
        metadata = providers[0].metadata
        self.assertEqual("sk-user", metadata["api_key"])
        self.assertEqual("user", metadata["credential_owner_type"])
        self.assertEqual(str(user_id), metadata["credential_owner_id"])
        self.assertEqual(30, metadata["credential_scope_rank"])

    async def test_runtime_provider_uses_department_before_tenant_when_user_key_missing(self):
        tenant_id = uuid4()
        user_id = uuid4()
        department_id = uuid4()
        provider = make_provider(tenant_id=tenant_id)
        rows = [
            (
                provider,
                make_credential(
                    tenant_id=tenant_id,
                    provider_id=provider.id,
                    owner_type="tenant",
                    owner_id=None,
                    secret="sk-tenant",
                ),
            ),
            (
                provider,
                make_credential(
                    tenant_id=tenant_id,
                    provider_id=provider.id,
                    owner_type="department",
                    owner_id=department_id,
                    secret="sk-department",
                ),
            ),
        ]

        providers = await _runtime_providers(
            FakeRuntimeProviderSession(rows),
            Principal(tenant_id=tenant_id, user_id=user_id, permissions={"models:read"}),
            department_id=department_id,
            user_id=user_id,
        )

        self.assertEqual("sk-department", providers[0].metadata["api_key"])
        self.assertEqual("department", providers[0].metadata["credential_owner_type"])

    async def test_runtime_provider_ignores_unmatched_department_credentials_without_tenant_fallback(
        self,
    ):
        tenant_id = uuid4()
        user_id = uuid4()
        provider = make_provider(tenant_id=tenant_id)
        rows = [
            (
                provider,
                make_credential(
                    tenant_id=tenant_id,
                    provider_id=provider.id,
                    owner_type="department",
                    owner_id=uuid4(),
                    secret="sk-other-department",
                ),
            )
        ]

        providers = await _runtime_providers(
            FakeRuntimeProviderSession(rows),
            Principal(tenant_id=tenant_id, user_id=user_id, permissions={"models:read"}),
            department_id=uuid4(),
            user_id=user_id,
        )

        self.assertEqual([], providers)

    async def test_runtime_provider_falls_back_when_higher_priority_secret_cannot_decrypt(self):
        tenant_id = uuid4()
        user_id = uuid4()
        provider = make_provider(tenant_id=tenant_id)
        broken_user_credential = make_credential(
            tenant_id=tenant_id,
            provider_id=provider.id,
            owner_type="user",
            owner_id=user_id,
            secret="sk-user",
        )
        broken_user_credential.secret_ref = "not-a-fernet-token"
        rows = [
            (
                provider,
                make_credential(
                    tenant_id=tenant_id,
                    provider_id=provider.id,
                    owner_type="tenant",
                    owner_id=None,
                    secret="sk-tenant",
                ),
            ),
            (provider, broken_user_credential),
        ]

        providers = await _runtime_providers(
            FakeRuntimeProviderSession(rows),
            Principal(tenant_id=tenant_id, user_id=user_id, permissions={"models:read"}),
            department_id=None,
            user_id=user_id,
        )

        self.assertEqual(1, len(providers))
        self.assertEqual("sk-tenant", providers[0].metadata["api_key"])
        self.assertEqual("tenant", providers[0].metadata["credential_owner_type"])

    async def test_runtime_provider_skips_provider_when_all_matching_secrets_are_invalid(self):
        tenant_id = uuid4()
        user_id = uuid4()
        provider = make_provider(tenant_id=tenant_id)
        broken_credential = make_credential(
            tenant_id=tenant_id,
            provider_id=provider.id,
            owner_type="tenant",
            owner_id=None,
            secret="sk-tenant",
        )
        broken_credential.secret_ref = "not-a-fernet-token"

        providers = await _runtime_providers(
            FakeRuntimeProviderSession([(provider, broken_credential)]),
            Principal(tenant_id=tenant_id, user_id=user_id, permissions={"models:read"}),
            department_id=None,
            user_id=user_id,
        )

        self.assertEqual([], providers)

    async def test_runtime_provider_allows_development_mock_when_demo_secret_cannot_decrypt(self):
        tenant_id = uuid4()
        user_id = uuid4()
        provider = make_provider(tenant_id=tenant_id, provider_key="litellm")
        provider.name = "LiteLLM Proxy"
        provider.adapter_type = "litellm"
        provider.config = {
            "capabilities": ["chat", "stream"],
            "mock_allowed_in_development": True,
        }
        broken_credential = make_credential(
            tenant_id=tenant_id,
            provider_id=provider.id,
            owner_type="tenant",
            owner_id=None,
            secret="sk-demo",
        )
        broken_credential.secret_ref = "not-a-fernet-token"

        providers = await _runtime_providers(
            FakeRuntimeProviderSession([(provider, broken_credential)]),
            Principal(tenant_id=tenant_id, user_id=user_id, permissions={"models:read"}),
            department_id=None,
            user_id=user_id,
        )

        self.assertEqual(1, len(providers))
        self.assertTrue(providers[0].metadata["credential_decrypt_failed"])
        self.assertTrue(providers[0].metadata["mock_adapter"])
        self.assertFalse(providers[0].metadata["live_network_call"])
        self.assertFalse(providers[0].credential_configured)

    async def test_demo_litellm_deployment_stays_mock_in_development(self):
        tenant_id = uuid4()
        provider = make_provider(tenant_id=tenant_id, provider_key="litellm")
        provider.name = "LiteLLM Proxy"
        provider.adapter_type = "litellm"
        provider.base_url = "http://127.0.0.1:14000"
        provider.config = {
            "capabilities": ["chat", "stream"],
            "mock_allowed_in_development": True,
        }
        credential = make_credential(
            tenant_id=tenant_id,
            provider_id=provider.id,
            owner_type="tenant",
            owner_id=None,
            secret="sk-agenthive-demo",
        )
        model = make_model()
        deployment = make_deployment(
            tenant_id=tenant_id,
            provider_id=provider.id,
            model_id=model.id,
            credential_id=credential.id,
        )

        deployments = await _runtime_deployments(
            FakeRuntimeDeploymentSession([(deployment, provider, model)]),
            Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"models:read"}),
        )

        self.assertEqual(1, len(deployments))
        self.assertTrue(deployments[0].config["mock"])
        self.assertFalse(deployments[0].config["live_network_call"])


if __name__ == "__main__":
    unittest.main()
