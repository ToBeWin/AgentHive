import unittest
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.audit import export_router, router
from app.core.database import get_session
from app.core.security import Permission, create_access_token
from app.models.audit_log import AuditLog
from app.models.tenant import Tenant
from app.models.user import User
from app.services.audit_redaction import REDACTED


class _FakeScalarResult:
    def __init__(self, rows: list[AuditLog]):
        self._rows = rows

    def all(self) -> list[AuditLog]:
        return self._rows


class _FakeExecuteResult:
    def __init__(self, rows: list[AuditLog]):
        self._rows = rows

    def scalars(self) -> _FakeScalarResult:
        return _FakeScalarResult(self._rows)


class _FakeAuditSession:
    def __init__(self, rows: list[AuditLog]):
        self.rows = rows
        self.added: list[object] = []
        self.commits = 0
        self.rollback_called = False
        self.user_id = UUID("00000000-0000-4000-8000-000000000301")
        self.tenant_id = UUID("00000000-0000-4000-8000-000000000401")

    async def execute(self, _statement) -> _FakeExecuteResult:
        return _FakeExecuteResult(self.rows)

    async def get(self, model, row_id):
        if model is User and row_id == self.user_id:
            return User(
                id=self.user_id,
                tenant_id=self.tenant_id,
                email="auditor@example.com",
                hashed_password="bcrypt-sha256$placeholder",
                is_active=True,
            )
        if model is Tenant and row_id == self.tenant_id:
            return Tenant(id=self.tenant_id, name="Demo", slug="demo", is_active=True)
        return None

    def add(self, row: object) -> None:
        self.added.append(row)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollback_called = True


def _build_client(session: _FakeAuditSession) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.include_router(export_router, prefix="/api/v1")

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


class AuditExportApiTests(unittest.TestCase):
    def test_json_export_supports_canonical_audit_logs_path(self) -> None:
        row = AuditLog(
            id=uuid4(),
            tenant_id=UUID("00000000-0000-4000-8000-000000000401"),
            request_id="req-canonical-json",
            actor_id=uuid4(),
            actor_type="user",
            action="chat.message.send",
            resource_type="conversation_message",
            resource_id=uuid4(),
            status="success",
            ip_address="127.0.0.1",
            user_agent="AgentHive API Test",
            details={"runtime": {"selected_route": {"routing_key": "deepseek-v4-flash"}}},
            created_at=datetime(2026, 6, 12, tzinfo=timezone.utc),
        )
        session = _FakeAuditSession([row])
        client = _build_client(session)

        response = client.get(
            "/api/v1/audit/logs/export?format=json",
            headers={"Authorization": f"Bearer {_token(Permission.AUDIT_EXPORT)}"},
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("agenthive.audit.export.v1", payload["format"])
        self.assertEqual(
            "deepseek-v4-flash",
            payload["items"][0]["details"]["runtime"]["selected_route"]["routing_key"],
        )

    def test_json_export_requires_export_permission_and_redacts_details(self) -> None:
        row = AuditLog(
            id=uuid4(),
            tenant_id=UUID("00000000-0000-4000-8000-000000000401"),
            request_id="req-json",
            actor_id=uuid4(),
            actor_type="user",
            action="models.credential.upsert",
            resource_type="llm_credential",
            resource_id=uuid4(),
            status="success",
            ip_address="127.0.0.1",
            user_agent="AgentHive API Test",
            details={"api_key": "sk-live-secret", "total_tokens": 123},
            created_at=datetime(2026, 6, 12, tzinfo=timezone.utc),
        )
        session = _FakeAuditSession([row])
        client = _build_client(session)

        response = client.get(
            "/api/v1/audit-logs/export?format=json",
            headers={"Authorization": f"Bearer {_token(Permission.AUDIT_EXPORT)}"},
        )

        self.assertEqual(200, response.status_code)
        self.assertIn("application/json", response.headers["content-type"])
        self.assertEqual(
            'attachment; filename="agenthive-audit-logs.json"',
            response.headers["content-disposition"],
        )
        payload = response.json()
        self.assertEqual("agenthive.audit.export.v1", payload["format"])
        self.assertEqual(REDACTED, payload["items"][0]["details"]["api_key"])
        self.assertEqual(123, payload["items"][0]["details"]["total_tokens"])
        self.assertNotIn("sk-live-secret", response.text)
        self.assertEqual(1, session.commits)
        audit_events = [item for item in session.added if isinstance(item, AuditLog)]
        self.assertEqual(1, len(audit_events))
        event = audit_events[0]
        self.assertEqual("audit.logs.export", event.action)
        self.assertEqual("audit_log", event.resource_type)
        self.assertEqual("json", event.details["format"])
        self.assertEqual(1, event.details["item_count"])
        self.assertNotIn("sk-live-secret", str(event.details))

    def test_export_rejects_read_only_audit_permission(self) -> None:
        client = _build_client(_FakeAuditSession([]))

        response = client.get(
            "/api/v1/audit-logs/export?format=json",
            headers={"Authorization": f"Bearer {_token(Permission.AUDIT_READ)}"},
        )

        self.assertEqual(403, response.status_code)


if __name__ == "__main__":
    unittest.main()
