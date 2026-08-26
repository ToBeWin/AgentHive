from datetime import datetime, timezone
from decimal import Decimal
import json
from uuid import UUID, uuid4
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import Principal
from app.api.v1.budgets import router as budgets_router
from app.core.database import get_session
from app.core.security import Permission, create_access_token
from app.models.audit_log import AuditLog
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.budget import (
    BudgetEventType,
    BudgetLedgerItem,
    BudgetScopeType,
    UsageLedgerItem,
)
from app.services.budget_admin_service import (
    budget_ledger_to_csv,
    budget_ledger_to_json,
    export_budget_ledger_json,
    export_usage_ledger_json,
    usage_ledger_to_csv,
    usage_ledger_to_json,
)


class BudgetLedgerExportTests(unittest.TestCase):
    def test_usage_ledger_csv_contains_finance_fields(self) -> None:
        tenant_id = uuid4()
        department_id = uuid4()
        item = UsageLedgerItem(
            id=uuid4(),
            tenant_id=tenant_id,
            created_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
            deployment_id=None,
            user_id=None,
            department_id=department_id,
            agent_id=None,
            channel_id=None,
            conversation_id=None,
            cost_center_id=None,
            request_id="req-1",
            model_key="qwen-plus",
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
            cost_amount=Decimal("0.0123"),
            status="success",
            error_code=None,
            metadata={"provider_key": "qwen"},
        )

        body = usage_ledger_to_csv([item])

        self.assertIn("tenant_id", body)
        self.assertIn("department_id", body)
        self.assertIn("model_key", body)
        self.assertIn("qwen-plus", body)
        self.assertIn("0.0123", body)
        self.assertIn("provider_key", body)
        self.assertIn("qwen", body)

    def test_usage_ledger_json_is_structured(self) -> None:
        item = UsageLedgerItem(
            id=uuid4(),
            tenant_id=uuid4(),
            created_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
            deployment_id=None,
            user_id=None,
            department_id=None,
            agent_id=None,
            channel_id=None,
            conversation_id=None,
            cost_center_id=None,
            request_id="req-2",
            model_key="deepseek-chat",
            input_tokens=1,
            output_tokens=2,
            total_tokens=3,
            cost_amount=Decimal("0.0001"),
            status="success",
            error_code=None,
            metadata={},
        )

        rows = json.loads(usage_ledger_to_json([item]))

        self.assertEqual("deepseek-chat", rows[0]["model_key"])
        self.assertEqual("0.0001", rows[0]["cost_amount"])

    def test_budget_ledger_csv_contains_budget_event_fields(self) -> None:
        budget_id = uuid4()
        item = BudgetLedgerItem(
            id=uuid4(),
            tenant_id=uuid4(),
            created_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
            budget_id=budget_id,
            reservation_id="res-1",
            request_id="req-3",
            event_type=BudgetEventType.DENY,
            scope_type=BudgetScopeType.DEPARTMENT,
            scope_id=uuid4(),
            user_id=None,
            department_id=uuid4(),
            cost_center_id=None,
            agent_id=None,
            channel_id=None,
            conversation_id=None,
            estimated_tokens=100,
            actual_tokens=0,
            estimated_cost_amount=Decimal("1.23"),
            actual_cost_amount=Decimal("0"),
            reason="department budget amount limit exceeded",
            metadata={"guard": "hard"},
        )

        body = budget_ledger_to_csv([item])

        self.assertIn(str(budget_id), body)
        self.assertIn("deny", body)
        self.assertIn("department", body)
        self.assertIn("department budget amount limit exceeded", body)

    def test_budget_ledger_json_is_structured(self) -> None:
        item = BudgetLedgerItem(
            id=uuid4(),
            tenant_id=uuid4(),
            created_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
            budget_id=None,
            reservation_id="res-2",
            request_id="req-4",
            event_type=BudgetEventType.SETTLE,
            scope_type=BudgetScopeType.TENANT,
            scope_id=None,
            user_id=None,
            department_id=None,
            cost_center_id=None,
            agent_id=None,
            channel_id=None,
            conversation_id=None,
            estimated_tokens=3,
            actual_tokens=2,
            estimated_cost_amount=Decimal("0.003"),
            actual_cost_amount=Decimal("0.002"),
            reason="budget_settled",
            metadata={},
        )

        rows = json.loads(budget_ledger_to_json([item]))

        self.assertEqual("settle", rows[0]["event_type"])
        self.assertEqual("tenant", rows[0]["scope_type"])
        self.assertEqual("0.002", rows[0]["actual_cost_amount"])


