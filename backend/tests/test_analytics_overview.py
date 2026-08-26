from datetime import date
from decimal import Decimal
import unittest
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.analytics import router as analytics_router
from app.core.database import get_session
from app.core.security import Permission, create_access_token
from app.models.tenant import Tenant
from app.models.user import User
from app.api.deps import Principal
from app.services.analytics_service import get_analytics_overview


class AnalyticsOverviewTests(unittest.IsolatedAsyncioTestCase):
    async def test_overview_includes_user_and_agent_usage(self) -> None:
        tenant_id = uuid4()
        user_id = uuid4()
        agent_id = uuid4()
        session = FakeAnalyticsSession(
            [
                FakeOneResult((4, 300, Decimal("0.25"), 3)),
                FakeAllResult([("qwen-plus", 300, Decimal("0.25"), 4)]),
                FakeAllResult([(date(2026, 6, 13), 300, Decimal("0.25"), 4)]),
                FakeAllResult([(uuid4(), "Support", 300, Decimal("0.25"), 4)]),
                FakeAllResult(
                    [(user_id, "Alice Admin", "alice@example.com", 220, Decimal("0.20"), 3)]
                ),
                FakeAllResult(
                    [(agent_id, "售后客服", "customer_service", 180, Decimal("0.15"), 2)]
                ),
            ]
        )

        response = await get_analytics_overview(
            session,
            Principal(
                tenant_id=tenant_id,
                user_id=uuid4(),
                permissions={Permission.ANALYTICS_READ.value, Permission.BUDGETS_EXPORT.value},
            ),
        )

        self.assertEqual(4, response.totals.total_requests)
        self.assertEqual("tenant", response.metadata["visibility_scope"])
        self.assertEqual("Alice Admin", response.user_usage[0].user_name)
        self.assertEqual(220, response.user_usage[0].tokens)
        self.assertEqual("售后客服", response.agent_usage[0].agent_name)
        self.assertEqual("customer_service", response.agent_usage[0].agent_key)
        self.assertEqual(6, len(session.statements))
        self.assertIn("users.tenant_id", str(session.statements[4]))
        self.assertIn("users.deleted_at IS NULL", str(session.statements[4]))
        self.assertIn("agent_instances.tenant_id", str(session.statements[5]))

    async def test_overview_with_analytics_read_is_scoped_to_user_departments(self) -> None:
        tenant_id = uuid4()
        user_id = uuid4()
        department_id = uuid4()
        session = FakeAnalyticsSession(
            [
                FakeAllResult([department_id]),
                FakeOneResult((1, 100, Decimal("0.10"), 1)),
                FakeAllResult([("qwen-plus", 100, Decimal("0.10"), 1)]),
                FakeAllResult([(date(2026, 6, 13), 100, Decimal("0.10"), 1)]),
                FakeAllResult([(department_id, "Support", 100, Decimal("0.10"), 1)]),
                FakeAllResult([(user_id, "Alice", "alice@example.com", 100, Decimal("0.10"), 1)]),
                FakeAllResult(
                    [(uuid4(), "客服 Agent", "customer_service", 100, Decimal("0.10"), 1)]
                ),
            ]
        )

        response = await get_analytics_overview(
            session,
            Principal(
                tenant_id=tenant_id, user_id=user_id, permissions={Permission.ANALYTICS_READ.value}
            ),
        )

        self.assertEqual(1, response.totals.total_requests)
        self.assertEqual("department", response.metadata["visibility_scope"])
        self.assertEqual(7, len(session.statements))
        self.assertIn("JOIN departments", str(session.statements[0]))
        for statement in session.statements[1:]:
            statement_text = str(statement)
            self.assertIn("llm_usage.user_id", statement_text)
            self.assertIn("llm_usage.department_id", statement_text)


class AnalyticsApiPermissionTests(unittest.TestCase):
    def test_analytics_overview_requires_analytics_read_not_budget_read(self) -> None:
        session = FakeAnalyticsApiSession()
        client = _build_client(session)

        response = client.get(
            "/api/v1/analytics/overview",
            headers={"Authorization": f"Bearer {_token(Permission.BUDGETS_READ)}"},
        )

        self.assertEqual(403, response.status_code)
        self.assertEqual(0, session.execute_count)

    def test_analytics_overview_accepts_analytics_read(self) -> None:
        session = FakeAnalyticsApiSession()
        client = _build_client(session)

        response = client.get(
            "/api/v1/analytics/overview",
            headers={"Authorization": f"Bearer {_token(Permission.ANALYTICS_READ)}"},
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual("unavailable", response.json()["metadata"]["storage"])
        self.assertEqual(1, session.execute_count)


class FakeAnalyticsSession:
    def __init__(self, results: list[object]) -> None:
        self.results = list(results)
        self.statements: list[object] = []

    async def execute(self, statement: object) -> object:
        self.statements.append(statement)
        if not self.results:
            raise AssertionError("Unexpected execute call.")
        return self.results.pop(0)

    async def rollback(self) -> None:
        return None


class FakeOneResult:
    def __init__(self, row: tuple[object, ...]) -> None:
        self.row = row

    def one(self) -> tuple[object, ...]:
        return self.row


class FakeAllResult:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows

    def all(self) -> list[tuple[object, ...]]:
        return self.rows

    def scalars(self) -> "FakeAllResult":
        return self


class FakeAnalyticsApiSession:
    def __init__(self) -> None:
        self.execute_count = 0
        self.user_id = UUID("00000000-0000-4000-8000-000000000301")
        self.tenant_id = UUID("00000000-0000-4000-8000-000000000401")

    async def get(self, model, row_id):
        if model is User and row_id == self.user_id:
            return User(
                id=self.user_id,
                tenant_id=self.tenant_id,
                email="analyst@example.com",
                hashed_password="bcrypt-sha256$placeholder",
                is_active=True,
            )
        if model is Tenant and row_id == self.tenant_id:
            return Tenant(id=self.tenant_id, name="Demo", slug="demo", is_active=True)
        return None

    async def execute(self, _statement):
        self.execute_count += 1
        raise SQLAlchemyError("analytics storage unavailable")

    async def rollback(self) -> None:
        return None


def _build_client(session: FakeAnalyticsApiSession) -> TestClient:
    app = FastAPI()
    app.include_router(analytics_router, prefix="/api/v1")

    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app)


def _token(*permissions: Permission) -> str:
    return create_access_token(
        subject=UUID("00000000-0000-4000-8000-000000000301"),
        tenant_id=UUID("00000000-0000-4000-8000-000000000401"),
        permissions=[permission.value for permission in permissions],
    )


if __name__ == "__main__":
    unittest.main()
