from typing import Any, cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import delete, select

from app.api.deps import Principal
from app.core.security import Permission, hash_password
from app.models.base import utc_now
from app.models.org import Department
from app.models.role import Role, UserRole
from app.models.tenant import CostCenter
from app.models.user import User, UserDepartment
from app.schemas.org_admin import (
    CostCenterCreateRequest,
    CostCenterListResponse,
    CostCenterResponse,
    CostCenterUpdateRequest,
    DeleteResponse,
    DepartmentCreateRequest,
    DepartmentListResponse,
    DepartmentResponse,
    DepartmentTreeNode,
    DepartmentUpdateRequest,
    PermissionCatalogItem,
    PermissionCatalogResponse,
    RoleCreateRequest,
    RoleDeleteResponse,
    RoleListResponse,
    RolePresetItem,
    RolePresetResponse,
    RoleResponse,
    RoleUpdateRequest,
    UserCreateRequest,
    UserDepartmentBindingResponse,
    UserListResponse,
    UserPasswordResetRequest,
    UserResponse,
    UserRoleResponse,
    UserStatusUpdateRequest,
    UserUpdateRequest,
)
from app.services.audit_service import record_audit_event
from app.services.license_service import ensure_license_capacity


_PERMISSION_LABELS: dict[Permission, str] = {
    Permission.TENANT_ADMIN: "Tenant administration",
    Permission.USERS_READ: "Read users",
    Permission.USERS_WRITE: "Manage users",
    Permission.DEPARTMENTS_READ: "Read departments",
    Permission.DEPARTMENTS_WRITE: "Manage departments",
    Permission.AGENTS_READ: "Read agents",
    Permission.AGENTS_WRITE: "Manage agents",
    Permission.CHAT_READ: "Read conversations",
    Permission.CHAT_WRITE: "Use digital employees",
    Permission.KNOWLEDGE_READ: "Read knowledge bases",
    Permission.KNOWLEDGE_WRITE: "Manage knowledge bases",
    Permission.CHANNELS_READ: "Read channels",
    Permission.CHANNELS_WRITE: "Manage channels",
    Permission.MCP_READ: "Read MCP servers",
    Permission.MCP_WRITE: "Manage MCP servers",
    Permission.MCP_INVOKE: "Invoke MCP tools",
    Permission.MODELS_READ: "Read model settings",
    Permission.MODELS_WRITE: "Manage model settings",
    Permission.BUDGETS_READ: "Read budgets",
    Permission.BUDGETS_WRITE: "Manage budgets",
    Permission.BUDGETS_EXPORT: "Export budget ledgers",
    Permission.ANALYTICS_READ: "Read analytics dashboards",
    Permission.AUDIT_READ: "Read audit logs",
    Permission.AUDIT_EXPORT: "Export audit logs",
    Permission.LICENSE_READ: "Read license",
    Permission.LICENSE_WRITE: "Manage license",
    Permission.SYSTEM_DIAGNOSTICS: "Export system diagnostics",
}

_ROLE_PRESETS: tuple[RolePresetItem, ...] = (
    RolePresetItem(
        key="enterprise_admin",
        name="Enterprise Admin",
        description="Full tenant administration for users, departments, models, budgets, License, audit, and delivery.",
        permissions=[Permission.TENANT_ADMIN.value],
        scope="tenant",
        category="administration",
    ),
    RolePresetItem(
        key="implementation_operator",
        name="Ops / Implementation",
        description="Runs diagnostics, support bundles, upgrades, and private delivery troubleshooting.",
        permissions=[
            Permission.USERS_READ.value,
            Permission.DEPARTMENTS_READ.value,
            Permission.AGENTS_READ.value,
            Permission.CHAT_READ.value,
            Permission.CHANNELS_READ.value,
            Permission.CHANNELS_WRITE.value,
            Permission.LICENSE_READ.value,
            Permission.AUDIT_READ.value,
            Permission.SYSTEM_DIAGNOSTICS.value,
        ],
        scope="tenant",
        category="operations",
    ),
    RolePresetItem(
        key="model_admin",
        name="Model Admin",
        description="Configures providers, Base URLs, API keys, model prices, routing policies, and budget guardrails.",
        permissions=[
            Permission.MODELS_READ.value,
            Permission.MODELS_WRITE.value,
            Permission.BUDGETS_READ.value,
            Permission.AUDIT_READ.value,
        ],
        scope="tenant",
        category="models",
    ),
    RolePresetItem(
        key="agent_admin",
        name="Agent Admin",
        description="Installs Agent modules, manages Agent instances, and binds knowledge bases by department.",
        permissions=[
            Permission.AGENTS_READ.value,
            Permission.AGENTS_WRITE.value,
            Permission.CHAT_READ.value,
            Permission.CHAT_WRITE.value,
            Permission.KNOWLEDGE_READ.value,
            Permission.KNOWLEDGE_WRITE.value,
            Permission.CHANNELS_READ.value,
        ],
        scope="department",
        category="agents",
    ),
    RolePresetItem(
        key="department_leader",
        name="Department Leader",
        description="Reviews department users, budget posture, Agent usage, and knowledge workflows.",
        permissions=[
            Permission.USERS_READ.value,
            Permission.DEPARTMENTS_READ.value,
            Permission.AGENTS_READ.value,
            Permission.CHAT_READ.value,
            Permission.KNOWLEDGE_READ.value,
            Permission.BUDGETS_READ.value,
            Permission.ANALYTICS_READ.value,
        ],
        scope="department",
        category="governance",
    ),
    RolePresetItem(
        key="employee",
        name="Employee",
        description="Uses approved Agents and knowledge workflows with minimal configuration visibility.",
        permissions=[
            Permission.AGENTS_READ.value,
            Permission.CHAT_READ.value,
            Permission.CHAT_WRITE.value,
            Permission.KNOWLEDGE_READ.value,
        ],
        scope="self",
        category="employee",
    ),
    RolePresetItem(
        key="audit_finance",
        name="Audit / Finance",
        description="Reviews audit records, budget ledgers, spend exports, and model cost evidence.",
        permissions=[
            Permission.BUDGETS_READ.value,
            Permission.BUDGETS_EXPORT.value,
            Permission.AUDIT_READ.value,
            Permission.AUDIT_EXPORT.value,
            Permission.ANALYTICS_READ.value,
        ],
        scope="tenant",
        category="audit",
    ),
)


