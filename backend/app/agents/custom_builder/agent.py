"""ConfigurableAgent — runtime for low-code Builder agents.

Reads ``builder_config`` from the run context (placed there by
``_apply_agent_instance_defaults`` from the AgentInstance.config column),
renders it via the Builder renderer, and delegates the LLM call to the
shared gateway. Falls back to a safe message when the config is missing or
invalid so a misconfigured instance cannot crash a conversation.

This agent is intentionally minimal: it does not implement LangGraph node
graphs. The "graph" is a single LLM call — sufficient for the MVP scope
described in AGENTS.md §7.6. Future iterations can swap the renderer for a
multi-node graph without changing the public surface.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentDefinition, BaseAgent
from app.agents.builder.config import AgentBuilderConfig
from app.agents.builder.renderer import render_builder_config
from app.agents.langchain_runtime import render_chat_prompt_messages
from app.agents.official.response_safety import sanitize_official_agent_answer
from app.agents.orchestration import (
    AgentOrchestrationRuntime,
    LANGCHAIN_STANDARD_FEATURES,
)
from app.api.deps import Principal
from app.schemas.agents import AgentRunRequest, AgentRunResponse
from app.schemas.llm import LLMChatRequest, LLMUsageResponse
from app.services.agent_module_service import get_module_definition
from app.services.llm_service import run_gateway_chat


_CONFIGURABLE_AGENT_KEY = "custom_builder"
_REQUIRED_MODULE = "agent.custom_builder"


class ConfigurableAgent(BaseAgent):
    """Agent whose behaviour is driven entirely by ``builder_config``."""

    def __init__(self) -> None:
        module = get_module_definition(_REQUIRED_MODULE)
        self.definition = AgentDefinition(
            agent_key=_CONFIGURABLE_AGENT_KEY,
            name=module.name,
            category=module.category,
            description=module.description,
            status="available",
            version=module.version,
            capabilities=list(module.capabilities),
            required_module=module.id,
            orchestration_runtime=AgentOrchestrationRuntime.LANGCHAIN,
            orchestration_features=list(LANGCHAIN_STANDARD_FEATURES),
        )

    async def run(
        self,
        payload: AgentRunRequest,
        principal: Principal,
        *,
        request_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> AgentRunResponse:
        config = _extract_builder_config(payload.context)
        if config is None:
            return _safe_fallback_response(
                payload,
                request_id,
                reason="builder_config_missing",
                message=(
                    "该自定义 Agent 尚未配置岗位参数。请在管理后台完成低代码配置后再发起对话。"
                ),
            )
        rendered = render_builder_config(config)

        # Greeting shortcut: when a greeting_message is configured and the
        # user input looks like a greeting, return the canned message
        # without calling the LLM (matches official customer-service Agent).
        if rendered.greeting_message and _looks_like_greeting(payload.input):
            return AgentRunResponse(
                answer=rendered.greeting_message,
                usage=_zero_usage(),
                model_key=payload.model_key or "",
                request_id=request_id or "",
                sources=[],
                metadata={
                    "agent_key": self.definition.agent_key,
                    "required_module": self.definition.required_module,
                    "greeting_intent": True,
                    "skipped_model_call": True,
                    "runtime_evidence": {
                        "execution": "greeting_shortcut",
                        "llm_gateway_called": False,
                    },
                },
            )

        user_prompt = rendered.user_prompt_template.format(
            user_input=payload.input,
            context=_format_context(payload.context),
        )
        llm_response = await run_gateway_chat(
            LLMChatRequest(
                model_key=payload.model_key or config.model_key,
                routing_key=payload.routing_key or config.routing_key,
                messages=render_chat_prompt_messages(
                    system_prompt=rendered.system_prompt,
                    user_prompt="{user_prompt}",
                    variables={"user_prompt": user_prompt},
                ),
                temperature=config.temperature,
                max_tokens=payload.max_tokens,
                metadata={
                    "agent_key": self.definition.agent_key,
                    "required_module": self.definition.required_module,
                    "request_id": request_id,
                    "builder_config_name": config.name,
                    "context_keys": sorted(payload.context.keys()),
                },
            ),
            principal,
            session=session,
            department_id=_optional_uuid(payload.context.get("department_id")),
            agent_id=_optional_uuid(payload.context.get("agent_id")),
            channel_id=_optional_uuid(payload.context.get("channel_id")),
            conversation_id=_optional_uuid(payload.context.get("conversation_id")),
            source=f"builder_agent.{self.definition.agent_key}",
        )
        return AgentRunResponse(
            answer=sanitize_official_agent_answer(
                llm_response.content, fallback=rendered.fallback_message
            ),
            usage=llm_response.usage,
            model_key=llm_response.model_key,
            request_id=llm_response.request_id,
            sources=_knowledge_sources(payload),
            metadata={
                **llm_response.metadata,
                "agent_key": self.definition.agent_key,
                "agent_version": self.definition.version,
                "required_module": self.definition.required_module,
                "provider_key": llm_response.provider_key,
                "deployment_id": str(llm_response.deployment_id)
                if llm_response.deployment_id
                else None,
                "orchestration_runtime": self.definition.orchestration_runtime.value,
                "builder_config_name": config.name,
                "response_style": rendered.response_style.value,
                "language": rendered.language.value,
                "runtime_evidence": {
                    "execution": "llm_gateway",
                    "llm_gateway_called": True,
                    "agent_key": self.definition.agent_key,
                    "provider_key": llm_response.provider_key,
                    "model_key": llm_response.model_key,
                    "deployment_id": str(llm_response.deployment_id)
                    if llm_response.deployment_id
                    else None,
                    "request_id": llm_response.request_id,
                    "finish_reason": llm_response.finish_reason,
                    "input_tokens": llm_response.usage.input_tokens,
                    "output_tokens": llm_response.usage.output_tokens,
                    "total_tokens": llm_response.usage.total_tokens,
                    "cost_usd": str(llm_response.usage.cost_usd),
                },
            },
        )


def _extract_builder_config(context: dict[str, Any]) -> AgentBuilderConfig | None:
    raw = context.get("builder_config")
    if not isinstance(raw, dict):
        return None
    config_dict = raw.get("config") if "config" in raw else raw
    if not isinstance(config_dict, dict):
        return None
    try:
        return AgentBuilderConfig.model_validate(config_dict)
    except Exception:
        return None


def _looks_like_greeting(text: str) -> bool:
    normalized = text.strip().lower()
    if len(normalized) > 30:
        return False
    greeting_markers = (
        "你好",
        "您好",
        "hi",
        "hello",
        "hey",
        "在吗",
        "在么",
        "早上好",
        "下午好",
        "晚上好",
        "good morning",
        "good afternoon",
    )
    return any(marker in normalized for marker in greeting_markers)


def _format_context(context: dict[str, Any]) -> str:
    if not context:
        return "无额外上下文。"
    lines: list[str] = []
    for key in sorted(context):
        if key in {"knowledge_sources", "builder_config", "mcp"}:
            continue
        value = context[key]
        if key == "knowledge_context":
            lines.append(f"- knowledge_context:\n{value}")
            continue
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def _knowledge_sources(payload: AgentRunRequest) -> list[dict[str, Any]]:
    sources = payload.context.get("knowledge_sources")
    if not isinstance(sources, list):
        return []
    return [source for source in sources if isinstance(source, dict)]


def _optional_uuid(value: object) -> UUID | None:
    if value in (None, ""):
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _zero_usage() -> LLMUsageResponse:
    return LLMUsageResponse(
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        cost_usd=Decimal("0"),
    )


def _safe_fallback_response(
    payload: AgentRunRequest,
    request_id: str | None,
    *,
    reason: str,
    message: str,
) -> AgentRunResponse:
    return AgentRunResponse(
        answer=message,
        usage=_zero_usage(),
        model_key=payload.model_key or "",
        request_id=request_id or "",
        sources=[],
        metadata={
            "agent_key": _CONFIGURABLE_AGENT_KEY,
            "required_module": _REQUIRED_MODULE,
            "fallback": True,
            "fallback_reason": reason,
            "skipped_model_call": True,
            "runtime_evidence": {
                "execution": "config_missing_fallback",
                "llm_gateway_called": False,
            },
        },
    )
