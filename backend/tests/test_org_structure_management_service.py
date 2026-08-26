import unittest
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException

from app.api.deps import Principal
from app.core.security import Permission
from app.models.audit_log import AuditLog
from app.models.org import Department
from app.models.tenant import CostCenter
from app.schemas.org_admin import CostCenterUpdateRequest, DepartmentUpdateRequest
from app.services.org_admin_service import (
    delete_cost_center,
    delete_department,
    update_cost_center,
    update_department,
)


class FakeOrgSession:
    def __init__(
        self, *, get_result: object | None = None, execute_results: list[object] | None = None
    ) -> None:
        self.get_result = get_result
        self.execute_results = execute_results or []
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.commits = 0
        self.refreshes = 0
        self.rollbacks = 0
        self.statements: list[object] = []

    async def get(self, _model: object, _row_id: object) -> object | None:
        return self.get_result

    async def execute(self, statement: object) -> object:
        self.statements.append(statement)
        if self.execute_results:
            return self.execute_results.pop(0)
        return FakeResult()

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


class FakeResult:
    def __init__(self, value: object | None = None) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object | None:
        return self.value


def make_principal() -> Principal:
    return Principal(
        tenant_id=uuid4(),
        user_id=uuid4(),
        permissions={Permission.DEPARTMENTS_WRITE.value},
    )


def make_department(*, tenant_id) -> Department:
    return Department(
        tenant_id=tenant_id,
        name="Customer Success",
        description="Support team",
        sort_order=10,
    )


def make_cost_center(*, tenant_id) -> CostCenter:
    return CostCenter(
        tenant_id=tenant_id,
        code="CS",
        name="Customer Success",
        description="Support cost center",
        monthly_budget_usd=Decimal("1000"),
        is_active=True,
    )


class OrgStructureManagementServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_update_department_records_audit(self) -> None:
        principal = make_principal()
        department = make_department(tenant_id=principal.tenant_id)
        session = FakeOrgSession(execute_results=[FakeResult(department)])

        response = await update_department(
            session,
            principal,
            department.id,
            DepartmentUpdateRequest(name="Customer Operations", sort_order=20),
        )

        self.assertEqual("Customer Operations", response.name)
        self.assertEqual(20, response.sort_order)
        self.assertEqual(1, session.commits)
        audit_events = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual(1, len(audit_events))
        self.assertEqual("org.department.update", audit_events[0].action)
        self.assertEqual(["name", "sort_order"], audit_events[0].details["changed_fields"])

    async def test_delete_department_rejects_referenced_department(self) -> None:
        principal = make_principal()
        department = make_department(tenant_id=principal.tenant_id)
        session = FakeOrgSession(execute_results=[FakeResult(department), FakeResult(uuid4())])

        with self.assertRaises(HTTPException) as raised:
            await delete_department(session, principal, department.id)

        self.assertEqual(409, raised.exception.status_code)
        self.assertEqual(1, session.rollbacks)
        self.assertEqual([], session.deleted)

    async def test_update_cost_center_can_deactivate_and_records_audit(self) -> None:
        principal = make_principal()
        cost_center = make_cost_center(tenant_id=principal.tenant_id)
        session = FakeOrgSession(get_result=cost_center)

        response = await update_cost_center(
            session,
            principal,
            cost_center.id,
            CostCenterUpdateRequest(name="Support Ops", is_active=False),
        )

        self.assertEqual("Support Ops", response.name)
        self.assertFalse(response.is_active)
        self.assertEqual(1, session.commits)
        audit_events = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual(1, len(audit_events))
        self.assertEqual("org.cost_center.update", audit_events[0].action)
        self.assertIn("is_active", audit_events[0].details["changed_fields"])

    async def test_delete_cost_center_rejects_user_binding(self) -> None:
        principal = make_principal()
        cost_center = make_cost_center(tenant_id=principal.tenant_id)
        session = FakeOrgSession(get_result=cost_center, execute_results=[FakeResult(uuid4())])

        with self.assertRaises(HTTPException) as raised:
            await delete_cost_center(session, principal, cost_center.id)

        self.assertEqual(409, raised.exception.status_code)
        self.assertEqual(1, session.rollbacks)
        self.assertEqual([], session.deleted)


if __name__ == "__main__":
    unittest.main()
