from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import settings
from app.core.secrets import encrypt_secret, mask_secret
from app.models.llm import (
    LLMBudget,
    LLMBudgetLedger,
    LLMCredential,
    LLMDeployment,
    LLMModel,
    LLMModelPrice,
    LLMPolicy,
    LLMProvider,
)


@dataclass(frozen=True)
class DemoModelSpec:
    provider_key: str
    model_key: str
    display_name: str
    context_window: int
    capabilities: tuple[str, ...]
    input_per_1k_tokens: Decimal
    output_per_1k_tokens: Decimal


_DEMO_MODEL_CATALOG: tuple[DemoModelSpec, ...] = (
    DemoModelSpec(
        "qwen",
        "qwen-plus",
        "Qwen Plus",
        131072,
        ("chat", "stream", "tool_calling"),
        Decimal("0.00030"),
        Decimal("0.00060"),
    ),
    DemoModelSpec(
        "deepseek",
        "deepseek-v4-flash",
        "DeepSeek V4 Flash",
        64000,
        ("chat", "stream", "reasoning", "coding"),
        Decimal("0.00014"),
        Decimal("0.00028"),
    ),
    DemoModelSpec(
        "kimi",
        "moonshot-v1-128k",
        "Kimi 128K",
        128000,
        ("chat", "stream", "long_context"),
        Decimal("0.00170"),
        Decimal("0.00170"),
    ),
    DemoModelSpec(
        "mimo",
        "mimo-chat",
        "MiMo Chat",
        32768,
        ("chat", "stream", "reasoning"),
        Decimal("0"),
        Decimal("0"),
    ),
    DemoModelSpec(
        "mimo",
        "mimo-v2.5-pro",
        "MiMo v2.5 Pro",
        65536,
        ("chat", "stream", "reasoning"),
        Decimal("0"),
        Decimal("0"),
    ),
    DemoModelSpec(
        "minimax",
        "abab6.5s-chat",
        "MiniMax Chat",
        245760,
        ("chat", "stream", "long_context"),
        Decimal("0.00020"),
        Decimal("0.00080"),
    ),
    DemoModelSpec(
        "glm",
        "glm-4-plus",
        "GLM-4 Plus",
        128000,
        ("chat", "stream", "tool_calling"),
        Decimal("0.00700"),
        Decimal("0.00700"),
    ),
    DemoModelSpec(
        "doubao",
        "doubao-pro-32k",
        "Doubao Pro 32K",
        32768,
        ("chat", "stream"),
        Decimal("0.00011"),
        Decimal("0.00022"),
    ),
    DemoModelSpec(
        "openai",
        "gpt-4o-mini",
        "GPT-4o mini",
        128000,
        ("chat", "stream", "tool_calling", "vision"),
        Decimal("0.00015"),
        Decimal("0.00060"),
    ),
)


async def seed_llm_defaults(
    session: AsyncSession,
    *,
    tenant_id: UUID,
) -> tuple[LLMProvider, LLMCredential, LLMModel, LLMDeployment]:
    provider = await _get_or_create_provider(session, tenant_id=tenant_id)
    credential = await _get_or_create_credential(
        session,
        tenant_id=tenant_id,
        provider_id=provider.id,
    )
    model = await _get_or_create_model(session)
    await _get_or_create_price(session, model_id=model.id)
    await _seed_demo_model_catalog(session)
    deployment = await _get_or_create_deployment(
        session,
        tenant_id=tenant_id,
        provider_id=provider.id,
        credential_id=credential.id,
        model_id=model.id,
    )
    preferred_live = await _preferred_live_deployment(session, tenant_id=tenant_id)
    if preferred_live is not None:
        provider, credential, model, deployment = preferred_live
    await _get_or_create_policy(
        session,
        tenant_id=tenant_id,
        model_key=model.model_key,
        routing_key=deployment.routing_key,
    )
    await get_or_create_budget(
        session,
        tenant_id=tenant_id,
        scope_type="tenant",
        scope_id=None,
        amount_usd=Decimal("5000.0000"),
        token_limit=5_000_000,
    )
    return provider, credential, model, deployment