async def list_departments(
    session: AsyncSession,
    principal: Principal,
) -> DepartmentListResponse:
    try:
        result = await session.execute(
            select(Department)
            .where(cast(ColumnElement[bool], Department.tenant_id == principal.tenant_id))
            .order_by(
                cast(Any, Department.sort_order).asc(),
                cast(Any, Department.created_at).asc(),
            )
        )
        departments = list(result.scalars().all())
    except (OSError, SQLAlchemyError) as exc:
        await session.rollback()
        raise _storage_unavailable("Department storage is not available.") from exc

    items = [_to_department_response(department) for department in departments]
    return DepartmentListResponse(
        departments=items,
        tree=_build_department_tree(items),
        total=len(items),
    )


async def create_department(
    session: AsyncSession,
    principal: Principal,
    payload: DepartmentCreateRequest,
    *,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> DepartmentResponse:
    try:
        if payload.parent_id is not None:
            parent = await _get_department(session, principal.tenant_id, payload.parent_id)
            if parent is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Parent department not found.",
                )

        department = Department(
            tenant_id=principal.tenant_id,
            parent_id=payload.parent_id,
            name=payload.name.strip(),
            description=payload.description,
            sort_order=payload.sort_order,
        )
        session.add(department)
        await session.flush()
        await record_audit_event(
            session,
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action="org.department.create",
            resource_type="department",
            resource_id=department.id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "name": department.name,
                "parent_id": str(department.parent_id) if department.parent_id else None,
            },
        )
        await session.commit()
        await session.refresh(department)
    except HTTPException:
        await session.rollback()
        raise
    except (OSError, SQLAlchemyError) as exc:
        await session.rollback()
        raise _storage_unavailable("Department storage is not available.") from exc

    return _to_department_response(department)


async def update_department(
    session: AsyncSession,
    principal: Principal,
    department_id: UUID,
    payload: DepartmentUpdateRequest,
    *,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> DepartmentResponse:
    try:
        department = await _get_department(session, principal.tenant_id, department_id)
        if department is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Department not found."
            )
        if payload.parent_id is not None:
            if payload.parent_id == department.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Department cannot be its own parent.",
                )
            parent = await _get_department(session, principal.tenant_id, payload.parent_id)
            if parent is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Parent department not found."
                )

        changed_fields: list[str] = []
        previous = {
            "name": department.name,
            "description": department.description,
            "parent_id": str(department.parent_id) if department.parent_id else None,
            "sort_order": department.sort_order,
        }
        if "name" in payload.model_fields_set and payload.name is not None:
            department.name = payload.name.strip()
            changed_fields.append("name")
        if "description" in payload.model_fields_set:
            department.description = payload.description
            changed_fields.append("description")
        if "parent_id" in payload.model_fields_set:
            department.parent_id = payload.parent_id
            changed_fields.append("parent_id")
        if payload.sort_order is not None:
            department.sort_order = payload.sort_order
            changed_fields.append("sort_order")
        if changed_fields:
            department.updated_at = utc_now()

        await record_audit_event(
            session,
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action="org.department.update",
            resource_type="department",
            resource_id=department.id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "changed_fields": changed_fields,
                "previous": previous,
                "current": {
                    "name": department.name,
                    "description": department.description,
                    "parent_id": str(department.parent_id) if department.parent_id else None,
                    "sort_order": department.sort_order,
                },
            },
        )
        await session.commit()
        await session.refresh(department)
    except HTTPException:
        await session.rollback()
        raise
    except (OSError, SQLAlchemyError) as exc:
        await session.rollback()
        raise _storage_unavailable("Department storage is not available.") from exc

    return _to_department_response(department)


async def delete_department(
    session: AsyncSession,
    principal: Principal,
    department_id: UUID,
    *,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> DeleteResponse:
    try:
        department = await _get_department(session, principal.tenant_id, department_id)
        if department is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Department not found."
            )
        if await _department_has_references(session, principal.tenant_id, department.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Departments with children, users, or cost centers cannot be deleted.",
            )
        await record_audit_event(
            session,
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action="org.department.delete",
            resource_type="department",
            resource_id=department.id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"name": department.name},
        )
        await session.delete(department)
        await session.commit()
    except HTTPException:
        await session.rollback()
        raise
    except (OSError, SQLAlchemyError) as exc:
        await session.rollback()
        raise _storage_unavailable("Department storage is not available.") from exc

    return DeleteResponse(id=department_id)


