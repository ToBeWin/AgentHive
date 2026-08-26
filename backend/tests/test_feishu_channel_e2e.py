"""End-to-end integration tests for the Feishu Channel.

Exercises the full ``receive_channel_webhook`` flow:
  webhook inbound -> signature verification -> normalize -> agent run
  -> outbound delivery via vendor_api (/im/v1/messages).

Mirrors the WeCom/DingTalk E2E suites.
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


def _feishu_payload(
    *, text: str = "你好", open_id: str = "ou_xxx", chat_id: str = "oc_chat1"
) -> dict[str, Any]:
    return {
        "event": {
            "message": {
                "message_id": f"om_{uuid4().hex[:8]}",
                "chat_id": chat_id,
                "message_type": "text",
                "content": text,
            },
            "sender": {
                "sender_id": {"open_id": open_id},
            },
        }
    }


def _make_channel(*, secret: str = "feishu-secret") -> ChannelRecord:
    return ChannelRecord(
        id=uuid4(),
        tenant_id=uuid4(),
        name="Feishu Customer Service",
        channel_type=ChannelType.FEISHU,
        channel_key="feishu-corp-1",
        agent_id=uuid4(),
        created_by=uuid4(),
        status=ChannelStatus.ACTIVE,
        config={
            "agent_key": "customer_service",
            "outbound_mode": "vendor_api",
            "feishu_tenant_access_token": "t-feishu",
            "feishu_receive_id": "ou_xxx",
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


class FeishuChannelEndToEndTests(unittest.IsolatedAsyncioTestCase):
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
                channel_type=ChannelType.FEISHU,
                channel_key=channel.channel_key,
                payload=payload,
                headers=headers,
                request_id="req-feishu-e2e-1",
            )

    async def test_happy_path_routes_and_delivers_via_im_v1_messages(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session = _FakeSession()

        payload = _feishu_payload(text="我想查询订单")
        headers = _signed_headers(secret=channel.secret, payload=payload)

        captured: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(
                {
                    "url": str(request.url),
                    "method": request.method,
                    "body": request.read().decode("utf-8"),
                    "params": dict(request.url.params),
                    "authorization": request.headers.get("authorization"),
                }
            )
            return httpx.Response(
                status_code=200,
                json={"code": 0, "msg": "success", "data": {"message_id": "om_abc"}},
            )

        transport = httpx.MockTransport(handler)
        run_agent_mock = AsyncMock(return_value=_agent_response(answer="您的订单已发货。"))

        with patch(
            "app.channels.feishu.httpx.AsyncClient",
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
        self.assertEqual("您的订单已发货。", response.processing.response_text)

        run_agent_mock.assert_awaited_once()
        run_request = run_agent_mock.await_args.args[2]
        self.assertEqual("我想查询订单", run_request.input)
        self.assertEqual("ou_xxx", run_request.context["external_user_id"])
        self.assertEqual("channel.feishu", run_request.context["source"])

        delivery = response.processing.outbound_delivery
        self.assertIsNotNone(delivery)
        self.assertTrue(delivery.attempted)
        self.assertTrue(delivery.delivered)
        self.assertEqual("vendor_api_feishu", delivery.mode)
        self.assertEqual(200, delivery.status_code)

        self.assertEqual(1, len(captured))
        self.assertTrue(
            captured[0]["url"].startswith("https://open.feishu.cn/open-apis/im/v1/messages"),
            captured[0]["url"],
        )
        self.assertEqual("open_id", captured[0]["params"]["receive_id_type"])
        self.assertEqual("Bearer t-feishu", captured[0]["authorization"])
        body = captured[0]["body"]
        self.assertIn('"receive_id":"ou_xxx"', body)
        self.assertIn('"msg_type":"text"', body)

        conversations = [r for r in session.added if isinstance(r, ConversationSession)]
        self.assertEqual(1, len(conversations))
        audit_events = [r for r in session.added if isinstance(r, AuditLog)]
        actions = [row.action for row in audit_events]
        self.assertIn("channel.webhook.received", actions)
        self.assertIn("channel.webhook.processed", actions)
        self.assertIn("channel.message.routed", actions)

    async def test_replay_protection_rejects_stale_timestamp(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session = _FakeSession()

        payload = _feishu_payload()
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

        payload = _feishu_payload()
        headers = _signed_headers(secret=channel.secret, payload=payload)
        headers["X-AgentHive-Signature"] = "sha256=bogus"

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

    async def test_missing_signature_headers_rejected(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session = _FakeSession()

        payload = _feishu_payload()
        run_agent_mock = AsyncMock(return_value=_agent_response())

        response = await self._run_webhook(
            channel=channel,
            payload=payload,
            headers={},
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

        payload = _feishu_payload(text="爆炸")
        headers = _signed_headers(secret=channel.secret, payload=payload)
        run_agent_mock = AsyncMock(side_effect=RuntimeError("provider api_key=sk-leak exploded"))

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

    async def test_feishu_code_nonzero_marks_not_delivered(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session = _FakeSession()

        payload = _feishu_payload()
        headers = _signed_headers(secret=channel.secret, payload=payload)

        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json={"code": 99991663, "msg": "invalid access token"})
        )
        run_agent_mock = AsyncMock(return_value=_agent_response())

        with patch(
            "app.channels.feishu.httpx.AsyncClient",
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
        self.assertEqual(99991663, delivery.details.get("feishu_code"))
        self.assertEqual("invalid access token", delivery.details.get("feishu_msg"))

    async def test_vendor_api_http_error_marks_not_delivered_but_routed(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session = _FakeSession()

        payload = _feishu_payload()
        headers = _signed_headers(secret=channel.secret, payload=payload)

        transport = httpx.MockTransport(lambda req: httpx.Response(500, text="boom"))
        run_agent_mock = AsyncMock(return_value=_agent_response())

        with patch(
            "app.channels.feishu.httpx.AsyncClient",
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
        self.assertEqual("vendor_api_feishu", delivery.mode)

    async def test_vendor_api_not_configured_still_routes_agent(self) -> None:
        channel = _make_channel()
        channel.config = {
            "agent_key": "customer_service",
            "outbound_mode": "vendor_api",
            # no feishu_tenant_access_token
        }
        _cache_channel(channel)
        session = _FakeSession()

        payload = _feishu_payload()
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
        self.assertEqual("missing_feishu_token_or_recipient", delivery.details["reason"])

    async def test_inactive_channel_does_not_route(self) -> None:
        channel = _make_channel()
        channel.status = ChannelStatus.DISABLED
        _cache_channel(channel)
        session = _FakeSession()

        payload = _feishu_payload()
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

        payload = _feishu_payload()
        headers = _signed_headers(secret=channel.secret, payload=payload)

        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                200, json={"code": 0, "msg": "success", "data": {"message_id": "om_1"}}
            )
        )
        run_agent_mock = AsyncMock(return_value=_agent_response())

        with patch(
            "app.channels.feishu.httpx.AsyncClient",
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

    async def test_dynamic_token_refresh_used_when_static_token_absent(self) -> None:
        """When feishu_app_id+feishu_app_secret are configured (and no static
        token), the adapter fetches a tenant_access_token from the Feishu
        token endpoint and uses it as the Bearer token for /im/v1/messages.
        """

        from app.services.channel_token_service import clear_token_cache

        clear_token_cache()
        channel = _make_channel()
        # Replace static token config with refresh credentials.
        channel.config = {
            "agent_key": "customer_service",
            "outbound_mode": "vendor_api",
            "feishu_app_id": "cli_app1",
            "feishu_app_secret": "secret_app1",
            "feishu_receive_id": "ou_xxx",
        }
        _cache_channel(channel)
        session = _FakeSession()

        payload = _feishu_payload(text="动态token测试")
        headers = _signed_headers(secret=channel.secret, payload=payload)

        captured: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            body = request.read().decode("utf-8")
            captured.append(
                {
                    "url": url,
                    "method": request.method,
                    "body": body,
                    "authorization": request.headers.get("authorization"),
                }
            )
            if "/auth/v3/tenant_access_token/internal" in url:
                return httpx.Response(
                    200,
                    json={
                        "code": 0,
                        "msg": "ok",
                        "tenant_access_token": "t-dynamic-xyz",
                        "expire": 7200,
                    },
                )
            return httpx.Response(
                200,
                json={"code": 0, "msg": "success", "data": {"message_id": "om_dyn"}},
            )

        transport = httpx.MockTransport(handler)
        run_agent_mock = AsyncMock(return_value=_agent_response(answer="动态token已生效"))

        try:
            with (
                patch(
                    "app.channels.feishu.httpx.AsyncClient",
                    side_effect=_async_client_factory(transport),
                ),
                patch(
                    "app.services.channel_token_service.httpx.AsyncClient",
                    side_effect=_async_client_factory(transport),
                ),
            ):
                response = await self._run_webhook(
                    channel=channel,
                    payload=payload,
                    headers=headers,
                    session=session,
                    run_agent_mock=run_agent_mock,
                )
        finally:
            clear_token_cache()

        self.assertTrue(response.accepted)
        delivery = response.processing.outbound_delivery
        self.assertIsNotNone(delivery)
        self.assertTrue(delivery.attempted)
        self.assertTrue(delivery.delivered)
        self.assertEqual("vendor_api_feishu", delivery.mode)

        # Two HTTP calls: token refresh + message send.
        self.assertEqual(2, len(captured))
        token_call = next((c for c in captured if "tenant_access_token/internal" in c["url"]), None)
        message_call = next((c for c in captured if "/im/v1/messages" in c["url"]), None)
        self.assertIsNotNone(token_call)
        self.assertIsNotNone(message_call)
        # Token endpoint is POST with JSON body containing app_id/app_secret.
        self.assertEqual("POST", token_call["method"])
        self.assertIn('"app_id":"cli_app1"', token_call["body"])
        self.assertIn('"app_secret":"secret_app1"', token_call["body"])
        # Message endpoint uses the dynamically fetched token as Bearer.
        self.assertEqual("Bearer t-dynamic-xyz", message_call["authorization"])


if __name__ == "__main__":
    unittest.main()
