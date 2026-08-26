"""Structured access log middleware.

Emits one JSON access-log line per request with method, path, status, latency,
request id, tenant hint and client address. Designed for production observability
(log aggregators such as Loki, ELK, Datadog).
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request, Response

from app.core.config import settings
from app.observability.metrics import metrics_collector

access_logger = logging.getLogger("agenthive.access")


async def access_log_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    if not settings.access_log_enabled or request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path
    if any(path.startswith(prefix) for prefix in settings.access_log_exclude_paths):
        return await call_next(request)

    start = time.perf_counter()
    response: Response
    try:
        response = await call_next(request)
    except Exception:
        latency_ms = (time.perf_counter() - start) * 1000
        _emit(
            request=request,
            status=500,
            latency_ms=latency_ms,
            error="unhandled_exception",
        )
        metrics_collector.observe_http_request(
            method=request.method,
            path=path,
            status=500,
            duration_ms=latency_ms,
        )
        raise

    latency_ms = (time.perf_counter() - start) * 1000
    _emit(
        request=request,
        status=response.status_code,
        latency_ms=latency_ms,
    )
    metrics_collector.observe_http_request(
        method=request.method,
        path=path,
        status=response.status_code,
        duration_ms=latency_ms,
    )
    return response


def _emit(
    *,
    request: Request,
    status: int,
    latency_ms: float,
    error: str | None = None,
) -> None:
    forwarded_for = request.headers.get("x-forwarded-for")
    client = (
        forwarded_for.split(",", 1)[0].strip()
        if forwarded_for
        else (request.client.host if request.client else None)
    )
    payload: dict[str, Any] = {
        "method": request.method,
        "path": request.url.path,
        "status": status,
        "latency_ms": round(latency_ms, 3),
        "request_id": getattr(request.state, "request_id", None),
        "tenant": request.headers.get("x-agenthive-tenant"),
        "client": client,
        "user_agent": request.headers.get("user-agent"),
    }
    if error is not None:
        payload["error"] = error
    access_logger.info(json.dumps(payload, ensure_ascii=False))
