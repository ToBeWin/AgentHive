from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.agent_module import AgentModule, TenantAgentModule
from app.schemas.agent_modules import (
    AgentModuleActionResponse,
    AgentModuleCatalogEntry,
    AgentModuleDetailResponse,
    AgentModuleListResponse,
)
from app.schemas.license import AgentModuleState, LicenseStatus
from app.schemas.license import LicenseStatusResponse
from app.services.agent_instance_reconcile_service import (
    reconcile_agent_instances_for_license_status,
)
from app.services.audit_service import record_audit_event
from app.services.license_service import (
    get_allowed_module_ids,
    get_license_status_for_tenant,
    get_license_status_value,
)


@dataclass(frozen=True)
class AgentModuleDefinition:
    id: str
    name: str
    scenario: str
    priority: str
    description: str
    version: str
    category: str
    capabilities: list[str]
    default_agent_slug: str
    required_features: list[str]
    dependencies: list[str]
    recommended_model_capabilities: list[str] | None = None
    recommended_orchestration_runtimes: list[str] | None = None
    default_config: dict[str, object] | None = None


LANGCHAIN_RUNTIME = "langchain"
LANGGRAPH_RUNTIME = "langgraph"
MEDIA_GATEWAY_RUNTIME = "media_gateway"


_MODULE_DEFINITIONS = [
    AgentModuleDefinition(
        id="agent.customer_service",
        name="电商客服助手",
        scenario="客服辅助回答，知识库检索",
        priority="P0",
        description="面向电商售前售后场景的知识库问答与话术辅助 Agent。",
        version="0.1.0",
        category="customer_success",
        capabilities=["knowledge_retrieval", "reply_drafting", "source_citation"],
        default_agent_slug="customer-service",
        required_features=["feature.agent_catalog"],
        dependencies=[],
        recommended_orchestration_runtimes=[LANGGRAPH_RUNTIME],
    ),
    AgentModuleDefinition(
        id="agent.hr_screening",
        name="HR简历筛选助手",
        scenario="简历解析，岗位匹配评分",
        priority="P0",
        description="根据岗位要求解析简历并生成结构化匹配建议。",
        version="0.1.0",
        category="hr",
        capabilities=["resume_parse", "candidate_scoring", "screening_summary"],
        default_agent_slug="hr-screening",
        required_features=["feature.agent_catalog"],
        dependencies=[],
        recommended_orchestration_runtimes=[LANGCHAIN_RUNTIME],
    ),
    AgentModuleDefinition(
        id="agent.copywriting",
        name="文案创作助手",
        scenario="小红书/抖音/朋友圈文案生成",
        priority="P0",
        description="按渠道、受众和商品卖点生成营销文案初稿。",
        version="0.1.0",
        category="marketing",
        capabilities=["copy_generation", "tone_variants", "platform_adaptation"],
        default_agent_slug="copywriting",
        required_features=["feature.agent_catalog"],
        dependencies=[],
        recommended_orchestration_runtimes=[LANGCHAIN_RUNTIME],
    ),
    AgentModuleDefinition(
        id="agent.image_generation",
        name="商品图片生成助手",
        scenario="商品图、营销海报、参考图重绘和多图变体生成",
        priority="P0",
        description="面向电商素材生产的图片生成 Agent，支持手写提示词、参考图和自然语言需求转译。",
        version="0.1.0",
        category="creative",
        capabilities=[
            "prompt_to_image",
            "reference_image",
            "image_variants",
            "product_visual",
            "brand_style_control",
        ],
        default_agent_slug="image-generation",
        required_features=[
            "feature.agent_catalog",
            "feature.media_generation",
            "feature.model_budget",
        ],
        dependencies=[],
        recommended_model_capabilities=["image_generation", "vision_input", "reference_image"],
        recommended_orchestration_runtimes=[
            MEDIA_GATEWAY_RUNTIME,
            LANGCHAIN_RUNTIME,
        ],
        default_config={
            "generation_kind": "image",
            "routing_keys": ["image-generation"],
            "supported_models": [
                "openai/gpt-image-2",
                "google/nano-banana",
                "openai-compatible-image",
            ],
            "storage": {"driver": "minio", "bucket_scope": "tenant"},
        },
    ),
    AgentModuleDefinition(
        id="agent.video_generation",
        name="短视频生成助手",
        scenario="商品短视频、参考视频续创、素材拆解和视频生成",
        priority="P0",
        description="面向电商短视频生产的生成 Agent，支持提示词、参考图、参考视频、素材拆解和异步生成任务。",
        version="0.1.0",
        category="creative",
        capabilities=[
            "prompt_to_video",
            "reference_image_to_video",
            "reference_video",
            "material_breakdown",
            "duration_fps_resolution_control",
        ],
        default_agent_slug="video-generation",
        required_features=[
            "feature.agent_catalog",
            "feature.media_generation",
            "feature.model_budget",
        ],
        dependencies=[],
        recommended_model_capabilities=[
            "video_generation",
            "image_input",
            "video_input",
            "async_job",
        ],
        recommended_orchestration_runtimes=[
            MEDIA_GATEWAY_RUNTIME,
            LANGGRAPH_RUNTIME,
        ],
        default_config={
            "generation_kind": "video",
            "routing_keys": ["video-generation"],
            "supported_models": ["volcengine/seedance-2.0", "openai-compatible-video"],
            "storage": {"driver": "minio", "bucket_scope": "tenant"},
            "default_video": {"duration_seconds": 5, "fps": 24, "resolution": "1080p"},
        },
    ),
    AgentModuleDefinition(
        id="agent.content_analysis",
        name="爆款内容拆解助手",
        scenario="视频/文章爆款要素分析",
        priority="P1",
        description="分析热门内容结构、钩子、节奏和可复用表达模式。",
        version="0.1.0",
        category="marketing",
        capabilities=["content_breakdown", "hook_analysis", "rewrite_brief"],
        default_agent_slug="content-analysis",
        required_features=["feature.agent_catalog"],
        dependencies=["agent.copywriting"],
        recommended_orchestration_runtimes=[LANGGRAPH_RUNTIME],
    ),
    AgentModuleDefinition(
        id="agent.report_writer",
        name="项目汇报助手",
        scenario="工作汇报/周报/月报生成",
        priority="P1",
        description="将项目材料整理为清晰的周报、月报和管理层汇报。",
        version="0.1.0",
        category="operations",
        capabilities=["report_outline", "progress_summary", "risk_summary"],
        default_agent_slug="report-writer",
        required_features=["feature.agent_catalog"],
        dependencies=[],
        recommended_orchestration_runtimes=[LANGCHAIN_RUNTIME],
    ),
    AgentModuleDefinition(
        id="agent.product_design",
        name="新品设计辅助",
        scenario="产品创意、卖点提炼",
        priority="P1",
        description="辅助沉淀新品创意、差异化卖点和上架素材方向。",
        version="0.1.0",
        category="product",
        capabilities=["idea_generation", "selling_point_extraction", "persona_fit"],
        default_agent_slug="product-design",
        required_features=["feature.agent_catalog"],
        dependencies=[],
        recommended_orchestration_runtimes=[LANGCHAIN_RUNTIME],
    ),
    AgentModuleDefinition(
        id="agent.finance",
        name="财务效率助手",
        scenario="财务问答、报表解读",
        priority="P2",
        description="辅助解释财务指标、报表口径和常见财务流程问题。",
        version="0.1.0",
        category="finance",
        capabilities=["finance_qa", "statement_interpretation", "policy_lookup"],
        default_agent_slug="finance",
        required_features=["feature.agent_catalog", "feature.model_budget"],
        dependencies=["agent.report_writer"],
        recommended_orchestration_runtimes=[LANGCHAIN_RUNTIME],
    ),
    AgentModuleDefinition(
        id="agent.store_operations",
        name="店铺运营助手",
        scenario="产品描述优化、运营建议",
        priority="P2",
        description="辅助优化商品标题、描述、活动方案和运营动作。",
        version="0.1.0",
        category="ecommerce",
        capabilities=["listing_optimization", "campaign_ideas", "operation_suggestions"],
        default_agent_slug="store-operations",
        required_features=["feature.agent_catalog"],
        dependencies=["agent.customer_service"],
        recommended_orchestration_runtimes=[LANGGRAPH_RUNTIME],
    ),
    AgentModuleDefinition(
        id="agent.custom_builder",
        name="低代码 Agent 配置",
        scenario="企业管理员通过 JSON 配置自定义岗位 Agent",
        priority="P1",
        description="低代码 Agent Builder：通过配置 system_prompt / 模型 / 知识库 / MCP 工具生成专属 Agent。",
        version="0.1.0",
        category="custom",
        capabilities=["low_code_config", "custom_persona", "knowledge_retrieval", "tool_calling"],
        default_agent_slug="custom-builder",
        required_features=["feature.agent_catalog", "feature.model_budget"],
        dependencies=[],
        recommended_orchestration_runtimes=[LANGCHAIN_RUNTIME],
    ),
    AgentModuleDefinition(
        id="agent.data_analyst",
        name="数据分析助手",
        scenario="经营数据问答、趋势分析",
        priority="P2",
        description="围绕经营数据进行问答、趋势归因和指标解释。",
        version="0.1.0",
        category="analytics",
        capabilities=["metric_qa", "trend_analysis", "insight_summary"],
        default_agent_slug="data-analyst",
        required_features=["feature.agent_catalog", "feature.model_budget"],
        dependencies=["agent.report_writer"],
        recommended_orchestration_runtimes=[LANGGRAPH_RUNTIME],
    ),
]

