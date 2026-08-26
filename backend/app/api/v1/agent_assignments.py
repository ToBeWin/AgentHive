"""Agent-User assignment API endpoints."""

from datetime import datetime, timezone
from typing import Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import ColumnElement, CursorResult, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_permission
from app.core.database import get_session
from app.core.security import Permission
from app.models.agent_module import AgentInstance, AgentUserAssignment
from app.models.user import User
from app.schemas.agent_assignments import (
    AgentAssignmentBulkRequest,
    AgentAssignmentListResponse,
    AgentAssignmentResponse,
    UserAgentItem,
    UserAgentsResponse,
)

router = APIRouter(prefix="/agent-assignments", tags=["agent-assignments"])


def _build_assignment_response(
    assignment: AgentUserAssignment,
    user: User,
) -> AgentAssignmentResponse:
    return AgentAssignmentResponse(
        id=assignment.id,
        agent_id=assignment.agent_id,
        user_id=assignment.user_id,
        user_email=user.email,
        user_full_name=user.full_name,
        role=assignment.role,
        assigned_by=assignment.assigned_by,
        created_at=assignment.created_at,
    )


async def _list_assignments_for_agent(
    session: AsyncSession,
    *,
    agent_id: UUID,
    tenant_id: UUID,
) -> AgentAssignmentListResponse:
    result = await session.execute(
        select(AgentUserAssignment, User)
        .join(User, cast(ColumnElement[bool], AgentUserAssignment.user_id == User.id))
        .where(
            cast(ColumnElement[bool], AgentUserAssignment.agent_id == agent_id),
            cast(ColumnElement[bool], AgentUserAssignment.tenant_id == tenant_id),
            cast(ColumnElement[bool], User.tenant_id == tenant_id),
            cast(Any, User.deleted_at).is_(None),
        )
        .order_by(cast(Any, AgentUserAssignment.created_at).asc())
    )
    assignments = [
        _build_assignment_response(assignment, user) for assignment, user in result.all()
    ]
    return AgentAssignmentListResponse(assignments=assignments)


@router.get("/agents/{agent_id}/users", response_model=AgentAssignmentListResponse)
async def list_agent_users(
    agent_id: UUID,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(require_permission(Permission.AGENTS_READ)),
) -> AgentAssignmentListResponse:
    """List all users assigned to an agent."""
    agent = await session.get(AgentInstance, agent_id)
    if not agent or agent.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail="Agent not found")

    return await _list_assignments_for_agent(
        session, agent_id=agent_id, tenant_id=principal.tenant_id
    )


@router.post(
    "/agents/{agent_id}/users",
    response_model=AgentAssignmentListResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_users_to_agent(
    agent_id: UUID,
    payload: AgentAssignmentBulkRequest,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(require_permission(Permission.AGENTS_WRITE)),
) -> AgentAssignmentListResponse:
    """Assign multiple users to an agent. Replaces existing assignments."""
    agent = await session.get(AgentInstance, agent_id)
    if not agent or agent.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail="Agent not found")

    await _validate_assignment_users(
        session,
        tenant_id=principal.tenant_id,
        user_ids=[item.user_id for item in payload.users],
    )

    # Delete existing assignments
    await session.execute(
        delete(AgentUserAssignment).where(
            cast(ColumnElement[bool], AgentUserAssignment.agent_id == agent_id),
            cast(ColumnElement[bool], AgentUserAssignment.tenant_id == principal.tenant_id),
        )
    )

    # Create new assignments
    now = datetime.now(timezone.utc)
    for item in payload.users:
        assignment = AgentUserAssignment(
            tenant_id=principal.tenant_id,
            agent_id=agent_id,
            user_id=item.user_id,
            role=item.role,
            assigned_by=principal.user_id,
            created_at=now,
            updated_at=now,
        )
        session.add(assignment)

    await session.commit()

    return await _list_assignments_for_agent(
        session, agent_id=agent_id, tenant_id=principal.tenant_id
    )


@router.delete("/agents/{agent_id}/users/{user_id}", status_code=204)
async def remove_agent_user(
    agent_id: UUID,
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(require_permission(Permission.AGENTS_WRITE)),
) -> None:
    """Remove a user from an agent assignment."""
    result = await session.execute(
        delete(AgentUserAssignment).where(
            cast(ColumnElement[bool], AgentUserAssignment.agent_id == agent_id),
            cast(ColumnElement[bool], AgentUserAssignment.user_id == user_id),
            cast(ColumnElement[bool], AgentUserAssignment.tenant_id == principal.tenant_id),
        )
    )
    if cast(CursorResult[Any], result).rowcount == 0:
        raise HTTPException(status_code=404, detail="Assignment not found")
    await session.commit()


@router.get("/users/{user_id}/agents", response_model=UserAgentsResponse)
async def list_user_agents(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(require_permission(Permission.AGENTS_READ)),
) -> UserAgentsResponse:
    """List all agents assigned to a user ('My Agents' view)."""
    await _validate_assignment_users(
        session,
        tenant_id=principal.tenant_id,
        user_ids=[user_id],
    )
    result = await session.execute(
        select(AgentUserAssignment, AgentInstance)
        .join(
            AgentInstance,
            cast(ColumnElement[bool], AgentUserAssignment.agent_id == AgentInstance.id),
        )
        .where(
            cast(ColumnElement[bool], AgentUserAssignment.user_id == user_id),
            cast(ColumnElement[bool], AgentUserAssignment.tenant_id == principal.tenant_id),
            cast(ColumnElement[bool], AgentInstance.status == "active"),
        )
        .order_by(cast(Any, AgentUserAssignment.created_at).asc())
    )
    agents = [
        UserAgentItem(
            agent_id=instance.id,
            agent_name=instance.name,
            agent_key=instance.agent_key,
            description=instance.description,
            role=assignment.role,
            status=instance.status,
        )
        for assignment, instance in result.all()
    ]
    return UserAgentsResponse(agents=agents)


@router.get("/my-agents", response_model=UserAgentsResponse)
async def list_my_agents(
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(require_permission(Permission.AGENTS_READ)),
) -> UserAgentsResponse:
    """List agents assigned to the current user ('My Agents' shortcut)."""
    return await list_user_agents(principal.user_id, session=session, principal=principal)


async def _validate_assignment_users(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_ids: list[UUID],
) -> None:
    """Reject duplicate, cross-tenant, deleted, or inactive assignment targets."""

    unique_ids = set(user_ids)
    if len(unique_ids) != len(user_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Agent assignment contains duplicate or unavailable users.",
        )
    result = await session.execute(
        select(cast(Any, User.id)).where(
            cast(Any, User.id).in_(unique_ids),
            cast(ColumnElement[bool], User.tenant_id == tenant_id),
            cast(Any, User.deleted_at).is_(None),
            cast(Any, User.is_active).is_(True),
        )
    )
    matched_ids = set(result.scalars().all())
    if matched_ids != unique_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Agent assignment contains duplicate or unavailable users.",
        )
