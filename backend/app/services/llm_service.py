from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
from typing import Any, cast
from uuid import UUID

from cryptography.fernet import InvalidToken
from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.deps import Principal, is_tenant_admin
from app.core.config import is_development_environment, settings
from app.core.secrets import decrypt_secret, encrypt_secret, mask_secret
from app.llm.budget import BudgetGuard
from app.llm import catalog_helpers, policy_validation
from app.llm import connection_diagnostics_service
from app.llm.gateway import LLMGateway
from app.llm.policy import ModelPolicyEngine, ModelPolicyRule
from app.llm.pricing import ModelPricingCatalog, PricingMatchType, PricingRule
from app.llm.router import ModelRouter
from app.llm.schemas import (
    DeploymentConfig,
    LLMAdapterType,
    LLMChatRequest as GatewayChatRequest,
    LLMDeploymentStatus,
    LLMProviderStatus,
    LLMRequestContext,
    ProviderConfig,
)
from app.llm.usage import UsageCollector
from app.media.http_provider import HTTPMediaProviderAdapter  # noqa: F401
from app.models.base import utc_now
from app.models.agent_module import AgentInstance
from app.models.channel import ChannelConfig
from app.models.llm import (
    LLMCredential,
    LLMDeployment,
    LLMModel,
    LLMModelPrice,
    LLMPolicy,
    LLMProvider,
)
from app.models.org import Department
from app.models.tenant import CostCenter
from app.models.user import User, UserDepartment
from app.schemas.llm import (
    LLMChatRequest,
    LLMChatResponse,
    LLMConnectionTestHistoryItem,
    LLMConnectionTestHistoryResponse,
    LLMConnectionTestRequest,
    LLMConnectionTestResponse,
    LLMCredentialResponse,
    LLMCredentialUpsertRequest,
    LLMDeploymentAcceptanceTestRequest,
    LLMDeploymentAcceptanceTestResponse,
    LLMDeploymentListResponse,
    LLMDeploymentReadinessResponse,
    LLMDeploymentResponse,
    LLMGovernanceTargetItem,
    LLMGovernanceTargetsResponse,
    LLMModelPriceListResponse,
    LLMModelPriceResponse,
    LLMModelPriceUpsertRequest,
    LLMPolicyEffect,
    LLMPolicyListResponse,
    LLMPolicyResponse,
    LLMPolicyScope,
    LLMPolicyStatus,
    LLMPolicyStatusUpdateRequest,
    LLMPolicyUpsertRequest,
    LLMProviderListResponse,
    LLMProviderResponse,
    LLMReadinessResponse,
    LLMUsageResponse,
)
from app.services.audit_service import record_audit_event


@dataclass(frozen=True)
class ProviderCatalogSpec:
    provider_key: str
    name: str
    model_key: str
    display_name: str
    context_window: int | None
    capabilities: tuple[str, ...] = ("chat", "stream", "tools")


DeploymentAcceptanceTarget = connection_diagnostics_service.DeploymentAcceptanceTarget


_PRIVATE_PROVIDER_KEYS = {
    "openai_compatible",
    "ollama",
    "vllm",
    "sglang",
    "lmstudio",
    "xinference",
    "localai",
}

_MODEL_POLICY_KEY_PATTERN = policy_validation.MODEL_POLICY_KEY_PATTERN
_MAX_MODEL_POLICY_LIST_ITEMS = policy_validation.MAX_MODEL_POLICY_LIST_ITEMS

_PROVIDER_CATALOG: tuple[ProviderCatalogSpec, ...] = (
    ProviderCatalogSpec("openai", "OpenAI GPT", "gpt-4o", "GPT-4o", 128000),
    ProviderCatalogSpec(
        "anthropic", "Anthropic Claude", "claude-3-5-sonnet", "Claude 3.5 Sonnet", 200000
    ),
    ProviderCatalogSpec("gemini", "Google Gemini", "gemini-1.5-pro", "Gemini 1.5 Pro", 1000000),
    ProviderCatalogSpec(
        "azure_openai", "Azure OpenAI", "gpt-4o-mini", "Azure OpenAI GPT-4o mini", 128000
    ),
    ProviderCatalogSpec(
        "bedrock",
        "AWS Bedrock",
        "anthropic.claude-3-5-sonnet-20240620-v1:0",
        "Claude 3.5 Sonnet via Bedrock",
        200000,
    ),
    ProviderCatalogSpec(
        "vertex_ai", "Google Vertex AI", "gemini-1.5-pro", "Gemini 1.5 Pro via Vertex", 1000000
    ),
    ProviderCatalogSpec("mistral", "Mistral", "mistral-large-latest", "Mistral Large", 128000),
    ProviderCatalogSpec("cohere", "Cohere", "command-r-plus", "Command R+", 128000),
    ProviderCatalogSpec("xai", "xAI", "grok-2-latest", "Grok 2", 128000),
    ProviderCatalogSpec("qwen", "Qwen / 通义千问", "qwen-plus", "Qwen Plus", 131072),
    ProviderCatalogSpec(
        "deepseek",
        "DeepSeek",
        "deepseek-v4-flash",
        "DeepSeek V4 Flash",
        64000,
        ("chat", "stream", "reasoning", "coding"),
    ),
    ProviderCatalogSpec("kimi", "Kimi / Moonshot", "moonshot-v1-128k", "Kimi 128K", 128000),
    ProviderCatalogSpec("minimax", "MiniMax", "abab6.5s-chat", "MiniMax Chat", 245760),
    ProviderCatalogSpec(
        "mimo", "MiMo", "mimo-chat", "MiMo Chat", 32768, ("chat", "stream", "reasoning")
    ),
    ProviderCatalogSpec("glm", "GLM / 智谱", "glm-4-plus", "GLM-4 Plus", 128000),
    ProviderCatalogSpec("doubao", "Doubao / 火山方舟", "doubao-pro-32k", "Doubao Pro 32K", 32768),
    ProviderCatalogSpec(
        "baidu_qianfan", "Baidu Qianfan / 文心", "ernie-4.0-turbo-8k", "ERNIE 4.0 Turbo", 8192
    ),
    ProviderCatalogSpec(
        "hunyuan", "Tencent Hunyuan / 腾讯混元", "hunyuan-pro", "Hunyuan Pro", 32768
    ),
    ProviderCatalogSpec("spark", "iFLYTEK Spark / 讯飞星火", "spark-max", "Spark Max", 32768),
    ProviderCatalogSpec(
        "openrouter", "OpenRouter", "openai/gpt-4o-mini", "GPT-4o mini via OpenRouter", 128000
    ),
    ProviderCatalogSpec(
        "together",
        "Together AI",
        "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        "Llama 3.1 70B via Together",
        128000,
    ),
    ProviderCatalogSpec(
        "fireworks",
        "Fireworks",
        "accounts/fireworks/models/llama-v3p1-70b-instruct",
        "Llama 3.1 70B via Fireworks",
        128000,
    ),
    ProviderCatalogSpec(
        "groq", "Groq", "llama-3.1-70b-versatile", "Llama 3.1 70B via Groq", 131072
    ),
    ProviderCatalogSpec(
        "novita", "Novita", "meta-llama/llama-3.1-70b-instruct", "Llama 3.1 70B via Novita", 128000
    ),
    ProviderCatalogSpec(
        "siliconflow",
        "SiliconFlow / 硅基流动",
        "deepseek-ai/DeepSeek-V3",
        "DeepSeek V3 via SiliconFlow",
        64000,
    ),
    ProviderCatalogSpec("ai302", "302.AI", "gpt-4o-mini", "GPT-4o mini via 302.AI", 128000),
    ProviderCatalogSpec(
        "ollama", "Ollama", "llama3.1", "Ollama Llama 3.1", 128000, ("chat", "stream")
    ),
    ProviderCatalogSpec("vllm", "vLLM", "local-chat", "vLLM Local Chat", 32768, ("chat", "stream")),
    ProviderCatalogSpec(
        "sglang", "SGLang", "local-chat", "SGLang Local Chat", 32768, ("chat", "stream")
    ),
    ProviderCatalogSpec(
        "lmstudio", "LM Studio", "local-model", "LM Studio Local Model", 32768, ("chat", "stream")
    ),
    ProviderCatalogSpec(
        "xinference", "Xinference", "local-chat", "Xinference Local Chat", 32768, ("chat", "stream")
    ),
    ProviderCatalogSpec(
        "localai", "LocalAI", "local-chat", "LocalAI Chat", 32768, ("chat", "stream")
    ),
    ProviderCatalogSpec(
        "openai_images",
        "OpenAI Images",
        "openai/gpt-image-2",
        "ChatGPT Images 2.0",
        None,
        ("image_generation", "reference_image"),
    ),
    ProviderCatalogSpec(
        "nano_banana",
        "Nano Banana",
        "google/nano-banana",
        "Nano Banana Image",
        None,
        ("image_generation", "reference_image", "style_transfer"),
    ),
    ProviderCatalogSpec(
        "volcengine_seedance",
        "Volcengine Seedance",
        "volcengine/seedance-2.0",
        "Seedance 2.0 Video",
        None,
        ("video_generation", "reference_image_to_video", "reference_video"),
    ),
    ProviderCatalogSpec(
        "openai_compatible_media",
        "Private OpenAI-compatible Media",
        "openai-compatible-image",
        "Private Image/Video Model",
        None,
        ("image_generation", "video_generation", "reference_image"),
    ),
)


