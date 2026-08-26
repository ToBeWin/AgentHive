from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
import unittest

from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import Principal
from app.models.llm import LLMBudgetLedger, LLMUsage
from app.schemas.budget import BudgetEventType, BudgetScopeType
from app.services.budget_admin_service import list_budget_ledger, list_usage_ledger


class FakeScalarRows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeRowsResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return FakeScalarRows(self._rows)


class FakeCountResult:
    def __init__(self, count: int):
        self._count = count

    def scalar_one(self):
        return self._count


class FakeBudgetLedgerSession:
    def __init__(self, rows=None, *, department_ids=None, fail=False):
        self.rows = rows or []
        self.department_ids = department_ids or []
        self.fail = fail
        self.execute_count = 0
        self.rollback_called = False
        self.statements = []

    async def execute(self, statement):
        if self.fail:
            raise SQLAlchemyError("budget ledger unavailable")
        self.statements.append(statement)
        statement_text = str(statement)
        if "user_departments" in statement_text:
            return FakeRowsResult(self.department_ids)
        self.execute_count += 1
        if self.execute_count == 1:
            return FakeCountResult(len(self.rows))
        return FakeRowsResult(self.rows)

    async def rollback(self):
        self.rollback_called = True


class BudgetLedgerServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_budget_ledger_maps_reservation_events(self):
        tenant_id = uuid4()
        budget_id = uuid4()
        user_id = uuid4()
        department_id = uuid4()
        created_at = datetime(2026, 6, 12, tzinfo=timezone.utc)
        row = LLMBudgetLedger(
            id=uuid4(),
            tenant_id=tenant_id,
            budget_id=budget_id,
            reservation_id="reservation-1",
            request_id="request-1",
            event_type="settle",
            scope_type="department",
            scope_id=department_id,
            user_id=user_id,
            department_id=department_id,
            estimated_tokens=100,
            actual_tokens=80,
            estimated_cost_usd=Decimal("0.050000"),
            actual_cost_usd=Decimal("0.040000"),
            reason="budget_settled",
            metadata_json={"source": "chat"},
            created_at=created_at,
            updated_at=created_at,
        )
        session = FakeBudgetLedgerSession(rows=[row])

        response = await list_budget_ledger(
            session,
            Principal(tenant_id=tenant_id, user_id=user_id, permissions={"budgets:export"}),
            event_type=BudgetEventType.SETTLE,
            scope_type=BudgetScopeType.DEPARTMENT,
        )

        self.assertEqual(1, response.total)
        self.assertEqual(1, len(response.items))
        item = response.items[0]
        self.assertEqual(budget_id, item.budget_id)
        self.assertEqual("reservation-1", item.reservation_id)
        self.assertEqual(BudgetEventType.SETTLE, item.event_type)
        self.assertEqual(BudgetScopeType.DEPARTMENT, item.scope_type)
        self.assertEqual(department_id, item.scope_id)
        self.assertEqual(100, item.estimated_tokens)
        self.assertEqual(80, item.actual_tokens)
        self.assertEqual(Decimal("0.050000"), item.estimated_cost_amount)
        self.assertEqual(Decimal("0.040000"), item.actual_cost_amount)
        self.assertEqual({"source": "chat"}, item.metadata)

    async def test_budget_ledger_read_scope_filters_to_user_departments(self):
        tenant_id = uuid4()
        user_id = uuid4()
        department_id = uuid4()
        row = LLMBudgetLedger(
            id=uuid4(),
            tenant_id=tenant_id,
            budget_id=uuid4(),
            reservation_id="reservation-2",
            request_id="request-2",
            event_type="reserve",
            scope_type="department",
            scope_id=department_id,
            user_id=user_id,
            department_id=department_id,
            estimated_tokens=10,
            actual_tokens=0,
            estimated_cost_usd=Decimal("0.010000"),
            actual_cost_usd=Decimal("0"),
            reason="budget_reserved",
            metadata_json={},
        )
        session = FakeBudgetLedgerSession(rows=[row], department_ids=[department_id])

        response = await list_budget_ledger(
            session,
            Principal(tenant_id=tenant_id, user_id=user_id, permissions={"budgets:read"}),
        )

        self.assertEqual(1, response.total)
        self.assertEqual(3, len(session.statements))
        self.assertIn("JOIN departments", str(session.statements[0]))
        scoped_query = str(session.statements[1])
        self.assertIn("llm_budget_ledger.user_id", scoped_query)
        self.assertIn("llm_budget_ledger.department_id", scoped_query)

    async def test_usage_ledger_read_scope_filters_to_user_departments(self):
        tenant_id = uuid4()
        user_id = uuid4()
        department_id = uuid4()
        row = LLMUsage(
            tenant_id=tenant_id,
            user_id=user_id,
            department_id=department_id,
            request_id="usage-request-1",
            model_key="qwen-plus",
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
            cost_usd=Decimal("0.010000"),
            status="success",
        )
        session = FakeBudgetLedgerSession(rows=[row], department_ids=[department_id])

        response = await list_usage_ledger(
            session,
            Principal(tenant_id=tenant_id, user_id=user_id, permissions={"budgets:read"}),
        )

        self.assertEqual(1, response.total)
        self.assertEqual(3, len(session.statements))
        self.assertIn("JOIN departments", str(session.statements[0]))
        scoped_query = str(session.statements[1])
        self.assertIn("llm_usage.user_id", scoped_query)
        self.assertIn("llm_usage.department_id", scoped_query)

    async def test_budget_ledger_returns_empty_when_storage_unavailable(self):
        tenant_id = uuid4()
        session = FakeBudgetLedgerSession(fail=True)

        response = await list_budget_ledger(
            session,
            Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"budgets:read"}),
        )

        self.assertEqual([], response.items)
        self.assertEqual(0, response.total)
        self.assertTrue(session.rollback_called)


if __name__ == "__main__":
    unittest.main()
