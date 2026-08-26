"""Unit tests for Web Widget SDK serving and Widget-scoped CORS middleware."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.widget_cors import widget_cors_middleware


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/v1/channels/poll/web_widget/{channel_key}")
    async def poll(channel_key: str) -> dict[str, str]:
        return {"channel_key": channel_key}

    @app.post("/api/v1/channels/webhook/web_widget/{channel_key}")
    async def webhook(channel_key: str) -> dict[str, str]:
        return {"ok": "true"}

    @app.get("/api/v1/orgs")
    async def orgs() -> dict[str, str]:
        return {"ok": "true"}

    app.middleware("http")(widget_cors_middleware)
    return app


class WidgetCorsMiddlewareTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = _build_app()
        self.client = TestClient(self.app)

    def test_cors_headers_on_widget_poll_with_origin(self) -> None:
        response = self.client.get(
            "/api/v1/channels/poll/web_widget/demo",
            headers={"Origin": "https://customer.example.com"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("access-control-allow-origin"), "*")
        self.assertIn("GET", response.headers.get("access-control-allow-methods", ""))
        self.assertIn(
            "X-AgentHive-Signature", response.headers.get("access-control-allow-headers", "")
        )

    def test_cors_headers_on_widget_webhook_with_origin(self) -> None:
        response = self.client.post(
            "/api/v1/channels/webhook/web_widget/demo",
            json={"text": "hi"},
            headers={"Origin": "https://customer.example.com"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("access-control-allow-origin"), "*")

    def test_options_preflight_returns_204_with_cors_headers(self) -> None:
        response = self.client.options(
            "/api/v1/channels/poll/web_widget/demo",
            headers={
                "Origin": "https://customer.example.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-AgentHive-Signature",
            },
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.headers.get("access-control-allow-origin"), "*")
        self.assertEqual(response.headers.get("access-control-max-age"), "86400")

    def test_no_cors_headers_when_origin_missing(self) -> None:
        response = self.client.get("/api/v1/channels/poll/web_widget/demo")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_no_cors_headers_on_non_widget_paths(self) -> None:
        """Non-widget endpoints must not get permissive CORS headers."""
        response = self.client.get(
            "/api/v1/orgs",
            headers={"Origin": "https://evil.example.com"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("access-control-allow-origin", response.headers)

    @patch("app.middleware.widget_cors.settings")
    def test_origin_restricted_when_not_wildcard(self, mock_settings) -> None:
        mock_settings.widget_cors_enabled = True
        mock_settings.widget_cors_origins = ["https://allowed.example.com"]
        response = self.client.get(
            "/api/v1/channels/poll/web_widget/demo",
            headers={"Origin": "https://allowed.example.com"},
        )
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            "https://allowed.example.com",
        )

    @patch("app.middleware.widget_cors.settings")
    def test_origin_blocked_when_not_in_allowlist(self, mock_settings) -> None:
        mock_settings.widget_cors_enabled = True
        mock_settings.widget_cors_origins = ["https://allowed.example.com"]
        response = self.client.get(
            "/api/v1/channels/poll/web_widget/demo",
            headers={"Origin": "https://evil.example.com"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("access-control-allow-origin", response.headers)

    @patch("app.middleware.widget_cors.settings")
    def test_cors_disabled_passthrough(self, mock_settings) -> None:
        mock_settings.widget_cors_enabled = False
        mock_settings.widget_cors_origins = ["*"]
        response = self.client.get(
            "/api/v1/channels/poll/web_widget/demo",
            headers={"Origin": "https://customer.example.com"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("access-control-allow-origin", response.headers)


class WidgetStaticAssetTests(unittest.TestCase):
    """Verify the Widget SDK static asset is mounted and served."""

    def test_widget_js_served_from_mount(self) -> None:
        from app.main import create_app

        app = create_app()
        client = TestClient(app)
        response = client.get("/widget/agenthive-widget.js")
        self.assertEqual(response.status_code, 200)
        body = response.text
        # SDK header should be present.
        self.assertIn("AgentHive Web Widget SDK", body)
        # Should contain the polling endpoint construction.
        self.assertIn("/api/v1/channels/poll/web_widget/", body)
        # Should contain the webhook endpoint construction.
        self.assertIn("/api/v1/channels/webhook/web_widget/", body)
        # Content type should be JavaScript.
        self.assertIn("javascript", response.headers.get("content-type", ""))

    def test_widget_js_not_rate_limited_or_logged(self) -> None:
        """Static widget asset should bypass rate limiter and access log."""
        # Indirect verification: the endpoint returns 200 without auth,
        # and we can call it multiple times rapidly without 429.
        from app.main import create_app

        app = create_app()
        client = TestClient(app)
        for _ in range(5):
            response = client.get("/widget/agenthive-widget.js")
            self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