def _catalog_provider_base_url(provider_key: str) -> str | None:
    if provider_key == "openai_images":
        return settings.openai_images_base_url
    if provider_key == "nano_banana":
        return settings.nano_banana_base_url
    if provider_key == "volcengine_seedance":
        return settings.volcengine_seedance_base_url
    if provider_key == "openai_compatible_media":
        return settings.media_openai_compatible_base_url
    # Local / on-prem inference engines (OpenAI-compatible endpoints).
    return _local_inference_base_urls().get(provider_key)


def _catalog_provider_configured(provider_key: str) -> bool:
    if provider_key == "openai_images":
        return bool(settings.openai_images_base_url and settings.openai_images_api_key)
    if provider_key == "nano_banana":
        return bool(settings.nano_banana_base_url and settings.nano_banana_api_key)
    if provider_key == "volcengine_seedance":
        return bool(settings.volcengine_seedance_base_url and settings.volcengine_seedance_api_key)
    if provider_key == "openai_compatible_media":
        return bool(
            settings.media_openai_compatible_base_url and settings.media_openai_compatible_api_key
        )
    # Local inference engines are "configured" when a base_url is set; api_key
    # is optional because these engines typically run without auth on localhost.
    return bool(_local_inference_base_urls().get(provider_key))


# Local / on-prem OpenAI-compatible inference engines. base_url alone activates
# the provider; auth is optional (engines may run without API key on localhost).
_LOCAL_INFERENCE_ENGINES: dict[str, tuple[str, str]] = {
    # provider_key: (base_url_attr, api_key_attr)
    "ollama": ("ollama_base_url", "ollama_api_key"),
    "vllm": ("vllm_base_url", "vllm_api_key"),
    "sglang": ("sglang_base_url", "sglang_api_key"),
    "lmstudio": ("lmstudio_base_url", "lmstudio_api_key"),
    "xinference": ("xinference_base_url", "xinference_api_key"),
    "localai": ("localai_base_url", "localai_api_key"),
}


def _local_inference_base_urls() -> dict[str, str | None]:
    return {key: getattr(settings, attrs[0]) for key, attrs in _LOCAL_INFERENCE_ENGINES.items()}


def _local_inference_api_key(provider_key: str) -> str:
    attrs = _LOCAL_INFERENCE_ENGINES.get(provider_key)
    if attrs is None:
        return ""
    return str(getattr(settings, attrs[1]) or "")


def _is_local_inference_engine(provider_key: str) -> bool:
    return provider_key in _LOCAL_INFERENCE_ENGINES


def _default_provider_routing_key(provider_key: str) -> str:
    return catalog_helpers.default_provider_routing_key(provider_key)


_PROVIDERS = [
    ProviderConfig(
        provider_key="litellm",
        name="LiteLLM Proxy",
        adapter_type=LLMAdapterType.LITELLM,
        base_url=settings.litellm_base_url,
        status=(
            LLMProviderStatus.ACTIVE
            if settings.litellm_base_url
            else LLMProviderStatus.NOT_CONFIGURED
        ),
        capabilities=["chat", "stream", "fallback", "multi_provider"],
        credential_configured=bool(settings.litellm_master_key),
        metadata={
            "control_plane": "AgentHive",
            "mock_adapter": not bool(settings.litellm_master_key),
            "live_network_call": bool(settings.litellm_master_key),
        },
    ),
    ProviderConfig(
        provider_key="openai_compatible",
        name="OpenAI-compatible Endpoint",
        adapter_type=LLMAdapterType.OPENAI_COMPATIBLE,
        base_url=settings.openai_compatible_base_url,
        status=(
            LLMProviderStatus.ACTIVE
            if settings.openai_compatible_base_url and settings.openai_compatible_api_key
            else LLMProviderStatus.NOT_CONFIGURED
        ),
        capabilities=["chat", "stream"],
        credential_configured=bool(settings.openai_compatible_api_key),
        metadata={
            "supports_private_endpoints": True,
            "mock_adapter": not bool(
                settings.openai_compatible_base_url and settings.openai_compatible_api_key
            ),
            "live_network_call": bool(
                settings.openai_compatible_base_url and settings.openai_compatible_api_key
            ),
        },
    ),
    ProviderConfig(
        provider_key="anthropic_compatible",
        name="Anthropic-compatible Endpoint",
        adapter_type=LLMAdapterType.ANTHROPIC_COMPATIBLE,
        base_url=None,
        status=LLMProviderStatus.NOT_CONFIGURED,
        capabilities=["chat", "stream"],
        credential_configured=False,
        metadata={
            "supports_private_endpoints": True,
            "protocol": "anthropic-compatible",
            "mock_adapter": True,
            "live_network_call": False,
        },
    ),
    *[
        ProviderConfig(
            provider_key=spec.provider_key,
            name=spec.name,
            adapter_type=LLMAdapterType.OPENAI_COMPATIBLE,
            base_url=_catalog_provider_base_url(spec.provider_key),
            status=LLMProviderStatus.ACTIVE
            if _catalog_provider_configured(spec.provider_key)
            else LLMProviderStatus.NOT_CONFIGURED,
            capabilities=list(spec.capabilities),
            credential_configured=_catalog_provider_configured(spec.provider_key),
            metadata={
                "supports_litellm": True,
                "supports_openai_compatible": True,
                "mock_adapter": not _catalog_provider_configured(spec.provider_key),
                "catalog_provider": True,
                "live_network_call": _catalog_provider_configured(spec.provider_key),
                # Local inference engines (ollama/vllm/...) accept no API key.
                "auth_required": not _is_local_inference_engine(spec.provider_key),
                "local_inference_engine": _is_local_inference_engine(spec.provider_key),
            },
        )
        for spec in _PROVIDER_CATALOG
    ],
]

_DEPLOYMENTS = [
    DeploymentConfig(
        id=UUID("00000000-0000-4000-8000-000000000101"),
        provider_key="litellm",
        provider_name="LiteLLM Proxy",
        adapter_type=LLMAdapterType.LITELLM,
        model_key="gpt-4o-mini",
        display_name="GPT-4o mini via LiteLLM",
        deployment_name="Default Chat",
        routing_key="default-chat",
        status=LLMDeploymentStatus.ACTIVE,
        context_window=128000,
        capabilities=["chat", "stream", "tool_calling"],
        priority=100,
        base_url=settings.litellm_base_url,
        config={
            "mock": not bool(settings.litellm_master_key),
            "fallback_group": "default",
            "live_network_call": bool(settings.litellm_master_key),
        },
    ),
    DeploymentConfig(
        id=UUID("00000000-0000-4000-8000-000000000102"),
        provider_key="openai_compatible",
        provider_name="OpenAI-compatible Endpoint",
        adapter_type=LLMAdapterType.OPENAI_COMPATIBLE,
        model_key="local-chat",
        display_name="Private OpenAI-compatible Chat",
        deployment_name="Private Endpoint Placeholder",
        routing_key="private-chat",
        status=(
            LLMDeploymentStatus.ACTIVE
            if settings.openai_compatible_base_url and settings.openai_compatible_api_key
            else LLMDeploymentStatus.INACTIVE
        ),
        context_window=32768,
        capabilities=["chat", "stream"],
        priority=200,
        base_url=settings.openai_compatible_base_url,
        config={
            "mock": not bool(
                settings.openai_compatible_base_url and settings.openai_compatible_api_key
            ),
            "requires_configuration": not bool(
                settings.openai_compatible_base_url and settings.openai_compatible_api_key
            ),
            "live_network_call": bool(
                settings.openai_compatible_base_url and settings.openai_compatible_api_key
            ),
        },
    ),
    DeploymentConfig(
        id=UUID("00000000-0000-4000-8000-000000000103"),
        provider_key="anthropic_compatible",
        provider_name="Anthropic-compatible Endpoint",
        adapter_type=LLMAdapterType.ANTHROPIC_COMPATIBLE,
        model_key="claude-compatible",
        display_name="Private Anthropic-compatible Chat",
        deployment_name="Anthropic-compatible Placeholder",
        routing_key="anthropic-private-chat",
        status=LLMDeploymentStatus.INACTIVE,
        context_window=200000,
        capabilities=["chat", "stream"],
        priority=210,
        base_url=None,
        config={
            "mock": True,
            "requires_configuration": True,
            "protocol": "anthropic-compatible",
            "live_network_call": False,
        },
    ),
    *[
        DeploymentConfig(
            id=deployment_id,
            provider_key=provider_key,
            provider_name=provider_name,
            adapter_type=LLMAdapterType.OPENAI_COMPATIBLE,
            model_key=model_key,
            display_name=display_name,
            deployment_name=f"{provider_name} Placeholder",
            routing_key=_default_provider_routing_key(provider_key),
            status=LLMDeploymentStatus.INACTIVE,
            context_window=context_window,
            capabilities=list(capabilities),
            priority=300,
            config={"mock": True, "requires_configuration": True},
        )
        for deployment_id, provider_key, provider_name, model_key, display_name, context_window, capabilities in [
            (
                UUID(f"00000000-0000-4000-8000-{index:012d}"),
                spec.provider_key,
                spec.name,
                spec.model_key,
                spec.display_name,
                spec.context_window,
                spec.capabilities,
            )
            for index, spec in enumerate(_PROVIDER_CATALOG, start=201)
        ]
    ],
]

