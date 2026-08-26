from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.agent_module import AgentInstance, AgentModule, TenantAgentModule
from app.services.agent_module_service import list_module_definitions


async def seed_agent_modules_and_instances(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    installed_by: UUID,
    department_id: UUID,
    owner_user_id: UUID,
    knowledge_base_id: UUID,
    model_key: str,
    routing_key: str,
) -> list[AgentInstance]:
    enabled_module_keys = [
        "agent.customer_service",
        "agent.copywriting",
        "agent.image_generation",
        "agent.video_generation",
        "agent.report_writer",
    ]
    for module_key in enabled_module_keys:
        module = await _get_agent_module_row(session, module_key=module_key)
        await _ensure_tenant_module(
            session,
            tenant_id=tenant_id,
            module_id=module.id,
            installed_by=installed_by,
        )
    instances = [
        await _get_or_create_agent_instance(
            session,
            tenant_id=tenant_id,
            department_id=department_id,
            owner_user_id=owner_user_id,
            knowledge_base_id=knowledge_base_id,
            model_key=model_key,
            routing_key=routing_key,
            created_by=installed_by,
        ),
        await _get_or_create_copywriting_agent(
            session,
            tenant_id=tenant_id,
            department_id=department_id,
            owner_user_id=owner_user_id,
            model_key=model_key,
            routing_key=routing_key,
            created_by=installed_by,
        ),
        await _get_or_create_report_writer_agent(
            session,
            tenant_id=tenant_id,
            department_id=department_id,
            owner_user_id=owner_user_id,
            model_key=model_key,
            routing_key=routing_key,
            created_by=installed_by,
        ),
    ]
    return instances


async def _get_agent_module_row(session: AsyncSession, *, module_key: str) -> AgentModule:
    result = await session.execute(select(AgentModule).where(AgentModule.module_key == module_key))
    module = result.scalar_one_or_none()
    if module:
        return module
    definition = next(item for item in list_module_definitions() if item.id == module_key)
    module = AgentModule(
        module_key=definition.id,
        name=definition.name,
        category=definition.category,
        priority=definition.priority,
        description=definition.description,
        version=definition.version,
        manifest={
            "scenario": definition.scenario,
            "capabilities": definition.capabilities,
            "default_agent_slug": definition.default_agent_slug,
            "required_features": definition.required_features,
            "dependencies": definition.dependencies,
            "recommended_model_capabilities": definition.recommended_model_capabilities or [],
            "recommended_orchestration_runtimes": definition.recommended_orchestration_runtimes or [],
            "default_config": definition.default_config or {},
        },
        is_official=True,
        is_active=True,
    )
    session.add(module)
    await session.flush()
    return module


async def _ensure_tenant_module(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    module_id: UUID,
    installed_by: UUID,
) -> None:
    result = await session.execute(
        select(TenantAgentModule).where(
            TenantAgentModule.tenant_id == tenant_id,
            TenantAgentModule.module_id == module_id,
        )
    )
    tenant_module = result.scalar_one_or_none()
    if tenant_module:
        tenant_module.state = "enabled"
        tenant_module.enabled_at = tenant_module.enabled_at or datetime.now(timezone.utc)
        return
    now = datetime.now(timezone.utc)
    session.add(
        TenantAgentModule(
            tenant_id=tenant_id,
            module_id=module_id,
            state="enabled",
            installed_by=installed_by,
            installed_at=now,
            enabled_at=now,
            config={"demo_seed": True},
        )
    )
    await session.flush()


async def _get_or_create_agent_instance(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    department_id: UUID,
    owner_user_id: UUID,
    knowledge_base_id: UUID,
    model_key: str,
    routing_key: str,
    created_by: UUID,
) -> AgentInstance:
    result = await session.execute(
        select(AgentInstance).where(
            AgentInstance.tenant_id == tenant_id,
            AgentInstance.slug == "ecommerce-customer-service",
        )
    )
    agent = result.scalar_one_or_none()
    if agent:
        agent.name = "E-commerce Customer Service Agent"
        agent.agent_key = "customer_service"
        agent.module_key = "agent.customer_service"
        agent.description = "Demo Agent wired to customer service SOP knowledge and model governance."
        agent.status = "active"
        agent.visibility = "department"
        agent.department_id = department_id
        agent.owner_user_id = owner_user_id
        agent.model_routing_key = routing_key
        agent.model_key = model_key
        agent.system_prompt = "Answer customer-service questions with concise steps and cite SOP knowledge when available."
        agent.config = _customer_service_agent_config(knowledge_base_id)
        agent.metadata_json = {"demo_seed": True, "channel_ready": True}
        return agent
    agent = AgentInstance(
        tenant_id=tenant_id,
        name="E-commerce Customer Service Agent",
        slug="ecommerce-customer-service",
        agent_key="customer_service",
        module_key="agent.customer_service",
        description="Demo Agent wired to customer service SOP knowledge and model governance.",
        status="active",
        visibility="department",
        department_id=department_id,
        owner_user_id=owner_user_id,
        model_routing_key=routing_key,
        model_key=model_key,
        system_prompt="Answer customer-service questions with concise steps and cite SOP knowledge when available.",
        config=_customer_service_agent_config(knowledge_base_id),
        metadata_json={"demo_seed": True, "channel_ready": True},
        created_by=created_by,
    )
    session.add(agent)
    await session.flush()
    return agent


