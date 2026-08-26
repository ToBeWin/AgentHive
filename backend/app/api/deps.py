from collections.abc import Callable, Coroutine
from secrets import compare_digest
from typing import Annotated, Any
from uuid import UUID

from fastapi import Cookie, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import is_development_environment, settings
from app.core.database import get_session
from app.core.security import Permission, decode_access_token
from app.models.tenant import Tenant
from app.models.user import User

AUTH_COOKIE_NAME = "agenthive_session"
CSRF_COOKIE_NAME = "agenthive_csrf"


class Principal(BaseModel):
    user_id: UUID
    tenant_id: UUID
    permissions: set[str]
    auth_version: int = 0
    is_development_fallback: bool = False

    def has_permission(self, permission: Permission | str) -> bool:
        required = permission.value if isinstance(permission, Permission) else permission
        return is_tenant_admin(self) or required in self.permissions

    def has_any_permission(self, permissions: set[Permission] | set[str]) -> bool:
        return is_tenant_admin(self) or any(
            self.has_permission(permission) for permission in permissions
        )

    def has_all_permissions(self, permissions: set[Permission] | set[str]) -> bool:
        return is_tenant_admin(self) or all(
            self.has_permission(permission) for permission in permissions
        )


async def get_current_principal(
    authorization: Annotated[str | None, Header()] = None,
    session_cookie: Annotated[str | None, Cookie(alias=AUTH_COOKIE_NAME)] = None,
    csrf_cookie: Annotated[str | None, Cookie(alias=CSRF_COOKIE_NAME)] = None,
    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    session: Annotated[AsyncSession | None, Depends(get_session)] = None,
) -> Principal:
    token: str | None = None
    if authorization is not None:
        scheme, _, bearer_token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not bearer_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Authorization header.",
            )
        token = bearer_token
    elif settings.auth_cookie_enabled and session_cookie:
        if not csrf_cookie or not csrf_header or not compare_digest(csrf_cookie, csrf_header):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing or invalid CSRF token.",
            )
        token = session_cookie
    else:
        if is_development_environment(settings):
            return _development_principal()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
        )

    try:
        payload = decode_access_token(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
        ) from exc

    principal = Principal(
        user_id=UUID(payload["sub"]),
        tenant_id=UUID(payload["tenant_id"]),
        permissions=set(payload.get("permissions", [])),
        auth_version=int(payload.get("ver", 0)),
    )
    if session is not None:
        await _assert_principal_is_active(session, principal)
    return principal


def require_permission(
    permission: Permission,
) -> Callable[..., Coroutine[Any, Any, Principal]]:
    async def dependency(
        authorization: Annotated[str | None, Header()] = None,
        session_cookie: Annotated[str | None, Cookie(alias=AUTH_COOKIE_NAME)] = None,
        csrf_cookie: Annotated[str | None, Cookie(alias=CSRF_COOKIE_NAME)] = None,
        csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
        session: Annotated[AsyncSession | None, Depends(get_session)] = None,
    ) -> Principal:
        principal = await get_current_principal(
            authorization,
            session_cookie,
            csrf_cookie,
            csrf_header,
            session=session,
        )
        if principal.has_permission(permission):
            return principal
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission required: {permission}",
        )

    return dependency


def require_any_permission(
    *permissions: Permission,
) -> Callable[..., Coroutine[Any, Any, Principal]]:
    permission_set = set(permissions)

    async def dependency(
        authorization: Annotated[str | None, Header()] = None,
        session_cookie: Annotated[str | None, Cookie(alias=AUTH_COOKIE_NAME)] = None,
        csrf_cookie: Annotated[str | None, Cookie(alias=CSRF_COOKIE_NAME)] = None,
        csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
        session: Annotated[AsyncSession | None, Depends(get_session)] = None,
    ) -> Principal:
        principal = await get_current_principal(
            authorization,
            session_cookie,
            csrf_cookie,
            csrf_header,
            session=session,
        )
        if principal.has_any_permission(permission_set):
            return principal
        required = ", ".join(sorted(permission.value for permission in permission_set))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"One of these permissions is required: {required}",
        )

    return dependency


def require_all_permissions(
    *permissions: Permission,
) -> Callable[..., Coroutine[Any, Any, Principal]]:
    permission_set = set(permissions)

    async def dependency(
        authorization: Annotated[str | None, Header()] = None,
        session_cookie: Annotated[str | None, Cookie(alias=AUTH_COOKIE_NAME)] = None,
        csrf_cookie: Annotated[str | None, Cookie(alias=CSRF_COOKIE_NAME)] = None,
        csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
        session: Annotated[AsyncSession | None, Depends(get_session)] = None,
    ) -> Principal:
        principal = await get_current_principal(
            authorization,
            session_cookie,
            csrf_cookie,
            csrf_header,
            session=session,
        )
        if principal.has_all_permissions(permission_set):
            return principal
        required = ", ".join(sorted(permission.value for permission in permission_set))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"All of these permissions are required: {required}",
        )

    return dependency


def is_tenant_admin(principal: Principal) -> bool:
    return Permission.TENANT_ADMIN.value in principal.permissions


def _development_principal() -> Principal:
    return Principal(
        user_id=UUID("00000000-0000-4000-8000-000000000001"),
        tenant_id=UUID("00000000-0000-4000-8000-000000000001"),
        permissions={permission.value for permission in Permission},
        auth_version=0,
        is_development_fallback=True,
    )


async def _assert_principal_is_active(session: AsyncSession, principal: Principal) -> None:
    user = await session.get(User, principal.user_id)
    if (
        user is None
        or user.tenant_id != principal.tenant_id
        or user.deleted_at is not None
        or not user.is_active
        or user.auth_version != principal.auth_version
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive user session.",
        )

    tenant = await session.get(Tenant, principal.tenant_id)
    if tenant is None or not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive tenant session.",
        )
