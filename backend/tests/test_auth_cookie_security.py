from datetime import UTC, datetime
from uuid import UUID

from fastapi import Response

from app.api.deps import AUTH_COOKIE_NAME, CSRF_COOKIE_NAME
from app.api.v1.auth import _browser_auth_response, _clear_auth_cookies, _set_auth_cookies
from app.core.config import settings
from app.schemas.auth import AuthTokenResponse, AuthUser


def _auth_response() -> AuthTokenResponse:
    return AuthTokenResponse(
        access_token="header-token-for-external-clients",
        expires_at=datetime(2026, 1, 1, tzinfo=UTC),
        user=AuthUser(
            id=UUID("00000000-0000-4000-8000-000000000001"),
            tenant_id=UUID("00000000-0000-4000-8000-000000000002"),
            email="admin@example.com",
            full_name="Admin",
            is_tenant_admin=True,
            is_super_admin=True,
            permissions=["tenant:admin"],
        ),
    )


class TestAuthCookieSecurity:
    def setup_method(self) -> None:
        self._enabled = settings.auth_cookie_enabled
        self._secure = settings.auth_cookie_secure
        settings.auth_cookie_enabled = True
        settings.auth_cookie_secure = True

    def teardown_method(self) -> None:
        settings.auth_cookie_enabled = self._enabled
        settings.auth_cookie_secure = self._secure

    def test_sets_http_only_session_and_readable_csrf_cookie(self) -> None:
        response = Response()

        _set_auth_cookies(response, _auth_response())

        cookies = [value.decode() for key, value in response.raw_headers if key == b"set-cookie"]
        session_cookie = next(
            value for value in cookies if value.startswith(f"{AUTH_COOKIE_NAME}=")
        )
        csrf_cookie = next(value for value in cookies if value.startswith(f"{CSRF_COOKIE_NAME}="))
        assert "HttpOnly" in session_cookie
        assert "Secure" in session_cookie
        assert "Path=/api" in session_cookie
        assert "SameSite=lax" in session_cookie
        assert "HttpOnly" not in csrf_cookie
        assert "Secure" in csrf_cookie
        assert "Path=/" in csrf_cookie

    def test_browser_response_redacts_bearer_token_but_preserves_api_compatibility_when_disabled(
        self,
    ) -> None:
        auth = _auth_response()
        assert _browser_auth_response(auth).access_token == ""
        assert auth.access_token == "header-token-for-external-clients"

        settings.auth_cookie_enabled = False
        assert _browser_auth_response(auth).access_token == "header-token-for-external-clients"

    def test_logout_deletes_both_cookie_paths(self) -> None:
        response = Response()

        _clear_auth_cookies(response)

        cookies = [value.decode() for key, value in response.raw_headers if key == b"set-cookie"]
        assert any(
            value.startswith(f"{AUTH_COOKIE_NAME}=") and "Path=/api" in value for value in cookies
        )
        assert any(
            value.startswith(f"{CSRF_COOKIE_NAME}=") and "Path=/" in value for value in cookies
        )