_module_states: dict[str, AgentModuleState] = {
    "agent.customer_service": AgentModuleState.ENABLED,
    "agent.hr_screening": AgentModuleState.INSTALLED,
    "agent.copywriting": AgentModuleState.DISABLED,
}


def list_module_definitions() -> list[AgentModuleDefinition]:
    return list(_MODULE_DEFINITIONS)


def get_module_definition(module_id: str) -> AgentModuleDefinition:
    for definition in _MODULE_DEFINITIONS:
        if definition.id == module_id:
            return definition
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Agent module not found.",
    )


def list_agent_modules() -> AgentModuleListResponse:
    return AgentModuleListResponse(
        modules=[_to_catalog_entry(definition) for definition in _MODULE_DEFINITIONS]
    )


def get_agent_module(module_id: str) -> AgentModuleDetailResponse:
    definition = _get_definition(module_id)
    catalog_entry = _to_catalog_entry(definition)
    return AgentModuleDetailResponse(
        **catalog_entry.model_dump(),
        category=definition.category,
        capabilities=list(definition.capabilities),
        default_agent_slug=definition.default_agent_slug,
        recommended_model_capabilities=list(definition.recommended_model_capabilities or []),
        recommended_orchestration_runtimes=list(
            definition.recommended_orchestration_runtimes or []
        ),
        default_config=dict(definition.default_config or {}),
    )


