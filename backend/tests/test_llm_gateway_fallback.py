from decimal import Decimal
from uuid import uuid4
import unittest

from fastapi import HTTPException, status

from app.llm.budget import BudgetGuard
from app.llm.gateway import LLMGateway
from app.llm.policy import ModelPolicyEngine
from app.llm.pricing import ModelPricingCatalog, PricingRule
from app.llm.router import ModelRouter
from app.llm.schemas import (
    BudgetReservation,
    ConnectionTestRequest,
    ConnectionTestResult,
    DeploymentConfig,
    LLMAdapterType,
    LLMCallStatus,
    LLMChatRequest,
    LLMRequestContext,
    LLMResponse,
    LLMUsageMetrics,
    PolicyDecision,
    ProviderConfig,
)
from app.llm.usage import UsageCollector


class AllowAllPolicy(ModelPolicyEngine):
    async def evaluate(self, request, context):
        return PolicyDecision(allowed=True, reason="test")


class DenyPolicy(ModelPolicyEngine):
    async def evaluate(self, request, context):
        return PolicyDecision(allowed=False, reason="model_policy_no_matching_allow")


class TrackingBudget(BudgetGuard):
    def __init__(self, pricing=None):
        super().__init__(pricing=pricing)
        self.settles = 0
        self.releases = 0
        self.reserves = 0
        self.settled_usage = None

    async def reserve(self, request, context):
        self.reserves += 1
        return await super().reserve(request, context)

    async def settle(self, reservation, actual_usage, context):
        self.settles += 1
        self.settled_usage = actual_usage

    async def release(self, reservation, context, reason):
        self.releases += 1


class FakeAdapter:
    adapter_name = "fake"

    def __init__(self, *, content: str | None = None, error: Exception | None = None):
        self.content = content
        self.error = error

    async def chat(self, request, context):
        if self.error is not None:
            raise self.error
        return LLMResponse(
            request_id=context.request_id,
            model_key=request.model_key or "fallback-model",
            provider_key="fallback-provider",
            deployment_id=None,
            content=self.content or "ok",
            usage=LLMUsageMetrics(
                input_tokens=4,
                output_tokens=6,
                total_tokens=10,
                cost_usd=Decimal("0.001"),
            ),
            metadata={"adapter": "fake"},
        )

    async def stream_chat(self, request, context):
        if self.error is not None:
            raise self.error
        for chunk in (self.content or "ok").split(" "):
            yield f"{chunk} "

    async def test_connection(self, request):
        if self.error is not None:
            return ConnectionTestResult(
                ok=False,
                provider_key=request.provider_key,
                adapter_type=LLMAdapterType.OPENAI_COMPATIBLE,
                model_key=request.model_key,
                latency_ms=12,
                message=str(self.error),
                diagnostics={"adapter": "fake"},
            )
        return ConnectionTestResult(
            ok=True,
            provider_key=request.provider_key,
            adapter_type=LLMAdapterType.OPENAI_COMPATIBLE,
            model_key=request.model_key,
            latency_ms=7,
            message=self.content or "ok",
            diagnostics={"adapter": "fake"},
        )


def make_provider(provider_key: str) -> ProviderConfig:
    return ProviderConfig(
        provider_key=provider_key,
        name=provider_key,
        adapter_type=LLMAdapterType.OPENAI_COMPATIBLE,
    )


def make_deployment(provider_key: str, priority: int) -> DeploymentConfig:
    return DeploymentConfig(
        provider_key=provider_key,
        provider_name=provider_key,
        adapter_type=LLMAdapterType.OPENAI_COMPATIBLE,
        model_key="agenthive-chat",
        display_name=f"{provider_key} Chat",
        deployment_name=f"{provider_key} Default",
        routing_key="general",
        priority=priority,
    )


