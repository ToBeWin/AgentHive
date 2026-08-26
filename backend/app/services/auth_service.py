from datetime import datetime, timedelta, timezone
from time import monotonic
from typing import Any, cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import settings
from app.core.security import (
    Permission,
    create_access_token,
    hash_password,
    password_hash_needs_rehash,
    verify_password,
)
from app.models.org import Department
from app.models.role import Role, UserRole
from app.models.tenant import CostCenter, Tenant
from app.models.user import User, UserDepartment
from app.schemas.auth import (
    AuthTokenResponse,
    AuthUser,
    BootstrapRequest,
    BootstrapResponse,
    LoginRequest,
    LogoutResponse,
    SetupStatusResponse,
)
from app.services.audit_service import record_audit_event


class LoginFailureLimiter:
    def __init__(self) -> None:
        self.failures: dict[str, list[float]] = {}

    def is_locked(
        self,
        keys: list[str],
        *,
        limit: int,
        window_seconds: int,
        now: float | None = None,
    ) -> bool:
        current = now if now is not None else monotonic()
        cutoff = current - window_seconds
        self._compact(cutoff)
        return any(len(self.failures.get(key, [])) >= limit for key in keys)

    def record_failure(
        self,
        keys: list[str],
        *,
        window_seconds: int,
        now: float | None = None,
    ) -> None:
        current = now if now is not None else monotonic()
        cutoff = current - window_seconds
        for key in keys:
            bucket = [item for item in self.failures.get(key, []) if item > cutoff]
            bucket.append(current)
            self.failures[key] = bucket
        self._compact(cutoff)

    def reset(self, keys: list[str]) -> None:
        for key in keys:
            self.failures.pop(key, None)

    def reset_all(self) -> None:
        self.failures.clear()

    def _compact(self, cutoff: float) -> None:
        for key in list(self.failures):
            bucket = [item for item in self.failures[key] if item > cutoff]
            if bucket:
                self.failures[key] = bucket
            else:
                self.failures.pop(key, None)


login_failure_limiter = LoginFailureLimiter()


async def bootstrap_first_tenant(
    session: AsyncSession,
    payload: BootstrapRequest,
    *,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> BootstrapResponse:
    tenant_count = await session.scalar(select(func.count(cast(Any, Tenant.id))))
    if tenant_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="AgentHive has already been initialized.",
        )

    tenant = Tenant(name=payload.tenant_name, slug=payload.tenant_slug, license_type="trial")
    session.add(tenant)
    await session.flush()

    root_department = Department(
        tenant_id=tenant.id,
        name=payload.tenant_name,
        description="Default root department created during AgentHive setup.",
    )
    session.add(root_department)
    await session.flush()

    cost_center = CostCenter(
        tenant_id=tenant.id,
        department_id=root_department.id,
        code="DEFAULT",
        name="Default Cost Center",
        description="Default cost center for initial setup.",
    )
    session.add(cost_center)

    role = Role(
        tenant_id=tenant.id,
        name="Tenant Admin",
        description="Full tenant administration role.",
        permissions=[permission.value for permission in Permission],
        is_system=True,
    )
    session.add(role)
    await session.flush()

    user = User(
        tenant_id=tenant.id,
        email=payload.admin_email.lower(),
        full_name=payload.admin_full_name,
        hashed_password=hash_password(payload.admin_password),
        is_tenant_admin=True,
        is_active=True,
    )
    session.add(user)
    await session.flush()

    session.add(UserRole(user_id=user.id, role_id=role.id, granted_by=user.id))
    session.add(
        UserDepartment(
            user_id=user.id,
            department_id=root_department.id,
            is_leader=True,
            is_primary=True,
            position_title="Administrator",
            cost_center_id=cost_center.id,
        )
    )
    await record_audit_event(
        session,
        tenant_id=tenant.id,
        actor_id=user.id,
        action="auth.bootstrap",
        resource_type="tenant",
        resource_id=tenant.id,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details={"tenant_slug": tenant.slug, "admin_email": user.email},
    )
    await session.commit()

    auth = _build_token_response(
        user=user,
        permissions=role.permissions,
    )
    return BootstrapResponse(
        tenant_id=tenant.id,
        admin_user_id=user.id,
        message="AgentHive initialized.",
        auth=auth,
    )


async def get_setup_status(session: AsyncSession) -> SetupStatusResponse:
    try:
        tenant_count = await session.scalar(select(func.count(cast(Any, Tenant.id)))) or 0
    except Exception as exc:
        return SetupStatusResponse(
            initialized=False,
            tenant_count=0,
            setup_available=False,
            message="AgentHive database is unavailable. Check PostgreSQL before continuing setup.",
            diagnostics={
                "component": "database",
                "status": "unhealthy",
                "error_type": exc.__class__.__name__,
                "action": "check_postgresql_before_setup",
            },
        )
    return SetupStatusResponse(
        initialized=tenant_count > 0,
        tenant_count=tenant_count,
        setup_available=True,
        message="AgentHive setup status is available.",
        diagnostics={"component": "database", "status": "healthy"},
    )


