from datetime import datetime, timezone
from decimal import Decimal
import unittest
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError

from app.api.deps import Principal
from app.models.audit_log import AuditLog
from app.models.llm import LLMBudget
from app.schemas.budget import (
    BudgetLimitType,
    BudgetPeriod,
    BudgetPolicyStatus,
    BudgetPolicyUpsertRequest,
    BudgetScopeType,
)
from app.services.budget_admin_service import upsert_budget_policy


class BudgetPolicyCustomPeriodTests(unittest.IsolatedAsyncioTestCase):
    def test_budget_policy_requires_amount_or_token_limit(self) -> None:
        with self.assertRaisesRegex(
            ValidationError,
            "budget policy requires amount_limit or token_limit",
        ):
            BudgetPolicyUpsertRequest(
                scope_type=BudgetScopeType.TENANT,
                amount_limit=Decimal("0"),
                token_limit=None,
            )

    def test_budget_policy_accepts_token_only_limit(self) -> None:
        request = BudgetPolicyUpsertRequest(
            scope_type=BudgetScopeType.TENANT,
            amount_limit=Decimal("0"),
            token_limit=1000,
        )

        self.assertEqual(Decimal("0"), request.amount_limit)
        self.assertEqual(1000, request.token_limit)

    def test_budget_policy_accepts_amount_only_limit(self) -> None:
        request = BudgetPolicyUpsertRequest(
            scope_type=BudgetScopeType.TENANT,
            amount_limit=Decimal("100"),
            token_limit=None,
        )

        self.assertEqual(Decimal("100"), request.amount_limit)
        self.assertIsNone(request.token_limit)

    async def test_upsert_budget_policy_accepts_cost_center_scope(self) -> None:
        principal = Principal(
            tenant_id=uuid4(),
            user_id=uuid4(),
            permissions={"budgets:write"},
        )
        cost_center_id = uuid4()
        session = FakeBudgetPolicyUpsertSession()

        response = await upsert_budget_policy(
            session,
            principal,
            BudgetPolicyUpsertRequest(
                scope_type=BudgetScopeType.COST_CENTER,
                scope_id=cost_center_id,
                period=BudgetPeriod.MONTHLY,
                budget_type=BudgetLimitType.HARD,
                amount_limit=Decimal("500"),
                alert_threshold_pct=80,
                status=BudgetPolicyStatus.ACTIVE,
            ),
            request_id="budget-cost-center",
        )

        budgets = [row for row in session.added if isinstance(row, LLMBudget)]
        self.assertEqual(1, len(budgets))
        self.assertEqual("cost_center", budgets[0].scope_type)
        self.assertEqual(cost_center_id, budgets[0].scope_id)
        self.assertEqual(BudgetScopeType.COST_CENTER, response.scope_type)
        self.assertEqual(cost_center_id, response.scope_id)

    async def test_upsert_budget_policy_persists_custom_period_window(self) -> None:
        principal = Principal(
            tenant_id=uuid4(),
            user_id=uuid4(),
            permissions={"budgets:write"},
        )
        start = datetime(2026, 6, 1, tzinfo=timezone.utc)
        end = datetime(2026, 6, 30, tzinfo=timezone.utc)
        session = FakeBudgetPolicyUpsertSession()

        response = await upsert_budget_policy(
            session,
            principal,
            BudgetPolicyUpsertRequest(
                scope_type=BudgetScopeType.TENANT,
                period=BudgetPeriod.CUSTOM,
                custom_period_start=start,
                custom_period_end=end,
                budget_type=BudgetLimitType.SOFT,
                amount_limit=Decimal("100"),
                alert_threshold_pct=75,
                status=BudgetPolicyStatus.ACTIVE,
            ),
            request_id="budget-custom-period",
        )

        budgets = [row for row in session.added if isinstance(row, LLMBudget)]
        self.assertEqual(1, len(budgets))
        policy = budgets[0]
        self.assertEqual("custom", policy.period)
        self.assertEqual(start, policy.custom_period_start)
        self.assertEqual(end, policy.custom_period_end)
        self.assertFalse(policy.hard_limit)
        self.assertEqual(start, response.custom_period_start)
        self.assertEqual(end, response.custom_period_end)
        audit_events = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual(start.isoformat(), audit_events[0].details["custom_period_start"])
        self.assertEqual(end.isoformat(), audit_events[0].details["custom_period_end"])

    async def test_upsert_budget_policy_rejects_unknown_tenant_scope_without_side_effects(
        self,
    ) -> None:
        principal = Principal(
            tenant_id=uuid4(),
            user_id=uuid4(),
            permissions={"budgets:write"},
        )

        for scope_type in (
            BudgetScopeType.DEPARTMENT,
            BudgetScopeType.COST_CENTER,
            BudgetScopeType.USER,
            BudgetScopeType.AGENT,
            BudgetScopeType.CHANNEL,
        ):
            with self.subTest(scope_type=scope_type):
                session = FakeBudgetPolicyUpsertSession(scope_target_exists=False)
                with self.assertRaises(HTTPException) as raised:
                    await upsert_budget_policy(
                        session,
                        principal,
                        BudgetPolicyUpsertRequest(
                            scope_type=scope_type,
                            scope_id=uuid4(),
                            period=BudgetPeriod.MONTHLY,
                            budget_type=BudgetLimitType.HARD,
                            amount_limit=Decimal("250"),
                            alert_threshold_pct=80,
                            status=BudgetPolicyStatus.ACTIVE,
                        ),
                        request_id="budget-scope-target",
                    )

                self.assertEqual(404, raised.exception.status_code)
                self.assertIn(scope_type.value, str(raised.exception.detail))
                self.assertEqual([], session.added)
                self.assertEqual(0, session.commits)
                self.assertEqual(0, session.refreshes)


class FakeBudgetPolicyUpsertSession:
    def __init__(self, *, scope_target_exists: bool = True) -> None:
        self.added: list[object] = []
        self.commits = 0
        self.flushes = 0
        self.refreshes = 0
        self.scope_target_exists = scope_target_exists

    def add(self, row: object) -> None:
        self.added.append(row)

    async def execute(self, _statement):
        return FakeScalarOneOrNoneResult(uuid4() if self.scope_target_exists else None)

    async def flush(self) -> None:
        self.flushes += 1

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, _row: object) -> None:
        self.refreshes += 1

    async def rollback(self) -> None:
        return None


class FakeScalarOneOrNoneResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


if __name__ == "__main__":
    unittest.main()
