from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_any_permission, require_permission
from app.core.database import get_session
from app.core.security import Permission
from app.schemas.license import (
    DeploymentFingerprintResponse,
    LicenseActivationRequest,
    LicenseActivationRequestExport,
    LicenseActivationResponse,
    LicenseDeactivateResponse,
    LicenseModulesResponse,
    LicenseStatusResponse,
)
from app.services.license_service import (
    activate_license_for_tenant,
    deactivate_license_for_tenant,
    get_activation_request_for_tenant,
    get_deployment_fingerprint,
    get_license_modules_for_tenant,
    get_license_status_for_tenant,
)

router = APIRouter(prefix="/admin/license", tags=["admin-license"])


@router.get(
    "/fingerprint",
    response_model=DeploymentFingerprintResponse,
    dependencies=[Depends(require_permission(Permission.LICENSE_READ))],
)
async def read_deployment_fingerprint() -> DeploymentFingerprintResponse:
    return get_deployment_fingerprint()


@router.get(
    "/activation-request",
    response_model=LicenseActivationRequestExport,
)
async def export_activation_request(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.LICENSE_READ))],
) -> LicenseActivationRequestExport:
    return await get_activation_request_for_tenant(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.post(
    "/activate",
    response_model=LicenseActivationResponse,
)
async def activate_deployment_license(
    request: Request,
    payload: LicenseActivationRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.LICENSE_WRITE))],
) -> LicenseActivationResponse:
    return await activate_license_for_tenant(
        session,
        payload,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.get(
    "/status",
    response_model=LicenseStatusResponse,
)
async def read_license_status(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.LICENSE_READ))],
) -> LicenseStatusResponse:
    return await get_license_status_for_tenant(session, tenant_id=principal.tenant_id)


@router.get(
    "/modules",
    response_model=LicenseModulesResponse,
)
async def read_license_modules(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[
        Principal,
        Depends(require_any_permission(Permission.LICENSE_READ, Permission.CHANNELS_READ)),
    ],
) -> LicenseModulesResponse:
    return await get_license_modules_for_tenant(session, tenant_id=principal.tenant_id)


@router.post(
    "/deactivate",
    response_model=LicenseDeactivateResponse,
)
async def deactivate_deployment_license(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.LICENSE_WRITE))],
) -> LicenseDeactivateResponse:
    return await deactivate_license_for_tenant(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
