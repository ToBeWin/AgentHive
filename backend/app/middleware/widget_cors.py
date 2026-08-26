"""CORS middleware for Web Widget endpoints.

The Web Widget SDK is embedded into customer websites with arbitrary origins,
so the global CORSMiddleware (which restricts to ``cors_origins``) cannot cover
it. This middleware injects permissive CORS headers only on Widget-scoped
paths so the rest of the API keeps its strict CORS policy.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from app.core.config import settings

WIDGET_PATH_PREFIXES: tuple[str, ...] = (
    "/api/v1/channels/poll/web_widget/",
    "/api/v1/channels/webhook/web_widget/",
)


def _origin_allowed(origin: str | None) -> bool:
    if not origin:
        return False
    if "*" in settings.widget_cors_origins:
        return True
    return origin in settings.widget_cors_origins


async def widget_cors_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    is_widget_path = any(request.url.path.startswith(prefix) for prefix in WIDGET_PATH_PREFIXES)
    if not settings.widget_cors_enabled or not is_widget_path:
        return await call_next(request)

    origin = request.headers.get("origin")
    if request.method == "OPTIONS":
        # Preflight: build response without invoking the downstream handler.
        response = Response(status_code=204)
    else:
        response = await call_next(request)

    if _origin_allowed(origin):
        response.headers["Access-Control-Allow-Origin"] = (
            "*" if "*" in settings.widget_cors_origins else origin or "*"
        )
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, X-AgentHive-Signature, X-AgentHive-Timestamp, X-AgentHive-Nonce, X-Request-ID"
        )
        response.headers["Access-Control-Max-Age"] = "86400"
        response.headers["Vary"] = "Origin"
    return response