_usage_collector = UsageCollector()


async def list_model_providers(
    session: AsyncSession | None = None,
    principal: Principal | None = None,
) -> LLMProviderListResponse:
    configured: set[str] = set()
    if session and principal:
        try:
            configured = await _configured_provider_keys(session, principal)
        except Exception:
            configured = set()
    return LLMProviderListResponse(
        providers=[
            LLMProviderResponse(
                **provider.model_copy(
                    update={
                        "credential_configured": provider.credential_configured
                        or provider.provider_key in configured,
                        "status": LLMProviderStatus.ACTIVE
                        if provider.credential_configured or provider.provider_key in configured
                        else provider.status,
                    }
                ).model_dump()
            )
            for provider in _PROVIDERS
        ]
    )


async def list_model_deployments(
    session: AsyncSession | None = None,
    principal: Principal | None = None,
) -> LLMDeploymentListResponse:
    deployments = _DEPLOYMENTS
    if session is not None and principal is not None:
        deployments = await _runtime_deployments(session, principal) or _DEPLOYMENTS
    return LLMDeploymentListResponse(
        deployments=[
            LLMDeploymentResponse(**deployment.model_dump(exclude={"base_url"}))
            for deployment in deployments
        ]
    )


async def list_model_policies(
    session: AsyncSession,
    principal: Principal,
) -> LLMPolicyListResponse:
    result = await session.execute(
        select(LLMPolicy)
        .where(cast(ColumnElement[bool], LLMPolicy.tenant_id == principal.tenant_id))
        .order_by(
            cast(Any, LLMPolicy.is_active).desc(),
            cast(Any, LLMPolicy.priority),
            cast(Any, LLMPolicy.created_at).desc(),
        )
    )
    return LLMPolicyListResponse(
        policies=[_policy_response(policy) for policy in result.scalars().all()]
    )


async def list_model_prices(session: AsyncSession) -> LLMModelPriceListResponse:
    result = await session.execute(
        select(LLMModelPrice, LLMModel)
        .join(LLMModel, cast(ColumnElement[bool], LLMModel.id == LLMModelPrice.model_id))
        .order_by(
            cast(Any, LLMModel.provider_key),
            cast(Any, LLMModel.model_key),
            cast(Any, LLMModelPrice.effective_from).desc(),
        )
    )
    return LLMModelPriceListResponse(
        prices=[_price_response(price, model) for price, model in result.all()]
    )


async def list_connection_test_history(
    session: AsyncSession,
    principal: Principal,
    *,
    limit: int = 20,
) -> LLMConnectionTestHistoryResponse:
    return await connection_diagnostics_service.list_connection_test_history(
        session,
        principal,
        limit=limit,
    )


async def get_model_readiness(
    session: AsyncSession,
    principal: Principal,
) -> LLMReadinessResponse:
    providers = (await list_model_providers(session, principal)).providers
    deployments = (await list_model_deployments(session, principal)).deployments
    prices = (await list_model_prices(session)).prices
    policies = (await list_model_policies(session, principal)).policies
    tests = (await list_connection_test_history(session, principal, limit=100)).tests
    provider_by_key = {provider.provider_key: provider for provider in providers}
    priced_model_keys = {price.model_key for price in prices}
    readiness_items = [
        _deployment_readiness_item(
            deployment=deployment,
            provider=provider_by_key.get(deployment.provider_key),
            priced_model_keys=priced_model_keys,
            policies=policies,
            tests=tests,
        )
        for deployment in deployments
    ]
    summary = {
        "total": len(readiness_items),
        "ready": sum(1 for item in readiness_items if item.readiness == "ready"),
        "warning": sum(1 for item in readiness_items if item.readiness == "warning"),
        "blocked": sum(1 for item in readiness_items if item.readiness == "blocked"),
    }
    return LLMReadinessResponse(
        generated_at=utc_now(),
        summary=summary,
        deployments=readiness_items,
    )


async def list_model_governance_targets(
    session: AsyncSession,
    principal: Principal,
) -> LLMGovernanceTargetsResponse:
    full_access = is_tenant_admin(principal)
    department_ids = (
        set() if full_access else await _model_governance_department_ids(session, principal)
    )
    departments_result = await session.execute(
        select(Department)
        .where(cast(ColumnElement[bool], Department.tenant_id == principal.tenant_id))
        .order_by(cast(Any, Department.sort_order), cast(Any, Department.name))
    )
    cost_centers_result = await session.execute(
        select(CostCenter)
        .where(cast(ColumnElement[bool], CostCenter.tenant_id == principal.tenant_id))
        .order_by(cast(Any, CostCenter.code), cast(Any, CostCenter.name))
    )
    users_result = await session.execute(
        select(User)
        .where(
            cast(ColumnElement[bool], User.tenant_id == principal.tenant_id),
            cast(Any, User.deleted_at).is_(None),
        )
        .order_by(cast(Any, User.full_name), cast(Any, User.email))
    )
    agents_result = await session.execute(
        select(AgentInstance)
        .where(AgentInstance.tenant_id == principal.tenant_id)
        .order_by(AgentInstance.name, AgentInstance.slug)
    )
    channels_result = await session.execute(
        select(ChannelConfig)
        .where(ChannelConfig.tenant_id == principal.tenant_id)
        .order_by(ChannelConfig.name, ChannelConfig.channel_type)
    )

    departments = [
        department
        for department in departments_result.scalars().all()
        if full_access or department.id in department_ids
    ]
    cost_centers = [
        cost_center
        for cost_center in cost_centers_result.scalars().all()
        if full_access or cost_center.department_id in department_ids
    ]
    users = [
        user for user in users_result.scalars().all() if full_access or user.id == principal.user_id
    ]
    agents = [
        agent
        for agent in agents_result.scalars().all()
        if _can_list_model_governance_agent(
            agent, principal, department_ids, full_access=full_access
        )
    ]
    agent_ids = {agent.id for agent in agents}
    channels = [
        channel
        for channel in channels_result.scalars().all()
        if full_access or (channel.agent_id is not None and channel.agent_id in agent_ids)
    ]
    return LLMGovernanceTargetsResponse(
        departments=[
            LLMGovernanceTargetItem(
                id=department.id,
                label=department.name,
                description=department.description,
                metadata={
                    "parent_id": str(department.parent_id) if department.parent_id else None,
                    "sort_order": department.sort_order,
                },
            )
            for department in departments
        ],
        cost_centers=[
            LLMGovernanceTargetItem(
                id=cost_center.id,
                label=f"{cost_center.code} - {cost_center.name}",
                description=cost_center.description,
                status="active" if cost_center.is_active else "inactive",
                metadata={
                    "code": cost_center.code,
                    "department_id": str(cost_center.department_id)
                    if cost_center.department_id
                    else None,
                    "monthly_budget_usd": str(cost_center.monthly_budget_usd)
                    if cost_center.monthly_budget_usd is not None
                    else None,
                },
            )
            for cost_center in cost_centers
        ],
        users=[
            LLMGovernanceTargetItem(
                id=user.id,
                label=f"{user.full_name or user.username or user.email} ({user.email})",
                status="active" if user.is_active else "inactive",
                metadata={
                    "email": user.email,
                    "is_tenant_admin": user.is_tenant_admin,
                },
            )
            for user in users
        ],
        agents=[
            LLMGovernanceTargetItem(
                id=agent.id,
                label=f"{agent.name} ({agent.agent_key}:{agent.slug}, {agent.status})",
                description=agent.description,
                status=agent.status,
                metadata={
                    "agent_key": agent.agent_key,
                    "module_key": agent.module_key,
                    "department_id": str(agent.department_id) if agent.department_id else None,
                    "visibility": agent.visibility,
                },
            )
            for agent in agents
        ],
        channels=[
            LLMGovernanceTargetItem(
                id=channel.id,
                label=f"{channel.name} ({channel.channel_type}:{channel.channel_key})",
                status=channel.status,
                metadata={
                    "channel_type": channel.channel_type,
                    "channel_key": channel.channel_key,
                    "agent_id": str(channel.agent_id) if channel.agent_id else None,
                },
            )
            for channel in channels
        ],
    )


