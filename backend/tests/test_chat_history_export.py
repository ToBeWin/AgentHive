"""Tests for conversation history export (P1 feature).

Validates:
- CSV/JSON output structure
- Access scoping (owner/department/admin allowed, outsider denied)
- Audit event recording
"""

from datetime import datetime, timezone
from decimal import Decimal
import csv
import json
import unittest
from uuid import uuid4

from fastapi import HTTPException

from app.api.deps import Principal
from app.models.conversation import ConversationMessage, ConversationSession
from app.services.chat_service import export_chat_history


class ChatHistoryExportTests(unittest.IsolatedAsyncioTestCase):
    def _make_conversation(
        self,
        *,
        tenant_id=None,
        owner_id=None,
        department_id=None,
    ) -> ConversationSession:
        return ConversationSession(
            id=uuid4(),
            tenant_id=tenant_id or uuid4(),
            title="Support case export",
            user_id=owner_id or uuid4(),
            department_id=department_id,
            source="chat_console",
            status="active",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    def _make_message(
        self, conversation: ConversationSession, role: str, content: str
    ) -> ConversationMessage:
        return ConversationMessage(
            id=uuid4(),
            tenant_id=conversation.tenant_id,
            conversation_id=conversation.id,
            role=role,
            content=content,
            user_id=conversation.user_id if role == "user" else None,
            request_id="req-export-test",
            model_key="gpt-4o" if role == "assistant" else None,
            provider_key="openai" if role == "assistant" else None,
            input_tokens=10 if role == "assistant" else 0,
            output_tokens=20 if role == "assistant" else 0,
            total_tokens=30 if role == "assistant" else 0,
            cost_usd=Decimal("0.001") if role == "assistant" else Decimal("0"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    def _build_session(self, conversation, messages, *, include_department_query=False):
        """Build a fake AsyncSession yielding the expected execute results.

        Export flow execute() calls:
        1. _get_accessible_conversation_session -> scalar_one_or_none (conversation)
        2. _principal_department_ids -> rows (department_ids, empty for owner/admin)
        3. _list_chat_messages_for_conversation -> rows (messages)
        4. record_audit_event -> insert (no fetch)
        5. commit
        """
        results = [
            FakeExecuteResult(scalar_value=conversation),
            FakeExecuteResult(rows=[]),  # department_ids
            FakeExecuteResult(rows=messages),
        ]
        return FakeExportSession(results)

    async def test_export_csv_returns_valid_csv_with_messages(self) -> None:
        tenant_id = uuid4()
        owner_id = uuid4()
        conversation = self._make_conversation(tenant_id=tenant_id, owner_id=owner_id)
        msg1 = self._make_message(conversation, "user", "你好")
        msg2 = self._make_message(conversation, "assistant", "您好，有什么可以帮您？")
        session = self._build_session(conversation, [msg1, msg2])

        principal = Principal(tenant_id=tenant_id, user_id=owner_id, permissions={"chat:read"})
        body = await export_chat_history(session, principal, conversation.id, fmt="csv")

        self.assertIn("message_id", body)
        self.assertIn("你好", body)
        self.assertIn("您好，有什么可以帮您？", body)
        self.assertIn("# conversation_id", body)
        # Parse CSV body (skip comment lines starting with #).
        data_lines = [line for line in body.splitlines() if line and not line.startswith("#")]
        reader = csv.DictReader(data_lines)
        rows = list(reader)
        self.assertEqual(2, len(rows))
        self.assertEqual("user", rows[0]["role"])
        self.assertEqual("assistant", rows[1]["role"])
        self.assertEqual("30", rows[1]["total_tokens"])
        self.assertTrue(session.committed)

    async def test_export_json_returns_valid_json_payload(self) -> None:
        tenant_id = uuid4()
        owner_id = uuid4()
        conversation = self._make_conversation(tenant_id=tenant_id, owner_id=owner_id)
        msg = self._make_message(conversation, "user", "导出测试")
        session = self._build_session(conversation, [msg])

        principal = Principal(tenant_id=tenant_id, user_id=owner_id, permissions={"chat:read"})
        body = await export_chat_history(session, principal, conversation.id, fmt="json")

        payload = json.loads(body)
        self.assertIn("conversation", payload)
        self.assertIn("messages", payload)
        self.assertEqual(1, len(payload["messages"]))
        self.assertEqual("导出测试", payload["messages"][0]["content"])
        self.assertEqual(str(conversation.id), payload["conversation"]["id"])

    async def test_export_records_audit_event(self) -> None:
        tenant_id = uuid4()
        owner_id = uuid4()
        conversation = self._make_conversation(tenant_id=tenant_id, owner_id=owner_id)
        session = self._build_session(conversation, [])

        principal = Principal(tenant_id=tenant_id, user_id=owner_id, permissions={"chat:read"})
        await export_chat_history(
            session,
            principal,
            conversation.id,
            fmt="csv",
            request_id="req-audit-test",
            ip_address="10.0.0.1",
            user_agent="pytest",
        )

        # Audit insert should have been called.
        self.assertTrue(session.audit_recorded)
        self.assertEqual("chat.history.export", session.audit_action)
        self.assertTrue(session.committed)

    async def test_export_denied_for_inaccessible_conversation(self) -> None:
        tenant_id = uuid4()
        conversation = self._make_conversation(
            tenant_id=tenant_id, owner_id=uuid4(), department_id=uuid4()
        )
        # Outsider: different user, no matching department.
        session = FakeExportSession(
            [
                FakeExecuteResult(scalar_value=conversation),
                FakeExecuteResult(rows=[uuid4()]),  # unrelated department
            ]
        )
        outsider = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"chat:read"})

        with self.assertRaises(HTTPException) as raised:
            await export_chat_history(session, outsider, conversation.id, fmt="csv")
        self.assertEqual(403, raised.exception.status_code)
        self.assertFalse(session.committed)


class FakeExportSession:
    """Minimal AsyncSession stub for export flow."""

    def __init__(self, execute_results: list[object]) -> None:
        self.execute_results = list(execute_results)
        self.execute_count = 0
        self.committed = False
        self.audit_recorded = False
        self.audit_action: str | None = None
        self._added: list[object] = []

    async def execute(self, _statement: object) -> object:
        self.execute_count += 1
        if not self.execute_results:
            raise AssertionError("Unexpected execute call.")
        return self.execute_results.pop(0)

    def add(self, entity: object) -> None:
        # Detect audit log insertion by class name.
        cls_name = type(entity).__name__
        if cls_name == "AuditLog":
            self.audit_recorded = True
            self.audit_action = getattr(entity, "action", None)
        self._added.append(entity)

    async def commit(self) -> None:
        self.committed = True

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
