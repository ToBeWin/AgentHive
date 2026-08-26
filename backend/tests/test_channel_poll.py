"""Unit tests for Channel polling API — outbound message retrieval for
Web Widget / REST API clients.

Covers:
- pure helpers: session matching, message pagination (conv filter, cursor,
  has_more, next_cursor).
- service-level polling: end-to-end with a fake session (role filter at DB
  emulated; conv/cursor/limit handled by pure helpers).
- API-level signature verification: missing signature, invalid signature,
  valid signature (current secret), valid signature (previous secret during
  rotation), channel with no secret (allowed), channel not found (404).
"""

from __future__ import annotations

import hashlib
import hmac
import unittest
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.models.conversation import ConversationMessage, ConversationSession
from app.schemas.channel import ChannelStatus, ChannelType
from app.services.channel_service import (
    ChannelRecord,
    _cache_channel,
    _channel_index,
    _channels_by_tenant,
    _paginate_messages,
    _select_matching_sessions,
    get_channel_by_key,
    poll_channel_messages_for_tenant,
)


def _make_channel(
    *,
    channel_type: ChannelType = ChannelType.WEB_WIDGET,
    secret: str | None = "widget-secret",
    previous_secret: str | None = None,
) -> ChannelRecord:
    return ChannelRecord(
        id=uuid4(),
        tenant_id=uuid4(),
        name=f"{channel_type.value}-poll-test",
        channel_type=channel_type,
        channel_key=f"{channel_type.value}-corp-1",
        agent_id=uuid4(),
        created_by=uuid4(),
        status=ChannelStatus.ACTIVE,
        config={"agent_key": "customer_service", "outbound_mode": "webhook_ack"},
        secret=secret,
        previous_secret=previous_secret,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        secret_configured=bool(secret),
    )


def _make_session_row(
    *,
    session_id: UUID,
    tenant_id: UUID,
    channel_id: UUID,
    external_user_id: str,
    conversation_key: str,
    updated_at: datetime | None = None,
) -> ConversationSession:
    row = ConversationSession(
        id=session_id,
        tenant_id=tenant_id,
        title="t",
        agent_id=uuid4(),
        channel_id=channel_id,
        source="channel.web_widget",
        status="active",
        metadata_json={
            "external_user_id": external_user_id,
            "conversation_key": conversation_key,
            "channel_key": "web_widget-corp-1",
        },
    )
    row.updated_at = updated_at or datetime.now(timezone.utc)
    return row


def _make_message_row(
    *,
    message_id: UUID,
    tenant_id: UUID,
    conversation_id: UUID,
    role: str,
    content: str,
    created_at: datetime,
) -> ConversationMessage:
    row = ConversationMessage(
        id=message_id,
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        role=role,
        content=content,
    )
    row.created_at = created_at
    return row


class _Scalars:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows


class _FakeResult:
    def __init__(self, rows: list[Any] | None = None) -> None:
        self._rows = rows or []

    def scalars(self) -> _Scalars:
        return _Scalars(self._rows)


class _FakeSession:
    """In-memory async session. Returns scripted sessions/messages.

    The DB-level role filter (``role IN ('assistant','agent')``) is emulated
    by pre-filtering the messages list; conversation-id / cursor / limit
    filtering is handled by the pure ``_paginate_messages`` helper.
    """

    def __init__(
        self,
        *,
        sessions: list[Any] | None = None,
        messages: list[Any] | None = None,
    ) -> None:
        self._sessions = sessions or []
        # Emulate DB role filter.
        self._messages = [m for m in (messages or []) if m.role in ("assistant", "agent")]

    async def execute(self, *_args: Any, **_kwargs: Any) -> _FakeResult:
        stmt = _args[0] if _args else None
        text = str(stmt) if stmt is not None else ""
        if "conversation_sessions" in text:
            return _FakeResult(self._sessions)
        return _FakeResult(self._messages)

    def add(self, value: Any) -> None:
        return None

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    async def get(self, *_args: Any, **_kwargs: Any) -> Any:
        return None


