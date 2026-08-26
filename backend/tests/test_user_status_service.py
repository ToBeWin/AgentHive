from uuid import uuid4
import unittest

from fastapi import HTTPException

from app.api.deps import Principal
from app.core.security import verify_password
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.org_admin import UserPasswordResetRequest, UserStatusUpdateRequest
from app.services.org_admin_service import reset_user_password, update_user_status


class FakeUserStatusSession:
    def __init__(self, user: User | None) -> None:
        self.user = user
        self.added: list[object] = []
        self.commits = 0
        self.refreshes = 0
        self.rollbacks = 0

    async def get(self, _model: object, _row_id: object) -> User | None:
        return self.user

    def add(self, value: object) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, _value: object) -> None:
        self.refreshes += 1

    async def execute(self, _statement: object) -> object:
        return _EmptyResult()

    async def rollback(self) -> None:
        self.rollbacks += 1


class _EmptyResult:
    def scalars(self) -> "_EmptyResult":
        return self

    def all(self) -> list[object]:
        return []


def make_principal(*, tenant_id=None, user_id=None) -> Principal:
    return Principal(
        tenant_id=tenant_id or uuid4(),
        user_id=user_id or uuid4(),
        permissions={"users:write"},
    )


def make_user(*, tenant_id, is_active: bool = True) -> User:
    return User(
        tenant_id=tenant_id,
        email="member@example.com",
        hashed_password="bcrypt-sha256$placeholder",
        full_name="Member",
        is_active=is_active,
    )


class UserStatusServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_update_user_status_deactivates_user_and_records_audit(self) -> None:
        principal = make_principal()
        user = make_user(tenant_id=principal.tenant_id)
        session = FakeUserStatusSession(user)

        response = await update_user_status(
            session,
            principal,
            user.id,
            UserStatusUpdateRequest(is_active=False),
            request_id="request-1",
        )

        self.assertFalse(response.is_active)
        self.assertFalse(user.is_active)
        self.assertEqual(1, session.commits)
        self.assertEqual(1, session.refreshes)
        audit_events = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual(1, len(audit_events))
        self.assertEqual("org.user.status.update", audit_events[0].action)
        self.assertEqual(False, audit_events[0].details["is_active"])

    async def test_update_user_status_rejects_self_deactivation(self) -> None:
        principal = make_principal()
        session = FakeUserStatusSession(None)

        with self.assertRaises(HTTPException) as raised:
            await update_user_status(
                session,
                principal,
                principal.user_id,
                UserStatusUpdateRequest(is_active=False),
            )

        self.assertEqual(409, raised.exception.status_code)
        self.assertEqual(0, session.commits)

    async def test_reset_user_password_hashes_new_password_and_records_audit(self) -> None:
        principal = make_principal()
        user = make_user(tenant_id=principal.tenant_id)
        session = FakeUserStatusSession(user)
        new_password = "NewPassword123!"

        response = await reset_user_password(
            session,
            principal,
            user.id,
            UserPasswordResetRequest(new_password=new_password),
            request_id="request-2",
        )

        self.assertEqual(user.id, response.id)
        self.assertTrue(verify_password(new_password, user.hashed_password))
        self.assertNotEqual(new_password, user.hashed_password)
        self.assertEqual(1, session.commits)
        self.assertEqual(1, session.refreshes)
        audit_events = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual(1, len(audit_events))
        self.assertEqual("org.user.password.reset", audit_events[0].action)
        self.assertEqual(user.email, audit_events[0].details["email"])
        self.assertNotIn(new_password, str(audit_events[0].details))


if __name__ == "__main__":
    unittest.main()
