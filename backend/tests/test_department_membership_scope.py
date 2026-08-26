import unittest
from uuid import uuid4

from app.api.deps import Principal
from app.services import agent_runtime_service, chat_service, knowledge_service


class DepartmentMembershipScopeTests(unittest.IsolatedAsyncioTestCase):
    async def test_agent_runtime_department_membership_is_tenant_scoped(self) -> None:
        principal = Principal(tenant_id=uuid4(), user_id=uuid4(), permissions={"agents:read"})
        session = FakeMembershipSession([uuid4()])

        result = await agent_runtime_service._principal_department_ids(session, principal)

        self.assertEqual(1, len(result))
        self.assert_membership_query_is_tenant_scoped(session.statements[0])

    async def test_chat_department_membership_is_tenant_scoped(self) -> None:
        principal = Principal(tenant_id=uuid4(), user_id=uuid4(), permissions={"agents:read"})
        session = FakeMembershipSession([uuid4()])

        result = await chat_service._principal_department_ids(session, principal)

        self.assertEqual(1, len(result))
        self.assert_membership_query_is_tenant_scoped(session.statements[0])

    async def test_knowledge_department_membership_is_tenant_scoped(self) -> None:
        principal = Principal(tenant_id=uuid4(), user_id=uuid4(), permissions={"knowledge:read"})
        session = FakeMembershipSession([uuid4()])

        result = await knowledge_service._principal_department_ids(session, principal)

        self.assertEqual(1, len(result))
        self.assert_membership_query_is_tenant_scoped(session.statements[0])

    def assert_membership_query_is_tenant_scoped(self, statement: object) -> None:
        statement_text = str(statement)
        self.assertIn("JOIN departments", statement_text)
        self.assertIn("departments.id = user_departments.department_id", statement_text)
        self.assertIn("departments.tenant_id", statement_text)
        self.assertIn("user_departments.user_id", statement_text)


class FakeMembershipSession:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows
        self.statements: list[object] = []

    async def execute(self, statement: object) -> object:
        self.statements.append(statement)
        return FakeScalarsResult(self.rows)


class FakeScalarsResult:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def scalars(self):
        return self

    def all(self) -> list[object]:
        return self.rows


if __name__ == "__main__":
    unittest.main()
