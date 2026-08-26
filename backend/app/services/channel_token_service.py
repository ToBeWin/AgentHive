"""Channel access-token refresh service.

WeCom and DingTalk vendor APIs require an ``access_token`` that expires every
2 hours. This module provides:

  * ``ChannelTokenCache`` — process-local in-memory cache keyed by channel id,
    storing ``(token, expires_at)`` with TTL-aware lookup.
  * ``get_access_token`` — returns a cached token if still valid (with a
    configurable safety margin), otherwise fetches a fresh one from the
    vendor's token endpoint. Falls back to a statically-configured token
    (``wecom_access_token`` / ``dingtalk_access_token``) when present, so the
    refresh path is opt-in: operators who prefer to manage tokens externally
    can keep using static config.
  * ``refresh_channel_token`` — force-refresh a single channel's token.
  * ``refresh_expiring_channel_tokens`` — batch refresh all cached tokens that
    are within the safety margin of expiry; used by the Celery beat task.

Token endpoints:
  * WeCom:    GET https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid=&corpsecret=
              Response: {"errcode":0,"errmsg":"ok","access_token":"...","expires_in":7200}
  * DingTalk: GET https://oapi.dingtalk.com/gettoken?appkey=&appsecret=
              Response: {"errcode":0,"errmsg":"ok","access_token":"...","expires_in":7200}
  * Feishu:   POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal
              Body: {"app_id":"...","app_secret":"..."}
              Response: {"code":0,"msg":"ok","tenant_access_token":"...","expire":7200}

The cache is intentionally process-local (not Redis-backed) because tokens are
cheap to fetch and the slight redundancy across workers is acceptable; a
Redis-backed cache would add a network hop on every outbound call. If a worker
restarts, the first outbound call triggers a fresh fetch — no correctness
impact, just one extra token call.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import httpx

from app.core.config import settings
from app.schemas.channel import ChannelType


@dataclass(slots=True)
class _CachedToken:
    access_token: str
    expires_at: float  # monotonic time.time() baseline
    fetched_at: float = field(default_factory=time.time)


# keyed by channel_id (UUID -> _CachedToken). Process-local.
_cache: dict[UUID, _CachedToken] = {}
_cache_lock = asyncio.Lock()


def _is_expired(cached: _CachedToken, *, now: float) -> bool:
    return cached.expires_at - now <= settings.channel_token_refresh_ahead_seconds


async def get_access_token(
    channel_id: UUID | None,
    channel_type: ChannelType,
    config: dict[str, Any],
    *,
    request_id: str | None = None,
    client_factory: Any = None,
) -> str | None:
    """Return a valid access_token for the channel, refreshing if needed.

    ``channel_id`` may be ``None`` (e.g. for test messages that aren't tied to
    a persisted channel); in that case the static token is returned without
    caching, since there's no stable key to cache under.

    Returns ``None`` when:
      * the channel type does not support token refresh (WebWidget/RestAPI),
      * neither refresh credentials nor a static token are configured.

    ``client_factory`` is an optional callable returning an httpx.AsyncClient;
    used by tests to inject a MockTransport. When ``None``, a real client is
    built per call.
    """

    static_token = _static_token_for(channel_type, config)
    refresh_creds = _refresh_credentials_for(channel_type, config)
    if refresh_creds is None:
        # No refresh credentials → fall back to static token (may be None).
        return static_token
    if channel_id is None:
        # No stable cache key → refresh on every call (rare; test path).
        return await _fetch_token(
            channel_id=channel_id,
            refresh_creds=refresh_creds,
            request_id=request_id,
            client_factory=client_factory,
        )

    now = time.time()
    async with _cache_lock:
        cached = _cache.get(channel_id)
        if cached is not None and not _is_expired(cached, now=now):
            return cached.access_token

    # Cache miss / expired → fetch fresh. Lock is released during the network
    # call so concurrent requests for different channels don't block each
    # other; a same-channel thundering herd is bounded by the small window
    # between the cache check and the write-back.
    fresh = await _fetch_token(
        channel_id=channel_id,
        refresh_creds=refresh_creds,
        request_id=request_id,
        client_factory=client_factory,
    )
    if fresh is None:
        # Refresh failed → fall back to static token if any (best-effort).
        return static_token
    return fresh


async def refresh_channel_token(
    channel_id: UUID | None,
    channel_type: ChannelType,
    config: dict[str, Any],
    *,
    request_id: str | None = None,
    client_factory: Any = None,
) -> str | None:
    """Force-refresh a channel's token, bypassing the cache."""

    refresh_creds = _refresh_credentials_for(channel_type, config)
    if refresh_creds is None:
        return _static_token_for(channel_type, config)
    return await _fetch_token(
        channel_id=channel_id,
        refresh_creds=refresh_creds,
        request_id=request_id,
        client_factory=client_factory,
    )


