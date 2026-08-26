from decimal import Decimal
from uuid import uuid4
import unittest

from app.llm.schemas import (
    DeploymentConfig,
    LLMAdapterType,
    LLMCallStatus,
    LLMRequestContext,
    LLMResponse,
    LLMUsageMetrics,
    ProviderConfig,
    RouteSelection,
)
from app.llm.usage import UsageCollector


class FakeScalarOneOrNoneResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeUsageSession:
    def __init__(self, resolved_cost_center_id=None):
        self.added = []
        self.commits = 0
        self.execute_count = 0
        self.resolved_cost_center_id = resolved_cost_center_id

    def add(self, row):
        self.added.append(row)

    async def commit(self):
        self.commits += 1

    async def execute(self, _statement):
        self.execute_count += 1
        return FakeScalarOneOrNoneResult(self.resolved_cost_center_id)


def make_route() -> RouteSelection:
    return RouteSelection(
        provider=ProviderConfig(
            provider_key="qwen",
            name="Qwen",
            adapter_type=LLMAdapterType.OPENAI_COMPATIBLE,
        ),
        deployment=DeploymentConfig(
            provider_key="qwen",
            provider_name="Qwen",
            adapter_type=LLMAdapterType.OPENAI_COMPATIBLE,
            model_key="qwen-plus",
            display_name="Qwen Plus",
            deployment_name="Qwen Default",
            routing_key="qwen-chat",
        ),
    )


def make_response(route: RouteSelection) -> LLMResponse:
    return LLMResponse(
        request_id="req_1",
        model_key=route.deployment.model_key,
        content="ok",
        provider_key=route.provider.provider_key,
        deployment_id=route.deployment.id,
        usage=LLMUsageMetrics(
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            cost_usd=Decimal("0.0002"),
        ),
    )


class UsageCollectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_cost_center_is_written_to_usage_row(self):
        tenant_id = uuid4()
        user_id = uuid4()
        department_id = uuid4()
        cost_center_id = uuid4()
        session = FakeUsageSession()
        collector = UsageCollector(session=session)
        route = make_route()

        record = await collector.record_success(
            context=LLMRequestContext(
                tenant_id=tenant_id,
                user_id=user_id,
                department_id=department_id,
                cost_center_id=cost_center_id,
            ),
            route=route,
            response=make_response(route),
        )

        self.assertEqual(LLMCallStatus.SUCCESS, record.status)
        self.assertEqual(1, session.commits)
        self.assertEqual(cost_center_id, session.added[0].cost_center_id)
        self.assertEqual("context", session.added[0].metadata_json["cost_center_source"])
        self.assertEqual(str(cost_center_id), collector.audit_events[0]["cost_center_id"])

    async def test_cost_center_is_resolved_from_user_department_binding(self):
        tenant_id = uuid4()
        user_id = uuid4()
        department_id = uuid4()
        cost_center_id = uuid4()
        session = FakeUsageSession(resolved_cost_center_id=cost_center_id)
        collector = UsageCollector(session=session)
        route = make_route()

        await collector.record_success(
            context=LLMRequestContext(
                tenant_id=tenant_id,
                user_id=user_id,
                department_id=department_id,
            ),
            route=route,
            response=make_response(route),
        )

        self.assertEqual(1, session.execute_count)
        self.assertEqual(cost_center_id, session.added[0].cost_center_id)
        self.assertEqual("user_department", session.added[0].metadata_json["cost_center_source"])


if __name__ == "__main__":
    unittest.main()