async def _model_governance_department_ids(
    session: AsyncSession, principal: Principal
) -> set[UUID]:
    result = await session.execute(
        select(UserDepartment.department_id)
        .join(
            Department,
            cast(ColumnElement[bool], Department.id == UserDepartment.department_id),
        )
        .where(
            cast(ColumnElement[bool], UserDepartment.user_id == principal.user_id),
            cast(ColumnElement[bool], Department.tenant_id == principal.tenant_id),
        )
    )
    return set(result.scalars().all())


def _can_list_model_governance_agent(
    agent: AgentInstance,
    principal: Principal,
    department_ids: set[UUID],
    *,
    full_access: bool,
) -> bool:
    if full_access:
        return True
    if agent.visibility == "tenant":
        return True
    if agent.visibility == "private":
        return principal.user_id in {agent.owner_user_id, agent.created_by}
    if agent.visibility == "department":
        return agent.department_id is not None and agent.department_id in department_ids
    return False


async def upsert_model_price(
    session: AsyncSession,
    payload: LLMModelPriceUpsertRequest,
    principal: Principal,
    *,
    request_id: str | None = None,
) -> LLMModelPriceResponse:
    await _require_global_model_price_write_access(session, principal)
    if payload.currency.upper() != "USD":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Only USD model prices are supported by the current cost ledger.",
        )
    effective_from = payload.effective_from or utc_now()
    if payload.effective_to is not None and payload.effective_to <= effective_from:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="effective_to must be after effective_from.",
        )

    provider_config = _provider_config(payload.provider_key)
    model = await _get_or_create_model(session, provider_config, payload.model_key)
    if payload.display_name:
        model.display_name = payload.display_name
    result = await session.execute(
        select(LLMModelPrice).where(
            LLMModelPrice.model_id == model.id,
            LLMModelPrice.currency == payload.currency.upper(),
            LLMModelPrice.effective_from == effective_from,
        )
    )
    price = result.scalar_one_or_none()
    if price is None:
        price = LLMModelPrice(
            model_id=model.id,
            currency=payload.currency.upper(),
            effective_from=effective_from,
        )
        session.add(price)

    price.input_per_1k_tokens = payload.input_per_1k_tokens
    price.output_per_1k_tokens = payload.output_per_1k_tokens
    price.effective_to = payload.effective_to
    await session.flush()
    await record_audit_event(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        action="llm.model_price.upsert",
        resource_type="llm_model_price",
        resource_id=price.id,
        request_id=request_id,
        details={
            "provider_key": payload.provider_key,
            "model_key": payload.model_key,
            "currency": price.currency,
            "input_per_1k_tokens": str(price.input_per_1k_tokens),
            "output_per_1k_tokens": str(price.output_per_1k_tokens),
            "effective_from": price.effective_from.isoformat(),
            "effective_to": price.effective_to.isoformat() if price.effective_to else None,
        },
    )
    await session.commit()
    await session.refresh(price)
    await session.refresh(model)
    return _price_response(price, model)


async def _require_global_model_price_write_access(
    session: AsyncSession,
    principal: Principal,
) -> None:
    """Fail closed because model prices are shared by every tenant at runtime."""
    user = await session.get(User, principal.user_id)
    if (
        user is None
        or user.tenant_id != principal.tenant_id
        or user.deleted_at is not None
        or not user.is_active
        or not user.is_super_admin
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=("Global model prices can only be modified by a platform super administrator."),
        )


async def upsert_model_policy(
    session: AsyncSession,
    payload: LLMPolicyUpsertRequest,
    principal: Principal,
    *,
    request_id: str | None = None,
) -> LLMPolicyResponse:
    _normalize_and_validate_policy_payload(payload)
    _validate_policy_scope(payload)
    await _validate_policy_scope_target(session, payload, principal)
    await _validate_policy_runtime_targets(session, payload, principal)
    policy: LLMPolicy | None
    if payload.id is None:
        policy = LLMPolicy(tenant_id=principal.tenant_id, name=payload.name)
        session.add(policy)
        action = "llm.policy.create"
    else:
        result = await session.execute(
            select(LLMPolicy).where(
                cast(ColumnElement[bool], LLMPolicy.tenant_id == principal.tenant_id),
                cast(ColumnElement[bool], LLMPolicy.id == payload.id),
            )
        )
        policy = result.scalar_one_or_none()
        if policy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="LLM policy not found.",
            )
        action = "llm.policy.update"

    policy.name = payload.name
    policy.description = payload.description
    policy.scope_type = payload.scope_type.value
    policy.scope_id = payload.scope_id
    policy.effect = payload.effect.value
    policy.allowed_models = _dedupe_text_list(payload.allowed_models)
    policy.allowed_routing_keys = _dedupe_text_list(payload.allowed_routing_keys)
    policy.default_model_key = payload.default_model_key
    policy.default_routing_key = payload.default_routing_key
    policy.max_tokens = payload.max_tokens
    policy.priority = payload.priority
    policy.is_active = payload.status == LLMPolicyStatus.ACTIVE
    policy.metadata_json = payload.metadata
    await session.flush()
    await record_audit_event(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        action=action,
        resource_type="llm_policy",
        resource_id=policy.id,
        request_id=request_id,
        details={
            "scope_type": policy.scope_type,
            "scope_id": str(policy.scope_id) if policy.scope_id else None,
            "effect": policy.effect,
            "allowed_models": policy.allowed_models,
            "allowed_routing_keys": policy.allowed_routing_keys,
            "default_model_key": policy.default_model_key,
            "default_routing_key": policy.default_routing_key,
            "max_tokens": policy.max_tokens,
        },
    )
    await session.commit()
    await session.refresh(policy)
    return _policy_response(policy)


async def update_model_policy_status(
    session: AsyncSession,
    policy_id: UUID,
    payload: LLMPolicyStatusUpdateRequest,
    principal: Principal,
    *,
    request_id: str | None = None,
) -> LLMPolicyResponse:
    result = await session.execute(
        select(LLMPolicy).where(
            LLMPolicy.tenant_id == principal.tenant_id,
            LLMPolicy.id == policy_id,
        )
    )
    policy = result.scalar_one_or_none()
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="LLM policy not found.",
        )

    previous_status = LLMPolicyStatus.ACTIVE if policy.is_active else LLMPolicyStatus.INACTIVE
    policy.is_active = payload.status == LLMPolicyStatus.ACTIVE
    policy.updated_at = utc_now()
    await record_audit_event(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        action="llm.policy.status.update",
        resource_type="llm_policy",
        resource_id=policy.id,
        request_id=request_id,
        details={
            "previous_status": previous_status.value,
            "status": payload.status.value,
            "scope_type": policy.scope_type,
            "scope_id": str(policy.scope_id) if policy.scope_id else None,
            "effect": policy.effect,
        },
    )
    await session.commit()
    await session.refresh(policy)
    return _policy_response(policy)


async def test_model_connection(
    payload: LLMConnectionTestRequest,
    principal: Principal,
    session: AsyncSession | None = None,
    *,
    request_id: str | None = None,
) -> LLMConnectionTestResponse:
    return await connection_diagnostics_service.run_connection_test(
        payload,
        principal,
        session,
        request_id=request_id,
        build_gateway=_build_gateway,
        provider_config=_provider_config,
        default_model_key=_default_model_key,
        default_routing_key=_default_routing_key,
    )