async def _preferred_live_deployment(
    session: AsyncSession,
    *,
    tenant_id: UUID,
) -> tuple[LLMProvider, LLMCredential, LLMModel, LLMDeployment] | None:
    result = await session.execute(
        select(LLMDeployment)
        .where(
            LLMDeployment.tenant_id == tenant_id,
            LLMDeployment.is_active.is_(True),
        )
        .order_by(LLMDeployment.priority.asc(), LLMDeployment.routing_key.asc())
    )
    for deployment in result.scalars().all():
        provider = await session.get(LLMProvider, deployment.provider_id)
        credential = await session.get(LLMCredential, deployment.credential_id) if deployment.credential_id else None
        model = await session.get(LLMModel, deployment.model_id)
        if (
            provider
            and provider.is_active
            and credential
            and credential.is_active
            and model
            and _is_preferred_live_deployment(provider, credential, deployment)
        ):
            return provider, credential, model, deployment
    return None


def _is_live_deployment_config(config: dict[str, object]) -> bool:
    return config.get("live_network_call") is True and config.get("mock") is not True


def _is_preferred_live_deployment(
    provider: LLMProvider,
    credential: LLMCredential,
    deployment: LLMDeployment,
) -> bool:
    if _is_live_deployment_config(deployment.config):
        return True
    if provider.provider_key == "litellm" and provider.config.get("demo_seed") is True:
        return False
    if credential.display_name == "Demo LiteLLM Virtual Key":
        return False
    return bool(provider.base_url and credential.secret_ref)


async def _seed_demo_model_catalog(session: AsyncSession) -> None:
    for item in _DEMO_MODEL_CATALOG:
        model = await _get_or_create_catalog_model(session, item)
        await _get_or_create_catalog_price(
            session,
            model_id=model.id,
            input_per_1k_tokens=item.input_per_1k_tokens,
            output_per_1k_tokens=item.output_per_1k_tokens,
        )


async def _get_or_create_catalog_model(session: AsyncSession, item: DemoModelSpec) -> LLMModel:
    model_key = item.model_key
    result = await session.execute(select(LLMModel).where(LLMModel.model_key == model_key))
    model = result.scalar_one_or_none()
    if model:
        model.provider_key = item.provider_key
        model.display_name = item.display_name
        model.context_window = item.context_window
        model.capabilities = list(item.capabilities)
        model.is_global = True
        return model
    model = LLMModel(
        provider_key=item.provider_key,
        model_key=model_key,
        display_name=item.display_name,
        model_type="chat",
        context_window=item.context_window,
        capabilities=list(item.capabilities),
        is_global=True,
    )
    session.add(model)
    await session.flush()
    return model


async def _get_or_create_catalog_price(
    session: AsyncSession,
    *,
    model_id: UUID,
    input_per_1k_tokens: Decimal,
    output_per_1k_tokens: Decimal,
) -> LLMModelPrice:
    result = await session.execute(
        select(LLMModelPrice).where(
            LLMModelPrice.model_id == model_id,
            LLMModelPrice.currency == "USD",
            LLMModelPrice.effective_to.is_(None),
        )
    )
    price = result.scalar_one_or_none()
    if price:
        price.input_per_1k_tokens = input_per_1k_tokens
        price.output_per_1k_tokens = output_per_1k_tokens
        return price
    price = LLMModelPrice(
        model_id=model_id,
        currency="USD",
        input_per_1k_tokens=input_per_1k_tokens,
        output_per_1k_tokens=output_per_1k_tokens,
        effective_from=datetime.now(timezone.utc) - timedelta(days=1),
    )
    session.add(price)
    await session.flush()
    return price