async def list_cost_centers(
    session: AsyncSession,
    principal: Principal,
) -> CostCenterListResponse:
    try:
        result = await session.execute(
            select(CostCenter)
            .where(cast(ColumnElement[bool], CostCenter.tenant_id == principal.tenant_id))
            .order_by(
                cast(Any, CostCenter.code).asc(),
                cast(Any, CostCenter.created_at).asc(),
            )
        )
        cost_centers = list(result.scalars().all())
    except (OSError, SQLAlchemyError) as exc:
        await session.rollback()
        raise _storage_unavailable("Cost center storage is not available.") from exc

    items = [_to_cost_center_response(cost_center) for cost_center in cost_centers]
    return CostCenterListResponse(cost_centers=items, total=len(items))


async def create_cost_center(
    session: AsyncSession,
    principal: Principal,
    payload: CostCenterCreateRequest,
    *,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> CostCenterResponse:
    try:
        if payload.department_id is not None:
            department = await _get_department(session, principal.tenant_id, payload.department_id)
            if department is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Department not found.",
                )

        cost_center = CostCenter(
            tenant_id=principal.tenant_id,
            department_id=payload.department_id,
            code=payload.code,
            name=payload.name.strip(),
            description=payload.description,
            monthly_budget_usd=payload.monthly_budget_usd,
            is_active=payload.is_active,
        )
        session.add(cost_center)
        await session.flush()
        await record_audit_event(
            session,
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action="org.cost_center.create",
            resource_type="cost_center",
            resource_id=cost_center.id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "code": cost_center.code,
                "name": cost_center.name,
                "department_id": (
                    str(cost_center.department_id) if cost_center.department_id else None
                ),
            },
        )
        await session.commit()
        await session.refresh(cost_center)
    except HTTPException:
        await session.rollback()
        raise
    except (OSError, SQLAlchemyError) as exc:
        await session.rollback()
        raise _storage_unavailable("Cost center storage is not available.") from exc

    return _to_cost_center_response(cost_center)


async def update_cost_center(
    session: AsyncSession,
    principal: Principal,
    cost_center_id: UUID,
    payload: CostCenterUpdateRequest,
    *,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> CostCenterResponse:
    try:
        cost_center = await _get_cost_center(session, principal.tenant_id, cost_center_id)
        if cost_center is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Cost center not found."
            )
        if "department_id" in payload.model_fields_set and payload.department_id is not None:
            department = await _get_department(session, principal.tenant_id, payload.department_id)
            if department is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Department not found."
                )

        changed_fields: list[str] = []
        previous = {
            "code": cost_center.code,
            "name": cost_center.name,
            "department_id": str(cost_center.department_id) if cost_center.department_id else None,
            "monthly_budget_usd": str(cost_center.monthly_budget_usd)
            if cost_center.monthly_budget_usd
            else None,
            "is_active": cost_center.is_active,
        }
        if payload.code is not None:
            cost_center.code = payload.code
            changed_fields.append("code")
        if payload.name is not None:
            cost_center.name = payload.name.strip()
            changed_fields.append("name")
        if "description" in payload.model_fields_set:
            cost_center.description = payload.description
            changed_fields.append("description")
        if "department_id" in payload.model_fields_set:
            cost_center.department_id = payload.department_id
            changed_fields.append("department_id")
        if "monthly_budget_usd" in payload.model_fields_set:
            cost_center.monthly_budget_usd = payload.monthly_budget_usd
            changed_fields.append("monthly_budget_usd")
        if payload.is_active is not None:
            cost_center.is_active = payload.is_active
            changed_fields.append("is_active")
        if changed_fields:
            cost_center.updated_at = utc_now()

        await record_audit_event(
            session,
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action="org.cost_center.update",
            resource_type="cost_center",
            resource_id=cost_center.id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "changed_fields": changed_fields,
                "previous": previous,
                "current": {
                    "code": cost_center.code,
                    "name": cost_center.name,
                    "department_id": str(cost_center.department_id)
                    if cost_center.department_id
                    else None,
                    "monthly_budget_usd": (
                        str(cost_center.monthly_budget_usd)
                        if cost_center.monthly_budget_usd
                        else None
                    ),
                    "is_active": cost_center.is_active,
                },
            },
        )
        await session.commit()
        await session.refresh(cost_center)
    except HTTPException:
        await session.rollback()
        raise
    except (OSError, SQLAlchemyError) as exc:
        await session.rollback()
        raise _storage_unavailable("Cost center storage is not available.") from exc

    return _to_cost_center_response(cost_center)


