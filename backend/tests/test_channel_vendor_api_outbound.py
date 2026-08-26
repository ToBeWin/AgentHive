from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import httpx

from app.channels.dingtalk import DingTalkChannelAdapter
from app.channels.feishu import FeishuChannelAdapter
from app.channels.wecom import WeComChannelAdapter
from app.schemas.channel import (
    ChannelMessageType,
    ChannelType,
    OutboundMessage,
)


def _make_outbound(
    *,
    channel_type: ChannelType,
    text: str,
    external_user_id: str | None = "user-1",
    conversation_key: str | None = None,
) -> OutboundMessage:
    return OutboundMessage(
        tenant_id=uuid4(),
        channel_type=channel_type,
        channel_key=f"{channel_type.value}-test",
        direction="outbound",
        external_user_id=external_user_id,
        external_message_id=None,
        conversation_key=conversation_key or f"{channel_type.value}:test:user-1",
        message_type=ChannelMessageType.TEXT,
        text=text,
        received_at=datetime.now(timezone.utc),
    )


def _async_client_factory(transport: httpx.MockTransport):
    """Build a side_effect that returns a real AsyncClient bound to transport."""

    # Capture the real AsyncClient before patching takes effect so the factory
    # does not recurse through the mock.
    real_async_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs.pop("transport", None)
        return real_async_client(*args, **kwargs, transport=transport)

    return factory


class WeComVendorApiOutboundTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_credentials_returns_not_configured(self) -> None:
        adapter = WeComChannelAdapter()
        message = _make_outbound(channel_type=ChannelType.WECOM, text="hi")
        result = await adapter.send_outbound(
            channel_config={"outbound_mode": "vendor_api"},
            message=message,
            request_id="req-1",
        )
        self.assertFalse(result.attempted)
        self.assertFalse(result.delivered)
        self.assertEqual("vendor_api_not_configured", result.mode)
        self.assertEqual("missing_wecom_access_token_or_agent_id", result.details["reason"])

    async def test_missing_recipient_returns_not_configured(self) -> None:
        adapter = WeComChannelAdapter()
        message = _make_outbound(channel_type=ChannelType.WECOM, text="hi", external_user_id=None)
        result = await adapter.send_outbound(
            channel_config={
                "outbound_mode": "vendor_api",
                "wecom_access_token": "tok",
                "wecom_agent_id": 1000002,
            },
            message=message,
            request_id="req-1",
        )
        self.assertFalse(result.attempted)
        self.assertEqual("missing_recipient_user_id", result.details["reason"])

    async def test_success_path_sends_to_wecom_message_send(self) -> None:
        captured: list[dict[str, object]] = []

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
                json={"errcode": 0, "errmsg": "ok", "msgid": "MSG-1"},
            )

        transport = httpx.MockTransport(handler)
        adapter = WeComChannelAdapter()
        message = _make_outbound(channel_type=ChannelType.WECOM, text="你好")
        with patch(
            "app.channels.wecom.httpx.AsyncClient",
            side_effect=_async_client_factory(transport),
        ):
            result = await adapter.send_outbound(
                channel_config={
                    "outbound_mode": "vendor_api",
                    "wecom_access_token": "tok-1",
                    "wecom_agent_id": 1000002,
                    "wecom_to_user": "StaffA",
                },
                message=message,
                request_id="req-1",
            )

        self.assertTrue(result.attempted)
        self.assertTrue(result.delivered)
        self.assertEqual("vendor_api_wecom", result.mode)
        self.assertEqual(200, result.status_code)
        self.assertTrue(
            captured[0]["url"].startswith("https://qyapi.weixin.qq.com/cgi-bin/message/send"),
            captured[0]["url"],
        )
        self.assertEqual("POST", captured[0]["method"])
        self.assertEqual("tok-1", captured[0]["params"]["access_token"])
        body = captured[0]["body"]
        self.assertIn('"touser":"StaffA"', body)
        self.assertIn('"agentid":1000002', body)
        self.assertIn('"content":"你好"', body)

    async def test_wecom_errcode_nonzero_marks_not_delivered(self) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                status_code=200,
                json={"errcode": 40014, "errmsg": "invalid access_token"},
            )
        )
        adapter = WeComChannelAdapter()
        message = _make_outbound(channel_type=ChannelType.WECOM, text="hi")
        with patch(
            "app.channels.wecom.httpx.AsyncClient",
            side_effect=_async_client_factory(transport),
        ):
            result = await adapter.send_outbound(
                channel_config={
                    "outbound_mode": "vendor_api",
                    "wecom_access_token": "bad",
                    "wecom_agent_id": 1000002,
                },
                message=message,
                request_id="req-1",
            )
        self.assertTrue(result.attempted)
        self.assertFalse(result.delivered)
        self.assertEqual(40014, result.details["wecom_errcode"])
        self.assertEqual("invalid access_token", result.details["wecom_errmsg"])

    async def test_http_error_returns_error_result(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        transport = httpx.MockTransport(handler)
        adapter = WeComChannelAdapter()
        message = _make_outbound(channel_type=ChannelType.WECOM, text="hi")
        with patch(
            "app.channels.wecom.httpx.AsyncClient",
            side_effect=_async_client_factory(transport),
        ):
            result = await adapter.send_outbound(
                channel_config={
                    "outbound_mode": "vendor_api",
                    "wecom_access_token": "tok",
                    "wecom_agent_id": 1000002,
                },
                message=message,
                request_id="req-1",
            )
        self.assertTrue(result.attempted)
        self.assertFalse(result.delivered)
        self.assertEqual("ConnectError", result.error)


class DingTalkRobotWebhookOutboundTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_webhook_url_returns_not_configured(self) -> None:
        adapter = DingTalkChannelAdapter()
        message = _make_outbound(channel_type=ChannelType.DINGTALK, text="hi")
        result = await adapter.send_outbound(
            channel_config={"outbound_mode": "vendor_api"},
            message=message,
            request_id="req-1",
        )
        self.assertFalse(result.attempted)
        self.assertEqual("missing_dingtalk_robot_webhook_url", result.details["reason"])

    async def test_robot_webhook_success_without_secret(self) -> None:
        captured: list[dict[str, object]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(
                {
                    "url": str(request.url),
                    "method": request.method,
                    "body": request.read().decode("utf-8"),
                }
            )
            return httpx.Response(status_code=200, json={"errcode": 0, "errmsg": "ok"})

        transport = httpx.MockTransport(handler)
        adapter = DingTalkChannelAdapter()
        message = _make_outbound(channel_type=ChannelType.DINGTALK, text="通知")
        with patch(
            "app.channels.dingtalk.httpx.AsyncClient",
            side_effect=_async_client_factory(transport),
        ):
            result = await adapter.send_outbound(
                channel_config={
                    "outbound_mode": "vendor_api",
                    "dingtalk_outbound_kind": "robot_webhook",
                    "dingtalk_robot_webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=tok",
                },
                message=message,
                request_id="req-1",
            )

        self.assertTrue(result.attempted)
        self.assertTrue(result.delivered)
        self.assertEqual("vendor_api_dingtalk_robot", result.mode)
        self.assertEqual(
            "https://oapi.dingtalk.com/robot/send?access_token=tok",
            captured[0]["url"],
        )
        self.assertIn('"msgtype":"text"', captured[0]["body"])
        self.assertIn('"content":"通知"', captured[0]["body"])

    async def test_robot_webhook_with_secret_appends_signed_query(self) -> None:
        captured: list[dict[str, object]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(
                {
                    "url": str(request.url),
                    "params": dict(request.url.params),
                }
            )
            return httpx.Response(status_code=200, json={"errcode": 0, "errmsg": "ok"})

        transport = httpx.MockTransport(handler)
        adapter = DingTalkChannelAdapter()
        message = _make_outbound(channel_type=ChannelType.DINGTALK, text="hi")
        with patch(
            "app.channels.dingtalk.httpx.AsyncClient",
            side_effect=_async_client_factory(transport),
        ):
            result = await adapter.send_outbound(
                channel_config={
                    "outbound_mode": "vendor_api",
                    "dingtalk_robot_webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=tok",
                    "dingtalk_robot_secret": "SEC-xxx",
                },
                message=message,
                request_id="req-1",
            )

        self.assertTrue(result.delivered)
        params = captured[0]["params"]
        self.assertIn("timestamp", params)
        self.assertIn("sign", params)
        self.assertEqual("tok", params["access_token"])

    async def test_robot_webhook_errcode_nonzero_not_delivered(self) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                status_code=200,
                json={"errcode": 310000, "errmsg": "keyword not match"},
            )
        )
        adapter = DingTalkChannelAdapter()
        message = _make_outbound(channel_type=ChannelType.DINGTALK, text="hi")
        with patch(
            "app.channels.dingtalk.httpx.AsyncClient",
            side_effect=_async_client_factory(transport),
        ):
            result = await adapter.send_outbound(
                channel_config={
                    "outbound_mode": "vendor_api",
                    "dingtalk_robot_webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=tok",
                },
                message=message,
                request_id="req-1",
            )
        self.assertFalse(result.delivered)
        self.assertEqual(310000, result.details["dingtalk_errcode"])


class DingTalkWorkNoticeOutboundTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_credentials_returns_not_configured(self) -> None:
        adapter = DingTalkChannelAdapter()
        message = _make_outbound(channel_type=ChannelType.DINGTALK, text="hi")
        result = await adapter.send_outbound(
            channel_config={
                "outbound_mode": "vendor_api",
                "dingtalk_outbound_kind": "work_notice",
            },
            message=message,
            request_id="req-1",
        )
        self.assertFalse(result.attempted)
        self.assertEqual("missing_dingtalk_work_notice_credentials", result.details["reason"])

    async def test_work_notice_success_sends_to_asyncsend_v2(self) -> None:
        captured: list[dict[str, object]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(
                {
                    "url": str(request.url),
                    "params": dict(request.url.params),
                    "body": request.read().decode("utf-8"),
                }
            )
            return httpx.Response(
                status_code=200,
                json={"errcode": 0, "errmsg": "ok", "task_id": 123},
            )

        transport = httpx.MockTransport(handler)
        adapter = DingTalkChannelAdapter()
        message = _make_outbound(channel_type=ChannelType.DINGTALK, text="hello")
        with patch(
            "app.channels.dingtalk.httpx.AsyncClient",
            side_effect=_async_client_factory(transport),
        ):
            result = await adapter.send_outbound(
                channel_config={
                    "outbound_mode": "vendor_api",
                    "dingtalk_outbound_kind": "work_notice",
                    "dingtalk_access_token": "tok-2",
                    "dingtalk_agent_id": "agent-9",
                    "dingtalk_userid_list": "staff001",
                },
                message=message,
                request_id="req-1",
            )

        self.assertTrue(result.delivered)
        self.assertEqual("vendor_api_dingtalk_work_notice", result.mode)
        self.assertTrue(
            captured[0]["url"].startswith(
                "https://oapi.dingtalk.com/topapi/message/corpconversation/asyncsend_v2"
            ),
            captured[0]["url"],
        )
        self.assertEqual("tok-2", captured[0]["params"]["access_token"])
        body = captured[0]["body"]
        self.assertIn('"agent_id":"agent-9"', body)
        self.assertIn('"userid_list":"staff001"', body)
        self.assertIn('"msgtype":"text"', body)

    async def test_work_notice_falls_back_to_external_user_id(self) -> None:
        captured: list[dict[str, object]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append({"body": request.read().decode("utf-8")})
            return httpx.Response(status_code=200, json={"errcode": 0, "errmsg": "ok"})

        transport = httpx.MockTransport(handler)
        adapter = DingTalkChannelAdapter()
        message = _make_outbound(
            channel_type=ChannelType.DINGTALK, text="hi", external_user_id="from-msg"
        )
        with patch(
            "app.channels.dingtalk.httpx.AsyncClient",
            side_effect=_async_client_factory(transport),
        ):
            result = await adapter.send_outbound(
                channel_config={
                    "outbound_mode": "vendor_api",
                    "dingtalk_outbound_kind": "work_notice",
                    "dingtalk_access_token": "tok-2",
                    "dingtalk_agent_id": 9,
                },
                message=message,
                request_id="req-1",
            )

        self.assertTrue(result.delivered)
        self.assertIn('"userid_list":"from-msg"', captured[0]["body"])


class FeishuVendorApiOutboundTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_token_returns_not_configured(self) -> None:
        adapter = FeishuChannelAdapter()
        message = _make_outbound(channel_type=ChannelType.FEISHU, text="hi")
        result = await adapter.send_outbound(
            channel_config={"outbound_mode": "vendor_api"},
            message=message,
            request_id="req-1",
        )
        self.assertFalse(result.attempted)
        self.assertEqual("missing_feishu_token_or_recipient", result.details["reason"])

    async def test_success_path_sends_to_im_v1_messages(self) -> None:
        captured: list[dict[str, object]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(
                {
                    "url": str(request.url),
                    "params": dict(request.url.params),
                    "authorization": request.headers.get("authorization"),
                    "body": request.read().decode("utf-8"),
                }
            )
            return httpx.Response(
                status_code=200,
                json={
                    "code": 0,
                    "msg": "success",
                    "data": {"message_id": "om_abc"},
                },
            )

        transport = httpx.MockTransport(handler)
        adapter = FeishuChannelAdapter()
        message = _make_outbound(channel_type=ChannelType.FEISHU, text="你好")
        with patch(
            "app.channels.feishu.httpx.AsyncClient",
            side_effect=_async_client_factory(transport),
        ):
            result = await adapter.send_outbound(
                channel_config={
                    "outbound_mode": "vendor_api",
                    "feishu_tenant_access_token": "t-feishu",
                    "feishu_receive_id": "ou_xxx",
                },
                message=message,
                request_id="req-1",
            )

        self.assertTrue(result.delivered)
        self.assertEqual("vendor_api_feishu", result.mode)
        self.assertTrue(
            captured[0]["url"].startswith("https://open.feishu.cn/open-apis/im/v1/messages"),
            captured[0]["url"],
        )
        self.assertEqual("open_id", captured[0]["params"]["receive_id_type"])
        self.assertEqual("Bearer t-feishu", captured[0]["authorization"])
        body = captured[0]["body"]
        self.assertIn('"receive_id":"ou_xxx"', body)
        self.assertIn('"msg_type":"text"', body)
        # content field must be JSON-encoded string
        self.assertIn('"content":"{\\"text\\": \\"你好\\"}"', body)

    async def test_chat_id_mode_falls_back_to_conversation_key(self) -> None:
        captured: list[dict[str, object]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(
                {"params": dict(request.url.params), "body": request.read().decode("utf-8")}
            )
            return httpx.Response(status_code=200, json={"code": 0, "msg": "ok"})

        transport = httpx.MockTransport(handler)
        adapter = FeishuChannelAdapter()
        message = _make_outbound(
            channel_type=ChannelType.FEISHU,
            text="hi",
            conversation_key="oc_chat_123",
            external_user_id=None,
        )
        with patch(
            "app.channels.feishu.httpx.AsyncClient",
            side_effect=_async_client_factory(transport),
        ):
            result = await adapter.send_outbound(
                channel_config={
                    "outbound_mode": "vendor_api",
                    "feishu_tenant_access_token": "t-feishu",
                    "feishu_receive_id_type": "chat_id",
                },
                message=message,
                request_id="req-1",
            )
        self.assertTrue(result.delivered)
        self.assertEqual("chat_id", captured[0]["params"]["receive_id_type"])
        self.assertIn('"receive_id":"oc_chat_123"', captured[0]["body"])

    async def test_feishu_code_nonzero_not_delivered(self) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                status_code=200,
                json={"code": 99991663, "msg": "token invalid"},
            )
        )
        adapter = FeishuChannelAdapter()
        message = _make_outbound(channel_type=ChannelType.FEISHU, text="hi")
        with patch(
            "app.channels.feishu.httpx.AsyncClient",
            side_effect=_async_client_factory(transport),
        ):
            result = await adapter.send_outbound(
                channel_config={
                    "outbound_mode": "vendor_api",
                    "feishu_tenant_access_token": "bad",
                    "feishu_receive_id": "ou_xxx",
                },
                message=message,
                request_id="req-1",
            )
        self.assertFalse(result.delivered)
        self.assertEqual(99991663, result.details["feishu_code"])
        self.assertEqual("token invalid", result.details["feishu_msg"])


class OutboundModeRoutingTests(unittest.IsolatedAsyncioTestCase):
    """Base class routing: outbound_mode defaults to outbound_webhook."""

    async def test_default_mode_uses_webhook(self) -> None:
        adapter = WeComChannelAdapter()
        message = _make_outbound(channel_type=ChannelType.WECOM, text="hi")
        # No outbound_webhook_url configured → not_configured. We just want to
        # confirm it does NOT route to vendor_api (which would return
        # vendor_api_not_configured with a different reason).
        result = await adapter.send_outbound(
            channel_config={},
            message=message,
            request_id="req-1",
        )
        self.assertEqual("not_configured", result.mode)
        self.assertEqual("outbound_webhook_url_not_configured", result.details["reason"])

    async def test_explicit_outbound_webhook_mode_routes_to_webhook(self) -> None:
        adapter = WeComChannelAdapter()
        message = _make_outbound(channel_type=ChannelType.WECOM, text="hi")
        result = await adapter.send_outbound(
            channel_config={"outbound_mode": "outbound_webhook"},
            message=message,
            request_id="req-1",
        )
        self.assertEqual("not_configured", result.mode)


class BaseVendorApiNotSupportedTests(unittest.IsolatedAsyncioTestCase):
    """Channels without vendor API override must report not_supported.

    WebWidget and RestAPI override send_outbound entirely (they return
    webhook_ack when no outbound_webhook_url is set), so we use a minimal
    adapter that only inherits BaseChannelAdapter's routing to verify the
    default vendor_api path returns not_supported.
    """

    async def test_default_vendor_api_path_returns_not_supported(self) -> None:
        from app.channels.base import BaseChannelAdapter

        class _MinimalAdapter(BaseChannelAdapter):
            channel_type = ChannelType.REST_API
            signature_method = "test"

            async def normalize_inbound(
                self,
                *,
                tenant_id,
                channel_id,
                channel_key,
                payload,
                headers,
                signature,
                request_id,
            ):
                raise NotImplementedError

        adapter = _MinimalAdapter()
        message = _make_outbound(channel_type=ChannelType.REST_API, text="hi")
        result = await adapter.send_outbound(
            channel_config={"outbound_mode": "vendor_api"},
            message=message,
            request_id="req-1",
        )
        self.assertFalse(result.attempted)
        self.assertEqual("vendor_api_not_supported", result.mode)
        self.assertEqual("vendor_api_not_supported_for_channel", result.details["reason"])


if __name__ == "__main__":
    unittest.main()
