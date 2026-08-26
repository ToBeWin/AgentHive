from decimal import Decimal
from datetime import datetime, timezone
from uuid import uuid4
import unittest

from app.llm.budget import BudgetGuard
from app.llm.schemas import LLMChatRequest, LLMRequestContext, LLMUsageMetrics, Message
from app.models.llm import LLMBudget


class FakeScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakePoliciesResult:
    def __init__(self, policies):
        self._policies = policies

    def scalars(self):
        return FakeScalarResult(self._policies)


class FakeUsageResult:
    def __init__(self, cost: str, tokens: int):
        self._cost = Decimal(cost)
        self._tokens = tokens

    def one(self):
        return self._cost, self._tokens


class FakeScalarOneOrNoneResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeBudgetSession:
    def __init__(
        self,
        *,
        policies,
        spent_cost: str = "0",
        spent_tokens: int = 0,
        resolved_cost_center_id=None,
    ):
        self._policies = policies
        self._spent_cost = spent_cost
        self._spent_tokens = spent_tokens
        self._resolved_cost_center_id = resolved_cost_center_id
        self.execute_count = 0
        self.rollback_called = False
        self.commit_count = 0
        self.added = []

    async def execute(self, statement):
        self.execute_count += 1
        statement_text = str(statement)
        if "user_departments" in statement_text:
            return FakeScalarOneOrNoneResult(self._resolved_cost_center_id)
        if "llm_budgets" in statement_text:
            return FakePoliciesResult(self._policies)
        return FakeUsageResult(self._spent_cost, self._spent_tokens)

    async def get(self, _model, row_id):
        return next((policy for policy in self._policies if policy.id == row_id), None)

    def add(self, row):
        self.added.append(row)

    async def commit(self):
        self.commit_count += 1

    async def rollback(self):
        self.rollback_called = True


def make_request(max_tokens: int = 10) -> LLMChatRequest:
    return LLMChatRequest(
        model_key="qwen-plus",
        messages=[Message(role="user", content="x" * 40)],
        max_tokens=max_tokens,
    )


def make_policy(
    *,
    tenant_id,
    scope_type: str,
    scope_id,
    amount_usd: str = "1",
    token_limit: int | None = None,
    hard_limit: bool = True,
) -> LLMBudget:
    return LLMBudget(
        tenant_id=tenant_id,
        scope_type=scope_type,
        scope_id=scope_id,
        period="monthly",
        amount_usd=Decimal(amount_usd),
        token_limit=token_limit,
        hard_limit=hard_limit,
        is_active=True,
    )


class BudgetGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_department_amount_limit_denies_matching_scope(self):
        tenant_id = uuid4()
        department_id = uuid4()
        policy = make_policy(
            tenant_id=tenant_id,
            scope_type="department",
            scope_id=department_id,
            amount_usd="1",
        )
        session = FakeBudgetSession(policies=[policy], spent_cost="1")

        reservation = await BudgetGuard(session=session).reserve(
            make_request(),
            LLMRequestContext(tenant_id=tenant_id, department_id=department_id),
        )

        self.assertFalse(reservation.approved)
        self.assertIn("department budget amount limit exceeded", reservation.reason)
        self.assertGreater(reservation.estimated_tokens, 0)
        self.assertFalse(session.rollback_called)
        self.assertEqual(["deny"], [row.event_type for row in session.added])
        self.assertEqual(policy.id, session.added[0].budget_id)
        self.assertEqual(department_id, session.added[0].department_id)

    async def test_reserve_usage_supports_non_token_model_costs(self):
        tenant_id = uuid4()
        department_id = uuid4()
        policy = make_policy(
            tenant_id=tenant_id,
            scope_type="department",
            scope_id=department_id,
            amount_usd="0.04",
        )
        session = FakeBudgetSession(policies=[policy], spent_cost="0.02")

        reservation = await BudgetGuard(session=session).reserve_usage(
            LLMUsageMetrics(total_tokens=0, cost_usd=Decimal("0.03")),
            LLMRequestContext(
                tenant_id=tenant_id,
                department_id=department_id,
                source="media_generation.image",
            ),
            metadata={"model_family": "media_generation"},
        )

        self.assertFalse(reservation.approved)
        self.assertEqual(0, reservation.estimated_tokens)
        self.assertEqual(Decimal("0.03"), reservation.estimated_cost_usd)
        self.assertEqual(["deny"], [row.event_type for row in session.added])
        self.assertEqual("media_generation.image", session.added[0].metadata_json["source"])
        self.assertEqual("media_generation", session.added[0].metadata_json["model_family"])

    async def test_agent_token_limit_denies_matching_scope(self):
        tenant_id = uuid4()
        agent_id = uuid4()
        policy = make_policy(
            tenant_id=tenant_id,
            scope_type="agent",
            scope_id=agent_id,
            amount_usd="0",
            token_limit=100,
        )
        session = FakeBudgetSession(policies=[policy], spent_tokens=95)

        reservation = await BudgetGuard(session=session).reserve(
            make_request(max_tokens=10),
            LLMRequestContext(tenant_id=tenant_id, agent_id=agent_id),
        )

        self.assertFalse(reservation.approved)
        self.assertIn("agent budget token limit exceeded", reservation.reason)
        self.assertEqual(["deny"], [row.event_type for row in session.added])

    async def test_cost_center_amount_limit_denies_resolved_scope(self):
        tenant_id = uuid4()
        user_id = uuid4()
        department_id = uuid4()
        cost_center_id = uuid4()
        policy = make_policy(
            tenant_id=tenant_id,
            scope_type="cost_center",
            scope_id=cost_center_id,
            amount_usd="1",
        )
        session = FakeBudgetSession(
            policies=[policy],
            spent_cost="1",
            resolved_cost_center_id=cost_center_id,
        )

        reservation = await BudgetGuard(session=session).reserve(
            make_request(),
            LLMRequestContext(tenant_id=tenant_id, user_id=user_id, department_id=department_id),
        )

        self.assertFalse(reservation.approved)
        self.assertIn("cost_center budget amount limit exceeded", reservation.reason)
        self.assertEqual(["deny"], [row.event_type for row in session.added])
        self.assertEqual(cost_center_id, session.added[0].scope_id)
        self.assertEqual(cost_center_id, session.added[0].cost_center_id)
        self.assertEqual("user_department", session.added[0].metadata_json["cost_center_source"])

    async def test_non_matching_scope_does_not_deny(self):
        tenant_id = uuid4()
        policy = make_policy(
            tenant_id=tenant_id,
            scope_type="channel",
            scope_id=uuid4(),
            amount_usd="0.0001",
            token_limit=1,
        )
        session = FakeBudgetSession(policies=[policy], spent_cost="999", spent_tokens=999)

        reservation = await BudgetGuard(session=session).reserve(
            make_request(max_tokens=1000),
            LLMRequestContext(tenant_id=tenant_id, channel_id=uuid4()),
        )

        self.assertTrue(reservation.approved)
        self.assertEqual("budget_approved", reservation.reason)
        self.assertEqual(1, session.execute_count)
        self.assertEqual([], session.added)

    async def test_tenant_policy_applies_without_scope_id(self):
        tenant_id = uuid4()
        policy = make_policy(
            tenant_id=tenant_id,
            scope_type="tenant",
            scope_id=None,
            amount_usd="0.0001",
        )
        session = FakeBudgetSession(policies=[policy], spent_cost="0")

        reservation = await BudgetGuard(session=session).reserve(
            make_request(max_tokens=1000),
            LLMRequestContext(tenant_id=tenant_id),
        )

        self.assertFalse(reservation.approved)
        self.assertIn("tenant budget amount limit exceeded", reservation.reason)
        self.assertEqual(["deny"], [row.event_type for row in session.added])

    async def test_matching_budget_is_reserved_settled_and_released_in_ledger(self):
        tenant_id = uuid4()
        user_id = uuid4()
        cost_center_id = uuid4()
        policy = make_policy(
            tenant_id=tenant_id,
            scope_type="tenant",
            scope_id=None,
            amount_usd="10",
        )
        session = FakeBudgetSession(
            policies=[policy],
            spent_cost="0",
            spent_tokens=0,
            resolved_cost_center_id=cost_center_id,
        )
        guard = BudgetGuard(session=session)
        context = LLMRequestContext(tenant_id=tenant_id, user_id=user_id)

        reservation = await guard.reserve(make_request(), context)
        await guard.settle(
            reservation,
            actual_usage=guard.pricing.estimate(make_request(max_tokens=5)),
            context=context,
        )
        await guard.release(reservation, context, "adapter_exception")

        self.assertTrue(reservation.approved)
        self.assertEqual([policy.id], [scope.budget_id for scope in reservation.budget_scopes])
        self.assertEqual(
            ["reserve", "settle", "release"], [row.event_type for row in session.added]
        )
        self.assertEqual(3, session.commit_count)
        self.assertEqual(reservation.reservation_id, session.added[0].reservation_id)
        self.assertEqual(user_id, session.added[0].user_id)
        self.assertEqual(cost_center_id, session.added[0].cost_center_id)
        self.assertEqual(
            "user_primary_department", session.added[0].metadata_json["cost_center_source"]
        )
        self.assertGreater(session.added[1].actual_tokens, 0)
        self.assertEqual("adapter_exception", session.added[2].reason)

    async def test_budget_ledger_resolves_cost_center_from_user_department(self):
        tenant_id = uuid4()
        user_id = uuid4()
        department_id = uuid4()
        cost_center_id = uuid4()
        policy = make_policy(
            tenant_id=tenant_id,
            scope_type="department",
            scope_id=department_id,
            amount_usd="10",
        )
        session = FakeBudgetSession(
            policies=[policy],
            spent_cost="0",
            spent_tokens=0,
            resolved_cost_center_id=cost_center_id,
        )

        reservation = await BudgetGuard(session=session).reserve(
            make_request(),
            LLMRequestContext(tenant_id=tenant_id, user_id=user_id, department_id=department_id),
        )

        self.assertTrue(reservation.approved)
        self.assertEqual(["reserve"], [row.event_type for row in session.added])
        self.assertEqual(department_id, session.added[0].department_id)
        self.assertEqual(cost_center_id, session.added[0].cost_center_id)
        self.assertEqual("user_department", session.added[0].metadata_json["cost_center_source"])

    async def test_soft_budget_records_alert_when_threshold_is_reached(self):
        tenant_id = uuid4()
        policy = make_policy(
            tenant_id=tenant_id,
            scope_type="tenant",
            scope_id=None,
            amount_usd="0.001",
            hard_limit=False,
        )
        policy.alert_threshold_pct = 80
        session = FakeBudgetSession(policies=[policy], spent_cost="0.00079", spent_tokens=0)
        guard = BudgetGuard(session=session)
        context = LLMRequestContext(tenant_id=tenant_id)

        reservation = await guard.reserve(make_request(max_tokens=10), context)
        await guard.settle(
            reservation,
            actual_usage=guard.pricing.estimate(make_request(max_tokens=10)),
            context=context,
        )

        self.assertTrue(reservation.approved)
        self.assertIn("alert", [row.event_type for row in session.added])
        alert = [row for row in session.added if row.event_type == "alert"][0]
        self.assertEqual("soft_budget_threshold_reached", alert.reason)
        self.assertEqual(80, alert.metadata_json["alert_threshold_pct"])

    async def test_soft_budget_does_not_repeat_alert_after_threshold_is_already_crossed(self):
        tenant_id = uuid4()
        policy = make_policy(
            tenant_id=tenant_id,
            scope_type="tenant",
            scope_id=None,
            amount_usd="0.001",
            hard_limit=False,
        )
        policy.alert_threshold_pct = 80
        session = FakeBudgetSession(policies=[policy], spent_cost="0.0009", spent_tokens=0)
        guard = BudgetGuard(session=session)
        context = LLMRequestContext(tenant_id=tenant_id)

        reservation = await guard.reserve(make_request(max_tokens=10), context)
        await guard.settle(
            reservation,
            actual_usage=guard.pricing.estimate(make_request(max_tokens=10)),
            context=context,
        )

        self.assertTrue(reservation.approved)
        self.assertNotIn("alert", [row.event_type for row in session.added])

    async def test_custom_period_budget_uses_persisted_window(self):
        tenant_id = uuid4()
        policy = make_policy(
            tenant_id=tenant_id,
            scope_type="tenant",
            scope_id=None,
            amount_usd="0.0001",
        )
        policy.period = "custom"
        policy.custom_period_start = datetime(2026, 6, 1, tzinfo=timezone.utc)
        policy.custom_period_end = datetime(2026, 6, 30, tzinfo=timezone.utc)
        session = FakeBudgetSession(policies=[policy], spent_cost="0.0001")

        reservation = await BudgetGuard(session=session).reserve(
            make_request(max_tokens=1000),
            LLMRequestContext(tenant_id=tenant_id),
        )

        self.assertFalse(reservation.approved)
        self.assertIn("tenant budget amount limit exceeded", reservation.reason)


if __name__ == "__main__":
    unittest.main()
