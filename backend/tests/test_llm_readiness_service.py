from datetime import datetime, timezone
from uuid import uuid4
import unittest

from app.llm.schemas import LLMAdapterType, LLMDeploymentStatus, LLMProviderStatus
from app.schemas.llm import (
    LLMConnectionTestHistoryItem,
    LLMDeploymentResponse,
    LLMPolicyEffect,
    LLMPolicyResponse,
    LLMPolicyScope,
    LLMProviderResponse,
)
from app.services.llm_service import _deployment_readiness_item


class LLMReadinessServiceTests(unittest.TestCase):
    def test_deployment_readiness_is_ready_with_live_probe_pricing_policy_and_fallback(
        self,
    ) -> None:
        deployment = make_deployment(config={"fallback_group": "default"})
        provider = make_provider(credential_configured=True)
        probe = make_probe(deployment=deployment, ok=True, live=True)
        policy = make_policy(default_routing_key=deployment.routing_key)

        readiness = _deployment_readiness_item(
            deployment=deployment,
            provider=provider,
            priced_model_keys={deployment.model_key},
            policies=[policy],
            tests=[probe],
        )

        self.assertEqual("ready", readiness.readiness)
        self.assertEqual([], readiness.blockers)
        self.assertEqual([], readiness.warnings)
        self.assertTrue(readiness.live_probe_ok)

    def test_deployment_readiness_blocks_missing_credential_and_inactive_deployment(self) -> None:
        deployment = make_deployment(
            status=LLMDeploymentStatus.INACTIVE, config={"requires_configuration": True}
        )
        provider = make_provider(credential_configured=False)

        readiness = _deployment_readiness_item(
            deployment=deployment,
            provider=provider,
            priced_model_keys=set(),
            policies=[],
            tests=[],
        )

        self.assertEqual("blocked", readiness.readiness)
        self.assertIn("deployment_inactive", readiness.blockers)
        self.assertIn("credential_missing", readiness.blockers)
        self.assertIn("deployment_requires_configuration", readiness.blockers)
        self.assertIn("live_probe_missing", readiness.warnings)
        self.assertTrue(readiness.pricing_configured)
        self.assertNotIn("pricing_missing", readiness.warnings)

    def test_deployment_readiness_uses_builtin_price_catalog_when_database_price_is_missing(
        self,
    ) -> None:
        deployment = make_deployment(
            config={"fallback_group": "default"},
            model_key="mimo-chat",
            provider_key="mimo",
            provider_name="MiMo",
            routing_key="mimo-chat",
        )
        provider = make_provider(credential_configured=True)
        probe = make_probe(deployment=deployment, ok=True, live=True)
        policy = make_policy(default_routing_key=deployment.routing_key)

        readiness = _deployment_readiness_item(
            deployment=deployment,
            provider=provider,
            priced_model_keys=set(),
            policies=[policy],
            tests=[probe],
        )

        self.assertEqual("ready", readiness.readiness)
        self.assertTrue(readiness.pricing_configured)
        self.assertNotIn("pricing_missing", readiness.warnings)

    def test_deployment_readiness_treats_successful_acceptance_call_as_live_evidence(self) -> None:
        deployment = make_deployment(config={"fallback_group": "default"})
        provider = make_provider(credential_configured=True)
        acceptance = make_probe(
            deployment=deployment,
            ok=True,
            live=True,
            operation="deployment_acceptance_test",
            configuration_source="saved_deployment",
        )
        policy = make_policy(default_routing_key=deployment.routing_key)

        readiness = _deployment_readiness_item(
            deployment=deployment,
            provider=provider,
            priced_model_keys={deployment.model_key},
            policies=[policy],
            tests=[acceptance],
        )

        self.assertEqual("ready", readiness.readiness)
        self.assertTrue(readiness.live_probe_ok)
        self.assertEqual("deployment_acceptance_test", readiness.evidence["last_probe_operation"])
        self.assertEqual("saved_deployment", readiness.evidence["configuration_source"])

    def test_deployment_readiness_warns_when_unknown_model_price_is_missing(self) -> None:
        deployment = make_deployment(
            config={"fallback_group": "default"},
            model_key="vendor/unknown-model",
            routing_key="unknown-model",
        )
        provider = make_provider(credential_configured=True)
        probe = make_probe(deployment=deployment, ok=True, live=True)
        policy = make_policy(default_routing_key=deployment.routing_key)

        readiness = _deployment_readiness_item(
            deployment=deployment,
            provider=provider,
            priced_model_keys=set(),
            policies=[policy],
            tests=[probe],
        )

        self.assertEqual("warning", readiness.readiness)
        self.assertFalse(readiness.pricing_configured)
        self.assertEqual([], readiness.blockers)
        self.assertIn("pricing_missing", readiness.warnings)

    def test_deployment_readiness_ignores_deny_policy_as_usage_evidence(self) -> None:
        deployment = make_deployment(config={"fallback_group": "default"})
        provider = make_provider(credential_configured=True)
        probe = make_probe(deployment=deployment, ok=True, live=True)
        policy = make_policy(
            default_routing_key=deployment.routing_key,
            effect=LLMPolicyEffect.DENY,
        )

        readiness = _deployment_readiness_item(
            deployment=deployment,
            provider=provider,
            priced_model_keys={deployment.model_key},
            policies=[policy],
            tests=[probe],
        )

        self.assertEqual("warning", readiness.readiness)
        self.assertFalse(readiness.policy_referenced)
        self.assertIn("policy_reference_missing", readiness.warnings)

    def test_deployment_readiness_ignores_inactive_allow_policy_as_usage_evidence(self) -> None:
        deployment = make_deployment(config={"fallback_group": "default"})
        provider = make_provider(credential_configured=True)
        probe = make_probe(deployment=deployment, ok=True, live=True)
        policy = make_policy(
            default_routing_key=deployment.routing_key,
            status="inactive",
        )

        readiness = _deployment_readiness_item(
            deployment=deployment,
            provider=provider,
            priced_model_keys={deployment.model_key},
            policies=[policy],
            tests=[probe],
        )

        self.assertEqual("warning", readiness.readiness)
        self.assertFalse(readiness.policy_referenced)
        self.assertIn("policy_reference_missing", readiness.warnings)