async def refresh_expiring_channel_tokens(
    channels: list[tuple[UUID, ChannelType, dict[str, Any]]],
    *,
    request_id: str | None = None,
    client_factory: Any = None,
) -> dict[str, Any]:
    """Batch-refresh tokens that are within the safety margin of expiry.

    ``channels`` is a list of ``(channel_id, channel_type, config)`` tuples.

    Returns a diagnostics dict: {"refreshed": [...ids...], "skipped": [...], "failed": [...]}.
    Channels without refresh credentials are skipped (not failed).
    """

    now = time.time()
    to_refresh: list[tuple[UUID, ChannelType, dict[str, Any]]] = []
    skipped: list[str] = []
    for channel_id, channel_type, config in channels:
        if _refresh_credentials_for(channel_type, config) is None:
            skipped.append(str(channel_id))
            continue
        cached = _cache.get(channel_id)
        if cached is None or _is_expired(cached, now=now):
            to_refresh.append((channel_id, channel_type, config))
        else:
            skipped.append(str(channel_id))

    refreshed: list[str] = []
    failed: list[str] = []
    for channel_id, channel_type, config in to_refresh:
        refresh_creds = _refresh_credentials_for(channel_type, config)
        token = await _fetch_token(
            channel_id=channel_id,
            refresh_creds=refresh_creds,  # type: ignore[arg-type]
            request_id=request_id,
            client_factory=client_factory,
        )
        if token is not None:
            refreshed.append(str(channel_id))
        else:
            failed.append(str(channel_id))

    return {"refreshed": refreshed, "skipped": skipped, "failed": failed}


def clear_token_cache(channel_id: UUID | None = None) -> None:
    """Drop cached tokens. Mainly for tests."""

    if channel_id is None:
        _cache.clear()
    else:
        _cache.pop(channel_id, None)


def _static_token_for(channel_type: ChannelType, config: dict[str, Any]) -> str | None:
    if channel_type == ChannelType.WECOM:
        return _string_or_none(config.get("wecom_access_token"))
    if channel_type == ChannelType.DINGTALK:
        return _string_or_none(config.get("dingtalk_access_token"))
    if channel_type == ChannelType.FEISHU:
        return _string_or_none(config.get("feishu_tenant_access_token"))
    return None


@dataclass(slots=True)
class _RefreshCredentials:
    channel_type: ChannelType
    # WeCom: (corpid, corpsecret); DingTalk: (appkey, appsecret); Feishu: (app_id, app_secret)
    key: str
    secret: str
    endpoint: str