async def delete_cost_center(
    session: AsyncSession,
    principal: Principal,
    cost_center_id: UUID,
    *,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> DeleteResponse:
    try:
        cost_center = await _get_cost_center(session, principal.tenant_id, cost_center_id)
        if cost_center is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Cost center not found."
            )
        if await _cost_center_has_user_bindings(session, cost_center.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cost centers assigned to users cannot be deleted.",
            )
        await record_audit_event(
            session,
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action="org.cost_center.delete",
            resource_type="cost_center",
            resource_id=cost_center.id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"code": cost_center.code, "name": cost_center.name},
        )
        await session.delete(cost_center)
        await session.commit()
    except HTTPException:
        await session.rollback()
        raise
    except (OSError, SQLAlchemyError) as exc:
        await session.rollback()
        raise _storage_unavailable("Cost center storage is not available.") from exc

    return DeleteResponse(id=cost_center_id)


async def list_users(
    session: AsyncSession,
    principal: Principal,
    *,
    search: str | None = None,
    department_id: UUID | None = None,
    role_id: UUID | None = None,
    is_active: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> UserListResponse:
    page = max(page, 1)
    page_size = max(min(page_size, 100), 1)
    try:
        users, total = await _list_visible_users(
            session,
            principal,
            search=search,
            department_id=department_id,
            role_id=role_id,
            is_active=is_active,
            page=page,
            page_size=page_size,
        )
        enriched = [
            await _to_user_response(session, user, include_permissions=True) for user in users
        ]
    except (OSError, SQLAlchemyError) as exc:
        await session.rollback()
        raise _storage_unavailable("User storage is not available.") from exc

    total_pages = (total + page_size - 1) // page_size if total else 0
    return UserListResponse(
        users=enriched,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


async def _list_visible_users(
    session: AsyncSession,
    principal: Principal,
    *,
    search: str | None = None,
    department_id: UUID | None = None,
    role_id: UUID | None = None,
    is_active: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[User], int]:
    base_query = select(User).where(
        cast(ColumnElement[bool], User.tenant_id == principal.tenant_id),
        cast(Any, User.deleted_at).is_(None),
    )
    if not _can_read_all_users(principal):
        department_ids = await _principal_department_ids(session, principal)
        if department_ids:
            base_query = (
                base_query.join(
                    UserDepartment,
                    cast(ColumnElement[bool], UserDepartment.user_id == User.id),
                    isouter=True,
                )
                .where(
                    or_(
                        cast(ColumnElement[bool], User.id == principal.user_id),
                        cast(Any, UserDepartment.department_id).in_(department_ids),
                    )
                )
                .distinct()
            )
        else:
            base_query = base_query.where(cast(ColumnElement[bool], User.id == principal.user_id))

    # Apply optional filters
    if search:
        like_pattern = f"%{search}%"
        base_query = base_query.where(
            or_(
                cast(Any, User.email).ilike(like_pattern),
                cast(Any, User.username).ilike(like_pattern),
                cast(Any, User.full_name).ilike(like_pattern),
            )
        )
    if is_active is not None:
        base_query = base_query.where(cast(ColumnElement[bool], User.is_active == is_active))
    if department_id is not None:
        base_query = base_query.where(
            cast(Any, User.id).in_(
                select(UserDepartment.user_id).where(
                    cast(ColumnElement[bool], UserDepartment.department_id == department_id)
                )
            )
        )
    if role_id is not None:
        base_query = base_query.where(
            cast(Any, User.id).in_(
                select(UserRole.user_id).where(
                    cast(ColumnElement[bool], UserRole.role_id == role_id)
                )
            )
        )

    # Count total matching rows (before pagination)
    count_query = select(func.count()).select_from(base_query.subquery())
    total = (await session.execute(count_query)).scalar_one()

    # Apply sorting + pagination
    result_query = (
        base_query.order_by(cast(Any, User.created_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(result_query)
    users = list(result.scalars().all())
    return users, total


def _can_read_all_users(principal: Principal) -> bool:
    return (
        Permission.TENANT_ADMIN.value in principal.permissions
        or Permission.USERS_WRITE.value in principal.permissions
    )


async def create_user(
    session: AsyncSession,
    principal: Principal,
    payload: UserCreateRequest,
    *,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> UserResponse:
    try:
        existing = await session.execute(
            select(User.id).where(
                cast(ColumnElement[bool], User.tenant_id == principal.tenant_id),
                cast(ColumnElement[bool], User.email == payload.email),
                cast(Any, User.deleted_at).is_(None),
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User email already exists in this tenant.",
            )

        await ensure_license_capacity(
            session,
            tenant_id=principal.tenant_id,
            resource="users",
        )
        await _validate_user_bindings(session, principal.tenant_id, payload)
        roles = await _load_roles_by_ids(session, principal.tenant_id, payload.role_ids)

        user = User(
            tenant_id=principal.tenant_id,
            email=payload.email,
            username=payload.username,
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name,
            avatar_url=payload.avatar_url,
            phone=payload.phone,
            is_tenant_admin=payload.is_tenant_admin,
            is_active=payload.is_active,
        )
        session.add(user)
        await session.flush()

        for binding in payload.department_bindings:
            session.add(
                UserDepartment(
                    user_id=user.id,
                    department_id=binding.department_id,
                    is_leader=binding.is_leader,
                    is_primary=binding.is_primary,
                    position_title=binding.position_title,
                    cost_center_id=binding.cost_center_id,
                )
            )

        for role in roles:
            session.add(UserRole(user_id=user.id, role_id=role.id, granted_by=principal.user_id))

        await record_audit_event(
            session,
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action="org.user.create",
            resource_type="user",
            resource_id=user.id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "email": user.email,
                "is_tenant_admin": user.is_tenant_admin,
                "department_ids": [
                    str(binding.department_id) for binding in payload.department_bindings
                ],
                "role_ids": [str(role.id) for role in roles],
            },
        )
        await session.commit()
        await session.refresh(user)
        return await _to_user_response(session, user, include_permissions=True)
    except HTTPException:
        await session.rollback()
        raise
    except (OSError, SQLAlchemyError) as exc:
        await session.rollback()
        raise _storage_unavailable("User storage is not available.") from exc


async def update_user_status(
    session: AsyncSession,
    principal: Principal,
    user_id: UUID,
    payload: UserStatusUpdateRequest,
    *,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> UserResponse:
    if user_id == principal.user_id and not payload.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Administrators cannot deactivate their own account.",
        )
    try:
        user = await session.get(User, user_id)
        if user is None or user.tenant_id != principal.tenant_id or user.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

        previous_status = user.is_active
        user.is_active = payload.is_active
        user.updated_at = utc_now()
        await record_audit_event(
            session,
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action="org.user.status.update",
            resource_type="user",
            resource_id=user.id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "email": user.email,
                "previous_is_active": previous_status,
                "is_active": user.is_active,
                "is_tenant_admin": user.is_tenant_admin,
            },
        )
        await session.commit()
        await session.refresh(user)
        return await _to_user_response(session, user, include_permissions=True)
    except HTTPException:
        await session.rollback()
        raise
    except (OSError, SQLAlchemyError) as exc:
        await session.rollback()
        raise _storage_unavailable("User storage is not available.") from exc


async def update_user(
    session: AsyncSession,
    principal: Principal,
    user_id: UUID,
    payload: UserUpdateRequest,
    *,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> UserResponse:
    if user_id == principal.user_id and payload.is_tenant_admin is False:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Administrators cannot remove their own tenant administrator access.",
        )
    try:
        user = await session.get(User, user_id)
        if user is None or user.tenant_id != principal.tenant_id or user.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

        if payload.email and payload.email != user.email:
            existing = await session.execute(
                select(User.id).where(
                    cast(ColumnElement[bool], User.tenant_id == principal.tenant_id),
                    cast(ColumnElement[bool], User.email == payload.email),
                    cast(ColumnElement[bool], User.id != user.id),
                    cast(Any, User.deleted_at).is_(None),
                )
            )
            if existing.scalar_one_or_none() is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User email already exists in this tenant.",
                )

        role_ids = payload.role_ids if payload.role_ids is not None else None
        roles = (
            await _load_roles_by_ids(session, principal.tenant_id, role_ids)
            if role_ids is not None
            else None
        )

        if payload.department_bindings is not None:
            _validate_primary_department_binding(payload.department_bindings)
            await _validate_user_bindings(session, principal.tenant_id, payload)

        changed_fields: list[str] = []
        previous = {
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
            "phone": user.phone,
            "is_tenant_admin": user.is_tenant_admin,
        }

        if payload.email is not None and payload.email != user.email:
            user.email = payload.email
            changed_fields.append("email")
        if "username" in payload.model_fields_set and payload.username != user.username:
            user.username = payload.username
            changed_fields.append("username")
        if "full_name" in payload.model_fields_set and payload.full_name != user.full_name:
            user.full_name = payload.full_name
            changed_fields.append("full_name")
        if "avatar_url" in payload.model_fields_set and payload.avatar_url != user.avatar_url:
            user.avatar_url = payload.avatar_url
            changed_fields.append("avatar_url")
        if "phone" in payload.model_fields_set and payload.phone != user.phone:
            user.phone = payload.phone
            changed_fields.append("phone")
        if payload.is_tenant_admin is not None and payload.is_tenant_admin != user.is_tenant_admin:
            user.is_tenant_admin = payload.is_tenant_admin
            changed_fields.append("is_tenant_admin")

        if payload.department_bindings is not None:
            await _replace_user_department_bindings(session, user.id, payload.department_bindings)
            changed_fields.append("department_bindings")

        if roles is not None:
            await _replace_user_roles(session, user.id, roles, granted_by=principal.user_id)
            changed_fields.append("role_ids")

        if changed_fields:
            user.updated_at = utc_now()

        await record_audit_event(
            session,
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action="org.user.update",
            resource_type="user",
            resource_id=user.id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "changed_fields": changed_fields,
                "previous": previous,
                "current": {
                    "email": user.email,
                    "username": user.username,
                    "full_name": user.full_name,
                    "phone": user.phone,
                    "is_tenant_admin": user.is_tenant_admin,
                },
                "department_ids": [
                    str(binding.department_id) for binding in (payload.department_bindings or [])
                ],
                "role_ids": [str(role.id) for role in roles] if roles is not None else None,
            },
        )
        await session.commit()
        await session.refresh(user)
        return await _to_user_response(session, user, include_permissions=True)
    except HTTPException:
        await session.rollback()
        raise
    except (OSError, SQLAlchemyError) as exc:
        await session.rollback()
        raise _storage_unavailable("User storage is not available.") from exc


async def reset_user_password(
    session: AsyncSession,
    principal: Principal,
    user_id: UUID,
    payload: UserPasswordResetRequest,
    *,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> UserResponse:
    try:
        user = await session.get(User, user_id)
        if user is None or user.tenant_id != principal.tenant_id or user.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

        user.hashed_password = hash_password(payload.new_password)
        user.updated_at = utc_now()
        await record_audit_event(
            session,
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action="org.user.password.reset",
            resource_type="user",
            resource_id=user.id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "email": user.email,
                "is_tenant_admin": user.is_tenant_admin,
                "target_is_self": user.id == principal.user_id,
            },
        )
        await session.commit()
        await session.refresh(user)
        return await _to_user_response(session, user, include_permissions=True)
    except HTTPException:
        await session.rollback()
        raise
    except (OSError, SQLAlchemyError) as exc:
        await session.rollback()
        raise _storage_unavailable("User storage is not available.") from exc


async def list_roles(
    session: AsyncSession,
    principal: Principal,
) -> RoleListResponse:
    try:
        result = await session.execute(
            select(Role)
            .where(cast(ColumnElement[bool], Role.tenant_id == principal.tenant_id))
            .order_by(
                cast(Any, Role.is_system).desc(),
                cast(Any, Role.created_at).asc(),
            )
        )
        roles = list(result.scalars().all())
    except (OSError, SQLAlchemyError) as exc:
        await session.rollback()
        raise _storage_unavailable("Role storage is not available.") from exc

    items = [_to_role_response(role) for role in roles]
    return RoleListResponse(roles=items, total=len(items))


def list_role_permissions() -> PermissionCatalogResponse:
    permissions = [
        PermissionCatalogItem(
            value=permission.value,
            category=_permission_category(permission),
            label=_PERMISSION_LABELS[permission],
        )
        for permission in Permission
    ]
    return PermissionCatalogResponse(permissions=permissions, total=len(permissions))


def list_role_presets() -> RolePresetResponse:
    presets = [preset.model_copy(deep=True) for preset in _ROLE_PRESETS]
    return RolePresetResponse(presets=presets, total=len(presets))


async def create_role(
    session: AsyncSession,
    principal: Principal,
    payload: RoleCreateRequest,
    *,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> RoleResponse:
    try:
        await _ensure_role_name_available(
            session,
            principal.tenant_id,
            payload.name.strip(),
        )
        role = Role(
            tenant_id=principal.tenant_id,
            name=payload.name.strip(),
            description=payload.description,
            permissions=[permission.value for permission in payload.permissions],
            is_system=payload.is_system,
        )
        session.add(role)
        await session.flush()
        await record_audit_event(
            session,
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action="org.role.create",
            resource_type="role",
            resource_id=role.id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"name": role.name, "permissions": role.permissions},
        )
        await session.commit()
        await session.refresh(role)
    except HTTPException:
        await session.rollback()
        raise
    except (OSError, SQLAlchemyError) as exc:
        await session.rollback()
        raise _storage_unavailable("Role storage is not available.") from exc

    return _to_role_response(role)


async def update_role(
    session: AsyncSession,
    principal: Principal,
    role_id: UUID,
    payload: RoleUpdateRequest,
    *,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> RoleResponse:
    try:
        role = await _get_role(session, principal.tenant_id, role_id)
        if role is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found.")
        if role.is_system:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="System roles cannot be modified.",
            )

        changed_fields: list[str] = []
        previous = {
            "name": role.name,
            "description": role.description,
            "permissions": list(role.permissions),
        }

        if "name" in payload.model_fields_set and payload.name is not None:
            next_name = payload.name.strip()
            if next_name != role.name:
                await _ensure_role_name_available(
                    session,
                    principal.tenant_id,
                    next_name,
                    exclude_role_id=role.id,
                )
                role.name = next_name
                changed_fields.append("name")
        if "description" in payload.model_fields_set:
            role.description = payload.description
            changed_fields.append("description")
        if payload.permissions is not None:
            role.permissions = [permission.value for permission in payload.permissions]
            changed_fields.append("permissions")

        if changed_fields:
            role.updated_at = utc_now()

        await record_audit_event(
            session,
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action="org.role.update",
            resource_type="role",
            resource_id=role.id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "changed_fields": changed_fields,
                "previous": previous,
                "current": {
                    "name": role.name,
                    "description": role.description,
                    "permissions": list(role.permissions),
                },
            },
        )
        await session.commit()
        await session.refresh(role)
    except HTTPException:
        await session.rollback()
        raise
    except (OSError, SQLAlchemyError) as exc:
        await session.rollback()
        raise _storage_unavailable("Role storage is not available.") from exc

    return _to_role_response(role)


async def delete_role(
    session: AsyncSession,
    principal: Principal,
    role_id: UUID,
    *,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> RoleDeleteResponse:
    try:
        role = await _get_role(session, principal.tenant_id, role_id)
        if role is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found.")
        if role.is_system:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="System roles cannot be deleted.",
            )
        if await _role_has_assignments(session, role.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Roles assigned to users cannot be deleted.",
            )

        await record_audit_event(
            session,
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action="org.role.delete",
            resource_type="role",
            resource_id=role.id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "name": role.name,
                "permissions": list(role.permissions),
            },
        )
        await session.delete(role)
        await session.commit()
    except HTTPException:
        await session.rollback()
        raise
    except (OSError, SQLAlchemyError) as exc:
        await session.rollback()
        raise _storage_unavailable("Role storage is not available.") from exc

    return RoleDeleteResponse(id=role_id)


async def _get_role(
    session: AsyncSession,
    tenant_id: UUID,
    role_id: UUID,
) -> Role | None:
    role = await session.get(Role, role_id)
    if role is None or role.tenant_id != tenant_id:
        return None
    return role


async def _ensure_role_name_available(
    session: AsyncSession,
    tenant_id: UUID,
    name: str,
    *,
    exclude_role_id: UUID | None = None,
) -> None:
    result = await session.execute(
        select(Role.id).where(
            Role.tenant_id == tenant_id,
            Role.name == name,
        )
    )
    existing_role_id = result.scalar_one_or_none()
    if existing_role_id is not None and existing_role_id != exclude_role_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role name already exists.",
        )