cast(Any, test_model_connection).__test__ = False


async def verify_model_deployment_call(
    session: AsyncSession,
    deployment_id: UUID,
    principal: Principal,
    payload: LLMDeploymentAcceptanceTestRequest,
    *,
    request_id: str | None = None,
) -> LLMDeploymentAcceptanceTestResponse:
    return await connection_diagnostics_service.run_deployment_acceptance_test(
        session,
        deployment_id,
        principal,
        payload,
        request_id=request_id,
        resolve_target=_get_acceptance_target,
        run_gateway_chat=run_gateway_chat,
    )


async def _record_deployment_acceptance_failure_audit(
    session: AsyncSession,
    *,
    deployment_id: UUID,
    principal: Principal,
    request_id: str | None,
    target: DeploymentAcceptanceTarget | None,
    exc: Exception,
) -> None:
    await connection_diagnostics_service._record_deployment_acceptance_failure_audit(
        session,
        deployment_id=deployment_id,
        principal=principal,
        request_id=request_id,
        target=target,
        exc=exc,
    )


async def _get_acceptance_target(
    session: AsyncSession,
    principal: Principal,
    deployment_id: UUID,
) -> DeploymentAcceptanceTarget:
    return await connection_diagnostics_service.get_acceptance_target(
        session,
        principal,
        deployment_id,
    )


async def _test_media_provider_connection(
    payload: LLMConnectionTestRequest,
    principal: Principal,
    session: AsyncSession | None,
) -> LLMConnectionTestResponse:
    return await connection_diagnostics_service._test_media_provider_connection(
        payload,
        principal,
        session,
        provider_config=_provider_config,
        default_model_key=_default_model_key,
        default_routing_key=_default_routing_key,
    )


def _is_media_connection_test(payload: LLMConnectionTestRequest) -> bool:
    return connection_diagnostics_service._is_media_connection_test(payload)


def _media_provider_key_for_connection_test(payload: LLMConnectionTestRequest) -> str:
    return connection_diagnostics_service._media_provider_key_for_connection_test(payload)


def _media_connection_source(
    payload: LLMConnectionTestRequest,
    has_database_adapter: bool,
    provider_config: ProviderConfig,
) -> str:
    return connection_diagnostics_service._media_connection_source(
        payload,
        has_database_adapter,
        provider_config,
    )


def _media_api_key_for_provider_key(provider_key: str) -> str:
    return connection_diagnostics_service._media_api_key_for_provider_key(provider_key)


async def upsert_provider_credential(
    session: AsyncSession,
    *,
    provider_key: str,
    payload: LLMCredentialUpsertRequest,
    principal: Principal,
    request_id: str | None = None,
) -> LLMCredentialResponse:
    provider_config = _provider_config(provider_key)
    await _validate_credential_owner_scope(session, payload, principal)
    provider = await _get_or_create_provider(session, principal, provider_config, payload.base_url)
    encrypted = encrypt_secret(payload.api_key)
    masked = mask_secret(payload.api_key)

    result = await session.execute(
        select(LLMCredential).where(
            LLMCredential.tenant_id == principal.tenant_id,
            LLMCredential.provider_id == provider.id,
            LLMCredential.owner_type == payload.owner_type,
            LLMCredential.owner_id == payload.owner_id,
        )
    )
    credential = result.scalar_one_or_none()
    if credential is None:
        credential = LLMCredential(
            tenant_id=principal.tenant_id,
            provider_id=provider.id,
            owner_type=payload.owner_type,
            owner_id=payload.owner_id,
            display_name=payload.display_name,
            secret_ref=encrypted,
            masked_secret=masked,
            is_active=True,
        )
        session.add(credential)
    else:
        credential.display_name = payload.display_name
        credential.owner_id = payload.owner_id
        credential.secret_ref = encrypted
        credential.masked_secret = masked
        credential.is_active = True

    if payload.base_url is not None:
        provider.base_url = payload.base_url
    provider.is_active = True
    deployment = await _upsert_default_deployment(
        session,
        principal,
        provider_config=provider_config,
        provider=provider,
        credential=credential,
        payload=payload,
    )
    await session.flush()
    await record_audit_event(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        action="llm.credential.upsert",
        resource_type="llm_provider",
        resource_id=provider.id,
        request_id=request_id,
        details={
            "provider_key": provider_key,
            "owner_type": payload.owner_type,
            "owner_id": str(payload.owner_id) if payload.owner_id else None,
        },
    )
    await session.commit()
    return LLMCredentialResponse(
        provider_key=provider.provider_key,
        display_name=credential.display_name,
        masked_secret=credential.masked_secret,
        credential_configured=True,
        base_url=provider.base_url,
        owner_type=credential.owner_type,
        owner_id=credential.owner_id,
        deployment_id=deployment.id if deployment else None,
        routing_key=deployment.routing_key if deployment else None,
        model_key=payload.model_key or _default_model_key(provider_config.provider_key),
    )


async def _record_connection_test_result_audit(
    session: AsyncSession | None,
    *,
    payload: LLMConnectionTestRequest,
    principal: Principal,
    request_id: str | None,
    response: LLMConnectionTestResponse,
) -> None:
    await connection_diagnostics_service._record_connection_test_result_audit(
        session,
        payload=payload,
        principal=principal,
        request_id=request_id,
        response=response,
    )


async def _record_connection_test_failure_audit(
    session: AsyncSession | None,
    *,
    payload: LLMConnectionTestRequest,
    principal: Principal,
    request_id: str | None,
    exc: HTTPException,
) -> None:
    await connection_diagnostics_service._record_connection_test_failure_audit(
        session,
        payload=payload,
        principal=principal,
        request_id=request_id,
        exc=exc,
    )


def _deployment_readiness_item(
    *,
    deployment: LLMDeploymentResponse,
    provider: LLMProviderResponse | None,
    priced_model_keys: set[str],
    policies: list[LLMPolicyResponse],
    tests: list[LLMConnectionTestHistoryItem],
) -> LLMDeploymentReadinessResponse:
    deployment_active = deployment.status == LLMDeploymentStatus.ACTIVE
    credential_configured = bool(provider and provider.credential_configured)
    requires_configuration = bool(
        deployment.config.get("requires_configuration") or deployment.config.get("mock")
    )
    matching_test = _latest_connection_test_for_deployment(deployment, tests)
    live_probe_ok = bool(
        matching_test and matching_test.ok and matching_test.live_network_call is True
    )
    pricing_configured = _model_has_pricing(deployment.model_key, priced_model_keys)
    policy_referenced = _deployment_referenced_by_policy(deployment, policies)
    fallback_configured = bool(
        deployment.config.get("fallback_group") or deployment.config.get("fallback_chain")
    )
    blockers: list[str] = []
    warnings: list[str] = []

    if not deployment_active:
        blockers.append("deployment_inactive")
    if not credential_configured:
        blockers.append("credential_missing")
    if requires_configuration:
        blockers.append("deployment_requires_configuration")
    if matching_test and matching_test.live_network_call is True and not matching_test.ok:
        blockers.append("live_probe_failed")
    if not matching_test or matching_test.live_network_call is not True:
        warnings.append("live_probe_missing")
    if not pricing_configured:
        warnings.append("pricing_missing")
    if not policy_referenced:
        warnings.append("policy_reference_missing")
    if not fallback_configured:
        warnings.append("fallback_not_configured")

    readiness = "blocked" if blockers else "warning" if warnings else "ready"
    return LLMDeploymentReadinessResponse(
        deployment_id=deployment.id,
        provider_key=deployment.provider_key,
        provider_name=deployment.provider_name,
        model_key=deployment.model_key,
        display_name=deployment.display_name,
        routing_key=deployment.routing_key,
        deployment_name=deployment.deployment_name,
        readiness=readiness,
        credential_configured=credential_configured,
        deployment_active=deployment_active,
        live_probe_ok=live_probe_ok,
        live_probe_checked_at=matching_test.checked_at if matching_test else None,
        last_probe_message=matching_test.message if matching_test else None,
        pricing_configured=pricing_configured,
        policy_referenced=policy_referenced,
        fallback_configured=fallback_configured,
        blockers=blockers,
        warnings=warnings,
        evidence={
            "adapter_type": deployment.adapter_type.value,
            "context_window": deployment.context_window,
            "capabilities": deployment.capabilities,
            "provider_status": provider.status.value if provider else None,
            "last_probe_request_id": matching_test.request_id if matching_test else None,
            "last_probe_operation": matching_test.operation if matching_test else None,
            "last_probe_live_network_call": matching_test.live_network_call
            if matching_test
            else None,
            "last_probe_status_code": matching_test.status_code if matching_test else None,
            "configuration_source": matching_test.configuration_source if matching_test else None,
        },
    )