async def list_agent_modules_for_tenant(
    session: AsyncSession,
    *,
    tenant_id: UUID,
) -> AgentModuleListResponse:
    modules = await _load_module_rows(session)
    if not modules:
        return AgentModuleListResponse(
            modules=[
                _definition_to_catalog_entry(definition, AgentModuleState.NOT_LICENSED)
                for definition in _MODULE_DEFINITIONS
            ]
        )

    tenant_states = await _load_tenant_module_states(session, tenant_id)
    license_status = await get_license_status_for_tenant(session, tenant_id=tenant_id)
    module_by_key = {module.module_key: module for module in modules}
    return AgentModuleListResponse(
        modules=[
            _row_to_catalog_entry(
                module,
                _effective_db_state(module, tenant_states, license_status),
                license_status,
                tenant_states=tenant_states,
                module_by_key=module_by_key,
            )
            for module in modules
        ]
    )


async def get_agent_module_for_tenant(
    session: AsyncSession,
    module_id: str,
    *,
    tenant_id: UUID,
) -> AgentModuleDetailResponse:
    module = await _get_module_row(session, module_id)
    tenant_states = await _load_tenant_module_states(session, tenant_id)
    license_status = await get_license_status_for_tenant(session, tenant_id=tenant_id)
    state = _effective_db_state(module, tenant_states, license_status)
    dependency_rows = await _load_modules_by_keys(session, _module_dependencies(module))
    module_by_key = {module.module_key: module, **dependency_rows}
    catalog_entry = _row_to_catalog_entry(
        module,
        state,
        license_status,
        tenant_states=tenant_states,
        module_by_key=module_by_key,
    )
    manifest = module.manifest
    return AgentModuleDetailResponse(
        **catalog_entry.model_dump(),
        category=module.category,
        capabilities=list(manifest.get("capabilities", [])),
        default_agent_slug=str(manifest.get("default_agent_slug", module.module_key)),
        recommended_model_capabilities=[
            str(capability) for capability in manifest.get("recommended_model_capabilities", [])
        ],
        recommended_orchestration_runtimes=[
            str(runtime) for runtime in manifest.get("recommended_orchestration_runtimes", [])
        ],
        default_config=dict(manifest.get("default_config", {})),
    )