def make_provider(*, credential_configured: bool) -> LLMProviderResponse:
    return LLMProviderResponse(
        provider_key="deepseek",
        name="DeepSeek",
        adapter_type=LLMAdapterType.OPENAI_COMPATIBLE,
        base_url="https://api.deepseek.com",
        region=None,
        status=LLMProviderStatus.ACTIVE
        if credential_configured
        else LLMProviderStatus.NOT_CONFIGURED,
        capabilities=["chat", "stream"],
        credential_configured=credential_configured,
    )


def make_deployment(
    *,
    config: dict[str, object],
    model_key: str = "deepseek-v4-flash",
    provider_key: str = "deepseek",
    provider_name: str = "DeepSeek",
    routing_key: str = "deepseek-chat",
    status: LLMDeploymentStatus = LLMDeploymentStatus.ACTIVE,
) -> LLMDeploymentResponse:
    return LLMDeploymentResponse(
        id=uuid4(),
        provider_key=provider_key,
        provider_name=provider_name,
        adapter_type=LLMAdapterType.OPENAI_COMPATIBLE,
        model_key=model_key,
        display_name=model_key,
        deployment_name=f"{provider_name} Production",
        routing_key=routing_key,
        status=status,
        context_window=128000,
        capabilities=["chat", "stream"],
        priority=10,
        config=config,
    )


def make_probe(
    *,
    deployment: LLMDeploymentResponse,
    live: bool,
    ok: bool,
    configuration_source: str = "database",
    operation: str = "llm_gateway_connection_test",
) -> LLMConnectionTestHistoryItem:
    return LLMConnectionTestHistoryItem(
        id=uuid4(),
        request_id="req-readiness",
        actor_id=uuid4(),
        status="success" if ok else "failure",
        ok=ok,
        provider_key=deployment.provider_key,
        provider_type="openai_compatible",
        deployment_id=str(deployment.id),
        model_key=deployment.model_key,
        adapter_type=deployment.adapter_type.value,
        latency_ms=42,
        checked_at=datetime.now(timezone.utc),
        message="Connection healthy." if ok else "Connection failed.",
        operation=operation,
        configuration_source=configuration_source,
        probe_path="/models",
        status_code=200 if ok else 500,
        fallback_attempt_count=0,
        selected_route_reason="direct",
        temporary_api_key_provided=False,
        temporary_base_url_provided=False,
        live_network_call=live,
    )


def make_policy(
    *,
    default_routing_key: str | None,
    effect: LLMPolicyEffect = LLMPolicyEffect.ALLOW,
    status: str = "active",
) -> LLMPolicyResponse:
    now = datetime.now(timezone.utc)
    return LLMPolicyResponse(
        id=uuid4(),
        tenant_id=uuid4(),
        name="Production default",
        scope_type=LLMPolicyScope.TENANT,
        scope_id=None,
        effect=effect,
        allowed_models=[],
        allowed_routing_keys=[],
        default_model_key=None,
        default_routing_key=default_routing_key,
        max_tokens=None,
        priority=100,
        status=status,
        metadata={},
        created_at=now,
        updated_at=now,
    )


if __name__ == "__main__":
    unittest.main()
