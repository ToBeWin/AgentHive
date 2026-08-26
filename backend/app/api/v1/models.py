from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_permission
from app.core.database import get_session
from app.core.security import Permission
from app.schemas.llm import (
    LLMConnectionTestRequest,
    LLMConnectionTestResponse,
    LLMConnectionTestHistoryResponse,
    LLMCredentialResponse,
    LLMCredentialUpsertRequest,
    LLMDeploymentAcceptanceTestRequest,
    LLMDeploymentAcceptanceTestResponse,
    LLMDeploymentListResponse,
    LLMGovernanceTargetsResponse,
    LLMModelPriceListResponse,
    LLMModelPriceResponse,
    LLMModelPriceUpsertRequest,
    LLMPolicyListResponse,
    LLMPolicyResponse,
    LLMPolicyStatusUpdateRequest,
    LLMPolicyUpsertRequest,
    LLMProviderListResponse,
    LLMReadinessResponse,
)
from app.services.llm_service import (
    get_model_readiness,
    list_model_deployments,
    list_model_governance_targets,
    list_connection_test_history,
    list_model_prices,
    list_model_policies,
    list_model_providers,
    test_model_connection,
    upsert_model_price,
    upsert_model_policy,
    upsert_provider_credential,
    update_model_policy_status,
    verify_model_deployment_call,
)

router = APIRouter(prefix="/models", tags=["models"])


@router.get(
    "/providers",
    response_model=LLMProviderListResponse,
)
async def read_model_providers(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.MODELS_READ))],
) -> LLMProviderListResponse:
    return await list_model_providers(session, principal)


@router.get(
    "/deployments",
    response_model=LLMDeploymentListResponse,
)
async def read_model_deployments(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.MODELS_READ))],
) -> LLMDeploymentListResponse:
    return await list_model_deployments(session, principal)


@router.post(
    "/deployments/{deployment_id}/acceptance-test",
    response_model=LLMDeploymentAcceptanceTestResponse,
)
async def run_model_deployment_acceptance_test(
    request: Request,
    deployment_id: UUID,
    payload: LLMDeploymentAcceptanceTestRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.MODELS_WRITE))],
) -> LLMDeploymentAcceptanceTestResponse:
    return await verify_model_deployment_call(
        session,
        deployment_id,
        principal,
        payload,
        request_id=getattr(request.state, "request_id", None),
    )


@router.get(
    "/readiness",
    response_model=LLMReadinessResponse,
)
async def read_model_readiness(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.MODELS_READ))],
) -> LLMReadinessResponse:
    return await get_model_readiness(session, principal)


@router.get(
    "/policies",
    response_model=LLMPolicyListResponse,
)
async def read_model_policies(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.MODELS_READ))],
) -> LLMPolicyListResponse:
    return await list_model_policies(session, principal)


@router.get(
    "/prices",
    response_model=LLMModelPriceListResponse,
)
async def read_model_prices(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.MODELS_READ))],
) -> LLMModelPriceListResponse:
    _ = principal
    return await list_model_prices(session)


@router.get(
    "/connection-tests",
    response_model=LLMConnectionTestHistoryResponse,
)
async def read_connection_test_history(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.MODELS_READ))],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> LLMConnectionTestHistoryResponse:
    return await list_connection_test_history(session, principal, limit=limit)


@router.get(
    "/governance-targets",
    response_model=LLMGovernanceTargetsResponse,
)
async def read_model_governance_targets(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.MODELS_READ))],
) -> LLMGovernanceTargetsResponse:
    return await list_model_governance_targets(session, principal)


@router.put(
    "/prices",
    response_model=LLMModelPriceResponse,
)
async def save_model_price(
    request: Request,
    payload: LLMModelPriceUpsertRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.MODELS_WRITE))],
) -> LLMModelPriceResponse:
    return await upsert_model_price(
        session,
        payload,
        principal,
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/policies",
    response_model=LLMPolicyResponse,
)
async def save_model_policy(
    request: Request,
    payload: LLMPolicyUpsertRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.MODELS_WRITE))],
) -> LLMPolicyResponse:
    return await upsert_model_policy(
        session,
        payload,
        principal,
        request_id=getattr(request.state, "request_id", None),
    )


@router.patch(
    "/policies/{policy_id}/status",
    response_model=LLMPolicyResponse,
)
async def patch_model_policy_status(
    request: Request,
    policy_id: UUID,
    payload: LLMPolicyStatusUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.MODELS_WRITE))],
) -> LLMPolicyResponse:
    return await update_model_policy_status(
        session,
        policy_id,
        payload,
        principal,
        request_id=getattr(request.state, "request_id", None),
    )


@router.put(
    "/providers/{provider_key}/credential",
    response_model=LLMCredentialResponse,
)
async def save_provider_credential(
    request: Request,
    provider_key: str,
    payload: LLMCredentialUpsertRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.MODELS_WRITE))],
) -> LLMCredentialResponse:
    return await upsert_provider_credential(
        session,
        provider_key=provider_key,
        payload=payload,
        principal=principal,
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/test-connection",
    response_model=LLMConnectionTestResponse,
)
async def test_connection(
    request: Request,
    payload: LLMConnectionTestRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Principal = Depends(require_permission(Permission.MODELS_WRITE)),
) -> LLMConnectionTestResponse:
    return await test_model_connection(
        payload,
        principal,
        session,
        request_id=getattr(request.state, "request_id", None),
    )
