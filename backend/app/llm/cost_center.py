from typing import Any, cast
from uuid import UUID

from sqlalchemy import ColumnElement
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.llm.schemas import LLMRequestContext
from app.models.org import Department
from app.models.tenant import CostCenter
from app.models.user import UserDepartment


async def resolve_cost_center(
    session: AsyncSession | None,
    context: LLMRequestContext,
) -> tuple[UUID | None, str]:
    if context.cost_center_id is not None:
        return context.cost_center_id, "context"
    if session is None or context.user_id is None:
        return None, "unresolved"

    try:
        if context.department_id is not None:
            result = await session.execute(
                select(UserDepartment.cost_center_id)
                .join(
                    Department,
                    cast(ColumnElement[bool], Department.id == UserDepartment.department_id),
                )
                .join(
                    CostCenter,
                    cast(ColumnElement[bool], CostCenter.id == UserDepartment.cost_center_id),
                )
                .where(
                    cast(ColumnElement[bool], UserDepartment.user_id == context.user_id),
                    cast(
                        ColumnElement[bool], UserDepartment.department_id == context.department_id
                    ),
                    cast(ColumnElement[bool], Department.tenant_id == context.tenant_id),
                    cast(ColumnElement[bool], CostCenter.tenant_id == context.tenant_id),
                    cast(Any, CostCenter.is_active).is_(True),
                )
            )
            cost_center_id = result.scalar_one_or_none()
            if cost_center_id is not None:
                return cost_center_id, "user_department"

        result = await session.execute(
            select(UserDepartment.cost_center_id)
            .join(
                Department, cast(ColumnElement[bool], Department.id == UserDepartment.department_id)
            )
            .join(
                CostCenter,
                cast(ColumnElement[bool], CostCenter.id == UserDepartment.cost_center_id),
            )
            .where(
                cast(ColumnElement[bool], UserDepartment.user_id == context.user_id),
                cast(Any, UserDepartment.cost_center_id).is_not(None),
                cast(ColumnElement[bool], Department.tenant_id == context.tenant_id),
                cast(ColumnElement[bool], CostCenter.tenant_id == context.tenant_id),
                cast(Any, CostCenter.is_active).is_(True),
            )
            .order_by(
                cast(Any, UserDepartment.is_primary).desc(),
                cast(Any, UserDepartment.created_at).asc(),
            )
            .limit(1)
        )
        cost_center_id = result.scalar_one_or_none()
        if cost_center_id is not None:
            return cost_center_id, "user_primary_department"
    except (OSError, SQLAlchemyError, AttributeError):
        rollback = getattr(session, "rollback", None)
        if rollback is not None:
            await rollback()
        return None, "resolution_failed"

    return None, "unresolved"
