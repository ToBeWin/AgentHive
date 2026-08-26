from uuid import uuid4
import unittest

from fastapi import HTTPException

from app.api.deps import Principal
from app.models.audit_log import AuditLog
from app.models.llm import LLMPolicy
from app.schemas.llm import LLMPolicyStatus, LLMPolicyStatusUpdateRequest
from app.services.llm_service import update_model_policy_status


class FakePolicyStatusSession:
    def __init__(self, policy: LLMPolicy | None) -> None:
        self.policy = policy
        self.added: list[object] = []
        self.commits = 0
        self.refreshes = 0

    async def execute(self, _statement: object) -> "_OneOrNoneResult":
        return _OneOrNoneResult(self.policy)

    def add(self, row: object) -> None:
        self.added.append(row)

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, _row: object) -> None:
        self.refreshes += 1


class _OneOrNoneResult:
    def __init__(self, row: LLMPolicy | None) -> None:
        self.row = row

    def scalar_one_or_none(self) -> LLMPolicy | None:
        return self.row


def make_principal() -> Principal:
    return Principal(
        tenant_id=uuid4(),
        user_id=uuid4(),
        permissions={"models:write"},
    )


def make_policy(*, tenant_id, is_active: bool = True) -> LLMPolicy:
    return LLMPolicy(
        tenant_id=tenant_id,
        name="Tenant default policy",
        scope_type="tenant",
        scope_id=None,
        effect="allow",
        allowed_models=["qwen-plus"],
        allowed_routing_keys=["qwen-chat"],
        default_model_key="qwen-plus",
        default_routing_key="qwen-chat",
        max_tokens=4096,
        priority=100,
        is_active=is_active,
    )


class LLMPolicyStatusServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_update_model_policy_status_deactivates_policy_and_records_audit(self) -> None:
        principal = make_principal()
        policy = make_policy(tenant_id=principal.tenant_id)
        session = FakePolicyStatusSession(policy)

        response = await update_model_policy_status(
            session,
            policy.id,
            LLMPolicyStatusUpdateRequest(status=LLMPolicyStatus.INACTIVE),
            principal,
            request_id="req-policy-status",
        )

        self.assertEqual(LLMPolicyStatus.INACTIVE, response.status)
        self.assertFalse(policy.is_active)
        self.assertEqual(1, session.commits)
        self.assertEqual(1, session.refreshes)
        audit_events = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual(1, len(audit_events))
        self.assertEqual("llm.policy.status.update", audit_events[0].action)
        self.assertEqual("active", audit_events[0].details["previous_status"])
        self.assertEqual("inactive", audit_events[0].details["status"])
        self.assertEqual("tenant", audit_events[0].details["scope_type"])

    async def test_update_model_policy_status_raises_404_for_missing_policy(self) -> None:
        principal = make_principal()
        session = FakePolicyStatusSession(None)

        with self.assertRaises(HTTPException) as raised:
            await update_model_policy_status(
                session,
                uuid4(),
                LLMPolicyStatusUpdateRequest(status=LLMPolicyStatus.ACTIVE),
                principal,
            )

        self.assertEqual(404, raised.exception.status_code)
        self.assertEqual(0, session.commits)


if __name__ == "__main__":
    unittest.main()
