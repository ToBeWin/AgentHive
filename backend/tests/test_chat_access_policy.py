from datetime import datetime, timezone
from decimal import Decimal
import unittest
from uuid import uuid4

from fastapi import HTTPException

from app.api.deps import Principal
from app.models.conversation import ConversationMessage, ConversationSession
from app.services.chat_service import _can_access_chat_session, list_chat_messages


class ChatAccessPolicyTests(unittest.IsolatedAsyncioTestCase):
    def test_chat_session_access_is_limited_to_owner_department_or_admin(self) -> None:
        tenant_id = uuid4()
        owner_id = uuid4()
        department_id = uuid4()
        conversation = ConversationSession(
            tenant_id=tenant_id,
            title="Department case",
            user_id=owner_id,
            department_id=department_id,
        )

        owner = Principal(tenant_id=tenant_id, user_id=owner_id, permissions={"chat:read"})
        department_member = Principal(
            tenant_id=tenant_id, user_id=uuid4(), permissions={"chat:read"}
        )
        tenant_admin = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"tenant.admin"})
        outsider = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"chat:read"})
        other_tenant_admin = Principal(
            tenant_id=uuid4(), user_id=uuid4(), permissions={"tenant.admin"}
        )

        self.assertTrue(_can_access_chat_session(conversation, owner, set()))
        self.assertTrue(_can_access_chat_session(conversation, department_member, {department_id}))
        self.assertTrue(_can_access_chat_session(conversation, tenant_admin, set()))
        self.assertFalse(_can_access_chat_session(conversation, outsider, {uuid4()}))
        self.assertFalse(
            _can_access_chat_session(conversation, other_tenant_admin, {department_id})
        )

    async def test_list_chat_messages_rejects_inaccessible_same_tenant_session(self) -> None:
        tenant_id = uuid4()
        conversation = ConversationSession(
            id=uuid4(),
            tenant_id=tenant_id,
            title="Private support case",
            user_id=uuid4(),
            department_id=uuid4(),
        )
        session = FakeChatAccessSession(
            [
                FakeExecuteResult(scalar_value=conversation),
                FakeExecuteResult(rows=[]),
            ]
        )

        with self.assertRaises(HTTPException) as raised:
            await list_chat_messages(
                session,
                Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"chat:read"}),
                conversation.id,
            )

        self.assertEqual(403, raised.exception.status_code)
        self.assertEqual(2, session.execute_count)

    async def test_list_chat_messages_allows_department_member(self) -> None:
        tenant_id = uuid4()
        department_id = uuid4()
        conversation = ConversationSession(
            id=uuid4(),
            tenant_id=tenant_id,
            title="Department support case",
            user_id=uuid4(),
            department_id=department_id,
        )
        message = ConversationMessage(
            id=uuid4(),
            tenant_id=tenant_id,
            conversation_id=conversation.id,
            role="assistant",
            content="已按部门权限返回。",
            request_id="req-chat-access",
            input_tokens=1,
            output_tokens=2,
            total_tokens=3,
            cost_usd=Decimal("0.000001"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session = FakeChatAccessSession(
            [
                FakeExecuteResult(scalar_value=conversation),
                FakeExecuteResult(rows=[department_id]),
                FakeExecuteResult(rows=[message]),
            ]
        )

        result = await list_chat_messages(
            session,
            Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"chat:read"}),
            conversation.id,
        )

        self.assertEqual(1, len(result.messages))
        self.assertEqual("已按部门权限返回。", result.messages[0].content)


class FakeChatAccessSession:
    def __init__(self, execute_results: list[object]) -> None:
        self.execute_results = list(execute_results)
        self.execute_count = 0

    async def execute(self, _statement: object) -> object:
        self.execute_count += 1
        if not self.execute_results:
            raise AssertionError("Unexpected execute call.")
        return self.execute_results.pop(0)

    async def rollback(self) -> None:
        return None


class FakeExecuteResult:
    def __init__(
        self, *, scalar_value: object | None = None, rows: list[object] | None = None
    ) -> None:
        self.scalar_value = scalar_value
        self.rows = list(rows or [])

    def scalar_one_or_none(self) -> object | None:
        return self.scalar_value

    def scalars(self):
        return self

    def all(self) -> list[object]:
        return self.rows


if __name__ == "__main__":
    unittest.main()