def _latest_connection_test_for_deployment(
    deployment: LLMDeploymentResponse,
    tests: list[LLMConnectionTestHistoryItem],
) -> LLMConnectionTestHistoryItem | None:
    deployment_id = str(deployment.id)
    for test in tests:
        if test.deployment_id == deployment_id:
            return test
    for test in tests:
        if test.provider_key == deployment.provider_key and test.model_key == deployment.model_key:
            return test
    for test in tests:
        if test.provider_key == deployment.provider_key:
            return test
    return None


def _model_has_pricing(model_key: str, priced_model_keys: set[str]) -> bool:
    if model_key in priced_model_keys:
        return True
    return ModelPricingCatalog().price_rule_for(model_key).match_type != PricingMatchType.DEFAULT


def _deployment_referenced_by_policy(
    deployment: LLMDeploymentResponse,
    policies: list[LLMPolicyResponse],
) -> bool:
    for policy in policies:
        if policy.status != LLMPolicyStatus.ACTIVE or policy.effect != LLMPolicyEffect.ALLOW:
            continue
        if policy.allowed_models and deployment.model_key in policy.allowed_models:
            return True
        if policy.allowed_routing_keys and deployment.routing_key in policy.allowed_routing_keys:
            return True
        if policy.default_model_key == deployment.model_key:
            return True
        if policy.default_routing_key == deployment.routing_key:
            return True
    return False


async def run_gateway_chat(
    payload: LLMChatRequest,
    principal: Principal,
    *,
    session: AsyncSession | None = None,
    conversation_id: UUID | None = None,
    department_id: UUID | None = None,
    agent_id: UUID | None = None,
    channel_id: UUID | None = None,
    source: str = "api",
) -> LLMChatResponse:
    gateway = await _build_gateway(
        session,
        principal,
        department_id=department_id,
        user_id=principal.user_id,
    )
    response = await gateway.chat(
        GatewayChatRequest(**payload.model_dump()),
        LLMRequestContext(
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            department_id=department_id,
            agent_id=agent_id,
            channel_id=channel_id,
            conversation_id=conversation_id,
            source=source,
        ),
    )
    return LLMChatResponse(
        request_id=response.request_id,
        provider_key=response.provider_key,
        deployment_id=response.deployment_id,
        model_key=response.model_key,
        content=response.content,
        finish_reason=response.finish_reason,
        usage=LLMUsageResponse(**response.usage.model_dump()),
        metadata=response.metadata,
    )


async def run_gateway_chat_stream(
    payload: LLMChatRequest,
    principal: Principal,
    *,
    session: AsyncSession | None = None,
    conversation_id: UUID | None = None,
    department_id: UUID | None = None,
    agent_id: UUID | None = None,
    channel_id: UUID | None = None,
    source: str = "api",
) -> AsyncIterator[str]:
    """Stream chat completions from the LLM Gateway, yielding content deltas.

    Mirrors :func:`run_gateway_chat` but delegates to ``gateway.stream_chat``
    so callers receive incremental content as the provider emits it.
    """
    gateway = await _build_gateway(
        session,
        principal,
        department_id=department_id,
        user_id=principal.user_id,
    )
    async for delta in gateway.stream_chat(
        GatewayChatRequest(**payload.model_dump()),
        LLMRequestContext(
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            department_id=department_id,
            agent_id=agent_id,
            channel_id=channel_id,
            conversation_id=conversation_id,
            source=source,
        ),
    ):
        yield delta


async def _build_gateway(
    session: AsyncSession | None = None,
    principal: Principal | None = None,
    *,
    department_id: UUID | None = None,
    user_id: UUID | None = None,
) -> LLMGateway:
    providers = _PROVIDERS
    deployments = _DEPLOYMENTS
    use_runtime_control_plane = False
    if session is not None and principal is not None:
        runtime_providers = await _runtime_providers(
            session,
            principal,
            department_id=department_id,
            user_id=user_id if user_id is not None else principal.user_id,
        )
        runtime_deployments = await _runtime_deployments(session, principal)
        runtime_provider_keys = {provider.provider_key for provider in runtime_providers}
        runtime_deployments = [
            deployment
            for deployment in runtime_deployments
            if deployment.provider_key in runtime_provider_keys
        ]
        if runtime_providers and runtime_deployments:
            providers = runtime_providers
            deployments = runtime_deployments
            use_runtime_control_plane = True
    runtime_policy_rules = None
    runtime_pricing_rules = None
    if session is not None and principal is not None and use_runtime_control_plane:
        runtime_policy_rules = _policy_rules_matching_deployments(
            await _runtime_policy_rules(session, principal),
            deployments,
        )
        runtime_pricing_rules = await _runtime_pricing_rules(session)
    pricing = ModelPricingCatalog(runtime_pricing_rules)
    return LLMGateway(
        policy=ModelPolicyEngine(
            runtime_policy_rules,
            session=session,
        ),
        budget=BudgetGuard(pricing=pricing, session=session),
        router=ModelRouter(
            providers=providers,
            deployments=deployments,
            pricing=pricing,
            cost_aware_routing_enabled=settings.llm_cost_aware_routing_enabled,
        ),
        usage=UsageCollector(session=session) if session is not None else _usage_collector,
    )


async def _configured_provider_keys(
    session: AsyncSession,
    principal: Principal,
) -> set[str]:
    result = await session.execute(
        select(LLMProvider.provider_key, LLMCredential.secret_ref)
        .join(LLMCredential, cast(ColumnElement[bool], LLMCredential.provider_id == LLMProvider.id))
        .where(
            cast(ColumnElement[bool], LLMProvider.tenant_id == principal.tenant_id),
            cast(Any, LLMProvider.is_active).is_(True),
            cast(Any, LLMCredential.is_active).is_(True),
        )
    )
    configured: set[str] = set()
    for provider_key, secret_ref in result.all():
        try:
            decrypt_secret(secret_ref)
        except InvalidToken:
            continue
        configured.add(provider_key)
    return configured


def _provider_config(provider_key: str) -> ProviderConfig:
    for provider in _PROVIDERS:
        if provider.provider_key == provider_key:
            return provider
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Unsupported LLM provider: {provider_key}",
    )


async def _get_or_create_provider(
    session: AsyncSession,
    principal: Principal,
    provider_config: ProviderConfig,
    base_url: str | None,
) -> LLMProvider:
    result = await session.execute(
        select(LLMProvider).where(
            LLMProvider.tenant_id == principal.tenant_id,
            LLMProvider.provider_key == provider_config.provider_key,
        )
    )
    provider = result.scalar_one_or_none()
    if provider is not None:
        return provider

    provider = LLMProvider(
        tenant_id=principal.tenant_id,
        provider_key=provider_config.provider_key,
        name=provider_config.name,
        adapter_type=provider_config.adapter_type.value,
        base_url=base_url or provider_config.base_url,
        region=provider_config.region,
        is_active=True,
        config={
            "capabilities": provider_config.capabilities,
            "metadata": provider_config.metadata,
        },
    )
    session.add(provider)
    await session.flush()
    return provider


async def _upsert_default_deployment(
    session: AsyncSession,
    principal: Principal,
    *,
    provider_config: ProviderConfig,
    provider: LLMProvider,
    credential: LLMCredential,
    payload: LLMCredentialUpsertRequest,
) -> LLMDeployment | None:
    model_key = payload.model_key or _default_model_key(provider_config.provider_key)
    if not model_key:
        return None

    model = await _get_or_create_model(session, provider_config, model_key)
    routing_key = payload.routing_key or _default_routing_key(provider_config.provider_key)
    result = await session.execute(
        select(LLMDeployment).where(
            LLMDeployment.tenant_id == principal.tenant_id,
            LLMDeployment.routing_key == routing_key,
        )
    )
    deployment = result.scalar_one_or_none()
    if deployment is None:
        deployment = LLMDeployment(
            tenant_id=principal.tenant_id,
            provider_id=provider.id,
            model_id=model.id,
            credential_id=credential.id,
            deployment_name=payload.deployment_name or f"{provider_config.name} Default Chat",
            routing_key=routing_key,
            is_active=True,
            priority=10 if payload.make_default else 100,
            config={
                "created_by": "credential_upsert",
                "provider_key": provider.provider_key,
            },
        )
        session.add(deployment)
    else:
        deployment.provider_id = provider.id
        deployment.model_id = model.id
        deployment.credential_id = credential.id
        deployment.deployment_name = payload.deployment_name or deployment.deployment_name
        deployment.is_active = True
        deployment.priority = (
            min(deployment.priority, 10) if payload.make_default else deployment.priority
        )
        deployment.config = {
            **deployment.config,
            "updated_by": "credential_upsert",
            "provider_key": provider.provider_key,
        }
    await session.flush()
    return deployment


