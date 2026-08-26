from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from hashlib import sha256
from ipaddress import ip_address, ip_network
import logging
import re
from time import monotonic
from typing import Any, cast

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.redis import get_redis_client

SKIP_PREFIXES = (
    "/api/docs",
    "/api/openapi.json",
    "/api/v1/health",
    "/api/v1/system/info",
    "/widget/",
)
_DYNAMIC_PATH_SEGMENT = re.compile(r"^(?:\d+|[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,}|[A-Za-z0-9_-]{24,})$")
_REDIS_FIXED_WINDOW_SCRIPT = """
local current = redis.call("INCR", KEYS[1])
if current == 1 then
  redis.call("EXPIRE", KEYS[1], ARGV[1])
end
local ttl = redis.call("TTL", KEYS[1])
return {current, ttl}
"""
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after: int
    backend: str


@dataclass
class InMemoryRateLimiter:
    buckets: dict[str, list[float]] = field(default_factory=dict)

    def allow(
        self, key: str, *, limit: int, window_seconds: int, now: float | None = None
    ) -> tuple[bool, int]:
        current = now if now is not None else monotonic()
        cutoff = current - window_seconds
        bucket = [item for item in self.buckets.get(key, []) if item > cutoff]
        allowed = len(bucket) < limit
        if allowed:
            bucket.append(current)
        if bucket:
            self.buckets[key] = bucket
        else:
            self.buckets.pop(key, None)
        self._compact(cutoff)
        return allowed, max(limit - len(bucket), 0)

    def reset(self) -> None:
        self.buckets.clear()

    def _compact(self, cutoff: float) -> None:
        for key in list(self.buckets):
            bucket = [item for item in self.buckets[key] if item > cutoff]
            if bucket:
                self.buckets[key] = bucket
            else:
                self.buckets.pop(key, None)


class RedisRateLimiter:
    def __init__(self, client_factory: Callable[[], Redis] = get_redis_client) -> None:
        self._client_factory = client_factory

    async def allow(self, key: str, *, limit: int, window_seconds: int) -> RateLimitDecision:
        redis_key = f"agenthive:rate-limit:{sha256(key.encode()).hexdigest()}"
        result = await cast(
            Awaitable[Any],
            self._client_factory().eval(
                _REDIS_FIXED_WINDOW_SCRIPT,
                1,
                redis_key,
                str(window_seconds),
            ),
        )
        if not isinstance(result, (list, tuple)) or len(result) != 2:
            raise RedisError("Unexpected Redis rate-limit response.")
        current = int(result[0])
        ttl = max(int(result[1]), 1)
        return RateLimitDecision(
            allowed=current <= limit,
            remaining=max(limit - current, 0),
            retry_after=ttl,
            backend="redis",
        )


rate_limiter = InMemoryRateLimiter()
redis_rate_limiter = RedisRateLimiter()
_last_redis_fallback_log_at = 0.0


async def rate_limit_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    if (
        not settings.rate_limit_enabled
        or request.method == "OPTIONS"
        or any(request.url.path.startswith(prefix) for prefix in SKIP_PREFIXES)
    ):
        return await call_next(request)

    limit = max(settings.rate_limit_requests, 1)
    window_seconds = max(settings.rate_limit_window_seconds, 1)
    decision = await _rate_limit_decision(
        _rate_limit_key(request),
        limit=limit,
        window_seconds=window_seconds,
    )
    headers = {
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(decision.remaining),
        "X-RateLimit-Window": str(window_seconds),
        "X-RateLimit-Backend": decision.backend,
    }
    if not decision.allowed:
        headers["Retry-After"] = str(decision.retry_after)
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Rate limit exceeded."},
            headers=headers,
        )

    response = await call_next(request)
    for name, value in headers.items():
        response.headers.setdefault(name, value)
    return response


async def _rate_limit_decision(
    key: str,
    *,
    limit: int,
    window_seconds: int,
) -> RateLimitDecision:
    if settings.rate_limit_backend == "redis":
        try:
            return await redis_rate_limiter.allow(
                key,
                limit=limit,
                window_seconds=window_seconds,
            )
        except RedisError:
            _log_redis_fallback()

    allowed, remaining = rate_limiter.allow(
        key,
        limit=limit,
        window_seconds=window_seconds,
    )
    backend = "memory-fallback" if settings.rate_limit_backend == "redis" else "memory"
    return RateLimitDecision(
        allowed=allowed,
        remaining=remaining,
        retry_after=window_seconds,
        backend=backend,
    )


def _rate_limit_key(request: Request) -> str:
    return f"{_client_ip(request)}:{_normalized_path(request.url.path)}"


def _client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    if not _is_trusted_proxy(peer):
        return peer
    forwarded_for = request.headers.get("x-forwarded-for", "")
    candidate = forwarded_for.split(",", 1)[0].strip()
    try:
        return str(ip_address(candidate))
    except ValueError:
        return peer


def _is_trusted_proxy(value: str) -> bool:
    try:
        peer = ip_address(value)
    except ValueError:
        return False
    for cidr in settings.trusted_proxy_cidrs:
        try:
            if peer in ip_network(cidr, strict=False):
                return True
        except ValueError:
            continue
    return False


def _normalized_path(path: str) -> str:
    segments = [
        "{id}" if _DYNAMIC_PATH_SEGMENT.fullmatch(segment) else segment
        for segment in path.split("/")
    ]
    return "/".join(segments)


def _log_redis_fallback() -> None:
    global _last_redis_fallback_log_at
    current = monotonic()
    if current - _last_redis_fallback_log_at >= 60:
        logger.warning("Redis rate limiter unavailable; using process-local fallback.")
        _last_redis_fallback_log_at = current