def make_gateway(*, fail_all: bool = False, pricing=None):
    providers = [make_provider("primary"), make_provider("secondary")]
    deployments = [
        make_deployment("primary", 10),
        make_deployment("secondary", 20),
    ]
    budget = TrackingBudget(pricing=pricing)
    usage = UsageCollector()
    gateway = LLMGateway(
        policy=AllowAllPolicy(),
        budget=budget,
        router=ModelRouter(providers=providers, deployments=deployments),
        usage=usage,
    )

    def adapter_for(route):
        if route.provider.provider_key == "primary":
            return FakeAdapter(error=RuntimeError("primary timeout"))
        if fail_all:
            return FakeAdapter(error=RuntimeError("secondary timeout"))
        return FakeAdapter(content="secondary ok")

    gateway._adapter_for = adapter_for
    return gateway, budget, usage


class LLMGatewayFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_streaming_reserves_and_settles_nonzero_estimated_usage(self):
        gateway, budget, usage = make_gateway()
        context = LLMRequestContext(tenant_id=uuid4())

        chunks = [
            chunk
            async for chunk in gateway.stream_chat(
                LLMChatRequest(
                    model_key="agenthive-chat",
                    messages=[{"role": "user", "content": "hello"}],
                    max_tokens=32,
                ),
                context,
            )
        ]

        self.assertEqual("secondary ok ", "".join(chunks))
        self.assertEqual(1, budget.reserves)
        self.assertEqual(1, budget.settles)
        self.assertEqual(0, budget.releases)
        self.assertIsNotNone(budget.settled_usage)
        self.assertGreater(budget.settled_usage.total_tokens, 0)
        self.assertEqual(LLMCallStatus.SUCCESS, usage.records[-1].status)
        self.assertGreater(usage.records[-1].usage.total_tokens, 0)
        self.assertTrue(usage.records[-1].metadata["usage_estimated"])

    async def test_streaming_releases_reservation_when_all_routes_fail(self):
        gateway, budget, usage = make_gateway(fail_all=True)

        with self.assertRaisesRegex(RuntimeError, "secondary timeout"):
            _ = [
                chunk
                async for chunk in gateway.stream_chat(
                    LLMChatRequest(
                        model_key="agenthive-chat",
                        messages=[{"role": "user", "content": "hello"}],
                    ),
                    LLMRequestContext(tenant_id=uuid4()),
                )
            ]

        self.assertEqual(1, budget.reserves)
        self.assertEqual(0, budget.settles)
        self.assertEqual(1, budget.releases)
        self.assertEqual(
            [LLMCallStatus.ERROR, LLMCallStatus.ERROR],
            [record.status for record in usage.records],
        )

    async def test_streaming_releases_reservation_when_client_closes_stream(self):
        gateway, budget, _usage = make_gateway()
        stream = gateway.stream_chat(
            LLMChatRequest(
                model_key="agenthive-chat",
                messages=[{"role": "user", "content": "hello"}],
            ),
            LLMRequestContext(tenant_id=uuid4()),
        )

        self.assertEqual("secondary ", await anext(stream))
        await stream.aclose()

        self.assertEqual(1, budget.reserves)
        self.assertEqual(0, budget.settles)
        self.assertEqual(1, budget.releases)

    async def test_streaming_budget_denial_happens_before_routing(self):
        gateway, _budget, usage = make_gateway()

        class DenyingBudget(TrackingBudget):
            async def reserve(self, request, context):
                self.reserves += 1
                return BudgetReservation(approved=False, reason="test_limit")

        budget = DenyingBudget()
        gateway.budget = budget

        with self.assertRaises(HTTPException) as raised:
            _ = [
                chunk
                async for chunk in gateway.stream_chat(
                    LLMChatRequest(
                        model_key="agenthive-chat",
                        messages=[{"role": "user", "content": "hello"}],
                    ),
                    LLMRequestContext(tenant_id=uuid4()),
                )
            ]

        self.assertEqual(status.HTTP_402_PAYMENT_REQUIRED, raised.exception.status_code)
        self.assertEqual(1, budget.reserves)
        self.assertEqual(0, budget.settles)
        self.assertEqual(0, budget.releases)
        self.assertEqual(LLMCallStatus.BUDGET_EXCEEDED, usage.records[-1].status)

    async def test_gateway_records_policy_denial_before_budget_and_routing(self):
        providers = [make_provider("primary")]
        deployments = [make_deployment("primary", 10)]
        budget = TrackingBudget()
        usage = UsageCollector()
        gateway = LLMGateway(
            policy=DenyPolicy(),
            budget=budget,
            router=ModelRouter(providers=providers, deployments=deployments),
            usage=usage,
        )

        with self.assertRaisesRegex(Exception, "LLM policy denied request"):
            await gateway.chat(
                LLMChatRequest(
                    model_key="agenthive-chat",
                    messages=[{"role": "user", "content": "hello"}],
                ),
                LLMRequestContext(tenant_id=uuid4()),
            )

        self.assertEqual(0, budget.settles)
        self.assertEqual(0, budget.releases)
        self.assertEqual(1, len(usage.records))
        self.assertEqual(LLMCallStatus.DENIED, usage.records[0].status)
        self.assertEqual("policy_denied", usage.records[0].error_code)

    async def test_gateway_falls_back_to_next_active_deployment(self):
        gateway, budget, usage = make_gateway()
        context = LLMRequestContext(tenant_id=uuid4())
        request = LLMChatRequest(
            model_key="agenthive-chat",
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=32,
        )

        response = await gateway.chat(request, context)

        self.assertEqual("secondary ok", response.content)
        self.assertEqual(1, budget.settles)
        self.assertEqual(0, budget.releases)
        self.assertEqual(2, len(usage.records))
        self.assertEqual(LLMCallStatus.ERROR, usage.records[0].status)
        self.assertEqual(LLMCallStatus.SUCCESS, usage.records[1].status)
        self.assertTrue(usage.records[0].metadata["fallback_attempt"])
        self.assertEqual(1, response.metadata["fallback_attempt_count"])
        self.assertEqual(
            ["error", "success"], [item["status"] for item in response.metadata["route_attempts"]]
        )

    async def test_gateway_records_route_planning_failure_after_budget_reservation(self):
        gateway, budget, usage = make_gateway()
        context = LLMRequestContext(tenant_id=uuid4())

        with self.assertRaises(HTTPException) as raised:
            await gateway.chat(
                LLMChatRequest(
                    model_key="missing-model",
                    messages=[{"role": "user", "content": "hello"}],
                    max_tokens=32,
                ),
                context,
            )

        self.assertEqual(404, raised.exception.status_code)
        self.assertEqual("deployment_not_found", raised.exception.detail["code"])
        self.assertEqual(0, budget.settles)
        self.assertEqual(1, budget.releases)
        self.assertEqual(1, len(usage.records))
        record = usage.records[0]
        self.assertEqual(LLMCallStatus.ERROR, record.status)
        self.assertEqual("deployment_not_found", record.error_code)
        self.assertEqual("route_planning", record.metadata["operation"])
        self.assertEqual(404, record.metadata["http_status"])
        self.assertEqual("missing-model", record.metadata["detail"]["request_model_key"])

    async def test_gateway_records_each_failed_route_and_releases_budget_once(self):
        gateway, budget, usage = make_gateway(fail_all=True)
        context = LLMRequestContext(tenant_id=uuid4())
        request = LLMChatRequest(
            model_key="agenthive-chat",
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=32,
        )

        with self.assertRaisesRegex(RuntimeError, "secondary timeout"):
            await gateway.chat(request, context)

        self.assertEqual(0, budget.settles)
        self.assertEqual(1, budget.releases)
        self.assertEqual(2, len(usage.records))
        self.assertEqual(
            [LLMCallStatus.ERROR, LLMCallStatus.ERROR], [record.status for record in usage.records]
        )
        self.assertTrue(usage.records[0].metadata["fallback_attempt"])
        self.assertFalse(usage.records[1].metadata["fallback_attempt"])

    async def test_connection_test_falls_back_when_no_route_is_explicit(self):
        gateway, budget, usage = make_gateway()
        context = LLMRequestContext(tenant_id=uuid4())

        result = await gateway.test_connection(
            ConnectionTestRequest(model_key="agenthive-chat"),
            context,
        )

        self.assertTrue(result.ok)
        self.assertEqual(0, budget.settles)
        self.assertEqual(1, budget.releases)
        self.assertEqual(2, len(usage.records))
        self.assertEqual(
            [LLMCallStatus.ERROR, LLMCallStatus.SUCCESS],
            [record.status for record in usage.records],
        )
        self.assertEqual(1, result.diagnostics["fallback_attempt_count"])
        self.assertEqual(
            ["error", "success"], [item["status"] for item in result.diagnostics["route_attempts"]]
        )

    async def test_connection_test_keeps_explicit_provider_scope(self):
        gateway, budget, usage = make_gateway()
        context = LLMRequestContext(tenant_id=uuid4())

        result = await gateway.test_connection(
            ConnectionTestRequest(provider_key="primary", model_key="agenthive-chat"),
            context,
        )

        self.assertFalse(result.ok)
        self.assertEqual(1, budget.releases)
        self.assertEqual(1, len(usage.records))
        self.assertEqual(LLMCallStatus.ERROR, usage.records[0].status)
        self.assertEqual(0, result.diagnostics["fallback_attempt_count"])

    async def test_connection_test_uses_temporary_unsaved_credential_config(self):
        gateway, budget, usage = make_gateway()
        context = LLMRequestContext(tenant_id=uuid4())
        captured_routes = []

        def adapter_for(route):
            captured_routes.append(route)
            return FakeAdapter(content="temporary config ok")

        gateway._adapter_for = adapter_for

        result = await gateway.test_connection(
            ConnectionTestRequest(
                provider_key="primary",
                model_key="new-chat-model",
                base_url="http://model.local/v1",
                api_key="sk-temporary-secret",
            ),
            context,
        )

        self.assertTrue(result.ok)
        self.assertEqual(1, budget.releases)
        self.assertEqual(1, len(captured_routes))
        route = captured_routes[0]
        self.assertEqual("temporary_connection_test", route.reason)
        self.assertEqual("new-chat-model", route.deployment.model_key)
        self.assertEqual("http://model.local/v1", route.provider.base_url)
        self.assertEqual("sk-temporary-secret", route.provider.metadata["api_key"])
        self.assertFalse(route.deployment.config["mock"])
        self.assertEqual("temporary_connection_test", result.diagnostics["selected_route_reason"])
        self.assertNotIn("sk-temporary-secret", str(usage.records[0].metadata))

    async def test_gateway_recalculates_success_usage_with_pricing_overrides(self):
        gateway, _budget, usage = make_gateway(
            pricing=ModelPricingCatalog(
                overrides=[
                    PricingRule(
                        pattern="agenthive-chat",
                        input_per_1k=Decimal("1"),
                        output_per_1k=Decimal("2"),
                        source="database",
                    )
                ]
            )
        )
        context = LLMRequestContext(tenant_id=uuid4())

        response = await gateway.chat(
            LLMChatRequest(
                model_key="agenthive-chat",
                messages=[{"role": "user", "content": "hello"}],
                max_tokens=32,
            ),
            context,
        )

        self.assertEqual(Decimal("0.016000"), response.usage.cost_usd)
        self.assertEqual(Decimal("0.016000"), usage.records[-1].usage.cost_usd)
        self.assertEqual("agenthive-chat", response.metadata["pricing_rule"])


if __name__ == "__main__":
    unittest.main()