async def install_agent_module_for_tenant(
    session: AsyncSession,
    module_id: str,
    *,
    tenant_id: UUID,
    actor_id: UUID | None,
    request_id: str | None = None,
) -> AgentModuleActionResponse:
    action = "agent_module.install"
    module: AgentModule | None = None
    try:
        module = await _get_module_row(session, module_id)
        await _ensure_db_module_licensed(session, tenant_id, module)
        await _ensure_db_module_dependencies(
            session,
            tenant_id=tenant_id,
            module=module,
            require_enabled=False,
        )
        tenant_module = await _get_or_create_tenant_module(session, tenant_id, module.id)
        now = datetime.now(timezone.utc)
        previous_state = tenant_module.state
        if tenant_module.state in {
            AgentModuleState.INSTALLED.value,
            AgentModuleState.ENABLED.value,
            AgentModuleState.DISABLED.value,
        }:
            message = "Agent module is already installed."
        else:
            tenant_module.state = AgentModuleState.INSTALLED.value
            tenant_module.installed_by = actor_id
            tenant_module.installed_at = now
            message = "Agent module installed."
        tenant_module.updated_at = now
        await _record_module_audit(
            session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            request_id=request_id,
            module=module,
            action=action,
            previous_state=previous_state,
            next_state=tenant_module.state,
            message=message,
        )
        await session.commit()
        return AgentModuleActionResponse(
            module_id=module.module_key,
            state=AgentModuleState(tenant_module.state),
            message=message,
        )
    except HTTPException as exc:
        await _record_module_failure_audit(
            session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            request_id=request_id,
            requested_module_id=module_id,
            module=module,
            action=action,
            exc=exc,
        )
        raise


async def enable_agent_module_for_tenant(
    session: AsyncSession,
    module_id: str,
    *,
    tenant_id: UUID,
    actor_id: UUID | None,
    request_id: str | None = None,
) -> AgentModuleActionResponse:
    action = "agent_module.enable"
    module: AgentModule | None = None
    try:
        module = await _get_module_row(session, module_id)
        await _ensure_db_module_licensed(session, tenant_id, module)
        await _ensure_db_module_dependencies(
            session,
            tenant_id=tenant_id,
            module=module,
            require_enabled=True,
        )
        tenant_module = await _get_or_create_tenant_module(session, tenant_id, module.id)
        now = datetime.now(timezone.utc)
        previous_state = tenant_module.state
        if tenant_module.installed_at is None:
            tenant_module.installed_by = actor_id
            tenant_module.installed_at = now
        tenant_module.state = AgentModuleState.ENABLED.value
        tenant_module.enabled_at = now
        tenant_module.disabled_at = None
        tenant_module.updated_at = now
        await _record_module_audit(
            session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            request_id=request_id,
            module=module,
            action=action,
            previous_state=previous_state,
            next_state=tenant_module.state,
            message="Agent module enabled.",
        )
        await session.commit()
        return AgentModuleActionResponse(
            module_id=module.module_key,
            state=AgentModuleState.ENABLED,
            message="Agent module enabled.",
        )
    except HTTPException as exc:
        await _record_module_failure_audit(
            session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            request_id=request_id,
            requested_module_id=module_id,
            module=module,
            action=action,
            exc=exc,
        )
        raise


