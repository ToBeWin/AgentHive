from contextlib import asynccontextmanager
from pathlib import Path
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import assert_production_config_safe, settings
from app.core.redis import close_redis_client
from app.llm.circuit_breaker import circuit_breaker
from app.middleware.access_log import access_log_middleware
from app.middleware.rate_limit import rate_limit_middleware
from app.middleware.request_id import request_id_middleware
from app.middleware.security_headers import security_headers_middleware
from app.middleware.widget_cors import widget_cors_middleware


def _init_sentry() -> None:
    """Initialise Sentry SDK if a DSN is configured.

    Uses lazy import so the `sentry-sdk` dependency is optional. When
    `SENTRY_DSN` is unset (the default), this is a no-op.
    """
    dsn = settings.sentry_dsn
    if not dsn:
        return
    try:
        import sentry_sdk
    except ImportError:
        # sentry-sdk not installed; skip silently. Operators who set
        # SENTRY_DSN should add sentry-sdk to pyproject.toml.
        return
    sentry_sdk.init(
        dsn=dsn,
        environment=settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
    )


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield
    await close_redis_client()


def create_app() -> FastAPI:
    assert_production_config_safe(settings)
    _init_sentry()
    circuit_breaker.configure(
        enabled=settings.llm_circuit_breaker_enabled,
        failure_threshold=settings.llm_circuit_breaker_failure_threshold,
        cooldown_seconds=settings.llm_circuit_breaker_cooldown_seconds,
        success_threshold=settings.llm_circuit_breaker_success_threshold,
    )
    app = FastAPI(
        title="AgentHive API",
        version=settings.app_version,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=_lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(rate_limit_middleware)
    app.middleware("http")(security_headers_middleware)
    app.middleware("http")(widget_cors_middleware)
    app.middleware("http")(access_log_middleware)
    app.middleware("http")(request_id_middleware)
    app.include_router(api_router, prefix="/api/v1")
    _mount_widget_static(app)
    return app


def _mount_widget_static(app: FastAPI) -> None:
    """Serve the Web Widget SDK at ``/widget/`` (no auth, public asset)."""
    static_dir = Path(__file__).resolve().parent / "static" / "widget"
    if static_dir.is_dir():
        app.mount(
            "/widget",
            StaticFiles(directory=str(static_dir), html=False),
            name="widget-static",
        )


app = create_app()
