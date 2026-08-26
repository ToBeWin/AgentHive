import unittest
from uuid import UUID
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.router import api_router
from app.core.database import get_session
from app.core.security import Permission, create_access_token
from app.models.audit_log import AuditLog
from app.models.tenant import Tenant
from app.models.user import User


class _FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0
        self.rollback_called = False
        self.user_id = UUID("00000000-0000-4000-8000-000000000301")
        self.tenant_id = UUID("00000000-0000-4000-8000-000000000401")

    async def get(self, model, row_id):
        if model is User and row_id == self.user_id:
            return User(
                id=self.user_id,
                tenant_id=self.tenant_id,
                email="ops@example.com",
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


def _client(session: _FakeSession) -> TestClient:
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")

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


class SystemSupportBundleApiTests(unittest.TestCase):
    def test_support_bundle_requires_permission_and_returns_attachment(self) -> None:
        session = _FakeSession()
        client = _client(session)

        with patch(
            "app.api.v1.router.build_support_bundle",
            new=AsyncMock(return_value=(b"fake-zip", "agenthive-support-bundle-test.zip")),
        ):
            response = client.get(
                "/api/v1/system/support-bundle",
                headers={"Authorization": f"Bearer {_token(Permission.SYSTEM_DIAGNOSTICS)}"},
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual(b"fake-zip", response.content)
        self.assertEqual("application/zip", response.headers["content-type"])
        self.assertEqual(
            'attachment; filename="agenthive-support-bundle-test.zip"',
            response.headers["content-disposition"],
        )
        self.assertEqual(1, session.commits)
        audit_events = [item for item in session.added if isinstance(item, AuditLog)]
        self.assertEqual(1, len(audit_events))
        self.assertEqual("system.support_bundle.export", audit_events[0].action)
        self.assertEqual("zip", audit_events[0].details["format"])

    def test_support_bundle_rejects_missing_diagnostics_permission(self) -> None:
        client = _client(_FakeSession())

        response = client.get(
            "/api/v1/system/support-bundle",
            headers={"Authorization": f"Bearer {_token(Permission.AUDIT_READ)}"},
        )

        self.assertEqual(403, response.status_code)


if __name__ == "__main__":
    unittest.main()