async def disable_agent_module_for_tenant(
    session: AsyncSession,
    module_id: str,
    *,
    tenant_id: UUID,
    actor_id: UUID | None,
    request_id: str | None = None,
) -> AgentModuleActionResponse:
    action = "agent_module.disable"
    module: AgentModule | None = None
    try:
        module = await _get_module_row(session, module_id)
        await _ensure_db_module_licensed(session, tenant_id, module)
        license_status = await get_license_status_for_tenant(session, tenant_id=tenant_id)
        tenant_module = await _get_or_create_tenant_module(session, tenant_id, module.id)
        now = datetime.now(timezone.utc)
        previous_state = tenant_module.state
        if tenant_module.installed_at is None:
            tenant_module.installed_by = actor_id
            tenant_module.installed_at = now
        tenant_module.state = AgentModuleState.DISABLED.value
        tenant_module.disabled_at = now
        tenant_module.updated_at = now
        disabled_instance_count = await reconcile_agent_instances_for_license_status(
            session,
            tenant_id=tenant_id,
            license_status=license_status,
            actor_id=actor_id,
            request_id=request_id,
            reason="agent_module_disabled",
            module_keys=[module.module_key],
        )
        await _record_module_audit(
            session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            request_id=request_id,
            module=module,
            action=action,
            previous_state=previous_state,
            next_state=tenant_module.state,
            message="Agent module disabled.",
            extra_details={"disabled_agent_instance_count": disabled_instance_count},
        )
        await session.commit()
        return AgentModuleActionResponse(
            module_id=module.module_key,
            state=AgentModuleState.DISABLED,
            message="Agent module disabled.",
        )
    except HTTPException as exc:
        await _record_module_failure_audit(
            session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            request_id=request_id,
            requested_module_id=module_id,
            module=module,
            action=action,
            exc=exc,
        )
        raise


async def ensure_agent_module_runnable_for_tenant(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    module_key: str,
    usage_label: str = "this Agent capability",
) -> AgentModule:
    module = await _get_module_row(session, module_key)
    await _ensure_db_module_licensed(session, tenant_id, module)
    tenant_states = await _load_tenant_module_states(session, tenant_id)
    tenant_module = tenant_states.get(module.id)
    if tenant_module is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Install and enable {module_key} before using {usage_label}.",
        )
    module_state = AgentModuleState(tenant_module.state)
    if module_state != AgentModuleState.ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Enable {module_key} before using {usage_label}.",
        )
    return module


def install_agent_module(module_id: str) -> AgentModuleActionResponse:
    _ensure_module_licensed(module_id)
    _ensure_module_dependencies(module_id, require_enabled=False)
    current_state = _module_states.get(module_id, AgentModuleState.NOT_INSTALLED)

    if current_state in {AgentModuleState.ENABLED, AgentModuleState.DISABLED}:
        message = "Agent module is already installed."
    else:
        _module_states[module_id] = AgentModuleState.INSTALLED
        message = "Agent module installed."

    return AgentModuleActionResponse(
        module_id=module_id,
        state=_module_states.get(module_id, current_state),
        message=message,
    )


def enable_agent_module(module_id: str) -> AgentModuleActionResponse:
    _ensure_module_licensed(module_id)
    _ensure_module_dependencies(module_id, require_enabled=True)
    current_state = _module_states.get(module_id, AgentModuleState.NOT_INSTALLED)
    if current_state == AgentModuleState.NOT_INSTALLED:
        _module_states[module_id] = AgentModuleState.INSTALLED
    _module_states[module_id] = AgentModuleState.ENABLED
    return AgentModuleActionResponse(
        module_id=module_id,
        state=AgentModuleState.ENABLED,
        message="Agent module enabled.",
    )


