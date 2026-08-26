from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
import unittest

from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import Principal
from app.schemas.budget import UsageBreakdownDimension
from app.services.budget_admin_service import get_usage_breakdown


class FakeBreakdownResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeBreakdownScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class FakeBreakdownSession:
    def __init__(self, rows=None, *, department_ids=None, fail=False):
        self.rows = rows or []
        self.department_ids = department_ids or []
        self.fail = fail
        self.rollback_called = False
        self.statements = []

    async def execute(self, statement):
        if self.fail:
            raise SQLAlchemyError("storage unavailable")
        self.statements.append(statement)
        if "user_departments" in str(statement):
            return FakeBreakdownScalarResult(self.department_ids)
        return FakeBreakdownResult(self.rows)

    async def rollback(self):
        self.rollback_called = True


class BudgetUsageBreakdownTests(unittest.IsolatedAsyncioTestCase):
    async def test_usage_breakdown_aggregates_dimension_rows(self):
        tenant_id = uuid4()
        department_id = uuid4()
        last_used_at = datetime(2026, 6, 12, tzinfo=timezone.utc)
        session = FakeBreakdownSession(
            rows=[
                (
                    department_id,
                    3,
                    2,
                    1,
                    120,
                    80,
                    200,
                    Decimal("0.1234"),
                    last_used_at,
                )
            ]
        )

        response = await get_usage_breakdown(
            session,
            Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"budgets:export"}),
            dimension=UsageBreakdownDimension.DEPARTMENT,
        )

        self.assertEqual(tenant_id, response.tenant_id)
        self.assertEqual(UsageBreakdownDimension.DEPARTMENT, response.dimension)
        self.assertEqual(1, len(response.items))
        self.assertEqual(str(department_id), response.items[0].key)
        self.assertEqual(3, response.items[0].request_count)
        self.assertEqual(2, response.items[0].success_count)
        self.assertEqual(1, response.items[0].error_count)
        self.assertEqual(200, response.items[0].total_tokens)
        self.assertEqual(Decimal("0.1234"), response.items[0].cost_amount)
        self.assertEqual(Decimal("0.1234"), response.total_cost_amount)
        self.assertEqual(200, response.total_tokens)

    async def test_usage_breakdown_read_scope_filters_to_user_departments(self):
        tenant_id = uuid4()
        user_id = uuid4()
        department_id = uuid4()
        session = FakeBreakdownSession(
            rows=[
                (
                    department_id,
                    1,
                    1,
                    0,
                    10,
                    20,
                    30,
                    Decimal("0.0100"),
                    datetime(2026, 6, 12, tzinfo=timezone.utc),
                )
            ],
            department_ids=[department_id],
        )

        response = await get_usage_breakdown(
            session,
            Principal(tenant_id=tenant_id, user_id=user_id, permissions={"budgets:read"}),
            dimension=UsageBreakdownDimension.DEPARTMENT,
        )

        self.assertEqual(1, len(response.items))
        self.assertEqual(2, len(session.statements))
        self.assertIn("JOIN departments", str(session.statements[0]))
        scoped_query = str(session.statements[1])
        self.assertIn("llm_usage.user_id", scoped_query)
        self.assertIn("llm_usage.department_id", scoped_query)

    async def test_usage_breakdown_returns_empty_when_storage_unavailable(self):
        tenant_id = uuid4()
        session = FakeBreakdownSession(fail=True)

        response = await get_usage_breakdown(
            session,
            Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"budgets:read"}),
            dimension=UsageBreakdownDimension.MODEL,
        )

        self.assertEqual([], response.items)
        self.assertEqual(0, response.total_request_count)
        self.assertTrue(session.rollback_called)


if __name__ == "__main__":
    unittest.main()
