from decimal import Decimal
from uuid import uuid4
import unittest

from fastapi import HTTPException

from app.api.deps import Principal
from app.models.audit_log import AuditLog
from app.models.llm import LLMBudget
from app.schemas.budget import BudgetPolicyStatus, BudgetPolicyStatusUpdateRequest
from app.services.budget_admin_service import update_budget_policy_status


class FakeBudgetPolicySession:
    def __init__(self, policy: LLMBudget | None) -> None:
        self.policy = policy
        self.added: list[object] = []
        self.commits = 0
        self.refreshes = 0
        self.rollbacks = 0

    async def execute(self, _statement: object) -> "_OneOrNoneResult":
        return _OneOrNoneResult(self.policy)

    def add(self, value: object) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, _value: object) -> None:
        self.refreshes += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class _OneOrNoneResult:
    def __init__(self, row: LLMBudget | None) -> None:
        self.row = row

    def scalar_one_or_none(self) -> LLMBudget | None:
        return self.row


def make_principal(*, tenant_id=None, user_id=None) -> Principal:
    return Principal(
        tenant_id=tenant_id or uuid4(),
        user_id=user_id or uuid4(),
        permissions={"budgets:write"},
    )


def make_policy(*, tenant_id, is_active: bool = True) -> LLMBudget:
    return LLMBudget(
        tenant_id=tenant_id,
        scope_type="tenant",
        scope_id=None,
        period="monthly",
        amount_usd=Decimal("100"),
        token_limit=10000,
        hard_limit=True,
        alert_threshold_pct=80,
        is_active=is_active,
    )


class BudgetPolicyStatusServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_update_budget_policy_status_deactivates_policy_and_records_audit(self) -> None:
        principal = make_principal()
        policy = make_policy(tenant_id=principal.tenant_id)
        session = FakeBudgetPolicySession(policy)

        response = await update_budget_policy_status(
            session,
            principal,
            policy.id,
            BudgetPolicyStatusUpdateRequest(status=BudgetPolicyStatus.INACTIVE),
            request_id="request-budget",
        )

        self.assertEqual(BudgetPolicyStatus.INACTIVE, response.status)
        self.assertFalse(policy.is_active)
        self.assertEqual(1, session.commits)
        self.assertEqual(1, session.refreshes)
        audit_events = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual(1, len(audit_events))
        self.assertEqual("budget.policy.status.update", audit_events[0].action)
        self.assertEqual("active", audit_events[0].details["previous_status"])
        self.assertEqual("inactive", audit_events[0].details["status"])
        self.assertEqual("tenant", audit_events[0].details["scope_type"])

    async def test_update_budget_policy_status_raises_404_for_missing_policy(self) -> None:
        principal = make_principal()
        session = FakeBudgetPolicySession(None)

        with self.assertRaises(HTTPException) as raised:
            await update_budget_policy_status(
                session,
                principal,
                uuid4(),
                BudgetPolicyStatusUpdateRequest(status=BudgetPolicyStatus.ACTIVE),
            )

        self.assertEqual(404, raised.exception.status_code)
        self.assertEqual(0, session.commits)
        self.assertEqual(1, session.rollbacks)


if __name__ == "__main__":
    unittest.main()
