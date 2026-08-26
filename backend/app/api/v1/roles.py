from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_permission
from app.core.database import get_session
from app.core.security import Permission
from app.schemas.org_admin import (
    PermissionCatalogResponse,
    RoleCreateRequest,
    RoleDeleteResponse,
    RoleListResponse,
    RolePresetResponse,
    RoleResponse,
    RoleUpdateRequest,
)
from app.services.org_admin_service import (
    create_role,
    delete_role,
    list_role_permissions,
    list_role_presets,
    list_roles,
    update_role,
)

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("", response_model=RoleListResponse)
async def read_roles(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.USERS_READ))],
) -> RoleListResponse:
    return await list_roles(session, principal)


@router.get("/permissions", response_model=PermissionCatalogResponse)
async def read_role_permissions(
    _principal: Annotated[Principal, Depends(require_permission(Permission.USERS_READ))],
) -> PermissionCatalogResponse:
    return list_role_permissions()


@router.get("/presets", response_model=RolePresetResponse)
async def read_role_presets(
    _principal: Annotated[Principal, Depends(require_permission(Permission.USERS_READ))],
) -> RolePresetResponse:
    return list_role_presets()


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def add_role(
    request: Request,
    payload: RoleCreateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.TENANT_ADMIN))],
) -> RoleResponse:
    return await create_role(
        session,
        principal,
        payload,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.patch("/{role_id}", response_model=RoleResponse)
async def edit_role(
    role_id: UUID,
    request: Request,
    payload: RoleUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.TENANT_ADMIN))],
) -> RoleResponse:
    return await update_role(
        session,
        principal,
        role_id,
        payload,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.delete("/{role_id}", response_model=RoleDeleteResponse)
async def remove_role(
    role_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.TENANT_ADMIN))],
) -> RoleDeleteResponse:
    return await delete_role(
        session,
        principal,
        role_id,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
