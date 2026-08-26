from datetime import timedelta
from secrets import token_urlsafe
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    AUTH_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    Principal,
    get_current_principal,
)
from app.core.config import settings
from app.core.database import get_session
from app.schemas.auth import (
    AuthTokenResponse,
    BootstrapRequest,
    BootstrapResponse,
    LoginRequest,
    LogoutResponse,
    SetupStatusResponse,
)
from app.services.auth_service import (
    bootstrap_first_tenant,
    get_setup_status,
    login,
    logout,
    refresh_session,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/setup-status", response_model=SetupStatusResponse)
async def read_setup_status(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SetupStatusResponse:
    return await get_setup_status(session)


@router.post("/bootstrap", response_model=BootstrapResponse, status_code=201)
async def bootstrap(
    request: Request,
    response: Response,
    payload: BootstrapRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BootstrapResponse:
    result = await bootstrap_first_tenant(
        session,
        payload,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    _set_auth_cookies(response, result.auth)
    return _browser_bootstrap_response(result)


@router.post("/login", response_model=AuthTokenResponse)
async def login_for_access_token(
    request: Request,
    response: Response,
    payload: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthTokenResponse:
    result = await login(
        session,
        payload,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    _set_auth_cookies(response, result)
    return _browser_auth_response(result)


@router.post("/refresh", response_model=AuthTokenResponse)
async def refresh_access_token(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> AuthTokenResponse:
    result = await refresh_session(
        session,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    _set_auth_cookies(response, result)
    return _browser_auth_response(result)


@router.post("/logout", response_model=LogoutResponse)
async def logout_current_user(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> LogoutResponse:
    result = await logout(
        session,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    _clear_auth_cookies(response)
    return result


def _set_auth_cookies(response: Response, auth: AuthTokenResponse) -> None:
    if not settings.auth_cookie_enabled:
        return
    max_age = max(int(timedelta(minutes=settings.access_token_expire_minutes).total_seconds()), 1)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=auth.access_token,
        max_age=max_age,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/api",
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token_urlsafe(32),
        max_age=max_age,
        httponly=False,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(
        AUTH_COOKIE_NAME,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/api",
    )
    response.delete_cookie(
        CSRF_COOKIE_NAME,
        httponly=False,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


def _browser_auth_response(auth: AuthTokenResponse) -> AuthTokenResponse:
    if not settings.auth_cookie_enabled:
        return auth
    return auth.model_copy(update={"access_token": ""})


def _browser_bootstrap_response(result: BootstrapResponse) -> BootstrapResponse:
    if not settings.auth_cookie_enabled:
        return result
    return result.model_copy(update={"auth": _browser_auth_response(result.auth)})
