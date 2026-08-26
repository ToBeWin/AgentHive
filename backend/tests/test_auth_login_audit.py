import unittest

from fastapi import HTTPException

from app.core.config import settings
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import LoginRequest
from app.services.auth_service import (
    _login_attempt_keys,
    login,
    login_failure_limiter,
    logout,
    refresh_session,
)


class FakeFirstResult:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeAuthSession:
    def __init__(self, *, login_row=None, tenant=None, scalar_user=None, scalar_mode: bool = False):
        self.login_row = login_row
        self.tenant = tenant
        self.scalar_user = scalar_user
        self.scalar_mode = scalar_mode
        self.added = []
        self.commits = 0
        self.execute_count = 0
        self.scalar_count = 0

    async def execute(self, _statement):
        self.execute_count += 1
        if self.scalar_mode:
            return FakeScalarResult(self.scalar_user)
        return FakeFirstResult(self.login_row)

    async def scalar(self, _statement):
        self.scalar_count += 1
        return self.tenant

    def add(self, row):
        self.added.append(row)

    async def commit(self):
        self.commits += 1


def make_login_request(*, password: str = "wrong-password") -> LoginRequest:
    return LoginRequest(
        tenant_slug="demo",
        email="Admin@Example.com",
        password=password,
    )


def make_tenant() -> Tenant:
    return Tenant(name="Demo", slug="demo", is_active=True)


def make_user(tenant_id, *, active: bool = True) -> User:
    return User(
        tenant_id=tenant_id,
        email="admin@example.com",
        hashed_password=hash_password("CorrectPassword123!"),
        is_active=active,
        is_tenant_admin=True,
    )


class AuthLoginAuditTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._login_failure_limit = settings.login_failure_limit
        self._login_failure_window_seconds = settings.login_failure_window_seconds
        login_failure_limiter.reset_all()

    def tearDown(self) -> None:
        settings.login_failure_limit = self._login_failure_limit
        settings.login_failure_window_seconds = self._login_failure_window_seconds
        login_failure_limiter.reset_all()

    async def test_wrong_password_records_failed_login_audit_without_success_login(self):
        tenant = make_tenant()
        user = make_user(tenant.id)
        session = FakeAuthSession(login_row=(user, tenant))

        with self.assertRaises(HTTPException) as raised:
            await login(
                session,
                make_login_request(),
                request_id="req-login",
                ip_address="203.0.113.10",
                user_agent="test-agent",
            )

        self.assertEqual(401, raised.exception.status_code)
        self.assertEqual(1, session.commits)
        audit_events = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual(1, len(audit_events))
        event = audit_events[0]
        self.assertEqual("auth.login_failed", event.action)
        self.assertEqual("failure", event.status)
        self.assertEqual(user.id, event.actor_id)
        self.assertEqual(user.id, event.resource_id)
        self.assertEqual("invalid_password", event.details["reason"])
        self.assertEqual("admin@example.com", event.details["email"])
        self.assertIsNone(user.last_login_at)

    async def test_inactive_user_records_failed_login_audit(self):
        tenant = make_tenant()
        user = make_user(tenant.id, active=False)
        session = FakeAuthSession(login_row=(user, tenant))

        with self.assertRaises(HTTPException) as raised:
            await login(session, make_login_request(password="CorrectPassword123!"))

        self.assertEqual(401, raised.exception.status_code)
        audit_events = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual(1, len(audit_events))
        self.assertEqual("inactive_user", audit_events[0].details["reason"])

    async def test_unknown_user_in_known_tenant_records_anonymous_failure(self):
        tenant = make_tenant()
        session = FakeAuthSession(login_row=None, tenant=tenant)

        with self.assertRaises(HTTPException) as raised:
            await login(session, make_login_request(), request_id="req-unknown")

        self.assertEqual(401, raised.exception.status_code)
        self.assertEqual(1, session.scalar_count)
        self.assertEqual(1, session.commits)
        audit_events = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual(1, len(audit_events))
        event = audit_events[0]
        self.assertEqual("auth.login_failed", event.action)
        self.assertEqual("anonymous", event.actor_type)
        self.assertIsNone(event.actor_id)
        self.assertEqual("invalid_credentials", event.details["reason"])
        self.assertEqual("admin@example.com", event.details["email"])

    async def test_unknown_tenant_keeps_response_generic_without_tenant_audit(self):
        session = FakeAuthSession(login_row=None, tenant=None)

        with self.assertRaises(HTTPException) as raised:
            await login(session, make_login_request())

        self.assertEqual(401, raised.exception.status_code)
        self.assertEqual(0, session.commits)
        self.assertEqual([], session.added)

    async def test_repeated_failed_login_attempts_are_throttled_before_password_check(self):
        settings.login_failure_limit = 2
        settings.login_failure_window_seconds = 900
        tenant = make_tenant()
        user = make_user(tenant.id)
        session = FakeAuthSession(login_row=(user, tenant))

        for _ in range(2):
            with self.assertRaises(HTTPException) as raised:
                await login(session, make_login_request(), ip_address="203.0.113.20")
            self.assertEqual(401, raised.exception.status_code)

        with self.assertRaises(HTTPException) as raised:
            await login(session, make_login_request(), ip_address="203.0.113.20")

        self.assertEqual(429, raised.exception.status_code)
        self.assertEqual("900", raised.exception.headers["Retry-After"])
        self.assertEqual(2, session.execute_count)

    async def test_successful_login_resets_previous_failure_counter(self):
        settings.login_failure_limit = 2
        settings.login_failure_window_seconds = 900
        tenant = make_tenant()
        user = make_user(tenant.id)
        session = FakeAuthSession(login_row=(user, tenant))
        attempt_keys = _login_attempt_keys(
            tenant_slug="demo",
            email="admin@example.com",
            ip_address="203.0.113.30",
        )

        with self.assertRaises(HTTPException):
            await login(session, make_login_request(), ip_address="203.0.113.30")

        self.assertTrue(
            login_failure_limiter.is_locked(
                attempt_keys,
                limit=1,
                window_seconds=settings.login_failure_window_seconds,
            )
        )

        response = await login(
            session,
            make_login_request(password="CorrectPassword123!"),
            ip_address="203.0.113.30",
        )

        self.assertEqual("admin@example.com", response.user.email)
        self.assertFalse(
            login_failure_limiter.is_locked(
                attempt_keys,
                limit=1,
                window_seconds=settings.login_failure_window_seconds,
            )
        )

    async def test_refresh_session_reloads_user_and_records_audit(self):
        tenant = make_tenant()
        user = make_user(tenant.id)
        session = FakeAuthSession(scalar_user=user, scalar_mode=True)

        response = await refresh_session(
            session,
            tenant_id=tenant.id,
            user_id=user.id,
            request_id="req-refresh",
            ip_address="203.0.113.40",
            user_agent="refresh-test",
        )

        self.assertEqual(user.email, response.user.email)
        self.assertEqual(1, session.commits)
        audit_events = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual(1, len(audit_events))
        self.assertEqual("auth.refresh", audit_events[0].action)
        self.assertEqual(user.id, audit_events[0].actor_id)

    async def test_refresh_session_rejects_inactive_or_missing_user(self):
        tenant = make_tenant()
        session = FakeAuthSession(scalar_user=None, scalar_mode=True)

        with self.assertRaises(HTTPException) as raised:
            await refresh_session(session, tenant_id=tenant.id, user_id=make_user(tenant.id).id)

        self.assertEqual(401, raised.exception.status_code)
        self.assertEqual(0, session.commits)
        self.assertEqual([], session.added)

    async def test_logout_records_audit_event(self):
        tenant = make_tenant()
        user = make_user(tenant.id)
        session = FakeAuthSession(scalar_user=user, scalar_mode=True)

        response = await logout(
            session,
            tenant_id=tenant.id,
            user_id=user.id,
            request_id="req-logout",
        )

        self.assertEqual("Logged out.", response.message)
        self.assertEqual(1, session.commits)
        self.assertEqual(1, user.auth_version)
        audit_events = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual(1, len(audit_events))
        self.assertEqual("auth.logout", audit_events[0].action)
        self.assertEqual(user.id, audit_events[0].actor_id)


if __name__ == "__main__":
    unittest.main()
