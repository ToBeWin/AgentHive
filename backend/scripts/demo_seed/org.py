from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.security import Permission, hash_password
from app.models.org import Department
from app.models.role import Role, UserRole
from app.models.tenant import CostCenter, Tenant
from app.models.user import User, UserDepartment
from scripts.demo_seed.constants import (
    DEMO_ADMIN_EMAIL,
    DEMO_ADMIN_PASSWORD,
    DEMO_EMPLOYEE_EMAIL,
    DEMO_TENANT_SLUG,
)


@dataclass(frozen=True)
class DemoOrganization:
    tenant: Tenant
    customer_success_department: Department
    marketing_department: Department
    customer_success_cost_center: CostCenter
    marketing_cost_center: CostCenter
    admin_user: User
    ops_user: User
    content_user: User
    employee_user: User


async def seed_organization(session: AsyncSession) -> DemoOrganization:
    tenant = await _get_or_create_tenant(session)
    customer_success = await _get_or_create_department(
        session,
        tenant_id=tenant.id,
        name="Customer Success",
        description="Owns customer-facing Agent workflows and knowledge quality.",
        sort_order=10,
    )
    marketing = await _get_or_create_department(
        session,
        tenant_id=tenant.id,
        name="Marketing",
        description="Runs copywriting, content analysis, and product launch Agents.",
        sort_order=20,
    )
    customer_success_cost_center = await _get_or_create_cost_center(
        session,
        tenant_id=tenant.id,
        department_id=customer_success.id,
        code="CS",
        name="Customer Success",
        monthly_budget_usd=Decimal("2500.0000"),
    )
    marketing_cost_center = await _get_or_create_cost_center(
        session,
        tenant_id=tenant.id,
        department_id=marketing.id,
        code="MKT",
        name="Marketing",
        monthly_budget_usd=Decimal("1200.0000"),
    )
    admin_role = await _get_or_create_role(
        session,
        tenant_id=tenant.id,
        name="Tenant Administrator",
        description="Full tenant administration for the private AgentHive deployment.",
        permissions=[permission.value for permission in Permission],
        is_system=True,
    )
    agent_manager_role = await _get_or_create_role(
        session,
        tenant_id=tenant.id,
        name="Agent Manager",
        description="Can manage Agents, knowledge bases, model policies, and budgets.",
        permissions=[
            Permission.AGENTS_READ.value,
            Permission.AGENTS_WRITE.value,
            Permission.CHAT_READ.value,
            Permission.CHAT_WRITE.value,
            Permission.KNOWLEDGE_READ.value,
            Permission.KNOWLEDGE_WRITE.value,
            Permission.MODELS_READ.value,
            Permission.MODELS_WRITE.value,
            Permission.BUDGETS_READ.value,
            Permission.BUDGETS_WRITE.value,
            Permission.ANALYTICS_READ.value,
        ],
        is_system=True,
    )
    employee_role = await _get_or_create_role(
        session,
        tenant_id=tenant.id,
        name="Employee",
        description="Can use assigned Agents without seeing administration surfaces.",
        permissions=[
            Permission.AGENTS_READ.value,
            Permission.CHAT_READ.value,
            Permission.CHAT_WRITE.value,
            Permission.KNOWLEDGE_READ.value,
        ],
        is_system=True,
    )
    admin_user = await _get_or_create_user(
        session,
        tenant_id=tenant.id,
        email=DEMO_ADMIN_EMAIL,
        full_name="Deployment Admin",
        password=DEMO_ADMIN_PASSWORD,
        is_tenant_admin=True,
    )
    ops_user = await _get_or_create_user(
        session,
        tenant_id=tenant.id,
        email="ops@example.com",
        full_name="Operations Lead",
        password=DEMO_ADMIN_PASSWORD,
        is_tenant_admin=False,
    )
    content_user = await _get_or_create_user(
        session,
        tenant_id=tenant.id,
        email="content@example.com",
        full_name="Content Manager",
        password=DEMO_ADMIN_PASSWORD,
        is_tenant_admin=False,
    )
    employee_user = await _get_or_create_user(
        session,
        tenant_id=tenant.id,
        email=DEMO_EMPLOYEE_EMAIL,
        full_name="Customer Support Specialist",
        password=DEMO_ADMIN_PASSWORD,
        is_tenant_admin=False,
    )
    await _ensure_user_role(session, user_id=admin_user.id, role_id=admin_role.id, granted_by=admin_user.id)
    await _ensure_user_role(session, user_id=ops_user.id, role_id=agent_manager_role.id, granted_by=admin_user.id)
    await _ensure_user_role(session, user_id=content_user.id, role_id=agent_manager_role.id, granted_by=admin_user.id)
    await _ensure_user_role(session, user_id=employee_user.id, role_id=employee_role.id, granted_by=admin_user.id)
    await _ensure_user_department(
        session,
        user_id=admin_user.id,
        department_id=customer_success.id,
        cost_center_id=customer_success_cost_center.id,
        position_title="Administrator",
        is_leader=True,
    )
    await _ensure_user_department(
        session,
        user_id=ops_user.id,
        department_id=customer_success.id,
        cost_center_id=customer_success_cost_center.id,
        position_title="Operations Lead",
        is_leader=True,
    )
    await _ensure_user_department(
        session,
        user_id=content_user.id,
        department_id=marketing.id,
        cost_center_id=marketing_cost_center.id,
        position_title="Content Manager",
        is_leader=True,
    )
    await _ensure_user_department(
        session,
        user_id=employee_user.id,
        department_id=customer_success.id,
        cost_center_id=customer_success_cost_center.id,
        position_title="Customer Support Specialist",
        is_leader=False,
    )
    return DemoOrganization(
        tenant=tenant,
        customer_success_department=customer_success,
        marketing_department=marketing,
        customer_success_cost_center=customer_success_cost_center,
        marketing_cost_center=marketing_cost_center,
        admin_user=admin_user,
        ops_user=ops_user,
        content_user=content_user,
        employee_user=employee_user,
    )