def disable_agent_module(module_id: str) -> AgentModuleActionResponse:
    _ensure_module_licensed(module_id)
    current_state = _module_states.get(module_id, AgentModuleState.NOT_INSTALLED)
    if current_state == AgentModuleState.NOT_INSTALLED:
        _module_states[module_id] = AgentModuleState.INSTALLED
        message = "Agent module installed and left disabled."
    else:
        _module_states[module_id] = AgentModuleState.DISABLED
        message = "Agent module disabled."

    return AgentModuleActionResponse(
        module_id=module_id,
        state=_module_states[module_id],
        message=message,
    )


def _to_catalog_entry(definition: AgentModuleDefinition) -> AgentModuleCatalogEntry:
    state = _effective_state(definition.id)
    return AgentModuleCatalogEntry(
        id=definition.id,
        name=definition.name,
        scenario=definition.scenario,
        priority=definition.priority,
        description=definition.description,
        version=definition.version,
        state=state,
        licensed=state != AgentModuleState.NOT_LICENSED,
        installed=state
        in {
            AgentModuleState.INSTALLED,
            AgentModuleState.ENABLED,
            AgentModuleState.DISABLED,
        },
        enabled=state == AgentModuleState.ENABLED,
        required_features=list(definition.required_features),
        missing_features=[],
        dependencies=list(definition.dependencies),
        missing_dependencies=_missing_module_dependencies(
            definition.dependencies,
            _module_states,
            require_enabled=False,
        ),
    )


def _effective_state(module_id: str) -> AgentModuleState:
    license_status = get_license_status_value()
    if module_id not in get_allowed_module_ids():
        return AgentModuleState.NOT_LICENSED
    if license_status == LicenseStatus.EXPIRED:
        return AgentModuleState.EXPIRED
    if license_status != LicenseStatus.ACTIVE:
        return AgentModuleState.NOT_LICENSED
    return _module_states.get(module_id, AgentModuleState.NOT_INSTALLED)


def _ensure_module_licensed(module_id: str) -> None:
    _get_definition(module_id)
    state = _effective_state(module_id)
    if state == AgentModuleState.NOT_LICENSED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent module is not licensed for this deployment.",
        )
    if state == AgentModuleState.EXPIRED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent module license is expired.",
        )


def _ensure_module_dependencies(module_id: str, *, require_enabled: bool) -> None:
    definition = _get_definition(module_id)
    missing_dependencies = _missing_module_dependencies(
        definition.dependencies,
        _module_states,
        require_enabled=require_enabled,
    )
    if missing_dependencies:
        action = "enabled" if require_enabled else "installed"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Agent module requires {action} dependencies: {', '.join(missing_dependencies)}."
            ),
        )


def _get_definition(module_id: str) -> AgentModuleDefinition:
    return get_module_definition(module_id)


async def _load_module_rows(session: AsyncSession) -> list[AgentModule]:
    result = await session.execute(
        select(AgentModule)
        .where(cast(Any, AgentModule.is_active).is_(True))
        .order_by(AgentModule.priority, AgentModule.module_key)
    )
    return list(result.scalars().all())


async def _get_module_row(session: AsyncSession, module_key: str) -> AgentModule:
    result = await session.execute(
        select(AgentModule).where(
            cast(ColumnElement[bool], AgentModule.module_key == module_key),
            cast(Any, AgentModule.is_active).is_(True),
        )
    )
    module = result.scalar_one_or_none()
    if module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent module not found.",
        )
    return module


async def _load_modules_by_keys(
    session: AsyncSession,
    module_keys: list[str],
) -> dict[str, AgentModule]:
    if not module_keys:
        return {}
    result = await session.execute(
        select(AgentModule).where(
            cast(Any, AgentModule.module_key).in_(module_keys),
            cast(Any, AgentModule.is_active).is_(True),
        )
    )
    return {module.module_key: module for module in result.scalars().all()}


async def _load_tenant_module_states(
    session: AsyncSession,
    tenant_id: UUID,
) -> dict[UUID, TenantAgentModule]:
    result = await session.execute(
        select(TenantAgentModule).where(TenantAgentModule.tenant_id == tenant_id)
    )
    return {row.module_id: row for row in result.scalars().all()}


