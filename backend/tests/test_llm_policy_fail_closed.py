import unittest
from uuid import uuid4

from fastapi import HTTPException

from app.llm.policy import ModelPolicyEngine, ModelPolicyRule
from app.llm.router import ModelRouter
from app.llm.schemas import (
    DeploymentConfig,
    LLMAdapterType,
    LLMChatRequest,
    LLMRequestContext,
    PolicyDecision,
    ProviderConfig,
)


class LLMPolicyFailClosedTests(unittest.IsolatedAsyncioTestCase):
    async def test_unmatched_explicit_route_remains_allowed_for_open_policy_environment(
        self,
    ) -> None:
        tenant_id = uuid4()

        decision = await ModelPolicyEngine([]).evaluate(
            _request(routing_key="qwen-chat"),
            LLMRequestContext(tenant_id=tenant_id),
        )

        self.assertTrue(decision.allowed)
        self.assertEqual("explicit_route", decision.reason)
        self.assertEqual("qwen-chat", decision.routing_key)

    async def test_matched_policy_scope_without_allow_denies_request(self) -> None:
        tenant_id = uuid4()
        policy = _policy(
            scope_type="tenant",
            effect="deny",
            allowed_models=("expensive-model",),
        )
        decision = await ModelPolicyEngine([policy]).evaluate(
            _request(model_key="qwen-plus"),
            LLMRequestContext(tenant_id=tenant_id),
        )

        self.assertFalse(decision.allowed)
        self.assertEqual("model_policy_no_matching_allow", decision.reason)

    async def test_allow_policy_with_nonmatching_explicit_model_denies_request(self) -> None:
        tenant_id = uuid4()
        policy = _policy(
            scope_type="tenant",
            effect="allow",
            allowed_models=("qwen-plus",),
            default_routing_key="qwen-chat",
        )
        decision = await ModelPolicyEngine([policy]).evaluate(
            _request(model_key="deepseek-v4-flash"),
            LLMRequestContext(tenant_id=tenant_id),
        )

        self.assertFalse(decision.allowed)
        self.assertEqual("model_policy_no_matching_allow", decision.reason)

    async def test_policy_routing_key_must_match_active_deployment(self) -> None:
        router = ModelRouter(
            providers=[
                ProviderConfig(
                    provider_key="qwen",
                    name="Qwen",
                    adapter_type=LLMAdapterType.OPENAI_COMPATIBLE,
                    credential_configured=True,
                )
            ],
            deployments=[
                DeploymentConfig(
                    provider_key="qwen",
                    provider_name="Qwen",
                    adapter_type=LLMAdapterType.OPENAI_COMPATIBLE,
                    model_key="qwen-plus",
                    display_name="Qwen Plus",
                    deployment_name="Qwen Plus",
                    routing_key="qwen-chat",
                )
            ],
        )

        with self.assertRaises(HTTPException) as raised:
            await router.plan(
                _request(),
                PolicyDecision(
                    allowed=True,
                    reason="model_policy_allowed:bad-route",
                    routing_key="missing-route",
                ),
            )

        self.assertEqual(404, raised.exception.status_code)
        self.assertEqual("policy_routing_key_not_found", raised.exception.detail["code"])
        self.assertIn("policy routing key", raised.exception.detail["message"])
        self.assertEqual("missing-route", raised.exception.detail["policy_routing_key"])
        self.assertEqual(1, raised.exception.detail["candidate_count"])

    async def test_router_reports_missing_provider_keys_for_deployment_misconfiguration(
        self,
    ) -> None:
        router = ModelRouter(
            providers=[],
            deployments=[
                DeploymentConfig(
                    provider_key="mimo",
                    provider_name="MiMo",
                    adapter_type=LLMAdapterType.OPENAI_COMPATIBLE,
                    model_key="mimo-chat",
                    display_name="MiMo Chat",
                    deployment_name="MiMo Chat",
                    routing_key="mimo-chat",
                )
            ],
        )

        with self.assertRaises(HTTPException) as raised:
            await router.plan(
                _request(model_key="mimo-chat"),
                PolicyDecision(allowed=True, reason="explicit_model"),
            )

        self.assertEqual(500, raised.exception.status_code)
        self.assertEqual("deployment_provider_not_registered", raised.exception.detail["code"])
        self.assertEqual(["mimo"], raised.exception.detail["missing_provider_keys"])
        self.assertEqual("mimo-chat", raised.exception.detail["request_model_key"])

    async def test_cost_center_policy_matches_explicit_context(self) -> None:
        tenant_id = uuid4()
        cost_center_id = uuid4()
        policy = _policy(
            scope_type="cost_center",
            scope_id=cost_center_id,
            effect="allow",
            allowed_models=("qwen-plus",),
            default_routing_key="qwen-chat",
        )

        decision = await ModelPolicyEngine([policy]).evaluate(
            _request(model_key="qwen-plus"),
            LLMRequestContext(tenant_id=tenant_id, cost_center_id=cost_center_id),
        )

        self.assertTrue(decision.allowed)
        self.assertEqual("model_policy_allowed:Tenant model policy", decision.reason)
        self.assertEqual("qwen-plus", decision.model_key)

    async def test_cost_center_policy_matches_resolved_user_department_binding(self) -> None:
        tenant_id = uuid4()
        user_id = uuid4()
        department_id = uuid4()
        cost_center_id = uuid4()
        policy = _policy(
            scope_type="cost_center",
            scope_id=cost_center_id,
            effect="allow",
            default_routing_key="qwen-chat",
        )

        decision = await ModelPolicyEngine(
            [policy],
            session=FakeCostCenterSession(cost_center_id),
        ).evaluate(
            _request(),
            LLMRequestContext(
                tenant_id=tenant_id,
                user_id=user_id,
                department_id=department_id,
            ),
        )

        self.assertTrue(decision.allowed)
        self.assertEqual("qwen-chat", decision.routing_key)


def _request(
    model_key: str | None = None,
    routing_key: str | None = None,
) -> LLMChatRequest:
    return LLMChatRequest(
        model_key=model_key,
        routing_key=routing_key,
        messages=[{"role": "user", "content": "hello"}],
    )


def _policy(
    *,
    scope_type: str,
    scope_id=None,
    effect: str,
    allowed_models: tuple[str, ...] = (),
    allowed_routing_keys: tuple[str, ...] = (),
    default_model_key: str | None = None,
    default_routing_key: str | None = None,
) -> ModelPolicyRule:
    return ModelPolicyRule(
        id=uuid4(),
        name="Tenant model policy",
        scope_type=scope_type,
        scope_id=scope_id,
        effect=effect,
        allowed_models=allowed_models,
        allowed_routing_keys=allowed_routing_keys,
        default_model_key=default_model_key,
        default_routing_key=default_routing_key,
        max_tokens=None,
        priority=100,
    )


class FakeCostCenterSession:
    def __init__(self, cost_center_id):
        self.cost_center_id = cost_center_id

    async def execute(self, _statement):
        return FakeScalarOneOrNoneResult(self.cost_center_id)


class FakeScalarOneOrNoneResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


if __name__ == "__main__":
    unittest.main()
