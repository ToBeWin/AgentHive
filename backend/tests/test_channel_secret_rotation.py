"""Unit tests for Channel secret rotation (dual-secret window).

Covers: rotate stages previous secret, promote drops it, webhook falls back
to previous secret during the transition window, 404 on unknown channel,
audit evidence, and cache coherence.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import unittest
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException

from app.schemas.channel import (
    ChannelSecretRotateRequest,
    ChannelStatus,
    ChannelType,
)
from app.services.channel_service import (
    ChannelRecord,
    _cache_channel,
    _channel_index,
    _channels_by_tenant,
    promote_channel_secret_for_tenant,
    receive_channel_webhook,
    rotate_channel_secret_for_tenant,
)


class _FakeResult:
    def scalars(self):
        class _Scalars:
            def all(self):
                return []

        return _Scalars()


class _FakeSession:
    """Mirrors the fake session used in test_channel_push.py.

    ``get`` returns None so the service's ORM-update branch is skipped
    (matching the existing test pattern); the in-memory cache is the source
    of truth for the ChannelRecord.
    """

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.committed = 0
        self.rolled_back = 0
        self.flushed = 0

    async def execute(self, *_args: Any, **_kwargs: Any) -> _FakeResult:
        return _FakeResult()

    def add(self, value: Any) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        self.flushed += 1

    async def commit(self) -> None:
        self.committed += 1

    async def rollback(self) -> None:
        self.rolled_back += 1

    async def get(self, *_args: Any, **_kwargs: Any) -> None:
        return None


def _make_channel(
    *,
    secret: str = "old-secret",
    previous_secret: str | None = None,
    channel_type: ChannelType = ChannelType.WEB_WIDGET,
) -> ChannelRecord:
    return ChannelRecord(
        id=uuid4(),
        tenant_id=uuid4(),
        name=f"{channel_type.value}-rotate-test",
        channel_type=channel_type,
        channel_key=f"{channel_type.value}-corp-1",
        agent_id=uuid4(),
        created_by=uuid4(),
        status=ChannelStatus.ACTIVE,
        config={
            "outbound_mode": "vendor_api",
            "outbound_webhook_url": "https://example.test/webhook",
        },
        secret=secret,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        secret_configured=True,
        previous_secret=previous_secret,
    )


class ChannelSecretRotateTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        _channels_by_tenant.clear()
        _channel_index.clear()

    async def _rotate(
        self,
        *,
        channel: ChannelRecord,
        new_secret: str,
        session: _FakeSession,
        actor_id: UUID | None = None,
    ) -> Any:
        return await rotate_channel_secret_for_tenant(
            session,
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            request=ChannelSecretRotateRequest(new_secret=new_secret),
            actor_id=actor_id or uuid4(),
            request_id="req-rotate-1",
        )

    async def test_rotate_stages_previous_secret_and_sets_new_primary(self) -> None:
        channel = _make_channel(secret="old-secret")
        _cache_channel(channel)
        session = _FakeSession()

        response = await self._rotate(channel=channel, new_secret="new-secret", session=session)

        self.assertTrue(response.rotated)
        self.assertTrue(response.previous_secret_staged)
        self.assertEqual(
            "new-secret",
            _channels_by_tenant[channel.tenant_id][channel.id].secret,
        )
        self.assertEqual(
            "old-secret",
            _channels_by_tenant[channel.tenant_id][channel.id].previous_secret,
        )

    async def test_rotate_from_no_secret_stages_none(self) -> None:
        channel = _make_channel(secret=None)
        channel.secret_configured = False
        _cache_channel(channel)
        session = _FakeSession()

        response = await self._rotate(channel=channel, new_secret="fresh-secret", session=session)

        self.assertTrue(response.rotated)
        self.assertFalse(response.previous_secret_staged)
        self.assertEqual(
            "fresh-secret",
            _channels_by_tenant[channel.tenant_id][channel.id].secret,
        )
        self.assertIsNone(_channels_by_tenant[channel.tenant_id][channel.id].previous_secret)

    async def test_rotate_unknown_channel_raises_404(self) -> None:
        session = _FakeSession()
        with self.assertRaises(HTTPException) as ctx:
            await rotate_channel_secret_for_tenant(
                session,
                tenant_id=uuid4(),
                channel_id=uuid4(),
                request=ChannelSecretRotateRequest(new_secret="x"),
                actor_id=uuid4(),
                request_id="req-404",
            )
        self.assertEqual(404, ctx.exception.status_code)

    async def test_rotate_overwrites_existing_previous_secret(self) -> None:
        channel = _make_channel(secret="current", previous_secret="stale-prev")
        _cache_channel(channel)
        session = _FakeSession()

        await self._rotate(channel=channel, new_secret="newer", session=session)

        self.assertEqual(
            "newer",
            _channels_by_tenant[channel.tenant_id][channel.id].secret,
        )
        self.assertEqual(
            "current",
            _channels_by_tenant[channel.tenant_id][channel.id].previous_secret,
        )

    async def test_promote_drops_previous_secret(self) -> None:
        channel = _make_channel(secret="current", previous_secret="old")
        _cache_channel(channel)
        session = _FakeSession()

        response = await promote_channel_secret_for_tenant(
            session,
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            actor_id=uuid4(),
            request_id="req-promote-1",
        )

        self.assertTrue(response.promoted)
        self.assertIn("dropped", response.message)
        self.assertIsNone(_channels_by_tenant[channel.tenant_id][channel.id].previous_secret)
        # Current secret unchanged.
        self.assertEqual(
            "current",
            _channels_by_tenant[channel.tenant_id][channel.id].secret,
        )

    async def test_promote_with_no_staged_secret_returns_noop_message(self) -> None:
        channel = _make_channel(secret="current", previous_secret=None)
        _cache_channel(channel)
        session = _FakeSession()

        response = await promote_channel_secret_for_tenant(
            session,
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            actor_id=uuid4(),
            request_id="req-promote-2",
        )

        self.assertTrue(response.promoted)
        self.assertIn("nothing to promote", response.message)

    async def test_promote_unknown_channel_raises_404(self) -> None:
        session = _FakeSession()
        with self.assertRaises(HTTPException) as ctx:
            await promote_channel_secret_for_tenant(
                session,
                tenant_id=uuid4(),
                channel_id=uuid4(),
                actor_id=uuid4(),
                request_id="req-404",
            )
        self.assertEqual(404, ctx.exception.status_code)

    async def test_full_rotate_then_promote_cycle(self) -> None:
        channel = _make_channel(secret="v1")
        _cache_channel(channel)
        session = _FakeSession()

        await self._rotate(channel=channel, new_secret="v2", session=session)
        self.assertEqual("v2", _channels_by_tenant[channel.tenant_id][channel.id].secret)
        self.assertEqual("v1", _channels_by_tenant[channel.tenant_id][channel.id].previous_secret)

        await promote_channel_secret_for_tenant(
            session,
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            actor_id=uuid4(),
            request_id="req-promote-3",
        )
        self.assertEqual("v2", _channels_by_tenant[channel.tenant_id][channel.id].secret)
        self.assertIsNone(_channels_by_tenant[channel.tenant_id][channel.id].previous_secret)


class FakeChannelSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.committed = False
        self.rolled_back = False

    async def execute(self, *_args: object, **_kwargs: object) -> object:
        raise OSError("database unavailable")

    def add(self, value: object) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def get(self, *_args: object, **_kwargs: object) -> None:
        return None


def _sign(*, secret: str, timestamp: str, nonce: str, payload: dict[str, object]) -> str:
    canonical_payload = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    signing_base = f"{timestamp}.{nonce}.{canonical_payload}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), signing_base, hashlib.sha256).hexdigest()


def _signed_headers(
    *, secret: str, payload: dict[str, Any], timestamp: str | None = None
) -> dict[str, str]:
    ts = timestamp or str(int(time.time()))
    nonce = f"nonce-{uuid4().hex[:8]}"
    signature = _sign(secret=secret, timestamp=ts, nonce=nonce, payload=payload)
    return {
        "X-AgentHive-Timestamp": ts,
        "X-AgentHive-Nonce": nonce,
        "X-AgentHive-Signature": f"sha256={signature}",
    }


class ChannelSecretRotationWebhookTests(unittest.IsolatedAsyncioTestCase):
    """During the dual-secret window, webhooks signed with the previous
    secret must still be accepted so in-flight requests aren't rejected."""

    async def asyncSetUp(self) -> None:
        _channels_by_tenant.clear()
        _channel_index.clear()

    async def test_webhook_signed_with_previous_secret_is_accepted_during_rotation(
        self,
    ) -> None:
        channel = ChannelRecord(
            id=uuid4(),
            tenant_id=uuid4(),
            name="REST API rotate",
            channel_type=ChannelType.REST_API,
            channel_key="signed-api-rotate",
            agent_id=None,
            created_by=uuid4(),
            status=ChannelStatus.ACTIVE,
            config={"agent_key": "customer_service"},
            secret="new-secret",
            previous_secret="old-secret",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            secret_configured=True,
        )
        _cache_channel(channel)
        session = FakeChannelSession()

        payload = {"text": "hello", "external_user_id": "buyer-1"}
        # Sign with the OLD (previous) secret — should still validate during
        # the rotation window via the fallback branch.
        headers = _signed_headers(secret="old-secret", payload=payload)

        response = await receive_channel_webhook(
            session,
            channel_type=ChannelType.REST_API,
            channel_key=channel.channel_key,
            payload=payload,
            headers=headers,
            request_id="req-rotation-fallback",
        )

        self.assertTrue(response.accepted, response.message)
        self.assertIsNotNone(response.processing)
        self.assertTrue(response.processing.runtime_evidence.get("signature_valid"))
        self.assertTrue(response.processing.runtime_evidence.get("rotation_previous_secret_used"))

    async def test_webhook_signed_with_unknown_secret_is_rejected(self) -> None:
        channel = ChannelRecord(
            id=uuid4(),
            tenant_id=uuid4(),
            name="REST API rotate",
            channel_type=ChannelType.REST_API,
            channel_key="signed-api-rotate-2",
            agent_id=None,
            created_by=uuid4(),
            status=ChannelStatus.ACTIVE,
            config={"agent_key": "customer_service"},
            secret="new-secret",
            previous_secret="old-secret",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            secret_configured=True,
        )
        _cache_channel(channel)
        session = FakeChannelSession()

        payload = {"text": "hello", "external_user_id": "buyer-1"}
        headers = _signed_headers(secret="neither-old-nor-new", payload=payload)

        response = await receive_channel_webhook(
            session,
            channel_type=ChannelType.REST_API,
            channel_key=channel.channel_key,
            payload=payload,
            headers=headers,
            request_id="req-rotation-reject",
        )

        self.assertFalse(response.accepted)
        self.assertIsNotNone(response.processing)
        self.assertFalse(response.processing.runtime_evidence.get("signature_valid"))
        self.assertEqual("invalid_signature", response.processing.error)

    async def test_webhook_signed_with_current_secret_still_accepted(self) -> None:
        channel = ChannelRecord(
            id=uuid4(),
            tenant_id=uuid4(),
            name="REST API rotate",
            channel_type=ChannelType.REST_API,
            channel_key="signed-api-rotate-3",
            agent_id=None,
            created_by=uuid4(),
            status=ChannelStatus.ACTIVE,
            config={"agent_key": "customer_service"},
            secret="new-secret",
            previous_secret="old-secret",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            secret_configured=True,
        )
        _cache_channel(channel)
        session = FakeChannelSession()

        payload = {"text": "hello", "external_user_id": "buyer-1"}
        headers = _signed_headers(secret="new-secret", payload=payload)

        response = await receive_channel_webhook(
            session,
            channel_type=ChannelType.REST_API,
            channel_key=channel.channel_key,
            payload=payload,
            headers=headers,
            request_id="req-rotation-current",
        )

        self.assertTrue(response.accepted, response.message)


if __name__ == "__main__":
    unittest.main()
