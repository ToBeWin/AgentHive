from sqlalchemy.ext.asyncio import AsyncSession

from scripts.demo_seed.activity import (
    record_seed_audit,
    seed_channel,
    seed_conversation,
    seed_usage,
)
from scripts.demo_seed.agents import seed_agent_modules_and_instances
from scripts.demo_seed.constants import DEMO_ADMIN_PASSWORD, DEMO_EMPLOYEE_EMAIL
from scripts.demo_seed.knowledge import seed_knowledge
from scripts.demo_seed.license import seed_demo_license
from scripts.demo_seed.llm import seed_governance, seed_llm_defaults
from scripts.demo_seed.org import seed_organization
from scripts.demo_seed.summary import DemoSeedSummary


async def seed_demo_data(session: AsyncSession) -> DemoSeedSummary:
    org = await seed_organization(session)
    await seed_demo_license(
        session,
        tenant_id=org.tenant.id,
        customer_name=org.tenant.name,
        activated_by=org.admin_user.id,
    )
    provider, credential, model, deployment = await seed_llm_defaults(
        session,
        tenant_id=org.tenant.id,
    )
    await seed_governance(
        session,
        tenant_id=org.tenant.id,
        department_id=org.customer_success_department.id,
        cost_center_id=org.customer_success_cost_center.id,
        user_id=org.ops_user.id,
    )
    knowledge_base, document = await seed_knowledge(
        session,
        tenant_id=org.tenant.id,
        department_id=org.customer_success_department.id,
    )
    agent_instances = await seed_agent_modules_and_instances(
        session,
        tenant_id=org.tenant.id,
        installed_by=org.admin_user.id,
        department_id=org.customer_success_department.id,
        owner_user_id=org.ops_user.id,
        knowledge_base_id=knowledge_base.id,
        model_key=model.model_key,
        routing_key=deployment.routing_key,
    )
    customer_agent = agent_instances[0]
    channel = await seed_channel(
        session,
        tenant_id=org.tenant.id,
        agent_id=customer_agent.id,
        created_by=org.admin_user.id,
    )
    conversation = await seed_conversation(
        session,
        tenant_id=org.tenant.id,
        agent_id=customer_agent.id,
        channel_id=channel.id,
        user_id=org.ops_user.id,
        department_id=org.customer_success_department.id,
        model_key=model.model_key,
    )
    await seed_usage(
        session,
        tenant_id=org.tenant.id,
        deployment_id=deployment.id,
        user_id=org.ops_user.id,
        department_id=org.customer_success_department.id,
        cost_center_id=org.customer_success_cost_center.id,
        agent_id=customer_agent.id,
        channel_id=channel.id,
        conversation_id=conversation.id,
        model_key=model.model_key,
    )
    await record_seed_audit(
        session,
        tenant_id=org.tenant.id,
        actor_id=org.admin_user.id,
        provider_id=provider.id,
        credential_id=credential.id,
        knowledge_base_id=knowledge_base.id,
        document_id=document.id,
        agent_id=customer_agent.id,
    )
    await session.commit()
    return DemoSeedSummary(
        tenant_slug=org.tenant.slug,
        admin_email=org.admin_user.email,
        admin_password=DEMO_ADMIN_PASSWORD,
        employee_email=DEMO_EMPLOYEE_EMAIL,
        employee_password=DEMO_ADMIN_PASSWORD,
    )
