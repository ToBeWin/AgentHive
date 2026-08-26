"""End-to-end integration tests for the DingTalk Channel.

Exercises the full ``receive_channel_webhook`` flow:
  webhook inbound -> signature verification -> normalize -> agent run
  -> outbound delivery via vendor_api (robot_webhook and work_notice).

Mirrors the WeCom E2E suite but covers DingTalk-specific outbound kinds.
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


def _dingtalk_payload(
    *, text: str = "你好", sender: str = "staff001", msg_id: str | None = None
) -> dict[str, Any]:
    return {
        "msgtype": "text",
        "text": {"content": text},
        "senderStaffId": sender,
        "msgId": msg_id or f"msg-{uuid4().hex[:8]}",
        "conversationId": f"cid-{sender}",
    }


def _make_channel(
    *, secret: str = "dingtalk-secret", config: dict[str, Any] | None = None
) -> ChannelRecord:
    return ChannelRecord(
        id=uuid4(),
        tenant_id=uuid4(),
        name="DingTalk Customer Service",
        channel_type=ChannelType.DINGTALK,
        channel_key="dingtalk-corp-1",
        agent_id=uuid4(),
        created_by=uuid4(),
        status=ChannelStatus.ACTIVE,
        config=config
        or {
            "agent_key": "customer_service",
            "outbound_mode": "vendor_api",
            "dingtalk_outbound_kind": "work_notice",
            "dingtalk_access_token": "tok-dt",
            "dingtalk_agent_id": "agent-9",
        },
        secret=secret,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        secret_configured=True,
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
        for conversation in self._pending_conversations:
            conversation.id = uuid4()
        self._pending_conversations.clear()

    async def rollback(self) -> None:
        self.rolled_back += 1


class DingTalkChannelEndToEndTests(unittest.IsolatedAsyncioTestCase):
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
                channel_type=ChannelType.DINGTALK,
                channel_key=channel.channel_key,
                payload=payload,
                headers=headers,
                request_id="req-dt-e2e-1",
            )

    async def test_work_notice_happy_path_routes_and_delivers(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session = _FakeSession()

        payload = _dingtalk_payload(text="我想请假")
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
                json={"errcode": 0, "errmsg": "ok", "task_id": 12345},
            )

        transport = httpx.MockTransport(handler)
        run_agent_mock = AsyncMock(return_value=_agent_response(answer="已为您发起请假流程。"))

        with patch(
            "app.channels.dingtalk.httpx.AsyncClient",
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
        self.assertEqual("customer_service", response.processing.agent_key)
        self.assertEqual("已为您发起请假流程。", response.processing.response_text)

        run_agent_mock.assert_awaited_once()
        run_request = run_agent_mock.await_args.args[2]
        self.assertEqual("我想请假", run_request.input)
        self.assertEqual("staff001", run_request.context["external_user_id"])
        self.assertEqual("channel.dingtalk", run_request.context["source"])

        delivery = response.processing.outbound_delivery
        self.assertIsNotNone(delivery)
        self.assertTrue(delivery.attempted)
        self.assertTrue(delivery.delivered)
        self.assertEqual("vendor_api_dingtalk_work_notice", delivery.mode)
        self.assertEqual(200, delivery.status_code)

        self.assertEqual(1, len(captured))
        self.assertTrue(
            captured[0]["url"].startswith(
                "https://oapi.dingtalk.com/topapi/message/corpconversation/asyncsend_v2"
            ),
            captured[0]["url"],
        )
        self.assertEqual("tok-dt", captured[0]["params"]["access_token"])
        body = captured[0]["body"]
        self.assertIn('"agent_id":"agent-9"', body)
        self.assertIn('"userid_list":"staff001"', body)
        self.assertIn('"content":"已为您发起请假流程。"', body)

        conversations = [r for r in session.added if isinstance(r, ConversationSession)]
        self.assertEqual(1, len(conversations))
        audit_events = [r for r in session.added if isinstance(r, AuditLog)]
        actions = [row.action for row in audit_events]
        self.assertIn("channel.webhook.received", actions)
        self.assertIn("channel.webhook.processed", actions)
        self.assertIn("channel.message.routed", actions)

    async def test_robot_webhook_happy_path_routes_and_delivers(self) -> None:
        channel = _make_channel(
            config={
                "agent_key": "customer_service",
                "outbound_mode": "vendor_api",
                "dingtalk_outbound_kind": "robot_webhook",
                "dingtalk_robot_webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=robot-tok",
            }
        )
        _cache_channel(channel)
        session = _FakeSession()

        payload = _dingtalk_payload(text="群通知")
        headers = _signed_headers(secret=channel.secret, payload=payload)

        captured: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(
                {
                    "url": str(request.url),
                    "body": request.read().decode("utf-8"),
                }
            )
            return httpx.Response(200, json={"errcode": 0, "errmsg": "ok"})

        transport = httpx.MockTransport(handler)
        run_agent_mock = AsyncMock(return_value=_agent_response(answer="已发送群通知。"))

        with patch(
            "app.channels.dingtalk.httpx.AsyncClient",
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
        self.assertTrue(delivery.delivered)
        self.assertEqual("vendor_api_dingtalk_robot", delivery.mode)
        self.assertEqual(1, len(captured))
        self.assertTrue(
            captured[0]["url"].startswith("https://oapi.dingtalk.com/robot/send"),
            captured[0]["url"],
        )
        body = captured[0]["body"]
        self.assertIn('"msgtype":"text"', body)
        self.assertIn('"content":"已发送群通知。"', body)

    async def test_replay_protection_rejects_stale_timestamp(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session = _FakeSession()

        payload = _dingtalk_payload()
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
        run_agent_mock.assert_not_awaited()
        self.assertEqual("invalid_signature", response.processing.error)

    async def test_invalid_signature_rejected_without_routing(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session = _FakeSession()

        payload = _dingtalk_payload()
        headers = _signed_headers(secret=channel.secret, payload=payload)
        headers["X-AgentHive-Signature"] = "sha256=tampered"

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
        run_agent_mock.assert_not_awaited()
        self.assertEqual("invalid_signature", response.processing.error)

    async def test_agent_runtime_exception_returns_processing_exception(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session = _FakeSession()

        payload = _dingtalk_payload(text="爆炸")
        headers = _signed_headers(secret=channel.secret, payload=payload)
        run_agent_mock = AsyncMock(side_effect=RuntimeError("provider api_key=sk-leak failed"))

        response = await self._run_webhook(
            channel=channel,
            payload=payload,
            headers=headers,
            session=session,
            run_agent_mock=run_agent_mock,
        )

        self.assertTrue(response.accepted)
        self.assertFalse(response.processing.routed)
        self.assertEqual("processing_exception", response.processing.error)
        self.assertNotIn("sk-leak", str(response.processing))
        self.assertGreaterEqual(session.rolled_back, 1)

    async def test_work_notice_errcode_nonzero_marks_not_delivered(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session = _FakeSession()

        payload = _dingtalk_payload()
        headers = _signed_headers(secret=channel.secret, payload=payload)

        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json={"errcode": 40078, "errmsg": "invalid userid"})
        )
        run_agent_mock = AsyncMock(return_value=_agent_response())

        with patch(
            "app.channels.dingtalk.httpx.AsyncClient",
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
        self.assertTrue(delivery.attempted)
        self.assertFalse(delivery.delivered)
        self.assertEqual(40078, delivery.details.get("dingtalk_errcode"))
        self.assertEqual("invalid userid", delivery.details.get("dingtalk_errmsg"))

    async def test_work_notice_http_error_marks_not_delivered_but_routed(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session = _FakeSession()

        payload = _dingtalk_payload()
        headers = _signed_headers(secret=channel.secret, payload=payload)

        transport = httpx.MockTransport(lambda req: httpx.Response(500, text="boom"))
        run_agent_mock = AsyncMock(return_value=_agent_response())

        with patch(
            "app.channels.dingtalk.httpx.AsyncClient",
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
        self.assertTrue(delivery.attempted)
        self.assertFalse(delivery.delivered)
        self.assertEqual("vendor_api_dingtalk_work_notice", delivery.mode)

    async def test_vendor_api_not_configured_still_routes_agent(self) -> None:
        channel = _make_channel(
            config={
                "agent_key": "customer_service",
                "outbound_mode": "vendor_api",
                "dingtalk_outbound_kind": "work_notice",
                # missing access_token / agent_id
            }
        )
        _cache_channel(channel)
        session = _FakeSession()

        payload = _dingtalk_payload()
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
        self.assertFalse(delivery.attempted)
        self.assertFalse(delivery.delivered)
        self.assertEqual("vendor_api_not_configured", delivery.mode)
        self.assertEqual("missing_dingtalk_work_notice_credentials", delivery.details["reason"])

    async def test_inactive_channel_does_not_route(self) -> None:
        channel = _make_channel()
        channel.status = ChannelStatus.DISABLED
        _cache_channel(channel)
        session = _FakeSession()

        payload = _dingtalk_payload()
        headers = _signed_headers(secret=channel.secret, payload=payload)
        run_agent_mock = AsyncMock(return_value=_agent_response())

        response = await self._run_webhook(
            channel=channel,
            payload=payload,
            headers=headers,
            session=session,
            run_agent_mock=run_agent_mock,
        )

        self.assertFalse(response.accepted)
        run_agent_mock.assert_not_awaited()
        self.assertEqual("channel_disabled", response.processing.error)

    async def test_audit_recorded_on_success_contains_runtime_evidence(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session = _FakeSession()

        payload = _dingtalk_payload()
        headers = _signed_headers(secret=channel.secret, payload=payload)

        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json={"errcode": 0, "errmsg": "ok"})
        )
        run_agent_mock = AsyncMock(return_value=_agent_response())

        with patch(
            "app.channels.dingtalk.httpx.AsyncClient",
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
        self.assertTrue(processed.details["signature_valid"])
        self.assertTrue(processed.details["outbound_delivery"]["delivered"])

        routed = next(
            (row for row in audit_events if row.action == "channel.message.routed"),
            None,
        )
        self.assertIsNotNone(routed)
        self.assertEqual("qwen-plus", routed.details["model_key"])
        self.assertTrue(routed.details["outbound_delivery"]["delivered"])


if __name__ == "__main__":
    unittest.main()