def _refresh_credentials_for(
    channel_type: ChannelType, config: dict[str, Any]
) -> _RefreshCredentials | None:
    if channel_type == ChannelType.WECOM:
        corp_id = _string_or_none(config.get("wecom_corp_id"))
        corp_secret = _string_or_none(config.get("wecom_secret"))
        if not corp_id or not corp_secret:
            return None
        base = (
            _string_or_none(config.get("wecom_api_base_url")) or "https://qyapi.weixin.qq.com"
        ).rstrip("/")
        return _RefreshCredentials(
            channel_type=ChannelType.WECOM,
            key=corp_id,
            secret=corp_secret,
            endpoint=f"{base}/cgi-bin/gettoken",
        )
    if channel_type == ChannelType.DINGTALK:
        app_key = _string_or_none(config.get("dingtalk_app_key"))
        app_secret = _string_or_none(config.get("dingtalk_app_secret"))
        if not app_key or not app_secret:
            return None
        base = (
            _string_or_none(config.get("dingtalk_api_base_url")) or "https://oapi.dingtalk.com"
        ).rstrip("/")
        return _RefreshCredentials(
            channel_type=ChannelType.DINGTALK,
            key=app_key,
            secret=app_secret,
            endpoint=f"{base}/gettoken",
        )
    if channel_type == ChannelType.FEISHU:
        app_id = _string_or_none(config.get("feishu_app_id"))
        app_secret = _string_or_none(config.get("feishu_app_secret"))
        if not app_id or not app_secret:
            return None
        base = (
            _string_or_none(config.get("feishu_api_base_url")) or "https://open.feishu.cn/open-apis"
        ).rstrip("/")
        return _RefreshCredentials(
            channel_type=ChannelType.FEISHU,
            key=app_id,
            secret=app_secret,
            endpoint=f"{base}/auth/v3/tenant_access_token/internal",
        )
    return None


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


async def _fetch_token(
    *,
    channel_id: UUID | None,
    refresh_creds: _RefreshCredentials,
    request_id: str | None,
    client_factory: Any,
) -> str | None:
    is_feishu = refresh_creds.channel_type == ChannelType.FEISHU
    if is_feishu:
        # Feishu uses POST with a JSON body (app_id + app_secret).
        request_kwargs: dict[str, Any] = {
            "json": {"app_id": refresh_creds.key, "app_secret": refresh_creds.secret},
        }
    else:
        # WeCom/DingTalk use GET with query params.
        params = (
            {"corpid": refresh_creds.key, "corpsecret": refresh_creds.secret}
            if refresh_creds.channel_type == ChannelType.WECOM
            else {"appkey": refresh_creds.key, "appsecret": refresh_creds.secret}
        )
        request_kwargs = {"params": params}
    timeout = settings.channel_token_request_timeout_seconds
    for attempt in range(settings.channel_token_max_retries + 1):
        try:
            if client_factory is not None:
                client = client_factory(timeout=timeout)
            else:
                client = httpx.AsyncClient(timeout=timeout)
            try:
                headers: dict[str, str] = {}
                if request_id:
                    headers["X-Request-Id"] = request_id
                if is_feishu:
                    response = await client.post(
                        refresh_creds.endpoint, headers=headers, **request_kwargs
                    )
                else:
                    response = await client.get(
                        refresh_creds.endpoint, headers=headers, **request_kwargs
                    )
            finally:
                await client.aclose()
            # 4xx is a permanent error (bad credentials) — don't retry.
            if 400 <= response.status_code < 500:
                return None
            # 5xx is transient — raise so the retry loop can kick in.
            if response.status_code >= 500:
                response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                return None
            if is_feishu:
                # Feishu envelope: {"code":0,"msg":"ok",
                # "tenant_access_token":"t-xxx","expire":7200}.
                code = data.get("code")
                if code not in (0, None):
                    return None
                access_token = data.get("tenant_access_token")
                expires_in = int(data.get("expire") or 7200)
            else:
                errcode = data.get("errcode")
                if errcode not in (0, None):
                    return None
                access_token = data.get("access_token")
                expires_in = int(data.get("expires_in") or 7200)
            if not access_token or expires_in <= 0:
                return None
            now = time.time()
            cached = _CachedToken(
                access_token=str(access_token),
                expires_at=now + expires_in,
            )
            if channel_id is not None:
                async with _cache_lock:
                    _cache[channel_id] = cached
            return cached.access_token
        except httpx.HTTPError:
            if attempt >= settings.channel_token_max_retries:
                return None
            backoff = settings.channel_token_retry_backoff_seconds * (2**attempt)
            await asyncio.sleep(backoff)
        except Exception:
            return None
    return None
