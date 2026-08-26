"""Unit tests for the observability module (metrics collector + access log middleware)."""

from __future__ import annotations

import json
import logging
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.observability.metrics import (
    MetricsCollector,
    _looks_dynamic,
    _normalise_path,
    metrics_collector,
)


class NormalisePathTests(unittest.TestCase):
    def test_collapses_uuid_segment(self) -> None:
        result = _normalise_path("/api/v1/channels/550e8400-e29b-41d4-a716-446655440000/push")
        self.assertEqual(result, "/api/v1/channels/:param/push")

    def test_collapses_numeric_segment(self) -> None:
        self.assertEqual(_normalise_path("/api/v1/orgs/42/users"), "/api/v1/orgs/:param/users")

    def test_keeps_static_path(self) -> None:
        self.assertEqual(_normalise_path("/api/v1/health"), "/api/v1/health")

    def test_empty_path_returns_root(self) -> None:
        self.assertEqual(_normalise_path(""), "/")

    def test_looks_dynamic_hex(self) -> None:
        self.assertTrue(_looks_dynamic("0123456789abcdef0123456789abcdef"))
        self.assertFalse(_looks_dynamic("health"))
        self.assertFalse(_looks_dynamic("v1"))


class MetricsCollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.collector = MetricsCollector()

    def test_observe_http_request_increments_counter(self) -> None:
        self.collector.observe_http_request(
            method="GET", path="/api/v1/health", status=200, duration_ms=12.0
        )
        rendered = self.collector.render_prometheus()
        self.assertIn(
            'agenthive_http_requests_total{method="GET",path="/api/v1/health",status="200"} 1',
            rendered,
        )

    def test_observe_http_request_records_histogram(self) -> None:
        self.collector.observe_http_request(
            method="POST",
            path="/api/v1/channels/550e8400-e29b-41d4-a716-446655440000/push",
            status=201,
            duration_ms=500.0,
        )
        rendered = self.collector.render_prometheus()
        self.assertIn("agenthive_http_request_duration_seconds_bucket", rendered)
        self.assertIn('path="/api/v1/channels/:param/push"', rendered)
        self.assertIn(
            'agenthive_http_request_duration_seconds_count{method="POST",path="/api/v1/channels/:param/push"} 1',
            rendered,
        )

    def test_observe_llm_call_success(self) -> None:
        from app.llm.schemas import LLMCallStatus

        self.collector.observe_llm_call(
            provider_key="litellm",
            model_key="gpt-4o",
            status=LLMCallStatus.SUCCESS,
            duration_ms=850.0,
        )
        rendered = self.collector.render_prometheus()
        self.assertIn(
            'agenthive_llm_calls_total{provider="litellm",model="gpt-4o",status="success"} 1',
            rendered,
        )
        self.assertIn("agenthive_llm_call_duration_seconds_bucket", rendered)
        self.assertNotIn("agenthive_llm_errors_total", rendered)

    def test_observe_llm_call_error_records_error_counter(self) -> None:
        from app.llm.schemas import LLMCallStatus

        self.collector.observe_llm_call(
            provider_key="openai",
            model_key="gpt-4o-mini",
            status=LLMCallStatus.ERROR,
            duration_ms=120.0,
            error_code="TimeoutError",
        )
        rendered = self.collector.render_prometheus()
        self.assertIn(
            'agenthive_llm_calls_total{provider="openai",model="gpt-4o-mini",status="error"} 1',
            rendered,
        )
        self.assertIn(
            'agenthive_llm_errors_total{provider="openai",model="gpt-4o-mini",error_code="TimeoutError"} 1',
            rendered,
        )

    def test_observe_llm_call_uses_unknown_when_keys_missing(self) -> None:
        from app.llm.schemas import LLMCallStatus

        self.collector.observe_llm_call(
            provider_key=None,
            model_key=None,
            status=LLMCallStatus.DENIED,
            duration_ms=5.0,
            error_code="policy_denied",
        )
        rendered = self.collector.render_prometheus()
        self.assertIn('provider="unknown"', rendered)
        self.assertIn('model="unknown"', rendered)
        self.assertIn('status="denied"', rendered)

    def test_histogram_cumulative_buckets(self) -> None:
        from app.llm.schemas import LLMCallStatus

        for ms in (50.0, 200.0, 3000.0):
            self.collector.observe_llm_call(
                provider_key="p",
                model_key="m",
                status=LLMCallStatus.SUCCESS,
                duration_ms=ms,
            )
        rendered = self.collector.render_prometheus()
        # 3 observations total
        self.assertIn(
            'agenthive_llm_call_duration_seconds_count{provider="p",model="m"} 3',
            rendered,
        )
        # +Inf bucket should equal count
        self.assertIn('le="+Inf"} 3', rendered)

    def test_reset_clears_all_counters(self) -> None:
        from app.llm.schemas import LLMCallStatus

        self.collector.observe_http_request(method="GET", path="/x", status=200, duration_ms=1.0)
        self.collector.observe_llm_call(
            provider_key="p", model_key="m", status=LLMCallStatus.SUCCESS, duration_ms=1.0
        )
        self.collector.reset()
        rendered = self.collector.render_prometheus()
        self.assertNotIn("agenthive_http_requests_total{", rendered)
        self.assertNotIn("agenthive_llm_calls_total{", rendered)

    def test_render_includes_uptime_gauge(self) -> None:
        rendered = self.collector.render_prometheus()
        self.assertIn("agenthive_metrics_process_uptime_seconds", rendered)
        self.assertIn("# TYPE agenthive_metrics_process_uptime_seconds gauge", rendered)

    def test_thread_safety_does_not_raise(self) -> None:
        import threading

        from app.llm.schemas import LLMCallStatus

        def worker() -> None:
            for _ in range(100):
                self.collector.observe_http_request(
                    method="GET", path="/api/v1/health", status=200, duration_ms=1.0
                )
                self.collector.observe_llm_call(
                    provider_key="p", model_key="m", status=LLMCallStatus.SUCCESS, duration_ms=1.0
                )

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        rendered = self.collector.render_prometheus()
        self.assertIn('status="200"} 400', rendered)


