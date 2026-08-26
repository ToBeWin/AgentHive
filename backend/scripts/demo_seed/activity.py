from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.secrets import encrypt_secret
from app.models.audit_log import AuditLog
from app.models.channel import ChannelConfig
from app.models.conversation import ConversationMessage, ConversationSession
from app.models.llm import LLMUsage


async def seed_channel(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    created_by: UUID,
) -> ChannelConfig:
    result = await session.execute(
        select(ChannelConfig).where(
            ChannelConfig.channel_type == "web_widget",
            ChannelConfig.channel_key == "demo-web-widget",
        )
    )
    channel = result.scalar_one_or_none()
    if channel:
        if channel.secret_ref and channel.secret_ref.startswith("demo://"):
            channel.secret_ref = encrypt_secret("demo-web-widget-secret")
            channel.secret_configured = True
        return channel
    channel = ChannelConfig(
        tenant_id=tenant_id,
        name="Demo Web Widget",
        channel_type="web_widget",
        channel_key="demo-web-widget",
        agent_id=agent_id,
        created_by=created_by,
        status="active",
        config={"origin": "https://demo.agenthive.local", "demo_seed": True},
        secret_ref=encrypt_secret("demo-web-widget-secret"),
        secret_configured=True,
    )
    session.add(channel)
    await session.flush()
    return channel


async def seed_conversation(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    channel_id: UUID,
    user_id: UUID,
    department_id: UUID,
    model_key: str,
) -> ConversationSession:
    result = await session.execute(
        select(ConversationSession).where(
            ConversationSession.tenant_id == tenant_id,
            ConversationSession.title == "Demo customer delivery question",
            ConversationSession.deleted_at.is_(None),
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation:
        return conversation
    conversation = ConversationSession(
        tenant_id=tenant_id,
        title="Demo customer delivery question",
        agent_id=agent_id,
        channel_id=channel_id,
        user_id=user_id,
        department_id=department_id,
        source="web_widget",
        status="active",
        metadata_json={"demo_seed": True},
    )
    session.add(conversation)
    await session.flush()
    session.add(
        ConversationMessage(
            tenant_id=tenant_id,
            conversation_id=conversation.id,
            role="user",
            content="客户询问订单延迟，应该如何回复？",
            user_id=user_id,
            metadata_json={"demo_seed": True},
        )
    )
    session.add(
        ConversationMessage(
            tenant_id=tenant_id,
            conversation_id=conversation.id,
            role="assistant",
            content="先致歉并确认订单状态，再说明预计处理时间；如超过承诺时效，主动提供补偿或升级处理。",
            request_id="demo-chat-001",
            model_key=model_key,
            provider_key="qwen",
            input_tokens=380,
            output_tokens=122,
            total_tokens=502,
            cost_usd=Decimal("0.000187"),
            metadata_json={"demo_seed": True, "sources": ["customer-service-sop.md"]},
        )
    )
    await session.flush()
    return conversation


async def seed_usage(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    deployment_id: UUID,
    user_id: UUID,
    department_id: UUID,
    cost_center_id: UUID,
    agent_id: UUID,
    channel_id: UUID,
    conversation_id: UUID,
    model_key: str,
) -> None:
    result = await session.execute(
        select(LLMUsage).where(
            LLMUsage.tenant_id == tenant_id,
            LLMUsage.request_id == "demo-chat-001",
        )
    )
    if result.scalar_one_or_none():
        return
    session.add(
        LLMUsage(
            tenant_id=tenant_id,
            deployment_id=deployment_id,
            user_id=user_id,
            department_id=department_id,
            cost_center_id=cost_center_id,
            agent_id=agent_id,
            channel_id=channel_id,
            conversation_id=conversation_id,
            request_id="demo-chat-001",
            model_key=model_key,
            input_tokens=380,
            output_tokens=122,
            total_tokens=502,
            cost_usd=Decimal("0.000187"),
            status="success",
            metadata_json={"demo_seed": True, "route_reason": "demo default policy"},
        )
    )
    await session.flush()


async def record_seed_audit(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    actor_id: UUID,
    provider_id: UUID,
    credential_id: UUID,
    knowledge_base_id: UUID,
    document_id: UUID,
    agent_id: UUID,
) -> None:
    result = await session.execute(
        select(func.count(AuditLog.id)).where(
            AuditLog.tenant_id == tenant_id,
            AuditLog.action == "demo.seed",
        )
    )
    if result.scalar_one():
        return
    session.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action="demo.seed",
            resource_type="tenant",
            resource_id=tenant_id,
            details={
                "provider_id": str(provider_id),
                "credential_id": str(credential_id),
                "knowledge_base_id": str(knowledge_base_id),
                "document_id": str(document_id),
                "agent_id": str(agent_id),
                "demo_seed": True,
            },
        )
    )
    await session.flush()