async def seed_governance(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    department_id: UUID,
    cost_center_id: UUID,
    user_id: UUID,
) -> None:
    department_budget = await get_or_create_budget(
        session,
        tenant_id=tenant_id,
        scope_type="department",
        scope_id=department_id,
        amount_usd=Decimal("1500.0000"),
        token_limit=2_000_000,
    )
    request_id = "demo-budget-reservation-001"
    result = await session.execute(
        select(LLMBudgetLedger).where(
            LLMBudgetLedger.tenant_id == tenant_id,
            LLMBudgetLedger.request_id == request_id,
        )
    )
    if result.scalar_one_or_none():
        return
    session.add(
        LLMBudgetLedger(
            tenant_id=tenant_id,
            budget_id=department_budget.id,
            reservation_id="demo-reservation-001",
            request_id=request_id,
            event_type="settled",
            scope_type="department",
            scope_id=department_id,
            user_id=user_id,
            department_id=department_id,
            cost_center_id=cost_center_id,
            estimated_tokens=1000,
            actual_tokens=1240,
            estimated_cost_usd=Decimal("0.000500"),
            actual_cost_usd=Decimal("0.000744"),
            reason="Seeded demo settlement for budget dashboard.",
            metadata_json={"demo_seed": True},
        )
    )
    await session.flush()


async def get_or_create_budget(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    scope_type: str,
    scope_id: UUID | None,
    amount_usd: Decimal,
    token_limit: int,
) -> LLMBudget:
    result = await session.execute(
        select(LLMBudget).where(
            LLMBudget.tenant_id == tenant_id,
            LLMBudget.scope_type == scope_type,
            LLMBudget.scope_id == scope_id,
            LLMBudget.period == "monthly",
        )
    )
    budget = result.scalars().first()
    if budget:
        budget.amount_usd = amount_usd
        budget.token_limit = token_limit
        budget.hard_limit = True
        budget.alert_threshold_pct = 80
        budget.is_active = True
        return budget
    budget = LLMBudget(
        tenant_id=tenant_id,
        scope_type=scope_type,
        scope_id=scope_id,
        period="monthly",
        amount_usd=amount_usd,
        token_limit=token_limit,
        hard_limit=True,
        alert_threshold_pct=80,
        is_active=True,
    )
    session.add(budget)
    await session.flush()
    return budget


async def _get_or_create_provider(session: AsyncSession, *, tenant_id: UUID) -> LLMProvider:
    result = await session.execute(
        select(LLMProvider).where(
            LLMProvider.tenant_id == tenant_id,
            LLMProvider.provider_key == "litellm",
        )
    )
    provider = result.scalar_one_or_none()
    if provider:
        provider.base_url = settings.litellm_base_url or provider.base_url
        provider.config = {
            **provider.config,
            "demo_seed": True,
            "mock_allowed_in_development": True,
        }
        return provider
    provider = LLMProvider(
        tenant_id=tenant_id,
        provider_key="litellm",
        name="LiteLLM Proxy",
        adapter_type="litellm",
        base_url=settings.litellm_base_url,
        region="private",
        is_active=True,
        config={"demo_seed": True, "mock_allowed_in_development": True},
    )
    session.add(provider)
    await session.flush()
    return provider


async def _get_or_create_credential(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    provider_id: UUID,
) -> LLMCredential:
    result = await session.execute(
        select(LLMCredential).where(
            LLMCredential.tenant_id == tenant_id,
            LLMCredential.provider_id == provider_id,
            LLMCredential.display_name == "Demo LiteLLM Virtual Key",
        )
    )
    credential = result.scalar_one_or_none()
    if credential:
        if credential.secret_ref and credential.secret_ref.startswith("demo://"):
            demo_secret = "sk-agenthive-demo"
            credential.secret_ref = encrypt_secret(demo_secret)
            credential.masked_secret = mask_secret(demo_secret)
        return credential
    demo_secret = "sk-agenthive-demo"
    credential = LLMCredential(
        tenant_id=tenant_id,
        provider_id=provider_id,
        owner_type="tenant",
        owner_id=None,
        display_name="Demo LiteLLM Virtual Key",
        secret_ref=encrypt_secret(demo_secret),
        masked_secret=mask_secret(demo_secret),
        is_active=True,
        last_rotated_at=datetime.now(timezone.utc),
    )
    session.add(credential)
    await session.flush()
    return credential


