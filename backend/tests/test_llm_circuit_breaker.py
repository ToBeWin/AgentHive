"""Unit tests for the LLM Gateway circuit breaker and its router/gateway wiring."""

from __future__ import annotations

import asyncio
import unittest
from uuid import uuid4

from app.llm.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    circuit_breaker as global_breaker,
)
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


def _deployment(dep_id, priority: int = 100, model_key: str = "m1") -> DeploymentConfig:
    return DeploymentConfig(
        id=dep_id,
        provider_key="p1",
        provider_name="p1",
        adapter_type=LLMAdapterType.OPENAI_COMPATIBLE,
        model_key=model_key,
        display_name=model_key,
        deployment_name=model_key,
        routing_key="default",
        status=LLMDeploymentStatus.ACTIVE,
        priority=priority,
    )


def _request(model_key: str = "m1") -> LLMChatRequest:
    return LLMChatRequest(
        model_key=model_key,
        messages=[Message(role="user", content="hi")],
    )


def _decision(model_key: str = "m1") -> PolicyDecision:
    return PolicyDecision(allowed=True, model_key=model_key)


class CircuitBreakerStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.b = CircuitBreaker(failure_threshold=3, cooldown_seconds=60, success_threshold=2)

    def test_initial_state_is_closed(self) -> None:
        self.assertEqual(self.b.get_state("d1"), CircuitState.CLOSED)
        self.assertFalse(self.b.is_open("d1"))

    def test_opens_after_failure_threshold(self) -> None:
        for _ in range(3):
            self.b.record_failure("d1", error_code="Timeout")
        self.assertEqual(self.b.get_state("d1"), CircuitState.OPEN)
        self.assertTrue(self.b.is_open("d1"))

    def test_does_not_open_below_threshold(self) -> None:
        self.b.record_failure("d1")
        self.b.record_failure("d1")
        self.assertEqual(self.b.get_state("d1"), CircuitState.CLOSED)
        self.assertFalse(self.b.is_open("d1"))

    def test_success_resets_consecutive_failures_when_closed(self) -> None:
        self.b.record_failure("d1")
        self.b.record_failure("d1")
        self.b.record_success("d1")
        # Counter reset, still closed.
        self.assertEqual(self.b.get_state("d1"), CircuitState.CLOSED)
        self.b.record_failure("d1")
        self.b.record_failure("d1")
        # Only 2 failures since reset, not enough to open.
        self.assertFalse(self.b.is_open("d1"))

    def test_disabled_breaker_never_reports_open(self) -> None:
        b = CircuitBreaker(failure_threshold=1, enabled=False)
        b.record_failure("d1")
        b.record_failure("d1")
        self.assertFalse(b.is_open("d1"))

    def test_open_transitions_to_half_open_after_cooldown(self) -> None:
        import time as _time

        b = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.05, success_threshold=1)
        b.record_failure("d1")
        self.assertTrue(b.is_open("d1"))
        _time.sleep(0.1)
        # After cooldown, is_open returns False and state becomes HALF_OPEN.
        self.assertFalse(b.is_open("d1"))
        self.assertEqual(b.get_state("d1"), CircuitState.HALF_OPEN)

    def test_half_open_success_closes_after_success_threshold(self) -> None:
        import time as _time

        b = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.05, success_threshold=2)
        b.record_failure("d1")
        _time.sleep(0.1)
        b.is_open("d1")  # trigger HALF_OPEN transition
        self.assertEqual(b.get_state("d1"), CircuitState.HALF_OPEN)
        b.record_success("d1")
        # Need 2 successes to close.
        self.assertEqual(b.get_state("d1"), CircuitState.HALF_OPEN)
        b.record_success("d1")
        self.assertEqual(b.get_state("d1"), CircuitState.CLOSED)

    def test_half_open_failure_reopens_immediately(self) -> None:
        import time as _time

        b = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.05, success_threshold=2)
        b.record_failure("d1")
        _time.sleep(0.1)
        b.is_open("d1")  # HALF_OPEN
        b.record_failure("d1", error_code="boom")
        self.assertEqual(b.get_state("d1"), CircuitState.OPEN)
        snap = b.snapshot("d1")
        self.assertIsNotNone(snap)
        self.assertEqual(snap.total_opened, 2)

    def test_reset_clears_single_deployment(self) -> None:
        self.b.record_failure("d1")
        self.b.record_failure("d2")
        self.b.reset("d1")
        self.assertIsNone(self.b.snapshot("d1"))
        self.assertIsNotNone(self.b.snapshot("d2"))

    def test_reset_all_clears_everything(self) -> None:
        self.b.record_failure("d1")
        self.b.record_failure("d2")
        self.b.reset()
        self.assertEqual(self.b.snapshot_all(), [])

    def test_force_state_open(self) -> None:
        self.b.force_state("d1", CircuitState.OPEN)
        self.assertTrue(self.b.is_open("d1"))
        snap = self.b.snapshot("d1")
        self.assertEqual(snap.state, CircuitState.OPEN)
        self.assertEqual(snap.total_opened, 1)

    def test_force_state_closed(self) -> None:
        self.b.record_failure("d1")
        self.b.record_failure("d1")
        self.b.record_failure("d1")  # opens
        self.b.force_state("d1", CircuitState.CLOSED)
        self.assertEqual(self.b.get_state("d1"), CircuitState.CLOSED)
        self.assertFalse(self.b.is_open("d1"))

    def test_configure_updates_thresholds(self) -> None:
        self.b.configure(failure_threshold=10)
        for _ in range(5):
            self.b.record_failure("d1")
        # 5 < 10, still closed.
        self.assertFalse(self.b.is_open("d1"))

    def test_snapshot_all_returns_all_tracked(self) -> None:
        self.b.record_failure("d1")
        self.b.record_success("d2")
        snaps = self.b.snapshot_all()
        ids = {s.deployment_id for s in snaps}
        self.assertEqual(ids, {"d1", "d2"})

    def test_snapshot_seconds_until_half_open(self) -> None:
        b = CircuitBreaker(failure_threshold=1, cooldown_seconds=60)
        b.record_failure("d1")
        snap = b.snapshot("d1")
        self.assertIsNotNone(snap)
        self.assertIsNotNone(snap.seconds_until_half_open)
        self.assertGreater(snap.seconds_until_half_open, 0)
        self.assertLessEqual(snap.seconds_until_half_open, 60)


class RouterCircuitBreakerIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dep_id_a = uuid4()
        self.dep_id_b = uuid4()
        self.breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=60)
        self.router = ModelRouter(
            providers=[_provider()],
            deployments=[
                _deployment(self.dep_id_a, priority=10),
                _deployment(self.dep_id_b, priority=20),
            ],
            circuit_breaker=self.breaker,
        )

    def test_open_circuit_is_skipped_in_favour_of_healthy_candidate(self) -> None:
        # Open the circuit for the higher-priority deployment A.
        self.breaker.record_failure(str(self.dep_id_a))
        self.assertTrue(self.breaker.is_open(str(self.dep_id_a)))
        routes = asyncio.run(self.router.plan(_request(), _decision()))
        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0].deployment.id, self.dep_id_b)

    def test_all_open_falls_back_to_all_candidates(self) -> None:
        self.breaker.record_failure(str(self.dep_id_a))
        self.breaker.record_failure(str(self.dep_id_b))
        routes = asyncio.run(self.router.plan(_request(), _decision()))
        # When everything is open we keep all so caller can attempt last-resort.
        self.assertEqual(len(routes), 2)

    def test_disabled_breaker_does_not_filter(self) -> None:
        breaker = CircuitBreaker(failure_threshold=1, enabled=False)
        router = ModelRouter(
            providers=[_provider()],
            deployments=[
                _deployment(self.dep_id_a, priority=10),
                _deployment(self.dep_id_b, priority=20),
            ],
            circuit_breaker=breaker,
        )
        breaker.record_failure(str(self.dep_id_a))
        routes = asyncio.run(router.plan(_request(), _decision()))
        self.assertEqual(len(routes), 2)

    def test_default_breaker_is_global_singleton(self) -> None:
        router = ModelRouter(providers=[_provider()], deployments=[])
        self.assertIs(router.circuit_breaker, global_breaker)


