"""Unit tests for cost-aware routing in the LLM ModelRouter."""

from __future__ import annotations

import unittest
from decimal import Decimal
from uuid import uuid4

from app.llm.pricing import ModelPricingCatalog, PricingRule
from app.llm.router import ModelRouter
from app.llm.schemas import (
    DeploymentConfig,
    LLMAdapterType,
    LLMChatRequest,
    LLMDeploymentStatus,
    LLMProviderStatus,
    Message,
    PolicyDecision,
    ProviderConfig,
)


def _provider(key: str = "p1") -> ProviderConfig:
    return ProviderConfig(
        provider_key=key,
        name=key,
        adapter_type=LLMAdapterType.OPENAI_COMPATIBLE,
        base_url="https://example.com",
        status=LLMProviderStatus.ACTIVE,
        credential_configured=True,
    )


def _deployment(
    dep_id,
    *,
    model_key: str,
    priority: int = 100,
    routing_key: str = "default",
) -> DeploymentConfig:
    return DeploymentConfig(
        id=dep_id,
        provider_key="p1",
        provider_name="p1",
        adapter_type=LLMAdapterType.OPENAI_COMPATIBLE,
        model_key=model_key,
        display_name=model_key,
        deployment_name=model_key,
        routing_key=routing_key,
        status=LLMDeploymentStatus.ACTIVE,
        priority=priority,
    )


def _request(model_key: str | None = None) -> LLMChatRequest:
    return LLMChatRequest(
        model_key=model_key,
        messages=[Message(role="user", content="hi")],
    )


def _decision(
    *,
    model_key: str | None = None,
    routing_key: str | None = None,
    routing_strategy: str | None = None,
) -> PolicyDecision:
    metadata: dict = {}
    if routing_strategy:
        metadata["routing_strategy"] = routing_strategy
    return PolicyDecision(
        allowed=True,
        model_key=model_key,
        routing_key=routing_key,
        metadata=metadata,
    )


class CostAwareRoutingTests(unittest.IsolatedAsyncioTestCase):
    """When ``routing_strategy=cost_priority`` is on the policy and the router
    is constructed with ``cost_aware_routing_enabled``, equal-priority
    candidates should be tie-broken by ascending per-1k-token cost."""

    async def test_cost_priority_picks_cheapest_same_priority(self) -> None:
        # Two deployments, both priority 100, different model prices.
        cheap = _deployment(uuid4(), model_key="gpt-4o-mini")  # 0.00015+0.0006 = 0.00075
        pricey = _deployment(uuid4(), model_key="gpt-4o")  # 0.0025+0.010 = 0.0125
        router = ModelRouter(
            providers=[_provider()],
            deployments=[pricey, cheap],
            pricing=ModelPricingCatalog(),
            cost_aware_routing_enabled=True,
        )

        routes = await router.plan(
            _request(),
            _decision(routing_strategy="cost_priority"),
        )
        self.assertEqual(routes[0].deployment.id, cheap.id)
        self.assertEqual(routes[0].reason, "cost_priority_route")
        self.assertEqual(routes[1].deployment.id, pricey.id)

    async def test_priority_still_wins_over_cost(self) -> None:
        # Cheap deployment has worse (higher) priority; priority must win.
        cheap_low_pri = _deployment(uuid4(), model_key="gpt-4o-mini", priority=200)
        pricey_high_pri = _deployment(uuid4(), model_key="gpt-4o", priority=10)
        router = ModelRouter(
            providers=[_provider()],
            deployments=[cheap_low_pri, pricey_high_pri],
            pricing=ModelPricingCatalog(),
            cost_aware_routing_enabled=True,
        )

        routes = await router.plan(
            _request(),
            _decision(routing_strategy="cost_priority"),
        )
        self.assertEqual(routes[0].deployment.id, pricey_high_pri.id)

    async def test_disabled_flag_uses_default_priority_order(self) -> None:
        cheap = _deployment(uuid4(), model_key="gpt-4o-mini")
        pricey = _deployment(uuid4(), model_key="gpt-4o")
        router = ModelRouter(
            providers=[_provider()],
            deployments=[pricey, cheap],
            pricing=ModelPricingCatalog(),
            cost_aware_routing_enabled=False,  # feature flag off
        )

        routes = await router.plan(
            _request(),
            _decision(routing_strategy="cost_priority"),  # policy asks for cost
        )
        # Flag off → default order (insertion after priority sort); both
        # have priority 100 so order is stable but NOT by cost.
        self.assertEqual(routes[0].reason, "priority_route")

    async def test_no_strategy_metadata_uses_default_order(self) -> None:
        cheap = _deployment(uuid4(), model_key="gpt-4o-mini")
        pricey = _deployment(uuid4(), model_key="gpt-4o")
        router = ModelRouter(
            providers=[_provider()],
            deployments=[pricey, cheap],
            pricing=ModelPricingCatalog(),
            cost_aware_routing_enabled=True,
        )

        routes = await router.plan(_request(), _decision())  # no strategy
        self.assertEqual(routes[0].reason, "priority_route")

    async def test_runtime_pricing_overrides_take_effect(self) -> None:
        # Override flips the cost ordering: make "gpt-4o" cheaper than "gpt-4o-mini".
        overrides = [
            PricingRule(
                pattern="gpt-4o",
                input_per_1k=Decimal("0.00001"),
                output_per_1k=Decimal("0.00002"),
            ),
            PricingRule(
                pattern="gpt-4o-mini",
                input_per_1k=Decimal("1.0"),
                output_per_1k=Decimal("1.0"),
            ),
        ]
        gpt4o = _deployment(uuid4(), model_key="gpt-4o")
        mini = _deployment(uuid4(), model_key="gpt-4o-mini")
        router = ModelRouter(
            providers=[_provider()],
            deployments=[mini, gpt4o],
            pricing=ModelPricingCatalog(overrides=overrides),
            cost_aware_routing_enabled=True,
        )

        routes = await router.plan(
            _request(),
            _decision(routing_strategy="cost_priority"),
        )
        self.assertEqual(routes[0].deployment.id, gpt4o.id)


if __name__ == "__main__":
    unittest.main()
