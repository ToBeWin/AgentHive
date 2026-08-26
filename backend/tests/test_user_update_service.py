import unittest
from uuid import uuid4

from fastapi import HTTPException

from app.api.deps import Principal
from app.core.security import Permission
from app.models.audit_log import AuditLog
from app.models.role import Role, UserRole
from app.models.user import User, UserDepartment
from app.schemas.org_admin import UserDepartmentBindingRequest, UserUpdateRequest
from app.services.org_admin_service import list_users, update_user


class FakeUserUpdateSession:
    def __init__(self, user: User | None, results: list[object]) -> None:
        self.user = user
        self.results = results
        self.added: list[object] = []
        self.commits = 0
        self.refreshes = 0
        self.rollbacks = 0
        self.statements: list[object] = []

    async def get(self, _model: object, _row_id: object) -> User | None:
        return self.user

    async def execute(self, statement: object) -> object:
        self.statements.append(statement)
        if self.results:
            return self.results.pop(0)
        return FakeResult()

    def add(self, value: object) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, _value: object) -> None:
        self.refreshes += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakeResult:
    def __init__(self, *, scalar: object | None = None, rows: list[object] | None = None) -> None:
        self.scalar = scalar
        self.rows = rows or []

    def scalar_one_or_none(self) -> object | None:
        return self.scalar

    def scalar_one(self) -> object:
        return self.scalar

    def scalars(self) -> "FakeResult":
        return self

    def all(self) -> list[object]:
        return self.rows


def make_principal(
    *, user_id=None, tenant_id=None, permissions: set[str] | None = None
) -> Principal:
    return Principal(
        tenant_id=tenant_id or uuid4(),
        user_id=user_id or uuid4(),
        permissions=permissions or {Permission.USERS_WRITE.value},
    )


def make_user(*, tenant_id, user_id=None, is_tenant_admin: bool = False) -> User:
    user = User(
        tenant_id=tenant_id,
        email="member@example.com",
        hashed_password="bcrypt-sha256$placeholder",
        full_name="Member",
        is_tenant_admin=is_tenant_admin,
    )
    if user_id is not None:
        user.id = user_id
    return user


def make_role(*, tenant_id, name: str) -> Role:
    return Role(
        tenant_id=tenant_id,
        name=name,
        description=None,
        permissions=[Permission.AGENTS_READ.value],
        is_system=False,
    )


class UserUpdateServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_update_user_rejects_self_tenant_admin_removal(self) -> None:
        principal = make_principal()
        session = FakeUserUpdateSession(None, [])

        with self.assertRaises(HTTPException) as raised:
            await update_user(
                session,
                principal,
                principal.user_id,
                UserUpdateRequest(is_tenant_admin=False),
            )

        self.assertEqual(409, raised.exception.status_code)
        self.assertEqual(0, session.commits)

    async def test_update_user_rejects_duplicate_email(self) -> None:
        principal = make_principal()
        user = make_user(tenant_id=principal.tenant_id)
        session = FakeUserUpdateSession(user, [FakeResult(scalar=uuid4())])

        with self.assertRaises(HTTPException) as raised:
            await update_user(
                session,
                principal,
                user.id,
                UserUpdateRequest(email="taken@example.com"),
            )

        self.assertEqual(409, raised.exception.status_code)
        self.assertEqual(1, session.rollbacks)
        self.assertEqual(0, session.commits)

    async def test_update_user_replaces_bindings_roles_and_records_audit(self) -> None:
        principal = make_principal()
        user = make_user(tenant_id=principal.tenant_id)
        role = make_role(tenant_id=principal.tenant_id, name="Agent Manager")
        department_id = uuid4()
        cost_center_id = uuid4()
        session = FakeUserUpdateSession(
            user,
            [
                FakeResult(scalar=None),
                FakeResult(rows=[role]),
                FakeResult(rows=[department_id]),
                FakeResult(rows=[cost_center_id]),
                FakeResult(),
                FakeResult(),
                FakeResult(rows=[role]),
                FakeResult(rows=[]),
            ],
        )

        response = await update_user(
            session,
            principal,
            user.id,
            UserUpdateRequest(
                email="member.updated@example.com",
                full_name="Updated Member",
                is_tenant_admin=True,
                department_bindings=[
                    UserDepartmentBindingRequest(
                        department_id=department_id,
                        cost_center_id=cost_center_id,
                        is_primary=True,
                        position_title="Support Lead",
                    )
                ],
                role_ids=[role.id],
            ),
            request_id="request-user-update",
        )

        self.assertEqual("member.updated@example.com", response.email)
        self.assertEqual("Updated Member", response.full_name)
        self.assertTrue(response.is_tenant_admin)
        self.assertEqual(1, session.commits)
        self.assertEqual(1, session.refreshes)
        self.assertTrue(
            any(
                "DELETE FROM user_departments" in str(statement) for statement in session.statements
            )
        )
        self.assertTrue(
            any("DELETE FROM user_roles" in str(statement) for statement in session.statements)
        )
        self.assertEqual(1, len([row for row in session.added if isinstance(row, UserDepartment)]))
        self.assertEqual(1, len([row for row in session.added if isinstance(row, UserRole)]))
        audit_events = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual(1, len(audit_events))
        self.assertEqual("org.user.update", audit_events[0].action)
        self.assertIn("department_bindings", audit_events[0].details["changed_fields"])
        self.assertIn("role_ids", audit_events[0].details["changed_fields"])

    async def test_list_users_with_write_permission_reads_tenant_scope(self) -> None:
        principal = make_principal(permissions={Permission.USERS_WRITE.value})
        visible_user = make_user(tenant_id=principal.tenant_id)
        session = FakeUserUpdateSession(
            visible_user,
            [
                FakeResult(scalar=1),
                FakeResult(rows=[visible_user]),
                FakeResult(rows=[]),
                FakeResult(rows=[]),
            ],
        )

        response = await list_users(session, principal)

        self.assertEqual(1, response.total)
        self.assertEqual(visible_user.id, response.users[0].id)
        self.assertEqual(4, len(session.statements))
        self.assertNotIn("JOIN user_departments", str(session.statements[0]))
        self.assertNotIn("JOIN user_departments", str(session.statements[1]))

    async def test_list_users_with_read_permission_is_scoped_to_departments(self) -> None:
        department_id = uuid4()
        principal = make_principal(
            permissions={Permission.USERS_READ.value},
            user_id=uuid4(),
        )
        visible_user = make_user(tenant_id=principal.tenant_id)
        session = FakeUserUpdateSession(
            visible_user,
            [
                FakeResult(rows=[department_id]),
                FakeResult(scalar=1),
                FakeResult(rows=[visible_user]),
                FakeResult(rows=[]),
                FakeResult(rows=[]),
            ],
        )

        response = await list_users(session, principal)

        self.assertEqual(1, response.total)
        self.assertEqual(visible_user.id, response.users[0].id)
        self.assertEqual(5, len(session.statements))
        membership_query = str(session.statements[0])
        scoped_user_query = str(session.statements[2])
        self.assertIn("JOIN departments", membership_query)
        self.assertIn("departments.tenant_id", membership_query)
        self.assertIn("JOIN user_departments", scoped_user_query)
        self.assertIn("user_departments.department_id", scoped_user_query)
        self.assertIn("users.id", scoped_user_query)

    async def test_list_users_without_department_scope_only_returns_self(self) -> None:
        principal = make_principal(
            permissions={Permission.USERS_READ.value},
            user_id=uuid4(),
        )
        self_user = make_user(tenant_id=principal.tenant_id, user_id=principal.user_id)
        session = FakeUserUpdateSession(
            self_user,
            [
                FakeResult(rows=[]),
                FakeResult(scalar=1),
                FakeResult(rows=[self_user]),
                FakeResult(rows=[]),
                FakeResult(rows=[]),
            ],
        )

        response = await list_users(session, principal)

        self.assertEqual(1, response.total)
        self.assertEqual(principal.user_id, response.users[0].id)
        self.assertEqual(5, len(session.statements))
        self.assertIn("users.id", str(session.statements[2]))


if __name__ == "__main__":
    unittest.main()