async def _role_has_assignments(session: AsyncSession, role_id: UUID) -> bool:
    result = await session.execute(
        select(UserRole.user_id).where(UserRole.role_id == role_id).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _get_department(
    session: AsyncSession,
    tenant_id: UUID,
    department_id: UUID,
) -> Department | None:
    result = await session.execute(
        select(Department).where(
            Department.tenant_id == tenant_id,
            Department.id == department_id,
        )
    )
    return result.scalar_one_or_none()


async def _get_cost_center(
    session: AsyncSession,
    tenant_id: UUID,
    cost_center_id: UUID,
) -> CostCenter | None:
    cost_center = await session.get(CostCenter, cost_center_id)
    if cost_center is None or cost_center.tenant_id != tenant_id:
        return None
    return cost_center


async def _department_has_references(
    session: AsyncSession,
    tenant_id: UUID,
    department_id: UUID,
) -> bool:
    checks = [
        select(Department.id).where(
            Department.tenant_id == tenant_id,
            Department.parent_id == department_id,
        ),
        select(UserDepartment.user_id).where(UserDepartment.department_id == department_id),
        select(CostCenter.id).where(
            CostCenter.tenant_id == tenant_id,
            CostCenter.department_id == department_id,
        ),
    ]
    for statement in checks:
        result = await session.execute(statement.limit(1))
        if result.scalar_one_or_none() is not None:
            return True
    return False


async def _cost_center_has_user_bindings(session: AsyncSession, cost_center_id: UUID) -> bool:
    result = await session.execute(
        select(UserDepartment.user_id)
        .where(UserDepartment.cost_center_id == cost_center_id)
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _principal_department_ids(session: AsyncSession, principal: Principal) -> set[UUID]:
    result = await session.execute(
        select(UserDepartment.department_id)
        .join(Department, cast(ColumnElement[bool], Department.id == UserDepartment.department_id))
        .where(
            cast(ColumnElement[bool], UserDepartment.user_id == principal.user_id),
            cast(ColumnElement[bool], Department.tenant_id == principal.tenant_id),
        )
    )
    return set(result.scalars().all())


async def _validate_user_bindings(
    session: AsyncSession,
    tenant_id: UUID,
    payload: UserCreateRequest | UserUpdateRequest,
) -> None:
    if payload.department_bindings is None:
        return

    department_ids = {binding.department_id for binding in payload.department_bindings}
    if department_ids:
        result = await session.execute(
            select(Department.id).where(
                cast(ColumnElement[bool], Department.tenant_id == tenant_id),
                cast(Any, Department.id).in_(department_ids),
            )
        )
        found = set(result.scalars().all())
        missing = department_ids - found
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more departments were not found.",
            )

    cost_center_ids = {
        binding.cost_center_id
        for binding in payload.department_bindings
        if binding.cost_center_id is not None
    }
    if cost_center_ids:
        result = await session.execute(
            select(CostCenter.id).where(
                cast(ColumnElement[bool], CostCenter.tenant_id == tenant_id),
                cast(Any, CostCenter.id).in_(cost_center_ids),
            )
        )
        found = set(result.scalars().all())
        missing = cost_center_ids - found
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more cost centers were not found.",
            )


