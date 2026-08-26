"""Unit tests for ``push_to_channel_for_tenant`` — proactive channel push API.

Covers DIRECT and AGENT modes across WeCom/DingTalk/Feishu vendor APIs,
plus channel-disabled, agent failure, vendor not-configured, audit evidence,
and conversation key resolution.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import httpx

from app.models.audit_log import AuditLog
from app.schemas.agents import AgentRunResponse
from app.schemas.channel import (
    ChannelPushMode,
    ChannelPushRequest,
    ChannelStatus,
    ChannelType,
)
from app.schemas.llm import LLMUsageResponse
from app.services.channel_service import (
    ChannelRecord,
    _cache_channel,
    _channel_index,
    _channels_by_tenant,
    push_to_channel_for_tenant,
)


_REAL_ASYNC_CLIENT = httpx.AsyncClient


def _async_client_factory(transport: httpx.MockTransport):
    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("transport", None)
        return _REAL_ASYNC_CLIENT(*args, **kwargs, transport=transport)

    return factory


def _make_channel(
    *,
    channel_type: ChannelType = ChannelType.WECOM,
    config: dict[str, Any] | None = None,
    status: ChannelStatus = ChannelStatus.ACTIVE,
    agent_id: UUID | None = None,
) -> ChannelRecord:
    return ChannelRecord(
        id=uuid4(),
        tenant_id=uuid4(),
        name=f"{channel_type.value}-push-test",
        channel_type=channel_type,
        channel_key=f"{channel_type.value}-corp-1",
        agent_id=agent_id or uuid4(),
        created_by=uuid4(),
        status=status,
        config=config
        or {
            "agent_key": "customer_service",
            "outbound_mode": "vendor_api",
            "wecom_corp_id": "corp-1",
            "wecom_agent_id": "1000001",
            "wecom_secret": "wecom-secret",
            "wecom_access_token": "tok-1",
            "wecom_default_user": "@all",
        },
        secret="any",
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

    async def execute(self, *_args: Any, **_kwargs: Any) -> _FakeResult:
        return _FakeResult()

    def add(self, value: Any) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.committed += 1

    async def rollback(self) -> None:
        self.rolled_back += 1

    async def get(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class ChannelPushTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        _channels_by_tenant.clear()
        _channel_index.clear()

    async def _push(
        self,
        *,
        channel: ChannelRecord,
        request: ChannelPushRequest,
        session: _FakeSession,
        run_agent_mock: AsyncMock | None = None,
        actor_id: UUID | None = None,
    ) -> Any:
        cm = patch("app.services.channel_service.run_agent", new=run_agent_mock)
        with cm:
            return await push_to_channel_for_tenant(
                session,
                tenant_id=channel.tenant_id,
                channel_id=channel.id,
                request=request,
                actor_id=actor_id or uuid4(),
                request_id="req-push-1",
            )

    async def test_direct_mode_delivers_text_verbatim_via_wecom_vendor_api(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session = _FakeSession()

        captured: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(
                {
                    "url": str(request.url),
                    "body": request.read().decode("utf-8"),
                    "params": dict(request.url.params),
                }
            )
            return httpx.Response(200, json={"errcode": 0, "errmsg": "ok"})

        transport = httpx.MockTransport(handler)
        run_agent_mock = AsyncMock(return_value=_agent_response())

        with patch(
            "app.channels.wecom.httpx.AsyncClient",
            side_effect=_async_client_factory(transport),
        ):
            response = await self._push(
                channel=channel,
                request=ChannelPushRequest(
                    external_user_id="user001",
                    text="系统将于今晚 22:00 进行维护。",
                    mode=ChannelPushMode.DIRECT,
                ),
                session=session,
                run_agent_mock=run_agent_mock,
            )

        # DIRECT mode must NOT call the agent runtime
        run_agent_mock.assert_not_awaited()
        self.assertFalse(response.agent_invoked)
        self.assertIsNone(response.agent_key)
        self.assertEqual(ChannelPushMode.DIRECT, response.mode)
        self.assertTrue(response.delivered)
        # WeCom body is JSON: {"touser":...,"text":{"content":"..."}}
        self.assertIn('"touser":"user001"', captured[0]["body"])
        self.assertIn('"content":"系统将于今晚 22:00 进行维护。"', captured[0]["body"])
        self.assertEqual("tok-1", captured[0]["params"]["access_token"])
        self.assertEqual("wecom:wecom-corp-1:user001", response.conversation_key)
        # Audit must reflect DIRECT, delivered, no agent invocation
        audit_events = [r for r in session.added if isinstance(r, AuditLog)]
        push_audit = next((row for row in audit_events if row.action == "channel.push"), None)
        self.assertIsNotNone(push_audit)
        self.assertEqual("success", push_audit.status)
        self.assertEqual("direct", push_audit.details["push_mode"])
        self.assertTrue(push_audit.details["delivered"])
        self.assertFalse(push_audit.details["agent_invoked"])

    async def test_agent_mode_invokes_agent_and_delivers_response(self) -> None:
        channel = _make_channel(
            config={
                "agent_key": "customer_service",
                "outbound_mode": "vendor_api",
                "wecom_corp_id": "corp-1",
                "wecom_agent_id": "1000001",
                "wecom_secret": "wecom-secret",
                "wecom_access_token": "tok-1",
                "wecom_default_user": "@all",
                "model_key": "qwen-plus",
            }
        )
        _cache_channel(channel)
        session = _FakeSession()

        captured: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request.read().decode("utf-8"))
            return httpx.Response(200, json={"errcode": 0, "errmsg": "ok"})

        transport = httpx.MockTransport(handler)
        run_agent_mock = AsyncMock(return_value=_agent_response(answer="您好，今日订单 12 单。"))

        with patch(
            "app.channels.wecom.httpx.AsyncClient",
            side_effect=_async_client_factory(transport),
        ):
            response = await self._push(
                channel=channel,
                request=ChannelPushRequest(
                    external_user_id="user002",
                    text="总结今日订单",
                    mode=ChannelPushMode.AGENT,
                ),
                session=session,
                run_agent_mock=run_agent_mock,
            )

        run_agent_mock.assert_awaited_once()
        # The agent's response (not the input) must be what's delivered.
        # WeCom body is JSON; check the content field.
        self.assertIn('"content":"您好，今日订单 12 单。"', captured[0])
        self.assertTrue(response.agent_invoked)
        self.assertEqual("customer_service", response.agent_key)
        self.assertEqual("您好，今日订单 12 单。", response.response_text)
        self.assertTrue(response.delivered)

        # Agent invocation context should include push-specific metadata
        run_request = run_agent_mock.await_args.args[2]
        self.assertEqual("user002", run_request.context["external_user_id"])
        self.assertEqual("channel_push.wecom", run_request.context["source"])
        self.assertEqual("agent", run_request.context["push_mode"])

    async def test_agent_mode_with_agent_key_override_uses_override(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session = _FakeSession()

        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json={"errcode": 0, "errmsg": "ok"})
        )
        run_agent_mock = AsyncMock(return_value=_agent_response(answer="已通知。"))

        with patch(
            "app.channels.wecom.httpx.AsyncClient",
            side_effect=_async_client_factory(transport),
        ):
            response = await self._push(
                channel=channel,
                request=ChannelPushRequest(
                    external_user_id="user003",
                    text="通知",
                    mode=ChannelPushMode.AGENT,
                    agent_key="ops_alert_agent",
                ),
                session=session,
                run_agent_mock=run_agent_mock,
            )

        run_agent_mock.assert_awaited_once()
        # The first positional arg to run_agent is the agent_key
        self.assertEqual("ops_alert_agent", run_agent_mock.await_args.args[1])
        self.assertEqual("ops_alert_agent", response.agent_key)

    async def test_disabled_channel_returns_error_without_invoking_agent_or_vendor(self) -> None:
        channel = _make_channel(status=ChannelStatus.DISABLED)
        _cache_channel(channel)
        session = _FakeSession()

        run_agent_mock = AsyncMock(return_value=_agent_response())
        vendor_called: list[Any] = []

        with patch(
            "app.channels.wecom.httpx.AsyncClient",
            side_effect=lambda *a, **k: vendor_called.append(1) or _REAL_ASYNC_CLIENT(*a, **k),
        ):
            response = await self._push(
                channel=channel,
                request=ChannelPushRequest(
                    external_user_id="user004",
                    text="hello",
                    mode=ChannelPushMode.AGENT,
                ),
                session=session,
                run_agent_mock=run_agent_mock,
            )

        self.assertFalse(response.delivered)
        self.assertEqual("channel_disabled", response.error)
        run_agent_mock.assert_not_awaited()
        self.assertEqual(0, len(vendor_called))
        # Audit failure recorded
        audit_events = [r for r in session.added if isinstance(r, AuditLog)]
        push_audit = next((row for row in audit_events if row.action == "channel.push"), None)
        self.assertIsNotNone(push_audit)
        self.assertEqual("failure", push_audit.status)
        self.assertEqual("channel_disabled", push_audit.details["error"])

    async def test_agent_runtime_failure_isolated_from_delivery(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session = _FakeSession()

        run_agent_mock = AsyncMock(side_effect=RuntimeError("provider api_key=sk-leak invalid"))
        vendor_called: list[Any] = []

        with patch(
            "app.channels.wecom.httpx.AsyncClient",
            side_effect=lambda *a, **k: vendor_called.append(1) or _REAL_ASYNC_CLIENT(*a, **k),
        ):
            response = await self._push(
                channel=channel,
                request=ChannelPushRequest(
                    external_user_id="user005",
                    text="爆炸",
                    mode=ChannelPushMode.AGENT,
                ),
                session=session,
                run_agent_mock=run_agent_mock,
            )

        self.assertFalse(response.delivered)
        self.assertTrue(response.agent_invoked)
        self.assertEqual("processing_exception", response.error)
        self.assertNotIn("sk-leak", response.error or "")
        self.assertNotIn("sk-leak", str(response))
        self.assertEqual(0, len(vendor_called))
        self.assertGreaterEqual(session.rolled_back, 1)
        # Audit failure must not leak the secret either
        audit_events = [r for r in session.added if isinstance(r, AuditLog)]
        push_audit = next((row for row in audit_events if row.action == "channel.push"), None)
        self.assertIsNotNone(push_audit)
        self.assertNotIn("sk-leak", str(push_audit.details))

    async def test_vendor_api_not_configured_returns_not_delivered_with_reason(self) -> None:
        channel = _make_channel(
            config={
                "agent_key": "customer_service",
                "outbound_mode": "vendor_api",
                # No vendor credentials
            }
        )
        _cache_channel(channel)
        session = _FakeSession()

        response = await self._push(
            channel=channel,
            request=ChannelPushRequest(
                external_user_id="user006",
                text="hello",
                mode=ChannelPushMode.DIRECT,
            ),
            session=session,
            run_agent_mock=AsyncMock(),
        )

        self.assertFalse(response.delivered)
        self.assertIsNotNone(response.outbound_delivery)
        self.assertFalse(response.outbound_delivery.attempted)
        self.assertFalse(response.outbound_delivery.delivered)
        self.assertEqual("vendor_api_not_configured", response.outbound_delivery.mode)

    async def test_dingtalk_work_notice_direct_push_delivers(self) -> None:
        channel = _make_channel(
            channel_type=ChannelType.DINGTALK,
            config={
                "agent_key": "customer_service",
                "outbound_mode": "vendor_api",
                "dingtalk_outbound_kind": "work_notice",
                "dingtalk_access_token": "tok-dt",
                "dingtalk_agent_id": "agent-9",
            },
        )
        _cache_channel(channel)
        session = _FakeSession()

        captured: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(
                {
                    "url": str(request.url),
                    "body": request.read().decode("utf-8"),
                    "params": dict(request.url.params),
                }
            )
            return httpx.Response(200, json={"errcode": 0, "errmsg": "ok"})

        transport = httpx.MockTransport(handler)
        run_agent_mock = AsyncMock(return_value=_agent_response())

        with patch(
            "app.channels.dingtalk.httpx.AsyncClient",
            side_effect=_async_client_factory(transport),
        ):
            response = await self._push(
                channel=channel,
                request=ChannelPushRequest(
                    external_user_id="staff001",
                    text="钉钉工作通知测试",
                    mode=ChannelPushMode.DIRECT,
                ),
                session=session,
                run_agent_mock=run_agent_mock,
            )

        run_agent_mock.assert_not_awaited()
        self.assertTrue(response.delivered)
        self.assertEqual(ChannelType.DINGTALK, response.channel_type)
        self.assertEqual(1, len(captured))
        self.assertTrue(
            captured[0]["url"].startswith(
                "https://oapi.dingtalk.com/topapi/message/corpconversation/asyncsend_v2"
            ),
            captured[0]["url"],
        )
        self.assertEqual("tok-dt", captured[0]["params"]["access_token"])
        self.assertIn('"userid_list":"staff001"', captured[0]["body"])
        self.assertIn("钉钉工作通知测试", captured[0]["body"])

    async def test_feishu_agent_push_uses_agent_response_text(self) -> None:
        channel = _make_channel(
            channel_type=ChannelType.FEISHU,
            config={
                "agent_key": "customer_service",
                "outbound_mode": "vendor_api",
                "feishu_tenant_access_token": "t-feishu",
            },
        )
        _cache_channel(channel)
        session = _FakeSession()

        captured: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request.read().decode("utf-8"))
            return httpx.Response(
                200, json={"code": 0, "msg": "success", "data": {"message_id": "om_1"}}
            )

        transport = httpx.MockTransport(handler)
        run_agent_mock = AsyncMock(return_value=_agent_response(answer="您的预约已确认。"))

        with patch(
            "app.channels.feishu.httpx.AsyncClient",
            side_effect=_async_client_factory(transport),
        ):
            response = await self._push(
                channel=channel,
                request=ChannelPushRequest(
                    external_user_id="ou_xxx",
                    text="预约",
                    mode=ChannelPushMode.AGENT,
                ),
                session=session,
                run_agent_mock=run_agent_mock,
            )

        run_agent_mock.assert_awaited_once()
        self.assertTrue(response.delivered)
        self.assertEqual("您的预约已确认。", response.response_text)
        # Feishu body must contain the agent response, not the input "预约"
        self.assertIn("您的预约已确认。", captured[0])
        self.assertNotIn('"content":"预约"', captured[0])

    async def test_custom_conversation_key_is_preserved(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session = _FakeSession()

        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json={"errcode": 0, "errmsg": "ok"})
        )

        with patch(
            "app.channels.wecom.httpx.AsyncClient",
            side_effect=_async_client_factory(transport),
        ):
            response = await self._push(
                channel=channel,
                request=ChannelPushRequest(
                    external_user_id="user007",
                    text="hello",
                    mode=ChannelPushMode.DIRECT,
                    conversation_key="custom:flow:abc",
                ),
                session=session,
                run_agent_mock=AsyncMock(),
            )

        self.assertEqual("custom:flow:abc", response.conversation_key)

    async def test_caller_metadata_surfaces_in_outbound_raw_payload_via_audit(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session = _FakeSession()

        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json={"errcode": 0, "errmsg": "ok"})
        )

        with patch(
            "app.channels.wecom.httpx.AsyncClient",
            side_effect=_async_client_factory(transport),
        ):
            response = await self._push(
                channel=channel,
                request=ChannelPushRequest(
                    external_user_id="user008",
                    text="hello",
                    mode=ChannelPushMode.DIRECT,
                    metadata={"campaign_id": "summer-2026", "source_system": "crm"},
                ),
                session=session,
                run_agent_mock=AsyncMock(),
            )

        self.assertTrue(response.delivered)
        audit_events = [r for r in session.added if isinstance(r, AuditLog)]
        push_audit = next((row for row in audit_events if row.action == "channel.push"), None)
        self.assertIsNotNone(push_audit)
        self.assertEqual(
            ["campaign_id", "source_system"],
            push_audit.details["caller_metadata_keys"],
        )

    async def test_vendor_http_error_marks_not_delivered(self) -> None:
        channel = _make_channel()
        _cache_channel(channel)
        session = _FakeSession()

        transport = httpx.MockTransport(lambda req: httpx.Response(500, text="boom"))

        with patch(
            "app.channels.wecom.httpx.AsyncClient",
            side_effect=_async_client_factory(transport),
        ):
            response = await self._push(
                channel=channel,
                request=ChannelPushRequest(
                    external_user_id="user009",
                    text="hello",
                    mode=ChannelPushMode.DIRECT,
                ),
                session=session,
                run_agent_mock=AsyncMock(),
            )

        self.assertFalse(response.delivered)
        self.assertTrue(response.outbound_delivery.attempted)
        self.assertEqual(500, response.outbound_delivery.status_code)


if __name__ == "__main__":
    unittest.main()