def _customer_service_agent_config(knowledge_base_id: UUID) -> dict[str, object]:
    return {
        "knowledge_base_ids": [str(knowledge_base_id)],
        "knowledge_base_names": ["Customer Service SOP"],
        "knowledge_top_k": 3,
        "demo_seed": True,
    }


async def _get_or_create_copywriting_agent(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    department_id: UUID,
    owner_user_id: UUID,
    model_key: str,
    routing_key: str,
    created_by: UUID,
) -> AgentInstance:
    result = await session.execute(
        select(AgentInstance).where(
            AgentInstance.tenant_id == tenant_id,
            AgentInstance.slug == "marketing-copywriter",
        )
    )
    agent = result.scalar_one_or_none()
    system_prompt = (
        "You are a marketing copywriting assistant. Generate compelling, on-brand copy "
        "for product descriptions, social media posts, email campaigns, and ad creatives. "
        "Always match the requested tone (playful, professional, luxurious, etc.) and keep "
        "copy concise. Offer 2-3 variations when helpful."
    )
    config: dict[str, object] = {"demo_seed": True}
    if agent:
        agent.name = "Marketing Copywriter"
        agent.agent_key = "copywriting"
        agent.module_key = "agent.copywriting"
        agent.description = "Generates marketing copy for product descriptions, ads, and social media."
        agent.status = "active"
        agent.visibility = "department"
        agent.department_id = department_id
        agent.owner_user_id = owner_user_id
        agent.model_routing_key = routing_key
        agent.model_key = model_key
        agent.system_prompt = system_prompt
        agent.config = config
        agent.metadata_json = {"demo_seed": True}
        return agent
    agent = AgentInstance(
        tenant_id=tenant_id,
        name="Marketing Copywriter",
        slug="marketing-copywriter",
        agent_key="copywriting",
        module_key="agent.copywriting",
        description="Generates marketing copy for product descriptions, ads, and social media.",
        status="active",
        visibility="department",
        department_id=department_id,
        owner_user_id=owner_user_id,
        model_routing_key=routing_key,
        model_key=model_key,
        system_prompt=system_prompt,
        config=config,
        metadata_json={"demo_seed": True},
        created_by=created_by,
    )
    session.add(agent)
    await session.flush()
    return agent


async def _get_or_create_report_writer_agent(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    department_id: UUID,
    owner_user_id: UUID,
    model_key: str,
    routing_key: str,
    created_by: UUID,
) -> AgentInstance:
    result = await session.execute(
        select(AgentInstance).where(
            AgentInstance.tenant_id == tenant_id,
            AgentInstance.slug == "business-report-writer",
        )
    )
    agent = result.scalar_one_or_none()
    system_prompt = (
        "You are a business report writing assistant. Transform raw data and bullet points "
        "into structured, professional reports with clear executive summaries, key findings, "
        "and actionable recommendations. Use Markdown formatting with headers, tables, and "
        "bullet lists. Keep language concise and data-driven."
    )
    config: dict[str, object] = {"demo_seed": True}
    if agent:
        agent.name = "Business Report Writer"
        agent.agent_key = "report_writer"
        agent.module_key = "agent.report_writer"
        agent.description = "Transforms raw data into structured business reports with recommendations."
        agent.status = "active"
        agent.visibility = "department"
        agent.department_id = department_id
        agent.owner_user_id = owner_user_id
        agent.model_routing_key = routing_key
        agent.model_key = model_key
        agent.system_prompt = system_prompt
        agent.config = config
        agent.metadata_json = {"demo_seed": True}
        return agent
    agent = AgentInstance(
        tenant_id=tenant_id,
        name="Business Report Writer",
        slug="business-report-writer",
        agent_key="report_writer",
        module_key="agent.report_writer",
        description="Transforms raw data into structured business reports with recommendations.",
        status="active",
        visibility="department",
        department_id=department_id,
        owner_user_id=owner_user_id,
        model_routing_key=routing_key,
        model_key=model_key,
        system_prompt=system_prompt,
        config=config,
        metadata_json={"demo_seed": True},
        created_by=created_by,
    )
    session.add(agent)
    await session.flush()
    return agent
