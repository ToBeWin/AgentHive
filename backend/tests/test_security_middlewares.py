import unittest
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from redis.asyncio import Redis
from starlette.requests import Request

from app.core.config import settings
from app.middleware.rate_limit import (
    InMemoryRateLimiter,
    RedisRateLimiter,
    _client_ip,
    _normalized_path,
    rate_limit_middleware,
    rate_limiter,
)
from app.middleware.request_id import REQUEST_ID_HEADER, request_id_middleware
from app.middleware.security_headers import security_headers_middleware


def _build_test_app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(rate_limit_middleware)
    app.middleware("http")(security_headers_middleware)
    app.middleware("http")(request_id_middleware)

    @app.get("/api/v1/test-rate")
    async def test_rate() -> dict[str, str]:
        return {"status": "ok"}

    return app


class SecurityMiddlewareTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old_rate_limit_enabled = settings.rate_limit_enabled
        self._old_rate_limit_requests = settings.rate_limit_requests
        self._old_rate_limit_window_seconds = settings.rate_limit_window_seconds
        self._old_rate_limit_backend = settings.rate_limit_backend
        self._old_trusted_proxy_cidrs = settings.trusted_proxy_cidrs
        self._old_security_headers_enabled = settings.security_headers_enabled
        settings.rate_limit_backend = "memory"
        rate_limiter.reset()

    def tearDown(self) -> None:
        settings.rate_limit_enabled = self._old_rate_limit_enabled
        settings.rate_limit_requests = self._old_rate_limit_requests
        settings.rate_limit_window_seconds = self._old_rate_limit_window_seconds
        settings.rate_limit_backend = self._old_rate_limit_backend
        settings.trusted_proxy_cidrs = self._old_trusted_proxy_cidrs
        settings.security_headers_enabled = self._old_security_headers_enabled
        rate_limiter.reset()

    def test_in_memory_rate_limiter_counts_within_window(self) -> None:
        limiter = InMemoryRateLimiter()

        self.assertEqual(
            (True, 1), limiter.allow("tenant:user", limit=2, window_seconds=10, now=100.0)
        )
        self.assertEqual(
            (True, 0), limiter.allow("tenant:user", limit=2, window_seconds=10, now=101.0)
        )
        self.assertEqual(
            (False, 0), limiter.allow("tenant:user", limit=2, window_seconds=10, now=102.0)
        )
        self.assertEqual(
            (True, 1), limiter.allow("tenant:user", limit=2, window_seconds=10, now=112.0)
        )

    def test_security_headers_are_added_to_successful_responses(self) -> None:
        settings.rate_limit_enabled = False
        settings.security_headers_enabled = True

        response = TestClient(_build_test_app()).get("/api/v1/test-rate")

        self.assertEqual(200, response.status_code)
        self.assertEqual("nosniff", response.headers["X-Content-Type-Options"])
        self.assertEqual("DENY", response.headers["X-Frame-Options"])
        self.assertEqual("strict-origin-when-cross-origin", response.headers["Referrer-Policy"])
        self.assertIn(REQUEST_ID_HEADER, response.headers)

    def test_rate_limit_returns_429_with_control_headers(self) -> None:
        settings.rate_limit_enabled = True
        settings.rate_limit_requests = 1
        settings.rate_limit_window_seconds = 60

        client = TestClient(_build_test_app())
        first = client.get("/api/v1/test-rate", headers={"X-AgentHive-Tenant": "tenant-a"})
        second = client.get("/api/v1/test-rate", headers={"X-AgentHive-Tenant": "tenant-a"})

        self.assertEqual(200, first.status_code)
        self.assertEqual("1", first.headers["X-RateLimit-Limit"])
        self.assertEqual("memory", first.headers["X-RateLimit-Backend"])
        self.assertEqual(429, second.status_code)
        self.assertEqual({"detail": "Rate limit exceeded."}, second.json())
        self.assertEqual("60", second.headers["Retry-After"])
        self.assertEqual("0", second.headers["X-RateLimit-Remaining"])

    def test_untrusted_peer_cannot_spoof_forwarded_ip(self) -> None:
        settings.trusted_proxy_cidrs = ["127.0.0.1/32"]
        request = _request("203.0.113.9", forwarded_for="198.51.100.20")

        self.assertEqual("203.0.113.9", _client_ip(request))

    def test_trusted_proxy_can_forward_valid_client_ip(self) -> None:
        settings.trusted_proxy_cidrs = ["172.16.0.0/12"]
        request = _request("172.20.0.4", forwarded_for="198.51.100.20")

        self.assertEqual("198.51.100.20", _client_ip(request))

    def test_dynamic_resource_ids_share_one_rate_limit_bucket(self) -> None:
        first = _normalized_path("/api/v1/agents/2a69476d-2f9e-4a42-9054-61199858fefe/run")
        second = _normalized_path("/api/v1/agents/cf704943-f4b3-45d4-adcf-912496f50631/run")

        self.assertEqual(first, second)


class RedisRateLimiterTest(unittest.IsolatedAsyncioTestCase):
    async def test_redis_limiter_uses_atomic_counter_result(self) -> None:
        fake = _FakeRedis([2, 37])
        limiter = RedisRateLimiter(lambda: cast(Redis, fake))

        decision = await limiter.allow("tenant:user", limit=3, window_seconds=60)

        self.assertTrue(decision.allowed)
        self.assertEqual(1, decision.remaining)
        self.assertEqual(37, decision.retry_after)
        self.assertEqual("redis", decision.backend)
        self.assertEqual(1, fake.calls)


class _FakeRedis:
    def __init__(self, result: list[int]) -> None:
        self.result = result
        self.calls = 0

    async def eval(self, *_args: object) -> list[int]:
        self.calls += 1
        return self.result


def _request(peer: str, *, forwarded_for: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v1/test-rate",
            "raw_path": b"/api/v1/test-rate",
            "query_string": b"",
            "headers": [(b"x-forwarded-for", forwarded_for.encode())],
            "client": (peer, 1234),
            "server": ("testserver", 80),
        }
    )


if __name__ == "__main__":
    unittest.main()