def _validate_primary_department_binding(bindings: list[Any]) -> None:
    primary_count = sum(1 for binding in bindings if binding.is_primary)
    if primary_count > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user can have at most one primary department.",
        )


async def _replace_user_department_bindings(
    session: AsyncSession,
    user_id: UUID,
    bindings: list[Any],
) -> None:
    await session.execute(
        delete(UserDepartment).where(cast(ColumnElement[bool], UserDepartment.user_id == user_id))
    )
    for index, binding in enumerate(bindings):
        session.add(
            UserDepartment(
                user_id=user_id,
                department_id=binding.department_id,
                is_leader=binding.is_leader,
                is_primary=binding.is_primary
                or (index == 0 and not any(item.is_primary for item in bindings)),
                position_title=binding.position_title,
                cost_center_id=binding.cost_center_id,
            )
        )


async def _replace_user_roles(
    session: AsyncSession,
    user_id: UUID,
    roles: list[Role],
    *,
    granted_by: UUID,
) -> None:
    await session.execute(
        delete(UserRole).where(cast(ColumnElement[bool], UserRole.user_id == user_id))
    )
    for role in roles:
        session.add(UserRole(user_id=user_id, role_id=role.id, granted_by=granted_by))


async def _load_roles_by_ids(
    session: AsyncSession,
    tenant_id: UUID,
    role_ids: list[UUID],
) -> list[Role]:
    if not role_ids:
        return []

    unique_role_ids = set(role_ids)
    result = await session.execute(
        select(Role).where(
            cast(ColumnElement[bool], Role.tenant_id == tenant_id),
            cast(Any, Role.id).in_(unique_role_ids),
        )
    )
    roles = list(result.scalars().all())
    if len(roles) != len(unique_role_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more roles were not found.",
        )
    return roles


