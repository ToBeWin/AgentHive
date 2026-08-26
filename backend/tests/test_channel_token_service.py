"""Tests for the channel access-token refresh service.

Covers: cache hit/miss, expiry-driven refresh, WeCom + DingTalk + Feishu
token endpoints, retry on 5xx, static-token fallback, batch refresh, and
the adapter integration (WeCom outbound uses refreshed token when static
is absent).
"""

from __future__ import annotations

import time
import unittest
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import httpx

from app.schemas.channel import ChannelType
from app.services.channel_token_service import (
    _cache,
    clear_token_cache,
    get_access_token,
    refresh_channel_token,
    refresh_expiring_channel_tokens,
)


_REAL_ASYNC_CLIENT = httpx.AsyncClient


def _client_factory(transport: httpx.MockTransport):
    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("transport", None)
        return _REAL_ASYNC_CLIENT(*args, **kwargs, transport=transport)

    return factory


def _wecom_config(*, with_refresh: bool = True, static_token: str | None = None) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "wecom_corp_id": "corp-1",
        "wecom_secret": "secret-1",
        "wecom_agent_id": 1000001,
    }
    if with_refresh:
        cfg["wecom_corp_id"] = "corp-1"
        cfg["wecom_secret"] = "secret-1"
    else:
        cfg.pop("wecom_corp_id", None)
        cfg.pop("wecom_secret", None)
    if static_token:
        cfg["wecom_access_token"] = static_token
    return cfg


def _dingtalk_config(*, with_refresh: bool = True) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "dingtalk_app_key": "appkey-1",
        "dingtalk_app_secret": "appsecret-1",
        "dingtalk_agent_id": "agent-9",
    }
    if not with_refresh:
        cfg.pop("dingtalk_app_key", None)
        cfg.pop("dingtalk_app_secret", None)
    return cfg


def _feishu_config(
    *,
    with_refresh: bool = True,
    static_token: str | None = None,
) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "feishu_app_id": "cli_app1",
        "feishu_app_secret": "secret_app1",
        "feishu_receive_id": "ou_xxx",
    }
    if not with_refresh:
        cfg.pop("feishu_app_id", None)
        cfg.pop("feishu_app_secret", None)
    if static_token:
        cfg["feishu_tenant_access_token"] = static_token
    return cfg


class ChannelTokenServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        clear_token_cache()

    async def asyncTearDown(self) -> None:
        clear_token_cache()

    async def test_wecom_refresh_fetches_and_caches_token(self) -> None:
        channel_id = uuid4()
        captured: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append({"url": str(request.url), "params": dict(request.url.params)})
            return httpx.Response(
                200,
                json={
                    "errcode": 0,
                    "errmsg": "ok",
                    "access_token": "tok-fresh-1",
                    "expires_in": 7200,
                },
            )

        transport = httpx.MockTransport(handler)
        token = await get_access_token(
            channel_id,
            ChannelType.WECOM,
            _wecom_config(),
            client_factory=_client_factory(transport),
        )

        self.assertEqual("tok-fresh-1", token)
        self.assertEqual(1, len(captured))
        self.assertTrue(
            captured[0]["url"].startswith("https://qyapi.weixin.qq.com/cgi-bin/gettoken"),
            captured[0]["url"],
        )
        self.assertEqual("corp-1", captured[0]["params"]["corpid"])
        self.assertEqual("secret-1", captured[0]["params"]["corpsecret"])
        # Cached
        self.assertIn(channel_id, _cache)
        self.assertEqual("tok-fresh-1", _cache[channel_id].access_token)

    async def test_cache_hit_avoids_network_call(self) -> None:
        channel_id = uuid4()
        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            return httpx.Response(
                200,
                json={"errcode": 0, "access_token": "tok-cached", "expires_in": 7200},
            )

        transport = httpx.MockTransport(handler)
        t1 = await get_access_token(
            channel_id,
            ChannelType.WECOM,
            _wecom_config(),
            client_factory=_client_factory(transport),
        )
        t2 = await get_access_token(
            channel_id,
            ChannelType.WECOM,
            _wecom_config(),
            client_factory=_client_factory(transport),
        )
        self.assertEqual("tok-cached", t1)
        self.assertEqual("tok-cached", t2)
        self.assertEqual(1, call_count["n"])

    async def test_expired_token_triggers_refresh(self) -> None:
        channel_id = uuid4()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"errcode": 0, "access_token": "tok-v2", "expires_in": 7200},
            )

        transport = httpx.MockTransport(handler)
        await get_access_token(
            channel_id,
            ChannelType.WECOM,
            _wecom_config(),
            client_factory=_client_factory(transport),
        )
        # Force expiry by backdating the cached entry.
        _cache[channel_id].expires_at = time.time() - 1
        t2 = await get_access_token(
            channel_id,
            ChannelType.WECOM,
            _wecom_config(),
            client_factory=_client_factory(transport),
        )
        self.assertEqual("tok-v2", t2)

    async def test_refresh_ahead_margin_triggers_early_refresh(self) -> None:
        channel_id = uuid4()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"errcode": 0, "access_token": "tok-early", "expires_in": 7200},
            )

        transport = httpx.MockTransport(handler)
        await get_access_token(
            channel_id,
            ChannelType.WECOM,
            _wecom_config(),
            client_factory=_client_factory(transport),
        )
        # Set expiry just within the safety margin (default 300s).
        _cache[channel_id].expires_at = time.time() + 100
        t2 = await get_access_token(
            channel_id,
            ChannelType.WECOM,
            _wecom_config(),
            client_factory=_client_factory(transport),
        )
        self.assertEqual("tok-early", t2)

    async def test_dingtalk_refresh_uses_appkey_appsecret(self) -> None:
        channel_id = uuid4()
        captured: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append({"url": str(request.url), "params": dict(request.url.params)})
            return httpx.Response(
                200,
                json={
                    "errcode": 0,
                    "access_token": "dt-tok-1",
                    "expires_in": 7200,
                },
            )

        transport = httpx.MockTransport(handler)
        token = await get_access_token(
            channel_id,
            ChannelType.DINGTALK,
            _dingtalk_config(),
            client_factory=_client_factory(transport),
        )

        self.assertEqual("dt-tok-1", token)
        self.assertTrue(
            captured[0]["url"].startswith("https://oapi.dingtalk.com/gettoken"),
            captured[0]["url"],
        )
        self.assertEqual("appkey-1", captured[0]["params"]["appkey"])
        self.assertEqual("appsecret-1", captured[0]["params"]["appsecret"])

    async def test_feishu_refresh_fetches_and_caches_token(self) -> None:
        channel_id = uuid4()
        captured: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(
                {
                    "url": str(request.url),
                    "method": request.method,
                    "body": request.read().decode("utf-8"),
                }
            )
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "msg": "ok",
                    "tenant_access_token": "t-feishu-1",
                    "expire": 7200,
                },
            )

        transport = httpx.MockTransport(handler)
        token = await get_access_token(
            channel_id,
            ChannelType.FEISHU,
            _feishu_config(),
            client_factory=_client_factory(transport),
        )

        self.assertEqual("t-feishu-1", token)
        self.assertEqual(1, len(captured))
        # Feishu uses POST with a JSON body, not GET with query params.
        self.assertEqual("POST", captured[0]["method"])
        self.assertTrue(
            captured[0]["url"].startswith(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            ),
            captured[0]["url"],
        )
        body = captured[0]["body"]
        self.assertIn('"app_id":"cli_app1"', body)
        self.assertIn('"app_secret":"secret_app1"', body)
        # Cached
        self.assertIn(channel_id, _cache)
        self.assertEqual("t-feishu-1", _cache[channel_id].access_token)

    async def test_feishu_cache_hit_avoids_network_call(self) -> None:
        channel_id = uuid4()
        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "tenant_access_token": "t-feishu-cached",
                    "expire": 7200,
                },
            )

        transport = httpx.MockTransport(handler)
        t1 = await get_access_token(
            channel_id,
            ChannelType.FEISHU,
            _feishu_config(),
            client_factory=_client_factory(transport),
        )
        t2 = await get_access_token(
            channel_id,
            ChannelType.FEISHU,
            _feishu_config(),
            client_factory=_client_factory(transport),
        )
        self.assertEqual("t-feishu-cached", t1)
        self.assertEqual("t-feishu-cached", t2)
        self.assertEqual(1, call_count["n"])

    async def test_feishu_code_nonzero_returns_none_and_falls_back_to_static(
        self,
    ) -> None:
        channel_id = uuid4()
        transport = httpx.MockTransport(
            lambda r: httpx.Response(
                200, json={"code": 99991663, "msg": "app_id or app_secret invalid"}
            )
        )
        token = await get_access_token(
            channel_id,
            ChannelType.FEISHU,
            _feishu_config(static_token="t-static-fallback"),
            client_factory=_client_factory(transport),
        )
        self.assertEqual("t-static-fallback", token)

    async def test_feishu_4xx_does_not_retry(self) -> None:
        channel_id = uuid4()
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(401, text="unauthorized")

        transport = httpx.MockTransport(handler)

        async def _no_sleep(_seconds: float) -> None:
            return None

        with patch("app.services.channel_token_service.asyncio.sleep", new=_no_sleep):
            token = await get_access_token(
                channel_id,
                ChannelType.FEISHU,
                _feishu_config(static_token="t-static-4xx"),
                client_factory=_client_factory(transport),
            )
        self.assertEqual("t-static-4xx", token)
        self.assertEqual(1, calls["n"])

    async def test_feishu_5xx_retries_then_succeeds(self) -> None:
        channel_id = uuid4()
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] < 3:
                return httpx.Response(503, text="unavailable")
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "tenant_access_token": "t-feishu-after-retry",
                    "expire": 7200,
                },
            )

        transport = httpx.MockTransport(handler)

        async def _no_sleep(_seconds: float) -> None:
            return None

        with patch("app.services.channel_token_service.asyncio.sleep", new=_no_sleep):
            token = await get_access_token(
                channel_id,
                ChannelType.FEISHU,
                _feishu_config(),
                client_factory=_client_factory(transport),
            )
        self.assertEqual("t-feishu-after-retry", token)
        self.assertEqual(3, calls["n"])

    async def test_feishu_no_refresh_credentials_falls_back_to_static(self) -> None:
        channel_id = uuid4()
        token = await get_access_token(
            channel_id,
            ChannelType.FEISHU,
            _feishu_config(with_refresh=False, static_token="t-static-feishu"),
            client_factory=_client_factory(httpx.MockTransport(lambda r: httpx.Response(500))),
        )
        self.assertEqual("t-static-feishu", token)
        self.assertNotIn(channel_id, _cache)

    async def test_no_refresh_credentials_falls_back_to_static_token(self) -> None:
        channel_id = uuid4()
        token = await get_access_token(
            channel_id,
            ChannelType.WECOM,
            _wecom_config(with_refresh=False, static_token="static-tok"),
            client_factory=_client_factory(httpx.MockTransport(lambda r: httpx.Response(500))),
        )
        self.assertEqual("static-tok", token)
        # No cache entry since refresh wasn't attempted.
        self.assertNotIn(channel_id, _cache)

    async def test_no_refresh_credentials_and_no_static_returns_none(self) -> None:
        channel_id = uuid4()
        token = await get_access_token(
            channel_id,
            ChannelType.WECOM,
            _wecom_config(with_refresh=False),
            client_factory=_client_factory(httpx.MockTransport(lambda r: httpx.Response(500))),
        )
        self.assertIsNone(token)

    async def test_refresh_failure_falls_back_to_static_token(self) -> None:
        channel_id = uuid4()
        transport = httpx.MockTransport(lambda r: httpx.Response(500, text="down"))
        token = await get_access_token(
            channel_id,
            ChannelType.WECOM,
            _wecom_config(static_token="static-fallback"),
            client_factory=_client_factory(transport),
        )
        self.assertEqual("static-fallback", token)

    async def test_errcode_nonzero_returns_none_and_falls_back_to_static(self) -> None:
        channel_id = uuid4()
        transport = httpx.MockTransport(
            lambda r: httpx.Response(200, json={"errcode": 40013, "errmsg": "invalid appid"})
        )
        token = await get_access_token(
            channel_id,
            ChannelType.WECOM,
            _wecom_config(static_token="static-2"),
            client_factory=_client_factory(transport),
        )
        self.assertEqual("static-2", token)

    async def test_5xx_retries_then_succeeds(self) -> None:
        channel_id = uuid4()
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] < 3:
                return httpx.Response(503, text="unavailable")
            return httpx.Response(
                200, json={"errcode": 0, "access_token": "tok-after-retry", "expires_in": 7200}
            )

        transport = httpx.MockTransport(handler)

        async def _no_sleep(_seconds: float) -> None:
            return None

        with patch("app.services.channel_token_service.asyncio.sleep", new=_no_sleep):
            token = await get_access_token(
                channel_id,
                ChannelType.WECOM,
                _wecom_config(),
                client_factory=_client_factory(transport),
            )
        self.assertEqual("tok-after-retry", token)
        self.assertEqual(3, calls["n"])

    async def test_4xx_does_not_retry(self) -> None:
        channel_id = uuid4()
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(401, text="unauthorized")

        transport = httpx.MockTransport(handler)

        async def _no_sleep(_seconds: float) -> None:
            return None

        with patch("app.services.channel_token_service.asyncio.sleep", new=_no_sleep):
            token = await get_access_token(
                channel_id,
                ChannelType.WECOM,
                _wecom_config(static_token="static-3"),
                client_factory=_client_factory(transport),
            )
        self.assertEqual("static-3", token)
        self.assertEqual(1, calls["n"])

    async def test_request_id_propagated_via_header(self) -> None:
        channel_id = uuid4()
        captured: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["x_request_id"] = request.headers.get("x-request-id", "")
            return httpx.Response(
                200, json={"errcode": 0, "access_token": "tok-rid", "expires_in": 7200}
            )

        transport = httpx.MockTransport(handler)
        await get_access_token(
            channel_id,
            ChannelType.WECOM,
            _wecom_config(),
            request_id="req-123",
            client_factory=_client_factory(transport),
        )
        self.assertEqual("req-123", captured["x_request_id"])

    async def test_refresh_channel_token_bypasses_cache(self) -> None:
        channel_id = uuid4()
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(
                200,
                json={
                    "errcode": 0,
                    "access_token": f"tok-force-{calls['n']}",
                    "expires_in": 7200,
                },
            )

        transport = httpx.MockTransport(handler)
        t1 = await get_access_token(
            channel_id,
            ChannelType.WECOM,
            _wecom_config(),
            client_factory=_client_factory(transport),
        )
        t2 = await refresh_channel_token(
            channel_id,
            ChannelType.WECOM,
            _wecom_config(),
            client_factory=_client_factory(transport),
        )
        self.assertEqual("tok-force-1", t1)
        self.assertEqual("tok-force-2", t2)
        self.assertEqual(2, calls["n"])

    async def test_batch_refresh_skips_channels_without_credentials(self) -> None:
        ch1 = (uuid4(), ChannelType.WECOM, _wecom_config())
        ch2 = (uuid4(), ChannelType.WECOM, _wecom_config(with_refresh=False, static_token="s"))
        ch3 = (uuid4(), ChannelType.DINGTALK, _dingtalk_config())
        ch4 = (uuid4(), ChannelType.FEISHU, _feishu_config())
        ch5 = (
            uuid4(),
            ChannelType.FEISHU,
            _feishu_config(with_refresh=False, static_token="t-static"),
        )

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                return httpx.Response(
                    200,
                    json={
                        "code": 0,
                        "tenant_access_token": "t-feishu-batch",
                        "expire": 7200,
                    },
                )
            return httpx.Response(
                200, json={"errcode": 0, "access_token": "batch-tok", "expires_in": 7200}
            )

        transport = httpx.MockTransport(handler)
        result = await refresh_expiring_channel_tokens(
            [ch1, ch2, ch3, ch4, ch5], client_factory=_client_factory(transport)
        )
        self.assertEqual(3, len(result["refreshed"]))
        self.assertEqual(2, len(result["skipped"]))
        self.assertEqual(0, len(result["failed"]))
        self.assertIn(str(ch2[0]), result["skipped"])
        self.assertIn(str(ch5[0]), result["skipped"])
        self.assertIn(str(ch4[0]), result["refreshed"])

    async def test_batch_refresh_skips_fresh_cached_tokens(self) -> None:
        ch1 = (uuid4(), ChannelType.WECOM, _wecom_config())

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, json={"errcode": 0, "access_token": "tok-fresh", "expires_in": 7200}
            )

        transport = httpx.MockTransport(handler)
        # Prime the cache with a fresh token.
        await get_access_token(ch1[0], ch1[1], ch1[2], client_factory=_client_factory(transport))
        result = await refresh_expiring_channel_tokens(
            [ch1], client_factory=_client_factory(transport)
        )
        self.assertEqual(0, len(result["refreshed"]))
        self.assertEqual(1, len(result["skipped"]))

    async def test_unsupported_channel_type_returns_static_or_none(self) -> None:
        token = await get_access_token(
            uuid4(),
            ChannelType.WEB_WIDGET,
            {},
            client_factory=_client_factory(httpx.MockTransport(lambda r: httpx.Response(500))),
        )
        self.assertIsNone(token)


if __name__ == "__main__":
    unittest.main()