async def _get_or_create_model(
    session: AsyncSession,
    provider_config: ProviderConfig,
    model_key: str,
) -> LLMModel:
    result = await session.execute(select(LLMModel).where(LLMModel.model_key == model_key))
    model = result.scalar_one_or_none()
    if model is not None:
        return model
    model = LLMModel(
        provider_key=provider_config.provider_key,
        model_key=model_key,
        display_name=model_key,
        model_type=_model_type_for_capabilities(provider_config.capabilities),
        context_window=_context_window_for(model_key),
        capabilities=list(provider_config.capabilities),
        is_global=False,
    )
    session.add(model)
    await session.flush()
    return model


async def _runtime_providers(
    session: AsyncSession,
    principal: Principal,
    *,
    department_id: UUID | None = None,
    user_id: UUID | None = None,
) -> list[ProviderConfig]:
    result = await session.execute(
        select(LLMProvider, LLMCredential)
        .join(LLMCredential, cast(ColumnElement[bool], LLMCredential.provider_id == LLMProvider.id))
        .where(
            cast(ColumnElement[bool], LLMProvider.tenant_id == principal.tenant_id),
            cast(Any, LLMProvider.is_active).is_(True),
            cast(Any, LLMCredential.is_active).is_(True),
        )
    )
    selected: dict[str, list[tuple[int, LLMProvider, LLMCredential]]] = {}
    for provider, credential in result.all():
        rank = _credential_scope_rank(
            credential,
            department_id=department_id,
            user_id=user_id,
        )
        if rank is None:
            continue
        selected.setdefault(provider.provider_key, []).append((rank, provider, credential))

    providers: dict[str, ProviderConfig] = {}
    for provider_key, candidates in selected.items():
        decrypted_candidate: tuple[int, LLMProvider, LLMCredential, str, bool] | None = None
        for rank, provider, credential in sorted(
            candidates, key=lambda item: item[0], reverse=True
        ):
            try:
                api_key = decrypt_secret(credential.secret_ref)
            except InvalidToken:
                if _development_mock_allowed_for_provider(provider):
                    decrypted_candidate = (rank, provider, credential, "", True)
                    break
                continue
            decrypted_candidate = (rank, provider, credential, api_key, False)
            break
        if decrypted_candidate is None:
            continue
        rank, provider, credential, api_key, demo_mock_credential = decrypted_candidate
        static = _provider_config(provider.provider_key)
        metadata = {
            **static.metadata,
            "credential_source": "database",
            "credential_owner_type": credential.owner_type,
            "credential_owner_id": str(credential.owner_id) if credential.owner_id else None,
            "credential_scope_rank": rank,
            "api_key": api_key,
            "credential_decrypt_failed": demo_mock_credential,
            "mock_adapter": demo_mock_credential,
            "live_network_call": not demo_mock_credential,
        }
        providers[provider_key] = ProviderConfig(
            provider_key=provider.provider_key,
            name=provider.name,
            adapter_type=LLMAdapterType(provider.adapter_type),
            base_url=provider.base_url or static.base_url,
            region=provider.region,
            status=LLMProviderStatus.ACTIVE,
            capabilities=list(provider.config.get("capabilities") or static.capabilities),
            credential_configured=not demo_mock_credential,
            metadata=metadata,
        )
    return list(providers.values())


def _development_mock_allowed_for_provider(provider: LLMProvider) -> bool:
    return bool(
        is_development_environment() and provider.config.get("mock_allowed_in_development") is True
    )


def _credential_scope_rank(
    credential: LLMCredential,
    *,
    department_id: UUID | None,
    user_id: UUID | None,
) -> int | None:
    if credential.owner_type == "user":
        return 30 if credential.owner_id is not None and credential.owner_id == user_id else None
    if credential.owner_type == "department":
        return (
            20 if credential.owner_id is not None and credential.owner_id == department_id else None
        )
    if credential.owner_type == "tenant":
        return 10 if credential.owner_id is None else None
    return None


async def _runtime_deployments(
    session: AsyncSession,
    principal: Principal,
) -> list[DeploymentConfig]:
    result = await session.execute(
        select(LLMDeployment, LLMProvider, LLMModel)
        .join(LLMProvider, cast(ColumnElement[bool], LLMProvider.id == LLMDeployment.provider_id))
        .join(LLMModel, cast(ColumnElement[bool], LLMModel.id == LLMDeployment.model_id))
        .where(
            cast(ColumnElement[bool], LLMDeployment.tenant_id == principal.tenant_id),
            cast(Any, LLMDeployment.is_active).is_(True),
            cast(Any, LLMProvider.is_active).is_(True),
        )
        .order_by(cast(Any, LLMDeployment.priority))
    )
    deployments: list[DeploymentConfig] = []
    for deployment, provider, model in result.all():
        static = _provider_config(provider.provider_key)
        demo_mock = bool(
            is_development_environment()
            and provider.config.get("mock_allowed_in_development") is True
        )
        deployments.append(
            DeploymentConfig(
                id=deployment.id,
                provider_key=provider.provider_key,
                provider_name=provider.name,
                adapter_type=LLMAdapterType(provider.adapter_type),
                model_key=model.model_key,
                display_name=model.display_name,
                deployment_name=deployment.deployment_name,
                routing_key=deployment.routing_key,
                status=LLMDeploymentStatus.ACTIVE,
                context_window=model.context_window,
                capabilities=list(model.capabilities or static.capabilities),
                priority=deployment.priority,
                base_url=provider.base_url or static.base_url,
                config={
                    **deployment.config,
                    "mock": demo_mock,
                    "live_network_call": not demo_mock,
                },
            )
        )
    return deployments


async def _runtime_policy_rules(
    session: AsyncSession,
    principal: Principal,
) -> list[ModelPolicyRule]:
    result = await session.execute(
        select(LLMPolicy)
        .where(
            cast(ColumnElement[bool], LLMPolicy.tenant_id == principal.tenant_id),
            cast(Any, LLMPolicy.is_active).is_(True),
        )
        .order_by(cast(Any, LLMPolicy.priority))
    )
    return [
        ModelPolicyRule(
            id=policy.id,
            name=policy.name,
            scope_type=policy.scope_type,
            scope_id=policy.scope_id,
            effect=policy.effect,
            allowed_models=tuple(policy.allowed_models),
            allowed_routing_keys=tuple(policy.allowed_routing_keys),
            default_model_key=policy.default_model_key,
            default_routing_key=policy.default_routing_key,
            max_tokens=policy.max_tokens,
            priority=policy.priority,
            metadata=dict(policy.metadata_json or {}),
        )
        for policy in result.scalars().all()
    ]


def _policy_rules_matching_deployments(
    rules: list[ModelPolicyRule],
    deployments: list[DeploymentConfig],
) -> list[ModelPolicyRule]:
    active_deployments = [
        deployment for deployment in deployments if deployment.status == LLMDeploymentStatus.ACTIVE
    ]
    available_model_keys = {deployment.model_key for deployment in active_deployments}
    available_routing_keys = {deployment.routing_key for deployment in active_deployments}
    filtered: list[ModelPolicyRule] = []
    for rule in rules:
        allowed_models = tuple(
            model_key for model_key in rule.allowed_models if model_key in available_model_keys
        )
        allowed_routing_keys = tuple(
            routing_key
            for routing_key in rule.allowed_routing_keys
            if routing_key in available_routing_keys
        )
        default_model_key = (
            rule.default_model_key if rule.default_model_key in available_model_keys else None
        )
        default_routing_key = (
            rule.default_routing_key if rule.default_routing_key in available_routing_keys else None
        )

        if rule.effect == "deny":
            if (rule.allowed_models or rule.allowed_routing_keys) and not (
                allowed_models or allowed_routing_keys
            ):
                continue
            filtered.append(
                replace(
                    rule,
                    allowed_models=allowed_models,
                    allowed_routing_keys=allowed_routing_keys,
                    default_model_key=default_model_key,
                    default_routing_key=default_routing_key,
                )
            )
            continue

        if rule.effect == "allow" and not (
            allowed_models or allowed_routing_keys or default_model_key or default_routing_key
        ):
            continue
        filtered.append(
            replace(
                rule,
                allowed_models=allowed_models,
                allowed_routing_keys=allowed_routing_keys,
                default_model_key=default_model_key,
                default_routing_key=default_routing_key,
            )
        )
    return filtered