async def _get_or_create_model(session: AsyncSession) -> LLMModel:
    result = await session.execute(select(LLMModel).where(LLMModel.model_key == "qwen-plus"))
    model = result.scalar_one_or_none()
    if model:
        return model
    model = LLMModel(
        provider_key="qwen",
        model_key="qwen-plus",
        display_name="Qwen Plus",
        model_type="chat",
        context_window=131072,
        capabilities=["chat", "stream", "tool_calling"],
        is_global=True,
    )
    session.add(model)
    await session.flush()
    return model


async def _get_or_create_price(session: AsyncSession, *, model_id: UUID) -> LLMModelPrice:
    result = await session.execute(
        select(LLMModelPrice).where(
            LLMModelPrice.model_id == model_id,
            LLMModelPrice.currency == "USD",
            LLMModelPrice.effective_to.is_(None),
        )
    )
    price = result.scalar_one_or_none()
    if price:
        return price
    price = LLMModelPrice(
        model_id=model_id,
        currency="USD",
        input_per_1k_tokens=Decimal("0.00030"),
        output_per_1k_tokens=Decimal("0.00060"),
        effective_from=datetime.now(timezone.utc) - timedelta(days=1),
    )
    session.add(price)
    await session.flush()
    return price


async def _get_or_create_deployment(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    provider_id: UUID,
    credential_id: UUID,
    model_id: UUID,
) -> LLMDeployment:
    result = await session.execute(
        select(LLMDeployment).where(
            LLMDeployment.tenant_id == tenant_id,
            LLMDeployment.routing_key == "cn-primary-chat",
        )
    )
    deployment = result.scalar_one_or_none()
    if deployment:
        return deployment
    deployment = LLMDeployment(
        tenant_id=tenant_id,
        provider_id=provider_id,
        credential_id=credential_id,
        model_id=model_id,
        deployment_name="CN Primary Chat",
        routing_key="cn-primary-chat",
        is_active=True,
        priority=80,
        config={"fallback": ["cost-chat"], "policy": "balanced-quality"},
    )
    session.add(deployment)
    await session.flush()
    return deployment


async def _get_or_create_policy(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    model_key: str,
    routing_key: str,
) -> LLMPolicy:
    result = await session.execute(
        select(LLMPolicy).where(
            LLMPolicy.tenant_id == tenant_id,
            LLMPolicy.name == "Demo Default Model Policy",
        )
    )
    policy = result.scalar_one_or_none()
    if policy:
        policy.allowed_models = _demo_allowed_models(model_key)
        policy.allowed_routing_keys = _demo_allowed_routing_keys(routing_key)
        return policy
    policy = LLMPolicy(
        tenant_id=tenant_id,
        name="Demo Default Model Policy",
        description="Default model policy for demo tenant, departments, users, and Agents.",
        scope_type="tenant",
        scope_id=None,
        effect="allow",
        allowed_models=_demo_allowed_models(model_key),
        allowed_routing_keys=_demo_allowed_routing_keys(routing_key),
        default_model_key=model_key,
        default_routing_key=routing_key,
        max_tokens=4096,
        priority=100,
        is_active=True,
        metadata_json={"demo_seed": True},
    )
    session.add(policy)
    await session.flush()
    return policy


def _demo_allowed_models(model_key: str) -> list[str]:
    return [
        model_key,
        "deepseek-v4-flash",
        "moonshot-v1-128k",
        "mimo-chat",
        "mimo-v2.5-pro",
        "abab6.5s-chat",
        "glm-4-plus",
        "doubao-pro-32k",
        "gpt-4o-mini",
        "openai/gpt-image-2",
        "google/nano-banana",
        "volcengine/seedance-2.0",
        "openai-compatible-image",
        "openai-compatible-video",
    ]


def _demo_allowed_routing_keys(routing_key: str) -> list[str]:
    return [
        routing_key,
        "cost-chat",
        "deepseek-chat",
        "long-context-chat",
        "mimo-chat",
        "minimax-chat",
        "glm-chat",
        "doubao-chat",
        "image-generation",
        "video-generation",
        "private-image-generation",
        "private-video-generation",
    ]