async def login(
    session: AsyncSession,
    payload: LoginRequest,
    *,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuthTokenResponse:
    normalized_email = payload.email.lower()
    attempt_keys = _login_attempt_keys(
        tenant_slug=payload.tenant_slug,
        email=normalized_email,
        ip_address=ip_address,
    )
    failure_limit = max(settings.login_failure_limit, 1)
    failure_window_seconds = max(settings.login_failure_window_seconds, 1)
    if login_failure_limiter.is_locked(
        attempt_keys,
        limit=failure_limit,
        window_seconds=failure_window_seconds,
    ):
        raise _too_many_login_attempts(failure_window_seconds)

    result = await session.execute(
        select(User, Tenant)
        .join(Tenant, cast(ColumnElement[bool], User.tenant_id == Tenant.id))
        .where(
            cast(ColumnElement[bool], Tenant.slug == payload.tenant_slug),
            cast(Any, Tenant.is_active).is_(True),
            cast(ColumnElement[bool], User.email == normalized_email),
            cast(Any, User.deleted_at).is_(None),
        )
    )
    row = result.first()
    if row is None:
        await _record_unknown_login_failure(
            session,
            tenant_slug=payload.tenant_slug,
            email=normalized_email,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        login_failure_limiter.record_failure(
            attempt_keys,
            window_seconds=failure_window_seconds,
        )
        raise _invalid_credentials()

    user, _tenant = row
    if not user.is_active:
        await _record_failed_login(
            session,
            user=user,
            reason="inactive_user",
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        login_failure_limiter.record_failure(
            attempt_keys,
            window_seconds=failure_window_seconds,
        )
        raise _invalid_credentials()
    if not verify_password(payload.password, user.hashed_password):
        await _record_failed_login(
            session,
            user=user,
            reason="invalid_password",
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        login_failure_limiter.record_failure(
            attempt_keys,
            window_seconds=failure_window_seconds,
        )
        raise _invalid_credentials()

    user.last_login_at = datetime.now(timezone.utc)
    login_failure_limiter.reset(attempt_keys)
    if password_hash_needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(payload.password)
    permissions = await _load_permissions(session, user)
    await record_audit_event(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="auth.login",
        resource_type="user",
        resource_id=user.id,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    await session.commit()

    return _build_token_response(user=user, permissions=permissions)


async def refresh_session(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuthTokenResponse:
    user = await _load_active_session_user(session, tenant_id=tenant_id, user_id=user_id)
    permissions = await _load_permissions(session, user)
    await record_audit_event(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="auth.refresh",
        resource_type="user",
        resource_id=user.id,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    await session.commit()
    return _build_token_response(user=user, permissions=permissions)


async def logout(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> LogoutResponse:
    user = await _load_active_session_user(session, tenant_id=tenant_id, user_id=user_id)
    user.auth_version += 1
    await record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=user_id,
        action="auth.logout",
        resource_type="user",
        resource_id=user_id,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    await session.commit()
    return LogoutResponse(message="Logged out.")


async def _load_active_session_user(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
) -> User:
    result = await session.execute(
        select(User)
        .join(Tenant, cast(ColumnElement[bool], User.tenant_id == Tenant.id))
        .where(
            cast(ColumnElement[bool], User.id == user_id),
            cast(ColumnElement[bool], User.tenant_id == tenant_id),
            cast(Any, User.deleted_at).is_(None),
            cast(Any, User.is_active).is_(True),
            cast(Any, Tenant.is_active).is_(True),
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session.",
        )
    return user


async def _record_unknown_login_failure(
    session: AsyncSession,
    *,
    tenant_slug: str,
    email: str,
    request_id: str | None,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    tenant = await session.scalar(
        select(Tenant).where(
            cast(ColumnElement[bool], Tenant.slug == tenant_slug),
            cast(Any, Tenant.is_active).is_(True),
        )
    )
    if tenant is None:
        return
    await record_audit_event(
        session,
        tenant_id=tenant.id,
        actor_id=None,
        actor_type="anonymous",
        action="auth.login_failed",
        status="failure",
        resource_type="user",
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details={
            "tenant_slug": tenant_slug,
            "email": email,
            "reason": "invalid_credentials",
        },
    )
    await session.commit()


async def _record_failed_login(
    session: AsyncSession,
    *,
    user: User,
    reason: str,
    request_id: str | None,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    await record_audit_event(
        session,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="auth.login_failed",
        status="failure",
        resource_type="user",
        resource_id=user.id,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details={"email": user.email, "reason": reason},
    )
    await session.commit()


async def _load_permissions(session: AsyncSession, user: User) -> list[str]:
    if user.is_tenant_admin or user.is_super_admin:
        return [permission.value for permission in Permission]

    result = await session.execute(
        select(Role.permissions)
        .join(UserRole, cast(ColumnElement[bool], UserRole.role_id == Role.id))
        .where(
            cast(ColumnElement[bool], UserRole.user_id == user.id),
            cast(ColumnElement[bool], Role.tenant_id == user.tenant_id),
        )
    )
    permissions: set[str] = set()
    for permission_list in result.scalars():
        permissions.update(permission_list)
    return sorted(permissions)


def _build_token_response(user: User, permissions: list[str]) -> AuthTokenResponse:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    token = create_access_token(
        subject=user.id,
        tenant_id=user.tenant_id,
        permissions=permissions,
        auth_version=user.auth_version,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    return AuthTokenResponse(
        access_token=token,
        expires_at=expires_at,
        user=AuthUser(
            id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            full_name=user.full_name,
            is_tenant_admin=user.is_tenant_admin,
            is_super_admin=user.is_super_admin,
            permissions=permissions,
        ),
    )


def _invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid tenant, email, or password.",
    )


def _too_many_login_attempts(retry_after_seconds: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many login attempts. Try again later.",
        headers={"Retry-After": str(retry_after_seconds)},
    )


def _login_attempt_keys(
    *,
    tenant_slug: str,
    email: str,
    ip_address: str | None,
) -> list[str]:
    normalized_tenant = tenant_slug.strip().lower()
    normalized_email = email.strip().lower()
    normalized_ip = (ip_address or "unknown").strip().lower()
    return [
        f"tenant:{normalized_tenant}:email:{normalized_email}",
        f"tenant:{normalized_tenant}:ip:{normalized_ip}",
    ]