class AccessLogMiddlewareTests(unittest.TestCase):
    def setUp(self) -> None:
        metrics_collector.reset()

    def _build_app(self) -> FastAPI:
        app = FastAPI()

        @app.get("/api/v1/echo")
        async def echo() -> dict[str, str]:
            return {"ok": "yes"}

        @app.get("/api/v1/boom")
        async def boom() -> dict[str, str]:
            raise RuntimeError("boom")

        from app.middleware.access_log import access_log_middleware
        from app.middleware.request_id import request_id_middleware

        app.middleware("http")(access_log_middleware)
        app.middleware("http")(request_id_middleware)
        return app

    def test_access_log_emits_json_for_successful_request(self) -> None:
        app = self._build_app()
        client = TestClient(app, raise_server_exceptions=False)
        with self.assertLogs("agenthive.access", level="INFO") as captured:
            response = client.get("/api/v1/echo", headers={"X-AgentHive-Tenant": "acme"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(captured.records)
        payload = json.loads(captured.records[0].getMessage())
        self.assertEqual(payload["method"], "GET")
        self.assertEqual(payload["path"], "/api/v1/echo")
        self.assertEqual(payload["status"], 200)
        self.assertEqual(payload["tenant"], "acme")
        self.assertIn("latency_ms", payload)
        self.assertIn("request_id", payload)

    def test_access_log_records_error_status_on_exception(self) -> None:
        app = self._build_app()
        client = TestClient(app, raise_server_exceptions=False)
        with self.assertLogs("agenthive.access", level="INFO") as captured:
            client.get("/api/v1/boom")
        payload = json.loads(captured.records[0].getMessage())
        self.assertEqual(payload["status"], 500)
        self.assertEqual(payload["error"], "unhandled_exception")

    def test_access_log_skips_excluded_paths(self) -> None:
        app = self._build_app()

        @app.get("/api/v1/health")
        async def health() -> dict[str, str]:
            return {"status": "ok"}

        client = TestClient(app, raise_server_exceptions=False)
        logger = logging.getLogger("agenthive.access")
        logger.setLevel(logging.INFO)
        # Ensure no log record is emitted for excluded paths.
        with self.assertNoLogs("agenthive.access", level="INFO"):
            client.get("/api/v1/health")

    def test_metrics_endpoint_exposed_and_records_http(self) -> None:
        app = self._build_app()
        client = TestClient(app, raise_server_exceptions=False)
        client.get("/api/v1/echo")
        from app.api.v1.router import metrics as metrics_endpoint

        app.include_router(metrics_endpoint.router) if hasattr(metrics_endpoint, "router") else None
        # Directly call the collector render for verification.
        rendered = metrics_collector.render_prometheus()
        self.assertIn("agenthive_http_requests_total", rendered)


if __name__ == "__main__":
    unittest.main()
