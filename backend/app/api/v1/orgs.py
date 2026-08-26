from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_permission
from app.core.database import get_session
from app.core.security import Permission
from app.schemas.org_admin import (
    CostCenterCreateRequest,
    CostCenterListResponse,
    CostCenterResponse,
    CostCenterUpdateRequest,
    DeleteResponse,
    DepartmentCreateRequest,
    DepartmentListResponse,
    DepartmentResponse,
    DepartmentUpdateRequest,
)
from app.services.org_admin_service import (
    create_cost_center,
    create_department,
    delete_cost_center,
    delete_department,
    list_cost_centers,
    list_departments,
    update_cost_center,
    update_department,
)

router = APIRouter(prefix="/orgs", tags=["orgs"])


@router.get("/departments", response_model=DepartmentListResponse)
async def read_departments(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.DEPARTMENTS_READ))],
) -> DepartmentListResponse:
    return await list_departments(session, principal)


@router.post(
    "/departments",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_department(
    request: Request,
    payload: DepartmentCreateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.DEPARTMENTS_WRITE))],
) -> DepartmentResponse:
    return await create_department(
        session,
        principal,
        payload,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.patch("/departments/{department_id}", response_model=DepartmentResponse)
async def patch_department(
    department_id: UUID,
    request: Request,
    payload: DepartmentUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.DEPARTMENTS_WRITE))],
) -> DepartmentResponse:
    return await update_department(
        session,
        principal,
        department_id,
        payload,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.delete("/departments/{department_id}", response_model=DeleteResponse)
async def remove_department(
    department_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.DEPARTMENTS_WRITE))],
) -> DeleteResponse:
    return await delete_department(
        session,
        principal,
        department_id,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.get("/cost-centers", response_model=CostCenterListResponse)
async def read_cost_centers(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.DEPARTMENTS_READ))],
) -> CostCenterListResponse:
    return await list_cost_centers(session, principal)


@router.post(
    "/cost-centers",
    response_model=CostCenterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_cost_center(
    request: Request,
    payload: CostCenterCreateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.DEPARTMENTS_WRITE))],
) -> CostCenterResponse:
    return await create_cost_center(
        session,
        principal,
        payload,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.patch("/cost-centers/{cost_center_id}", response_model=CostCenterResponse)
async def patch_cost_center(
    cost_center_id: UUID,
    request: Request,
    payload: CostCenterUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.DEPARTMENTS_WRITE))],
) -> CostCenterResponse:
    return await update_cost_center(
        session,
        principal,
        cost_center_id,
        payload,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.delete("/cost-centers/{cost_center_id}", response_model=DeleteResponse)
async def remove_cost_center(
    cost_center_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.DEPARTMENTS_WRITE))],
) -> DeleteResponse:
    return await delete_cost_center(
        session,
        principal,
        cost_center_id,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