async def _to_user_response(
    session: AsyncSession,
    user: User,
    *,
    include_permissions: bool,
) -> UserResponse:
    role_result = await session.execute(
        select(Role)
        .join(UserRole, cast(ColumnElement[bool], UserRole.role_id == Role.id))
        .where(
            cast(ColumnElement[bool], UserRole.user_id == user.id),
            cast(ColumnElement[bool], Role.tenant_id == user.tenant_id),
        )
        .order_by(cast(Any, Role.name).asc())
    )
    roles = list(role_result.scalars().all())

    department_result = await session.execute(
        select(UserDepartment, Department, CostCenter)
        .join(Department, cast(ColumnElement[bool], Department.id == UserDepartment.department_id))
        .join(
            CostCenter,
            cast(ColumnElement[bool], CostCenter.id == UserDepartment.cost_center_id),
            isouter=True,
        )
        .where(
            cast(ColumnElement[bool], UserDepartment.user_id == user.id),
            cast(ColumnElement[bool], Department.tenant_id == user.tenant_id),
        )
        .order_by(
            cast(Any, UserDepartment.is_primary).desc(),
            cast(Any, Department.sort_order).asc(),
        )
    )
    departments = [
        UserDepartmentBindingResponse(
            department_id=binding.department_id,
            department_name=department.name,
            is_leader=binding.is_leader,
            is_primary=binding.is_primary,
            position_title=binding.position_title,
            cost_center_id=binding.cost_center_id,
            cost_center_code=cost_center.code if cost_center else None,
            cost_center_name=cost_center.name if cost_center else None,
        )
        for binding, department, cost_center in department_result.all()
    ]

    permissions = _permissions_for_user(user, roles) if include_permissions else []
    return UserResponse(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        phone=user.phone,
        is_super_admin=user.is_super_admin,
        is_tenant_admin=user.is_tenant_admin,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        departments=departments,
        roles=[_to_user_role_response(role) for role in roles],
        permissions=permissions,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _permissions_for_user(user: User, roles: list[Role]) -> list[str]:
    if user.is_super_admin or user.is_tenant_admin:
        return [permission.value for permission in Permission]

    permissions: set[str] = set()
    for role in roles:
        permissions.update(role.permissions)
    return sorted(permissions)


def _permission_category(permission: Permission) -> str:
    value = permission.value
    if value == Permission.TENANT_ADMIN.value:
        return "admin"
    prefix = value.split(":", maxsplit=1)[0]
    if prefix in {"users", "departments"}:
        return "organization"
    if prefix in {"agents", "knowledge"}:
        return "agent"
    if prefix == "analytics":
        return "analytics"
    return prefix


def _build_department_tree(
    departments: list[DepartmentResponse],
) -> list[DepartmentTreeNode]:
    nodes = {
        department.id: DepartmentTreeNode(**department.model_dump(), children=[])
        for department in departments
    }
    roots: list[DepartmentTreeNode] = []
    for node in nodes.values():
        if node.parent_id in nodes:
            nodes[node.parent_id].children.append(node)
        else:
            roots.append(node)

    for node in nodes.values():
        node.children.sort(key=lambda item: (item.sort_order, item.created_at))
    return sorted(roots, key=lambda item: (item.sort_order, item.created_at))


def _to_department_response(department: Department) -> DepartmentResponse:
    return DepartmentResponse(
        id=department.id,
        tenant_id=department.tenant_id,
        parent_id=department.parent_id,
        name=department.name,
        description=department.description,
        sort_order=department.sort_order,
        created_at=department.created_at,
        updated_at=department.updated_at,
    )


def _to_cost_center_response(cost_center: CostCenter) -> CostCenterResponse:
    return CostCenterResponse(
        id=cost_center.id,
        tenant_id=cost_center.tenant_id,
        department_id=cost_center.department_id,
        code=cost_center.code,
        name=cost_center.name,
        description=cost_center.description,
        monthly_budget_usd=cost_center.monthly_budget_usd,
        is_active=cost_center.is_active,
        created_at=cost_center.created_at,
        updated_at=cost_center.updated_at,
    )


def _to_role_response(role: Role) -> RoleResponse:
    return RoleResponse(
        id=role.id,
        tenant_id=role.tenant_id,
        name=role.name,
        description=role.description,
        permissions=role.permissions,
        is_system=role.is_system,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


def _to_user_role_response(role: Role) -> UserRoleResponse:
    return UserRoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        permissions=role.permissions,
        is_system=role.is_system,
    )


def _storage_unavailable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)