class GatewayCircuitBreakerRecordingTests(unittest.TestCase):
    """Verify the gateway records outcomes to the breaker on each attempt."""

    def setUp(self) -> None:
        self.breaker = CircuitBreaker(failure_threshold=2, cooldown_seconds=60)

    def _build_gateway(self, adapter_responses: dict[str, object]):
        from app.llm.gateway import LLMGateway
        from app.llm.schemas import (
            BudgetReservation,
            ConnectionTestResult,
            LLMResponse,
            LLMUsageMetrics,
        )

        dep_id = uuid4()
        provider = _provider()
        deployment = _deployment(dep_id)

        class StubAdapter:
            async def chat(self, request, context):
                outcome = adapter_responses.get("chat")
                if isinstance(outcome, Exception):
                    raise outcome
                return LLMResponse(
                    request_id="req",
                    model_key=request.model_key or "m1",
                    content="ok",
                    usage=LLMUsageMetrics(),
                    provider_key="p1",
                    deployment_id=dep_id,
                )

            async def test_connection(self, request):
                outcome = adapter_responses.get("test_connection")
                if isinstance(outcome, Exception):
                    raise outcome
                ok = outcome if isinstance(outcome, bool) else True
                return ConnectionTestResult(
                    ok=ok,
                    provider_key="p1",
                    adapter_type=LLMAdapterType.OPENAI_COMPATIBLE,
                    model_key="m1",
                    latency_ms=10,
                )

        # Duck-typed stubs (no subclassing of real DB-bound classes).
        class StubPolicy:
            async def evaluate(self, request, context):
                return PolicyDecision(allowed=True, model_key=request.model_key or "m1")

        class StubBudget:
            pricing = type(
                "P",
                (),
                {
                    "recalculate_usage": staticmethod(lambda u, model_key=None: u),
                    "price_rule_for": staticmethod(lambda mk: type("R", (), {"pattern": "stub"})()),
                },
            )()

            async def reserve(self, request, context):
                return BudgetReservation(approved=True)

            async def settle(self, reservation, usage, context):
                pass

            async def release(self, reservation, context, reason=None):
                pass

        class StubUsage:
            async def record_success(self, context, route, response):
                pass

            async def record_failure(
                self, context, status, error_code, error_message=None, route=None, metadata=None
            ):
                pass

            async def record_connection_test(self, context, route, result):
                pass

        router = ModelRouter(
            providers=[provider],
            deployments=[deployment],
            circuit_breaker=self.breaker,
        )
        gateway = LLMGateway(
            policy=StubPolicy(),
            budget=StubBudget(),
            router=router,
            usage=StubUsage(),
            circuit_breaker=self.breaker,
        )
        gateway._adapter_for = lambda route: StubAdapter()  # type: ignore[assignment]
        return gateway, dep_id

    def test_chat_success_records_success(self) -> None:
        from app.llm.schemas import LLMRequestContext

        gateway, dep_id = self._build_gateway({"chat": "ok"})
        ctx = LLMRequestContext(tenant_id=uuid4())
        asyncio.run(gateway.chat(_request(), ctx))
        self.assertEqual(self.breaker.get_state(str(dep_id)), CircuitState.CLOSED)
        snap = self.breaker.snapshot(str(dep_id))
        self.assertIsNotNone(snap)

    def test_chat_failure_records_failure(self) -> None:
        from app.llm.schemas import LLMRequestContext

        gateway, dep_id = self._build_gateway({"chat": RuntimeError("boom")})
        ctx = LLMRequestContext(tenant_id=uuid4())
        with self.assertRaises(RuntimeError):
            asyncio.run(gateway.chat(_request(), ctx))
        snap = self.breaker.snapshot(str(dep_id))
        self.assertIsNotNone(snap)
        self.assertEqual(snap.consecutive_failures, 1)
        self.assertEqual(snap.last_failure_code, "RuntimeError")

    def test_repeated_failures_open_circuit(self) -> None:
        from app.llm.schemas import LLMRequestContext

        gateway, dep_id = self._build_gateway({"chat": RuntimeError("boom")})
        ctx = LLMRequestContext(tenant_id=uuid4())
        # failure_threshold is 2; two failures should open.
        for _ in range(2):
            with self.assertRaises(RuntimeError):
                asyncio.run(gateway.chat(_request(), ctx))
        self.assertEqual(self.breaker.get_state(str(dep_id)), CircuitState.OPEN)
        self.assertTrue(self.breaker.is_open(str(dep_id)))


if __name__ == "__main__":
    unittest.main()