class PureHelperTests(unittest.TestCase):
    def test_select_matching_sessions_filters_by_user(self) -> None:
        tenant = uuid4()
        channel = uuid4()
        s1 = _make_session_row(
            session_id=uuid4(),
            tenant_id=tenant,
            channel_id=channel,
            external_user_id="u1",
            conversation_key="k1",
        )
        s2 = _make_session_row(
            session_id=uuid4(),
            tenant_id=tenant,
            channel_id=channel,
            external_user_id="u2",
            conversation_key="k2",
        )
        ids, resolved = _select_matching_sessions([s1, s2], "u1", None)
        self.assertEqual(ids, [s1.id])
        self.assertEqual(resolved, "k1")

    def test_select_matching_sessions_filters_by_conversation_key(self) -> None:
        tenant = uuid4()
        channel = uuid4()
        s1 = _make_session_row(
            session_id=uuid4(),
            tenant_id=tenant,
            channel_id=channel,
            external_user_id="u1",
            conversation_key="k1",
        )
        s2 = _make_session_row(
            session_id=uuid4(),
            tenant_id=tenant,
            channel_id=channel,
            external_user_id="u1",
            conversation_key="k2",
        )
        ids, resolved = _select_matching_sessions([s1, s2], "u1", "k1")
        self.assertEqual(ids, [s1.id])
        self.assertEqual(resolved, "k1")

    def test_select_matching_sessions_no_match_returns_empty(self) -> None:
        s1 = _make_session_row(
            session_id=uuid4(),
            tenant_id=uuid4(),
            channel_id=uuid4(),
            external_user_id="u1",
            conversation_key="k1",
        )
        ids, resolved = _select_matching_sessions([s1], "unknown", None)
        self.assertEqual(ids, [])
        self.assertIsNone(resolved)

    def test_paginate_filters_by_matching_sessions(self) -> None:
        s1 = uuid4()
        s2 = uuid4()
        now = datetime.now(timezone.utc)
        rows = [
            _make_message_row(
                message_id=uuid4(),
                tenant_id=uuid4(),
                conversation_id=s1,
                role="assistant",
                content="from-s1",
                created_at=now,
            ),
            _make_message_row(
                message_id=uuid4(),
                tenant_id=uuid4(),
                conversation_id=s2,
                role="assistant",
                content="from-s2",
                created_at=now,
            ),
        ]
        key_map = {s1: "k1", s2: "k2"}
        msgs, has_more, cursor = _paginate_messages(
            rows, matching_session_ids=[s1], after=None, limit=50, session_key_map=key_map
        )
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].content, "from-s1")
        self.assertEqual(msgs[0].conversation_key, "k1")
        self.assertFalse(has_more)
        self.assertIsNone(cursor)

    def test_paginate_cursor_after_filters_older(self) -> None:
        s1 = uuid4()
        now = datetime.now(timezone.utc)
        m1 = _make_message_row(
            message_id=UUID("00000000-0000-0000-0000-000000000001"),
            tenant_id=uuid4(),
            conversation_id=s1,
            role="assistant",
            content="m1",
            created_at=now,
        )
        m2 = _make_message_row(
            message_id=UUID("00000000-0000-0000-0000-000000000002"),
            tenant_id=uuid4(),
            conversation_id=s1,
            role="assistant",
            content="m2",
            created_at=now,
        )
        m3 = _make_message_row(
            message_id=UUID("00000000-0000-0000-0000-000000000003"),
            tenant_id=uuid4(),
            conversation_id=s1,
            role="assistant",
            content="m3",
            created_at=now,
        )
        msgs, _, _ = _paginate_messages(
            [m1, m2, m3],
            matching_session_ids=[s1],
            after=m2.id,
            limit=50,
            session_key_map={s1: "k1"},
        )
        self.assertEqual([m.message_id for m in msgs], [m3.id])

    def test_paginate_has_more_and_next_cursor(self) -> None:
        s1 = uuid4()
        now = datetime.now(timezone.utc)
        rows = [
            _make_message_row(
                message_id=UUID(f"00000000-0000-0000-0000-00000000000{i}"),
                tenant_id=uuid4(),
                conversation_id=s1,
                role="assistant",
                content=f"m{i}",
                created_at=now,
            )
            for i in range(1, 4)
        ]
        msgs, has_more, cursor = _paginate_messages(
            rows, matching_session_ids=[s1], after=None, limit=2, session_key_map={s1: "k1"}
        )
        self.assertTrue(has_more)
        self.assertEqual(len(msgs), 2)
        self.assertEqual(cursor, msgs[-1].message_id)

    def test_paginate_empty_rows(self) -> None:
        msgs, has_more, cursor = _paginate_messages(
            [], matching_session_ids=[uuid4()], after=None, limit=50, session_key_map={}
        )
        self.assertEqual(msgs, [])
        self.assertFalse(has_more)
        self.assertIsNone(cursor)


class PollServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        _channels_by_tenant.clear()
        _channel_index.clear()

    async def test_returns_assistant_messages_for_external_user(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session_id = uuid4()
        session_row = _make_session_row(
            session_id=session_id,
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            external_user_id="visitor-1",
            conversation_key="web_widget:web_widget-corp-1:visitor-1",
        )
        now = datetime.now(timezone.utc)
        m1 = _make_message_row(
            message_id=uuid4(),
            tenant_id=channel.tenant_id,
            conversation_id=session_id,
            role="assistant",
            content="你好，有什么可以帮您？",
            created_at=now,
        )
        m2 = _make_message_row(
            message_id=uuid4(),
            tenant_id=channel.tenant_id,
            conversation_id=session_id,
            role="user",
            content="查询订单",
            created_at=now,
        )
        m3 = _make_message_row(
            message_id=uuid4(),
            tenant_id=channel.tenant_id,
            conversation_id=session_id,
            role="assistant",
            content="您的订单 #123 已发货。",
            created_at=now,
        )
        session = _FakeSession(sessions=[session_row], messages=[m1, m2, m3])
        resp = await poll_channel_messages_for_tenant(
            session,
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            external_user_id="visitor-1",
        )
        self.assertEqual(resp.channel_id, channel.id)
        self.assertEqual(resp.external_user_id, "visitor-1")
        self.assertEqual(resp.conversation_key, "web_widget:web_widget-corp-1:visitor-1")
        roles = [m.role for m in resp.messages]
        self.assertEqual(roles, ["assistant", "assistant"])
        self.assertEqual(resp.messages[0].content, "你好，有什么可以帮您？")
        self.assertEqual(resp.messages[1].content, "您的订单 #123 已发货。")
        self.assertFalse(resp.has_more)
        self.assertIsNone(resp.next_cursor)

    async def test_filters_by_conversation_key(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        s1 = _make_session_row(
            session_id=uuid4(),
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            external_user_id="visitor-1",
            conversation_key="web_widget:k1:visitor-1",
        )
        s2 = _make_session_row(
            session_id=uuid4(),
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            external_user_id="visitor-1",
            conversation_key="web_widget:k2:visitor-1",
        )
        now = datetime.now(timezone.utc)
        m1 = _make_message_row(
            message_id=uuid4(),
            tenant_id=channel.tenant_id,
            conversation_id=s1.id,
            role="assistant",
            content="from-k1",
            created_at=now,
        )
        m2 = _make_message_row(
            message_id=uuid4(),
            tenant_id=channel.tenant_id,
            conversation_id=s2.id,
            role="assistant",
            content="from-k2",
            created_at=now,
        )
        session = _FakeSession(sessions=[s1, s2], messages=[m1, m2])
        resp = await poll_channel_messages_for_tenant(
            session,
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            external_user_id="visitor-1",
            conversation_key="web_widget:k1:visitor-1",
        )
        self.assertEqual(len(resp.messages), 1)
        self.assertEqual(resp.messages[0].content, "from-k1")

    async def test_cursor_after_filters_older_messages(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session_id = uuid4()
        session_row = _make_session_row(
            session_id=session_id,
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            external_user_id="visitor-1",
            conversation_key="k1",
        )
        m1_id = UUID("00000000-0000-0000-0000-000000000001")
        m2_id = UUID("00000000-0000-0000-0000-000000000002")
        m3_id = UUID("00000000-0000-0000-0000-000000000003")
        now = datetime.now(timezone.utc)
        messages = [
            _make_message_row(
                message_id=m1_id,
                tenant_id=channel.tenant_id,
                conversation_id=session_id,
                role="assistant",
                content="m1",
                created_at=now,
            ),
            _make_message_row(
                message_id=m2_id,
                tenant_id=channel.tenant_id,
                conversation_id=session_id,
                role="assistant",
                content="m2",
                created_at=now,
            ),
            _make_message_row(
                message_id=m3_id,
                tenant_id=channel.tenant_id,
                conversation_id=session_id,
                role="assistant",
                content="m3",
                created_at=now,
            ),
        ]
        session = _FakeSession(sessions=[session_row], messages=messages)
        resp = await poll_channel_messages_for_tenant(
            session,
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            external_user_id="visitor-1",
            after=m2_id,
        )
        self.assertEqual([m.message_id for m in resp.messages], [m3_id])

    async def test_has_more_and_next_cursor(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session_id = uuid4()
        session_row = _make_session_row(
            session_id=session_id,
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            external_user_id="visitor-1",
            conversation_key="k1",
        )
        now = datetime.now(timezone.utc)
        messages = [
            _make_message_row(
                message_id=UUID(f"00000000-0000-0000-0000-00000000000{i}"),
                tenant_id=channel.tenant_id,
                conversation_id=session_id,
                role="assistant",
                content=f"m{i}",
                created_at=now,
            )
            for i in range(1, 4)
        ]
        session = _FakeSession(sessions=[session_row], messages=messages)
        resp = await poll_channel_messages_for_tenant(
            session,
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            external_user_id="visitor-1",
            limit=2,
        )
        self.assertTrue(resp.has_more)
        self.assertEqual(len(resp.messages), 2)
        self.assertEqual(resp.next_cursor, resp.messages[-1].message_id)

    async def test_no_matching_user_returns_empty(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session_row = _make_session_row(
            session_id=uuid4(),
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            external_user_id="visitor-1",
            conversation_key="k1",
        )
        session = _FakeSession(sessions=[session_row], messages=[])
        resp = await poll_channel_messages_for_tenant(
            session,
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            external_user_id="unknown-user",
        )
        self.assertEqual(resp.messages, [])
        self.assertFalse(resp.has_more)

    async def test_get_channel_by_key_returns_cached_channel(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        found = await get_channel_by_key(_FakeSession(), channel.channel_type, channel.channel_key)
        self.assertIsNotNone(found)
        self.assertEqual(found.id, channel.id)


class PollSignatureTests(unittest.TestCase):
    """Signature verification on the poll endpoint via FastAPI TestClient.

    ``get_session`` is overridden to return a fake session (empty results) so
    no live database is required; the channel is resolved from the in-process
    cache via ``_cache_channel``.
    """

    @classmethod
    def setUpClass(cls) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.deps import get_session
        from app.api.v1.channels import router

        async def _fake_get_session() -> Any:
            yield _FakeSession()

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[get_session] = _fake_get_session
        cls._client = TestClient(app)

    def setUp(self) -> None:
        _channels_by_tenant.clear()
        _channel_index.clear()

    def _sign(
        self,
        *,
        method: str,
        path: str,
        query: str,
        secret: str,
        timestamp: str = "1700000000",
        nonce: str = "n-1",
    ) -> str:
        pairs = sorted(query.split("&")) if query else []
        canonical = "&".join(pairs)
        base = f"{timestamp}.{nonce}.{method}.{path}?{canonical}"
        return hmac.new(secret.encode(), base.encode(), hashlib.sha256).hexdigest()

    def test_missing_signature_returns_401(self) -> None:
        channel = _make_channel(secret="widget-secret")
        _cache_channel(channel)
        resp = self._client.get(
            f"/api/v1/channels/poll/{channel.channel_type.value}/{channel.channel_key}",
            params={"external_user_id": "visitor-1"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_invalid_signature_returns_401(self) -> None:
        channel = _make_channel(secret="widget-secret")
        _cache_channel(channel)
        resp = self._client.get(
            f"/api/v1/channels/poll/{channel.channel_type.value}/{channel.channel_key}",
            params={"external_user_id": "visitor-1"},
            headers={
                "X-AgentHive-Signature": "sha256=deadbeef",
                "X-AgentHive-Timestamp": "1700000000",
                "X-AgentHive-Nonce": "n-1",
            },
        )
        self.assertEqual(resp.status_code, 401)

    def test_channel_not_found_returns_404(self) -> None:
        resp = self._client.get(
            "/api/v1/channels/poll/web_widget/no-such-channel",
            params={"external_user_id": "visitor-1"},
        )
        self.assertEqual(resp.status_code, 404)

    def test_valid_signature_returns_200(self) -> None:
        channel = _make_channel(secret="widget-secret")
        _cache_channel(channel)
        query = "external_user_id=visitor-1"
        path = f"/api/v1/channels/poll/{channel.channel_type.value}/{channel.channel_key}"
        sig = self._sign(method="GET", path=path, query=query, secret="widget-secret")
        resp = self._client.get(
            path,
            params={"external_user_id": "visitor-1"},
            headers={
                "X-AgentHive-Signature": f"sha256={sig}",
                "X-AgentHive-Timestamp": "1700000000",
                "X-AgentHive-Nonce": "n-1",
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["external_user_id"], "visitor-1")
        self.assertEqual(body["messages"], [])

    def test_previous_secret_accepted_during_rotation(self) -> None:
        channel = _make_channel(secret="new-secret", previous_secret="old-secret")
        _cache_channel(channel)
        query = "external_user_id=visitor-1"
        path = f"/api/v1/channels/poll/{channel.channel_type.value}/{channel.channel_key}"
        sig = self._sign(method="GET", path=path, query=query, secret="old-secret")
        resp = self._client.get(
            path,
            params={"external_user_id": "visitor-1"},
            headers={
                "X-AgentHive-Signature": f"sha256={sig}",
                "X-AgentHive-Timestamp": "1700000000",
                "X-AgentHive-Nonce": "n-1",
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)

    def test_channel_without_secret_allows_poll(self) -> None:
        channel = _make_channel(secret=None)
        _cache_channel(channel)
        path = f"/api/v1/channels/poll/{channel.channel_type.value}/{channel.channel_key}"
        resp = self._client.get(
            path,
            params={"external_user_id": "visitor-1"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)


if __name__ == "__main__":
    unittest.main()