async def _get_or_create_tenant(session: AsyncSession) -> Tenant:
    result = await session.execute(select(Tenant).where(Tenant.slug == DEMO_TENANT_SLUG))
    tenant = result.scalar_one_or_none()
    if tenant:
        return tenant
    tenant = Tenant(
        name="AgentHive Demo Company",
        slug=DEMO_TENANT_SLUG,
        license_type="enterprise",
        max_users=500,
        max_agents=50,
        max_kb_size_gb=Decimal("50.0"),
        config={"demo_seed": True, "delivery_mode": "private_deployment"},
    )
    session.add(tenant)
    await session.flush()
    return tenant


async def _get_or_create_department(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    name: str,
    description: str,
    sort_order: int,
) -> Department:
    result = await session.execute(
        select(Department).where(Department.tenant_id == tenant_id, Department.name == name)
    )
    department = result.scalar_one_or_none()
    if department:
        return department
    department = Department(tenant_id=tenant_id, name=name, description=description, sort_order=sort_order)
    session.add(department)
    await session.flush()
    return department


async def _get_or_create_cost_center(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    department_id: UUID,
    code: str,
    name: str,
    monthly_budget_usd: Decimal,
) -> CostCenter:
    result = await session.execute(
        select(CostCenter).where(CostCenter.tenant_id == tenant_id, CostCenter.code == code)
    )
    cost_center = result.scalar_one_or_none()
    if cost_center:
        return cost_center
    cost_center = CostCenter(
        tenant_id=tenant_id,
        department_id=department_id,
        code=code,
        name=name,
        monthly_budget_usd=monthly_budget_usd,
        description="Seeded demo cost center for budget and model-cost governance.",
    )
    session.add(cost_center)
    await session.flush()
    return cost_center


async def _get_or_create_role(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    name: str,
    description: str,
    permissions: list[str],
    is_system: bool,
) -> Role:
    result = await session.execute(select(Role).where(Role.tenant_id == tenant_id, Role.name == name))
    role = result.scalar_one_or_none()
    if role:
        role.description = description
        role.permissions = permissions
        role.is_system = is_system
        return role
    role = Role(
        tenant_id=tenant_id,
        name=name,
        description=description,
        permissions=permissions,
        is_system=is_system,
    )
    session.add(role)
    await session.flush()
    return role


async def _get_or_create_user(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    email: str,
    full_name: str,
    password: str,
    is_tenant_admin: bool,
) -> User:
    normalized_email = email.lower()
    result = await session.execute(
        select(User).where(
            User.tenant_id == tenant_id,
            User.email == normalized_email,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()
    if user:
        return user
    user = User(
        tenant_id=tenant_id,
        email=normalized_email,
        full_name=full_name,
        hashed_password=hash_password(password),
        is_tenant_admin=is_tenant_admin,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _ensure_user_role(
    session: AsyncSession,
    *,
    user_id: UUID,
    role_id: UUID,
    granted_by: UUID,
) -> None:
    existing = await session.get(UserRole, (user_id, role_id))
    if existing:
        return
    session.add(UserRole(user_id=user_id, role_id=role_id, granted_by=granted_by))
    await session.flush()


async def _ensure_user_department(
    session: AsyncSession,
    *,
    user_id: UUID,
    department_id: UUID,
    cost_center_id: UUID,
    position_title: str,
    is_leader: bool,
) -> None:
    existing = await session.get(UserDepartment, (user_id, department_id))
    if existing:
        return
    session.add(
        UserDepartment(
            user_id=user_id,
            department_id=department_id,
            cost_center_id=cost_center_id,
            position_title=position_title,
            is_leader=is_leader,
            is_primary=True,
        )
    )
    await session.flush()