class BudgetLedgerExportAuditTests(unittest.IsolatedAsyncioTestCase):
    async def test_usage_ledger_export_records_audit_without_copying_report_rows(self) -> None:
        tenant_id = uuid4()
        actor_id = uuid4()
        department_id = uuid4()
        item = UsageLedgerItem(
            id=uuid4(),
            tenant_id=tenant_id,
            created_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
            deployment_id=None,
            user_id=actor_id,
            department_id=department_id,
            agent_id=None,
            channel_id=None,
            conversation_id=None,
            cost_center_id=None,
            request_id="llm-request-1",
            model_key="qwen-plus",
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
            cost_amount=Decimal("0.0123"),
            status="success",
            error_code=None,
            metadata={"provider_key": "qwen"},
        )
        session = FakeAuditSession()
        principal = Principal(tenant_id=tenant_id, user_id=actor_id, permissions={"budgets:read"})

        with patch(
            "app.services.budget_admin_service._export_usage_ledger_items",
            new=AsyncMock(return_value=[item]),
        ):
            body = await export_usage_ledger_json(
                session,
                principal,
                limit=100,
                start=None,
                end=None,
                user_id=actor_id,
                department_id=department_id,
                cost_center_id=None,
                agent_id=None,
                channel_id=None,
                model_key="qwen-plus",
                status_filter="success",
                request_id="export-request-1",
                ip_address="127.0.0.1",
                user_agent="AgentHive Test",
            )

        self.assertIn("qwen-plus", body)
        self.assertEqual(1, session.commits)
        event = session.added[0]
        self.assertIsInstance(event, AuditLog)
        self.assertEqual("budget.usage_ledger.export", event.action)
        self.assertEqual("export-request-1", event.request_id)
        self.assertEqual("json", event.details["format"])
        self.assertEqual(1, event.details["item_count"])
        self.assertEqual(100, event.details["limit"])
        self.assertEqual(str(actor_id), event.details["filters"]["user_id"])
        self.assertEqual(str(department_id), event.details["filters"]["department_id"])
        self.assertEqual("qwen-plus", event.details["filters"]["model_key"])
        self.assertNotIn("llm-request-1", json.dumps(event.details))
        self.assertNotIn("provider_key", json.dumps(event.details))

    async def test_budget_ledger_export_records_audit_with_budget_filters(self) -> None:
        tenant_id = uuid4()
        actor_id = uuid4()
        budget_id = uuid4()
        scope_id = uuid4()
        item = BudgetLedgerItem(
            id=uuid4(),
            tenant_id=tenant_id,
            created_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
            budget_id=budget_id,
            reservation_id="reservation-1",
            request_id="budget-request-1",
            event_type=BudgetEventType.DENY,
            scope_type=BudgetScopeType.DEPARTMENT,
            scope_id=scope_id,
            user_id=actor_id,
            department_id=scope_id,
            cost_center_id=None,
            agent_id=None,
            channel_id=None,
            conversation_id=None,
            estimated_tokens=100,
            actual_tokens=0,
            estimated_cost_amount=Decimal("1.23"),
            actual_cost_amount=Decimal("0"),
            reason="department budget amount limit exceeded",
            metadata={"guard": "hard"},
        )
        session = FakeAuditSession()
        principal = Principal(tenant_id=tenant_id, user_id=actor_id, permissions={"budgets:read"})

        with patch(
            "app.services.budget_admin_service._export_budget_ledger_items",
            new=AsyncMock(return_value=[item]),
        ):
            body = await export_budget_ledger_json(
                session,
                principal,
                limit=50,
                start=None,
                end=None,
                budget_id=budget_id,
                reservation_id=None,
                request_id="budget-request-1",
                event_type=BudgetEventType.DENY,
                scope_type=BudgetScopeType.DEPARTMENT,
                scope_id=scope_id,
                user_id=actor_id,
                department_id=scope_id,
                cost_center_id=None,
                agent_id=None,
                channel_id=None,
                request_id_for_audit="export-request-2",
                ip_address="127.0.0.1",
                user_agent="AgentHive Test",
            )

        self.assertIn("reservation-1", body)
        event = session.added[0]
        self.assertEqual("budget.budget_ledger.export", event.action)
        self.assertEqual("export-request-2", event.request_id)
        self.assertEqual("json", event.details["format"])
        self.assertEqual(1, event.details["item_count"])
        self.assertEqual(str(budget_id), event.details["filters"]["budget_id"])
        self.assertEqual("budget-request-1", event.details["filters"]["request_id"])
        self.assertEqual("deny", event.details["filters"]["event_type"])
        self.assertEqual("department", event.details["filters"]["scope_type"])
        self.assertNotIn("department budget amount limit exceeded", json.dumps(event.details))


class BudgetLedgerExportApiPermissionTests(unittest.TestCase):
    def test_usage_ledger_export_requires_budget_export_permission(self) -> None:
        client = _build_budget_client(FakePrincipalSession())

        response = client.get(
            "/api/v1/budgets/usage-ledger/export?format=json",
            headers={"Authorization": f"Bearer {_token(Permission.BUDGETS_READ)}"},
        )

        self.assertEqual(403, response.status_code)

    def test_usage_ledger_export_accepts_budget_export_permission(self) -> None:
        client = _build_budget_client(FakePrincipalSession())

        with patch("app.api.v1.budgets.export_usage_ledger_json", new=AsyncMock(return_value="[]")):
            response = client.get(
                "/api/v1/budgets/usage-ledger/export?format=json",
                headers={"Authorization": f"Bearer {_token(Permission.BUDGETS_EXPORT)}"},
            )

        self.assertEqual(200, response.status_code)
        self.assertIn("application/json", response.headers["content-type"])


class FakeAuditSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, row: object) -> None:
        self.added.append(row)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakePrincipalSession:
    user_id = UUID("00000000-0000-4000-8000-000000000501")
    tenant_id = UUID("00000000-0000-4000-8000-000000000601")

    async def get(self, model, row_id):
        if model is User and row_id == self.user_id:
            return User(
                id=row_id,
                tenant_id=self.tenant_id,
                email="budget-exporter@example.com",
                hashed_password="bcrypt-sha256$placeholder",
                is_active=True,
            )
        if model is Tenant and row_id == self.tenant_id:
            return Tenant(id=row_id, name="Budget Buyer", slug="budget-buyer", is_active=True)
        return None


def _build_budget_client(session: FakePrincipalSession) -> TestClient:
    app = FastAPI()
    app.include_router(budgets_router, prefix="/api/v1")

    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app)


def _token(*permissions: Permission) -> str:
    return create_access_token(
        subject=FakePrincipalSession.user_id,
        tenant_id=FakePrincipalSession.tenant_id,
        permissions=[permission.value for permission in permissions],
    )


if __name__ == "__main__":
    unittest.main()
