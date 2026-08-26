import unittest
from uuid import uuid4

from fastapi import HTTPException

from app.api.deps import Principal
from app.core.security import Permission
from app.models.audit_log import AuditLog
from app.models.role import Role
from app.schemas.org_admin import RoleUpdateRequest
from app.services.org_admin_service import delete_role, update_role


class FakeRoleSession:
    def __init__(
        self,
        role: Role | None,
        *,
        scalar_results: list[object | None] | None = None,
    ) -> None:
        self.role = role
        self.scalar_results = scalar_results or []
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.commits = 0
        self.refreshes = 0
        self.rollbacks = 0
        self.statements: list[object] = []

    async def get(self, _model: object, _row_id: object) -> Role | None:
        return self.role

    async def execute(self, statement: object) -> object:
        self.statements.append(statement)
        result = self.scalar_results.pop(0) if self.scalar_results else None
        return FakeScalarResult(result)

    def add(self, value: object) -> None:
        self.added.append(value)

    async def delete(self, value: object) -> None:
        self.deleted.append(value)

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, _value: object) -> None:
        self.refreshes += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakeScalarResult:
    def __init__(self, value: object | None) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object | None:
        return self.value


def make_principal() -> Principal:
    return Principal(
        tenant_id=uuid4(),
        user_id=uuid4(),
        permissions={Permission.TENANT_ADMIN.value},
    )


def make_role(
    *,
    tenant_id,
    is_system: bool = False,
    name: str = "Agent Operator",
) -> Role:
    return Role(
        tenant_id=tenant_id,
        name=name,
        description="Can manage approved Agent operations.",
        permissions=[Permission.AGENTS_READ.value],
        is_system=is_system,
    )


class RoleManagementServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_update_role_changes_permissions_and_records_audit(self) -> None:
        principal = make_principal()
        role = make_role(tenant_id=principal.tenant_id)
        session = FakeRoleSession(role, scalar_results=[None])

        response = await update_role(
            session,
            principal,
            role.id,
            RoleUpdateRequest(
                name="Support Operator",
                permissions=[Permission.AGENTS_READ, Permission.KNOWLEDGE_READ],
            ),
            request_id="request-role-update",
        )

        self.assertEqual("Support Operator", response.name)
        self.assertEqual(
            [Permission.AGENTS_READ.value, Permission.KNOWLEDGE_READ.value],
            response.permissions,
        )
        self.assertEqual(1, session.commits)
        self.assertEqual(1, session.refreshes)
        audit_events = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual(1, len(audit_events))
        self.assertEqual("org.role.update", audit_events[0].action)
        self.assertEqual(["name", "permissions"], audit_events[0].details["changed_fields"])
        self.assertEqual("Agent Operator", audit_events[0].details["previous"]["name"])

    async def test_update_role_rejects_system_role(self) -> None:
        principal = make_principal()
        role = make_role(tenant_id=principal.tenant_id, is_system=True)
        session = FakeRoleSession(role)

        with self.assertRaises(HTTPException) as raised:
            await update_role(
                session,
                principal,
                role.id,
                RoleUpdateRequest(name="Changed"),
            )

        self.assertEqual(409, raised.exception.status_code)
        self.assertEqual(0, session.commits)
        self.assertEqual(1, session.rollbacks)

    async def test_delete_role_rejects_assigned_role(self) -> None:
        principal = make_principal()
        role = make_role(tenant_id=principal.tenant_id)
        session = FakeRoleSession(role, scalar_results=[uuid4()])

        with self.assertRaises(HTTPException) as raised:
            await delete_role(session, principal, role.id)

        self.assertEqual(409, raised.exception.status_code)
        self.assertEqual(0, session.commits)
        self.assertEqual([], session.deleted)
        self.assertEqual(1, session.rollbacks)

    async def test_delete_role_removes_custom_role_and_records_audit(self) -> None:
        principal = make_principal()
        role = make_role(tenant_id=principal.tenant_id)
        session = FakeRoleSession(role, scalar_results=[None])

        response = await delete_role(
            session,
            principal,
            role.id,
            request_id="request-role-delete",
        )

        self.assertTrue(response.deleted)
        self.assertEqual(role.id, response.id)
        self.assertEqual([role], session.deleted)
        self.assertEqual(1, session.commits)
        audit_events = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual(1, len(audit_events))
        self.assertEqual("org.role.delete", audit_events[0].action)
        self.assertEqual(role.name, audit_events[0].details["name"])


if __name__ == "__main__":
    unittest.main()