async def _runtime_pricing_rules(session: AsyncSession) -> list[PricingRule]:
    now = utc_now()
    result = await session.execute(
        select(LLMModel, LLMModelPrice)
        .join(LLMModelPrice, cast(ColumnElement[bool], LLMModelPrice.model_id == LLMModel.id))
        .where(
            cast(ColumnElement[bool], LLMModelPrice.currency == "USD"),
            cast(ColumnElement[bool], LLMModelPrice.effective_from <= now),
            (
                cast(Any, LLMModelPrice.effective_to).is_(None)
                | cast(ColumnElement[bool], cast(Any, LLMModelPrice.effective_to) > now)
            ),
        )
        .order_by(
            cast(Any, LLMModelPrice.effective_from).desc(),
            cast(Any, LLMModelPrice.created_at).desc(),
        )
    )
    rules_by_model: dict[str, PricingRule] = {}
    for model, price in result.all():
        if model.model_key in rules_by_model:
            continue
        rules_by_model[model.model_key] = PricingRule(
            pattern=model.model_key,
            input_per_1k=price.input_per_1k_tokens,
            output_per_1k=price.output_per_1k_tokens,
            source="database",
        )
    return list(rules_by_model.values())


def _policy_response(policy: LLMPolicy) -> LLMPolicyResponse:
    return LLMPolicyResponse(
        id=policy.id,
        tenant_id=policy.tenant_id,
        name=policy.name,
        description=policy.description,
        scope_type=LLMPolicyScope(policy.scope_type),
        scope_id=policy.scope_id,
        effect=LLMPolicyEffect(policy.effect),
        allowed_models=list(policy.allowed_models),
        allowed_routing_keys=list(policy.allowed_routing_keys),
        default_model_key=policy.default_model_key,
        default_routing_key=policy.default_routing_key,
        max_tokens=policy.max_tokens,
        priority=policy.priority,
        status=LLMPolicyStatus.ACTIVE if policy.is_active else LLMPolicyStatus.INACTIVE,
        metadata=policy.metadata_json,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


def _price_response(price: LLMModelPrice, model: LLMModel) -> LLMModelPriceResponse:
    return LLMModelPriceResponse(
        id=price.id,
        model_id=model.id,
        provider_key=model.provider_key,
        model_key=model.model_key,
        display_name=model.display_name,
        currency=price.currency,
        input_per_1k_tokens=price.input_per_1k_tokens,
        output_per_1k_tokens=price.output_per_1k_tokens,
        effective_from=price.effective_from,
        effective_to=price.effective_to,
    )


def _normalize_and_validate_policy_payload(payload: LLMPolicyUpsertRequest) -> None:
    policy_validation.normalize_and_validate_policy_payload(payload)


def _validate_policy_scope(payload: LLMPolicyUpsertRequest) -> None:
    policy_validation.validate_policy_scope(payload)


async def _validate_policy_scope_target(
    session: AsyncSession,
    payload: LLMPolicyUpsertRequest,
    principal: Principal,
) -> None:
    if payload.scope_type == LLMPolicyScope.TENANT:
        return
    if payload.scope_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="scope_id is required for non-tenant model policies.",
        )

    model = _policy_scope_model(payload.scope_type)
    conditions: list[ColumnElement[bool]] = [
        cast(ColumnElement[bool], model.id == payload.scope_id),
        cast(ColumnElement[bool], model.tenant_id == principal.tenant_id),
    ]
    if model is User:
        conditions.append(cast(Any, User.deleted_at).is_(None))
    result = await session.execute(select(model.id).where(*conditions))
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model policy {payload.scope_type.value} scope target was not found in this tenant.",
        )


async def _validate_policy_runtime_targets(
    session: AsyncSession,
    payload: LLMPolicyUpsertRequest,
    principal: Principal,
) -> None:
    model_keys = set(payload.allowed_models)
    if payload.default_model_key:
        model_keys.add(payload.default_model_key)
    routing_keys = set(payload.allowed_routing_keys)
    if payload.default_routing_key:
        routing_keys.add(payload.default_routing_key)
    if not model_keys and not routing_keys:
        return

    target_filters: list[Any] = []
    if model_keys:
        target_filters.append(cast(Any, LLMModel.model_key).in_(model_keys))
    if routing_keys:
        target_filters.append(cast(Any, LLMDeployment.routing_key).in_(routing_keys))

    result = await session.execute(
        select(LLMDeployment, LLMProvider, LLMModel)
        .join(LLMProvider, cast(ColumnElement[bool], LLMProvider.id == LLMDeployment.provider_id))
        .join(LLMModel, cast(ColumnElement[bool], LLMModel.id == LLMDeployment.model_id))
        .where(
            cast(ColumnElement[bool], LLMDeployment.tenant_id == principal.tenant_id),
            cast(Any, LLMDeployment.is_active).is_(True),
            cast(Any, LLMProvider.is_active).is_(True),
            or_(*target_filters),
        )
    )
    active_model_contexts: dict[str, int | None] = {}
    active_routing_keys: set[str] = set()
    for deployment, _provider, model in result.all():
        active_model_contexts[model.model_key] = model.context_window
        active_routing_keys.add(deployment.routing_key)

    missing_models = sorted(model_keys - set(active_model_contexts))
    if missing_models:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Model policy references inactive or missing model_key: {', '.join(missing_models)}.",
        )

    missing_routes = sorted(routing_keys - active_routing_keys)
    if missing_routes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Model policy references inactive or missing routing_key: {', '.join(missing_routes)}.",
        )

    if payload.max_tokens is not None:
        context_windows = [
            window for window in active_model_contexts.values() if window is not None
        ]
        if context_windows and payload.max_tokens > min(context_windows):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "max_tokens cannot exceed the smallest context window of the "
                    f"referenced active models ({min(context_windows)})."
                ),
            )


def _policy_scope_model(scope_type: LLMPolicyScope) -> Any:
    return {
        LLMPolicyScope.DEPARTMENT: Department,
        LLMPolicyScope.COST_CENTER: CostCenter,
        LLMPolicyScope.USER: User,
        LLMPolicyScope.AGENT: AgentInstance,
        LLMPolicyScope.CHANNEL: ChannelConfig,
    }[scope_type]


async def _validate_credential_owner_scope(
    session: AsyncSession,
    payload: LLMCredentialUpsertRequest,
    principal: Principal,
) -> None:
    if payload.owner_type == "tenant":
        return
    if payload.owner_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="owner_id is required for department or user credentials.",
        )
    if payload.owner_type == "department":
        result = await session.execute(
            select(Department.id).where(
                Department.id == payload.owner_id,
                Department.tenant_id == principal.tenant_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credential owner department was not found in this tenant.",
            )
        return
    if payload.owner_type == "user":
        result = await session.execute(
            select(User.id).where(
                cast(ColumnElement[bool], User.id == payload.owner_id),
                cast(ColumnElement[bool], User.tenant_id == principal.tenant_id),
                cast(Any, User.deleted_at).is_(None),
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credential owner user was not found in this tenant.",
            )


def _dedupe_text_list(values: list[str]) -> list[str]:
    return policy_validation.dedupe_text_list(values)


def _normalize_policy_key_list(values: list[str], *, field_name: str) -> list[str]:
    return policy_validation.normalize_policy_key_list(values, field_name=field_name)


def _normalize_policy_key(value: str | None, *, field_name: str, required: bool) -> str | None:
    return policy_validation.normalize_policy_key(value, field_name=field_name, required=required)


def _default_model_key(provider_key: str) -> str:
    return catalog_helpers.default_model_key(provider_key, _DEPLOYMENTS)


def _default_routing_key(provider_key: str) -> str:
    return catalog_helpers.default_provider_routing_key(provider_key)


def _context_window_for(model_key: str) -> int | None:
    return catalog_helpers.context_window_for(model_key, _DEPLOYMENTS)


def _model_type_for_capabilities(capabilities: list[str]) -> str:
    return catalog_helpers.model_type_for_capabilities(capabilities)
