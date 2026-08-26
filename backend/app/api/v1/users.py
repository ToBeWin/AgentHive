from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_permission
from app.core.database import get_session
from app.core.security import Permission
from app.schemas.org_admin import (
    UserCreateRequest,
    UserListResponse,
    UserPasswordResetRequest,
    UserResponse,
    UserStatusUpdateRequest,
    UserUpdateRequest,
)
from app.services.org_admin_service import (
    create_user,
    list_users,
    reset_user_password,
    update_user,
    update_user_status,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=UserListResponse)
async def read_users(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.USERS_READ))],
    search: Annotated[str | None, Query(max_length=100)] = None,
    department_id: Annotated[UUID | None, Query()] = None,
    role_id: Annotated[UUID | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> UserListResponse:
    return await list_users(
        session,
        principal,
        search=search,
        department_id=department_id,
        role_id=role_id,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def add_user(
    request: Request,
    payload: UserCreateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.USERS_WRITE))],
) -> UserResponse:
    return await create_user(
        session,
        principal,
        payload,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def patch_user(
    user_id: UUID,
    request: Request,
    payload: UserUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.USERS_WRITE))],
) -> UserResponse:
    return await update_user(
        session,
        principal,
        user_id,
        payload,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.patch("/{user_id}/status", response_model=UserResponse)
async def patch_user_status(
    user_id: UUID,
    request: Request,
    payload: UserStatusUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.USERS_WRITE))],
) -> UserResponse:
    return await update_user_status(
        session,
        principal,
        user_id,
        payload,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.patch("/{user_id}/password", response_model=UserResponse)
async def patch_user_password(
    user_id: UUID,
    request: Request,
    payload: UserPasswordResetRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.USERS_WRITE))],
) -> UserResponse:
    return await reset_user_password(
        session,
        principal,
        user_id,
        payload,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
