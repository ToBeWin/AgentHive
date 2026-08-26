from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_permission
from app.core.database import get_session
from app.core.security import Permission
from app.schemas.analytics import AnalyticsOverviewResponse
from app.services.analytics_service import get_analytics_overview

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverviewResponse)
async def read_analytics_overview(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.ANALYTICS_READ))],
) -> AnalyticsOverviewResponse:
    return await get_analytics_overview(session, principal)
