import unittest
from uuid import uuid4

from app.llm.cost_center import resolve_cost_center
from app.llm.schemas import LLMRequestContext


class CostCenterScopeTests(unittest.IsolatedAsyncioTestCase):
    async def test_department_cost_center_resolution_is_tenant_scoped(self) -> None:
        tenant_id = uuid4()
        cost_center_id = uuid4()
        session = FakeCostCenterSession([cost_center_id])

        resolved_id, source = await resolve_cost_center(
            session,
            LLMRequestContext(
                tenant_id=tenant_id,
                user_id=uuid4(),
                department_id=uuid4(),
            ),
        )

        self.assertEqual(cost_center_id, resolved_id)
        self.assertEqual("user_department", source)
        self.assertEqual(1, len(session.statements))
        self.assert_cost_center_query_is_tenant_scoped(session.statements[0])

    async def test_primary_cost_center_resolution_is_tenant_scoped(self) -> None:
        tenant_id = uuid4()
        cost_center_id = uuid4()
        session = FakeCostCenterSession([None, cost_center_id])

        resolved_id, source = await resolve_cost_center(
            session,
            LLMRequestContext(
                tenant_id=tenant_id,
                user_id=uuid4(),
                department_id=uuid4(),
            ),
        )

        self.assertEqual(cost_center_id, resolved_id)
        self.assertEqual("user_primary_department", source)
        self.assertEqual(2, len(session.statements))
        self.assert_cost_center_query_is_tenant_scoped(session.statements[0])
        self.assert_cost_center_query_is_tenant_scoped(session.statements[1])

    def assert_cost_center_query_is_tenant_scoped(self, statement: object) -> None:
        statement_text = str(statement)
        self.assertIn("JOIN departments", statement_text)
        self.assertIn("JOIN cost_centers", statement_text)
        self.assertIn("departments.tenant_id", statement_text)
        self.assertIn("cost_centers.tenant_id", statement_text)
        self.assertIn("cost_centers.is_active IS true", statement_text)
        self.assertIn("user_departments.user_id", statement_text)


class FakeCostCenterSession:
    def __init__(self, scalar_values: list[object]) -> None:
        self.scalar_values = list(scalar_values)
        self.statements: list[object] = []

    async def execute(self, statement: object) -> object:
        self.statements.append(statement)
        if not self.scalar_values:
            raise AssertionError("Unexpected execute call.")
        return FakeScalarOneOrNoneResult(self.scalar_values.pop(0))


class FakeScalarOneOrNoneResult:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object:
        return self.value


if __name__ == "__main__":
    unittest.main()