async def _get_or_create_tenant_module(
    session: AsyncSession,
    tenant_id: UUID,
    module_id: UUID,
) -> TenantAgentModule:
    result = await session.execute(
        select(TenantAgentModule).where(
            TenantAgentModule.tenant_id == tenant_id,
            TenantAgentModule.module_id == module_id,
        )
    )
    tenant_module = result.scalar_one_or_none()
    if tenant_module is not None:
        return tenant_module

    tenant_module = TenantAgentModule(
        tenant_id=tenant_id,
        module_id=module_id,
        state=AgentModuleState.NOT_INSTALLED.value,
    )
    session.add(tenant_module)
    await session.flush()
    return tenant_module


async def _ensure_db_module_licensed(
    session: AsyncSession,
    tenant_id: UUID,
    module: AgentModule,
) -> None:
    license_status = await get_license_status_for_tenant(session, tenant_id=tenant_id)
    _ensure_license_allows_module(
        module.module_key,
        _module_required_features(module),
        license_status,
    )


async def _ensure_db_module_dependencies(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    module: AgentModule,
    require_enabled: bool,
) -> None:
    dependencies = _module_dependencies(module)
    if not dependencies:
        return
    dependency_rows = await _load_modules_by_keys(session, dependencies)
    tenant_states = await _load_tenant_module_states(session, tenant_id)
    dependency_states = _dependency_states_by_key(tenant_states, dependency_rows)
    missing_dependencies = _missing_module_dependencies(
        dependencies,
        dependency_states,
        require_enabled=require_enabled,
    )
    if missing_dependencies:
        action = "enabled" if require_enabled else "installed"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Agent module requires {action} dependencies: {', '.join(missing_dependencies)}."
            ),
        )


def _effective_db_state(
    module: AgentModule,
    tenant_states: dict[UUID, TenantAgentModule],
    license_status: LicenseStatusResponse,
) -> AgentModuleState:
    licensed_modules = set(license_status.allowed_modules)
    if license_status.status == LicenseStatus.EXPIRED and module.module_key in licensed_modules:
        return AgentModuleState.EXPIRED
    if license_status.status != LicenseStatus.ACTIVE or module.module_key not in licensed_modules:
        return AgentModuleState.NOT_LICENSED
    tenant_module = tenant_states.get(module.id)
    if tenant_module is None:
        return AgentModuleState.NOT_INSTALLED
    return AgentModuleState(tenant_module.state)


def _row_to_catalog_entry(
    module: AgentModule,
    state: AgentModuleState,
    license_status: LicenseStatusResponse,
    *,
    tenant_states: dict[UUID, TenantAgentModule] | None = None,
    module_by_key: dict[str, AgentModule] | None = None,
) -> AgentModuleCatalogEntry:
    manifest = module.manifest
    required_features = _module_required_features(module)
    missing_features = _missing_required_features(required_features, license_status)
    dependencies = _module_dependencies(module)
    dependency_states = _dependency_states_by_key(
        tenant_states or {},
        module_by_key or {},
    )
    missing_dependencies = _missing_module_dependencies(
        dependencies,
        dependency_states,
        require_enabled=False,
    )
    licensed = (
        license_status.status in {LicenseStatus.ACTIVE, LicenseStatus.EXPIRED}
        and module.module_key in license_status.allowed_modules
    )
    return AgentModuleCatalogEntry(
        id=module.module_key,
        name=module.name,
        scenario=str(manifest.get("scenario", "")),
        priority=module.priority,
        description=module.description or "",
        version=module.version,
        state=state,
        licensed=licensed,
        installed=state
        in {
            AgentModuleState.INSTALLED,
            AgentModuleState.ENABLED,
            AgentModuleState.DISABLED,
        },
        enabled=state == AgentModuleState.ENABLED,
        required_features=required_features,
        missing_features=missing_features,
        dependencies=dependencies,
        missing_dependencies=missing_dependencies,
    )


