"""End-to-end integration tests for the WeCom Channel.

These tests exercise the full ``receive_channel_webhook`` flow:
  webhook inbound -> signature verification -> normalize -> agent run
  -> outbound delivery via vendor_api.

They cover:
  * Happy path with a valid HMAC signature and a successful vendor API call.
  * Replay protection (timestamp outside the allowed skew window).
  * Invalid / missing signature headers (webhook rejected, not routed).
  * Agent runtime exception (routed=False, error=processing_exception).
  * Vendor API HTTP error and WeCom errcode!=0 (delivered=False but routed=True).
  * Outbound delivery evidence is surfaced in the processing result and audit.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx

from app.models.audit_log import AuditLog
from app.models.conversation import ConversationSession
from app.schemas.agents import AgentRunResponse
from app.schemas.channel import ChannelStatus, ChannelType
from app.schemas.llm import LLMUsageResponse
from app.services.channel_service import (
    ChannelRecord,
    _cache_channel,
    _channel_index,
    _channels_by_tenant,
    receive_channel_webhook,
)


# Capture the real AsyncClient class before any test patches it, so the mock
# factory can build genuine async-context-manager instances wired to a
# MockTransport without recursing through the patch target.
_REAL_ASYNC_CLIENT = httpx.AsyncClient


def _async_client_factory(transport: httpx.MockTransport):
    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("transport", None)
        return _REAL_ASYNC_CLIENT(*args, **kwargs, transport=transport)

    return factory


def _sign(*, secret: str, timestamp: str, nonce: str, payload: dict[str, Any]) -> str:
    canonical_payload = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    signing_base = f"{timestamp}.{nonce}.{canonical_payload}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), signing_base, hashlib.sha256).hexdigest()


def _signed_headers(
    *, secret: str, payload: dict[str, Any], timestamp: str | None = None
) -> dict[str, str]:
    ts = timestamp or str(int(time.time()))
    nonce = hashlib.sha256(f"{ts}:{secret}".encode("utf-8")).hexdigest()[:24]
    signature = _sign(secret=secret, timestamp=ts, nonce=nonce, payload=payload)
    return {
        "X-AgentHive-Timestamp": ts,
        "X-AgentHive-Nonce": nonce,
        "X-AgentHive-Signature": f"sha256={signature}",
    }


def _wecom_payload(
    *, text: str = "你好", user: str = "StaffA", msg_id: str | None = None
) -> dict[str, Any]:
    return {
        "MsgType": "text",
        "Text": {"Content": text},
        "FromUserName": user,
        "MsgId": msg_id or f"msg-{uuid4().hex[:8]}",
        "AgentID": 1000002,
    }


def _make_channel(*, secret: str | None = "wecom-secret") -> ChannelRecord:
    return ChannelRecord(
        id=uuid4(),
        tenant_id=uuid4(),
        name="WeCom Customer Service",
        channel_type=ChannelType.WECOM,
        channel_key="wecom-corp-1",
        agent_id=uuid4(),
        created_by=uuid4(),
        status=ChannelStatus.ACTIVE,
        config={
            "agent_key": "customer_service",
            "outbound_mode": "vendor_api",
            "wecom_access_token": "tok-1",
            "wecom_agent_id": 1000002,
        },
        secret=secret,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        secret_configured=bool(secret),
    )


def _agent_response(*, answer: str = "已为您查询到结果。") -> AgentRunResponse:
    return AgentRunResponse(
        answer=answer,
        usage=LLMUsageResponse(
            input_tokens=12,
            output_tokens=8,
            total_tokens=20,
            cost_usd=Decimal("0.0001"),
        ),
        model_key="qwen-plus",
        request_id=f"run-{uuid4().hex[:8]}",
        metadata={"provider_key": "dashscope"},
    )


class _FakeResult:
    def scalars(self):
        class _Scalars:
            def all(self):
                return []

        return _Scalars()


class _FakeSession:
    """Minimal async session that drives channel_service without a database.

    - ``execute`` returns an empty result so _get_or_create_channel_conversation
      always creates a new ConversationSession.
    - ``flush`` assigns an id to any pending ConversationSession so downstream
      code can reference ``conversation.id``.
    - ``add`` records rows for audit assertions.
    """

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.committed = 0
        self.rolled_back = 0
        self._pending_conversations: list[ConversationSession] = []

    async def execute(self, *_args: Any, **_kwargs: Any) -> _FakeResult:
        return _FakeResult()

    def add(self, value: Any) -> None:
        self.added.append(value)
        if isinstance(value, ConversationSession) and value.id is None:
            self._pending_conversations.append(value)

    async def flush(self) -> None:
        for conversation in self._pending_conversations:
            conversation.id = uuid4()
        self._pending_conversations.clear()

    async def commit(self) -> None:
        self.committed += 1
        # commit implies flush for any un-flushed pending conversations
        for conversation in self._pending_conversations:
            conversation.id = uuid4()
        self._pending_conversations.clear()

    async def rollback(self) -> None:
        self.rolled_back += 1


class WeComChannelEndToEndTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        _channels_by_tenant.clear()
        _channel_index.clear()

    async def _run_webhook(
        self,
        *,
        channel: ChannelRecord,
        payload: dict[str, Any],
        headers: dict[str, str],
        session: _FakeSession,
        run_agent_mock: AsyncMock,
    ) -> Any:
        with patch("app.services.channel_service.run_agent", new=run_agent_mock):
            return await receive_channel_webhook(
                session,
                channel_type=ChannelType.WECOM,
                channel_key=channel.channel_key,
                payload=payload,
                headers=headers,
                request_id="req-e2e-1",
            )

    async def test_happy_path_routes_to_agent_and_delivers_via_vendor_api(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session = _FakeSession()

        payload = _wecom_payload(text="我想退货")
        headers = _signed_headers(secret=channel.secret, payload=payload)

        captured: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(
                {
                    "url": str(request.url),
                    "method": request.method,
                    "body": request.read().decode("utf-8"),
                    "params": dict(request.url.params),
                }
            )
            return httpx.Response(
                status_code=200,
                json={"errcode": 0, "errmsg": "ok", "msgid": "MSG-OK-1"},
            )

        transport = httpx.MockTransport(handler)
        run_agent_mock = AsyncMock(return_value=_agent_response(answer="好的，已为您发起退货。"))

        with patch(
            "app.channels.wecom.httpx.AsyncClient",
            side_effect=_async_client_factory(transport),
        ):
            response = await self._run_webhook(
                channel=channel,
                payload=payload,
                headers=headers,
                session=session,
                run_agent_mock=run_agent_mock,
            )

        # Webhook accepted and routed
        self.assertTrue(response.accepted)
        self.assertIsNotNone(response.processing)
        self.assertTrue(response.processing.routed)
        self.assertEqual("customer_service", response.processing.agent_key)
        self.assertEqual("qwen-plus", response.processing.model_key)
        self.assertEqual("好的，已为您发起退货。", response.processing.response_text)

        # run_agent was called with channel context
        run_agent_mock.assert_awaited_once()
        run_request = run_agent_mock.await_args.args[2]
        self.assertEqual("我想退货", run_request.input)
        self.assertEqual(str(channel.id), run_request.context["channel_id"])
        self.assertEqual("StaffA", run_request.context["external_user_id"])
        self.assertEqual("channel.wecom", run_request.context["source"])

        # Outbound delivered via vendor_api
        delivery = response.processing.outbound_delivery
        self.assertIsNotNone(delivery)
        self.assertTrue(delivery.attempted)
        self.assertTrue(delivery.delivered)
        self.assertEqual("vendor_api_wecom", delivery.mode)
        self.assertEqual(200, delivery.status_code)

        # Vendor API was hit with the right target + payload
        self.assertEqual(1, len(captured))
        self.assertTrue(
            captured[0]["url"].startswith("https://qyapi.weixin.qq.com/cgi-bin/message/send"),
            captured[0]["url"],
        )
        self.assertEqual("tok-1", captured[0]["params"]["access_token"])
        body = captured[0]["body"]
        self.assertIn('"touser":"StaffA"', body)
        self.assertIn('"agentid":1000002', body)
        self.assertIn('"content":"好的，已为您发起退货。"', body)

        # Conversation + audit rows were persisted
        conversations = [r for r in session.added if isinstance(r, ConversationSession)]
        self.assertEqual(1, len(conversations))
        audit_events = [r for r in session.added if isinstance(r, AuditLog)]
        actions = [row.action for row in audit_events]
        self.assertIn("channel.webhook.received", actions)
        self.assertIn("channel.webhook.processed", actions)
        self.assertIn("channel.message.routed", actions)

    async def test_replay_protection_rejects_timestamp_outside_skew_window(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session = _FakeSession()

        payload = _wecom_payload()
        # 10 minutes ago -> outside the 300s skew window
        old_timestamp = str(int(time.time()) - 600)
        headers = _signed_headers(secret=channel.secret, payload=payload, timestamp=old_timestamp)

        run_agent_mock = AsyncMock(return_value=_agent_response())

        response = await self._run_webhook(
            channel=channel,
            payload=payload,
            headers=headers,
            session=session,
            run_agent_mock=run_agent_mock,
        )

        self.assertFalse(response.accepted)
        self.assertFalse(response.signature.valid)
        self.assertIn("replay window", response.signature.reason or "")
        # Agent must NOT be invoked when signature is invalid
        run_agent_mock.assert_not_awaited()
        self.assertIsNotNone(response.processing)
        self.assertFalse(response.processing.routed)
        self.assertEqual("invalid_signature", response.processing.error)

    async def test_invalid_signature_rejects_webhook_without_routing(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session = _FakeSession()

        payload = _wecom_payload()
        headers = _signed_headers(secret=channel.secret, payload=payload)
        # Tamper with the signature
        headers["X-AgentHive-Signature"] = "sha256=deadbeef"

        run_agent_mock = AsyncMock(return_value=_agent_response())

        response = await self._run_webhook(
            channel=channel,
            payload=payload,
            headers=headers,
            session=session,
            run_agent_mock=run_agent_mock,
        )

        self.assertFalse(response.accepted)
        self.assertFalse(response.signature.valid)
        self.assertEqual("Signature mismatch.", response.signature.reason)
        run_agent_mock.assert_not_awaited()
        self.assertEqual("invalid_signature", response.processing.error)
        self.assertFalse(response.processing.routed)

    async def test_missing_signature_headers_rejects_webhook(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session = _FakeSession()

        payload = _wecom_payload()
        run_agent_mock = AsyncMock(return_value=_agent_response())

        response = await self._run_webhook(
            channel=channel,
            payload=payload,
            headers={},  # no signature headers
            session=session,
            run_agent_mock=run_agent_mock,
        )

        self.assertFalse(response.accepted)
        self.assertFalse(response.signature.valid)
        self.assertIn("Missing", response.signature.reason or "")
        run_agent_mock.assert_not_awaited()
        self.assertEqual("invalid_signature", response.processing.error)

    async def test_agent_runtime_exception_returns_processing_exception(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session = _FakeSession()

        payload = _wecom_payload(text="爆炸")
        headers = _signed_headers(secret=channel.secret, payload=payload)

        sensitive_error = "provider blew up with api_key=sk-leak and base_url=https://llm.internal"
        run_agent_mock = AsyncMock(side_effect=RuntimeError(sensitive_error))

        response = await self._run_webhook(
            channel=channel,
            payload=payload,
            headers=headers,
            session=session,
            run_agent_mock=run_agent_mock,
        )

        # Webhook is still accepted (signature was valid, channel active),
        # but processing failed safely.
        self.assertTrue(response.accepted)
        self.assertIsNotNone(response.processing)
        self.assertFalse(response.processing.routed)
        self.assertEqual("processing_exception", response.processing.error)
        # Sensitive details must not leak into the result surface
        self.assertNotIn("sk-leak", str(response.processing))
        self.assertNotIn("llm.internal", str(response.processing))
        # Session was rolled back on exception
        self.assertGreaterEqual(session.rolled_back, 1)

    async def test_vendor_api_http_error_marks_not_delivered_but_routed(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session = _FakeSession()

        payload = _wecom_payload()
        headers = _signed_headers(secret=channel.secret, payload=payload)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status_code=500, text="internal server error")

        transport = httpx.MockTransport(handler)
        run_agent_mock = AsyncMock(return_value=_agent_response())

        with patch(
            "app.channels.wecom.httpx.AsyncClient",
            side_effect=_async_client_factory(transport),
        ):
            response = await self._run_webhook(
                channel=channel,
                payload=payload,
                headers=headers,
                session=session,
                run_agent_mock=run_agent_mock,
            )

        self.assertTrue(response.accepted)
        self.assertTrue(response.processing.routed)
        delivery = response.processing.outbound_delivery
        self.assertIsNotNone(delivery)
        self.assertTrue(delivery.attempted)
        self.assertFalse(delivery.delivered)
        self.assertEqual("vendor_api_wecom", delivery.mode)

    async def test_vendor_api_wecom_errcode_nonzero_marks_not_delivered(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session = _FakeSession()

        payload = _wecom_payload()
        headers = _signed_headers(secret=channel.secret, payload=payload)

        def handler(request: httpx.Request) -> httpx.Response:
            # 40014 = invalid access_token
            return httpx.Response(
                status_code=200,
                json={"errcode": 40014, "errmsg": "invalid access_token"},
            )

        transport = httpx.MockTransport(handler)
        run_agent_mock = AsyncMock(return_value=_agent_response())

        with patch(
            "app.channels.wecom.httpx.AsyncClient",
            side_effect=_async_client_factory(transport),
        ):
            response = await self._run_webhook(
                channel=channel,
                payload=payload,
                headers=headers,
                session=session,
                run_agent_mock=run_agent_mock,
            )

        self.assertTrue(response.processing.routed)
        delivery = response.processing.outbound_delivery
        self.assertIsNotNone(delivery)
        self.assertTrue(delivery.attempted)
        self.assertFalse(delivery.delivered)
        self.assertEqual(40014, delivery.details.get("wecom_errcode"))
        self.assertEqual("invalid access_token", delivery.details.get("wecom_errmsg"))

    async def test_vendor_api_not_configured_still_routes_agent(self) -> None:
        """When vendor_api credentials are missing, agent still runs but
        outbound is skipped (attempted=False)."""

        channel = _make_channel()
        channel.config = {
            "agent_key": "customer_service",
            "outbound_mode": "vendor_api",
            # no wecom_access_token / wecom_agent_id
        }
        _cache_channel(channel)
        session = _FakeSession()

        payload = _wecom_payload()
        headers = _signed_headers(secret=channel.secret, payload=payload)
        run_agent_mock = AsyncMock(return_value=_agent_response())

        response = await self._run_webhook(
            channel=channel,
            payload=payload,
            headers=headers,
            session=session,
            run_agent_mock=run_agent_mock,
        )

        self.assertTrue(response.processing.routed)
        delivery = response.processing.outbound_delivery
        self.assertIsNotNone(delivery)
        self.assertFalse(delivery.attempted)
        self.assertFalse(delivery.delivered)
        self.assertEqual("vendor_api_not_configured", delivery.mode)
        self.assertEqual("missing_wecom_access_token_or_agent_id", delivery.details["reason"])

    async def test_audit_recorded_on_success_contains_runtime_evidence(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session = _FakeSession()

        payload = _wecom_payload()
        headers = _signed_headers(secret=channel.secret, payload=payload)

        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                status_code=200, json={"errcode": 0, "errmsg": "ok", "msgid": "M1"}
            )
        )
        run_agent_mock = AsyncMock(return_value=_agent_response())

        with patch(
            "app.channels.wecom.httpx.AsyncClient",
            side_effect=_async_client_factory(transport),
        ):
            await self._run_webhook(
                channel=channel,
                payload=payload,
                headers=headers,
                session=session,
                run_agent_mock=run_agent_mock,
            )

        audit_events = [r for r in session.added if isinstance(r, AuditLog)]
        processed = next(
            (row for row in audit_events if row.action == "channel.webhook.processed"),
            None,
        )
        self.assertIsNotNone(processed)
        self.assertEqual("success", processed.status)
        self.assertTrue(processed.details["routed"])
        self.assertEqual("customer_service", processed.details["agent_key"])
        self.assertTrue(processed.details["signature_valid"])
        self.assertTrue(processed.details["signature_checked"])
        self.assertTrue(processed.details["response_present"])
        self.assertIsNotNone(processed.details["outbound_delivery"])
        self.assertTrue(processed.details["outbound_delivery"]["delivered"])

        routed = next(
            (row for row in audit_events if row.action == "channel.message.routed"),
            None,
        )
        self.assertIsNotNone(routed)
        self.assertEqual("qwen-plus", routed.details["model_key"])
        self.assertTrue(routed.details["outbound_delivery"]["delivered"])
        self.assertEqual(20, routed.details["total_tokens"])

    async def test_inactive_channel_does_not_route(self) -> None:
        channel = _make_channel()
        channel.status = ChannelStatus.DISABLED
        _cache_channel(channel)
        session = _FakeSession()

        payload = _wecom_payload()
        headers = _signed_headers(secret=channel.secret, payload=payload)
        run_agent_mock = AsyncMock(return_value=_agent_response())

        response = await self._run_webhook(
            channel=channel,
            payload=payload,
            headers=headers,
            session=session,
            run_agent_mock=run_agent_mock,
        )

        # Disabled channel: signature still valid but webhook not accepted
        self.assertFalse(response.accepted)
        run_agent_mock.assert_not_awaited()
        self.assertIsNotNone(response.processing)
        self.assertFalse(response.processing.routed)
        self.assertEqual("channel_disabled", response.processing.error)


if __name__ == "__main__":
    unittest.main()