def _definition_to_catalog_entry(
    definition: AgentModuleDefinition,
    state: AgentModuleState,
) -> AgentModuleCatalogEntry:
    return AgentModuleCatalogEntry(
        id=definition.id,
        name=definition.name,
        scenario=definition.scenario,
        priority=definition.priority,
        description=definition.description,
        version=definition.version,
        state=state,
        licensed=state != AgentModuleState.NOT_LICENSED,
        installed=False,
        enabled=False,
        required_features=list(definition.required_features),
        missing_features=list(definition.required_features),
        dependencies=list(definition.dependencies),
        missing_dependencies=list(definition.dependencies),
    )


def _ensure_license_allows_module(
    module_key: str,
    required_features: list[str],
    license_status: LicenseStatusResponse,
) -> None:
    if license_status.status == LicenseStatus.EXPIRED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent module license is expired.",
        )
    if license_status.status != LicenseStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active AgentHive license is required to manage Agent modules.",
        )
    if module_key not in license_status.allowed_modules:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent module is not licensed for this deployment.",
        )
    missing_features = _missing_required_features(required_features, license_status)
    if missing_features:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Agent module requires license features: {', '.join(missing_features)}.",
        )


def _missing_required_features(
    required_features: list[str],
    license_status: LicenseStatusResponse,
) -> list[str]:
    allowed_features = set(license_status.allowed_features)
    return [feature for feature in required_features if feature not in allowed_features]


def _missing_module_dependencies(
    dependencies: list[str],
    dependency_states: Mapping[str, AgentModuleState | str],
    *,
    require_enabled: bool,
) -> list[str]:
    allowed_states = {AgentModuleState.ENABLED}
    if not require_enabled:
        allowed_states.update(
            {
                AgentModuleState.INSTALLED,
                AgentModuleState.DISABLED,
            }
        )
    missing = []
    for dependency in dependencies:
        raw_state = dependency_states.get(dependency)
        state = AgentModuleState(raw_state) if isinstance(raw_state, str) else raw_state
        if state not in allowed_states:
            missing.append(dependency)
    return missing


def _module_required_features(module: AgentModule) -> list[str]:
    return [str(feature) for feature in module.manifest.get("required_features", [])]


def _module_dependencies(module: AgentModule) -> list[str]:
    return [str(dependency) for dependency in module.manifest.get("dependencies", [])]


def _dependency_states_by_key(
    tenant_states: dict[UUID, TenantAgentModule],
    module_by_key: dict[str, AgentModule],
) -> dict[str, AgentModuleState]:
    states: dict[str, AgentModuleState] = {}
    for module_key, module in module_by_key.items():
        tenant_module = tenant_states.get(module.id)
        if tenant_module is None:
            continue
        states[module_key] = AgentModuleState(tenant_module.state)
    return states


async def _record_module_audit(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    actor_id: UUID | None,
    request_id: str | None,
    module: AgentModule,
    action: str,
    previous_state: str | None = None,
    next_state: str | None = None,
    message: str | None = None,
    extra_details: dict[str, int | str | None] | None = None,
) -> None:
    details: dict[str, int | str | None] = {
        "module_key": module.module_key,
        "previous_state": previous_state,
        "next_state": next_state,
    }
    if message is not None:
        details["message"] = message
    if extra_details:
        details.update(extra_details)
    await record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        request_id=request_id,
        action=action,
        resource_type="agent_module",
        resource_id=module.id,
        details=details,
    )


async def _record_module_failure_audit(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    actor_id: UUID | None,
    request_id: str | None,
    requested_module_id: str,
    module: AgentModule | None,
    action: str,
    exc: HTTPException,
) -> None:
    try:
        await session.rollback()
        await record_audit_event(
            session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            request_id=request_id,
            action=action,
            status="failure",
            resource_type="agent_module",
            resource_id=module.id if module else None,
            details={
                "module_key": module.module_key if module else requested_module_id,
                "requested_module_id": requested_module_id,
                "reason": str(exc.detail),
                "status_code": exc.status_code,
            },
        )
        await session.commit()
    except Exception:
        await session.rollback()
