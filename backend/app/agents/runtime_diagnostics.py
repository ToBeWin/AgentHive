"""Pure runtime diagnostics and knowledge-context helpers for agents."""

from typing import Any, cast


MAX_KNOWLEDGE_CONTEXT_SOURCE_CHARS = 2000
KNOWLEDGE_CONFIDENCE_HIGH_THRESHOLD = 0.75
KNOWLEDGE_CONFIDENCE_MEDIUM_THRESHOLD = 0.35
KNOWLEDGE_GUARDRAIL_DEFAULT_MODE = "strict"
KNOWLEDGE_GUARDRAIL_REQUIRED_KEYWORDS = (
    "赔偿",
    "补偿",
    "退款",
    "退货",
    "换货",
    "售后",
    "发票",
    "订单",
    "物流",
    "运费",
    "平台规则",
    "店铺规则",
    "政策",
    "规则",
    "合同",
    "承诺",
    "处罚",
    "投诉",
    "维权",
    "customer",
    "refund",
    "return",
    "compensation",
    "policy",
    "order",
)


def knowledge_confidence_diagnostics(sources: list[dict[str, object]]) -> dict[str, object]:
    if not sources:
        return {
            "confidence_level": "no_match",
            "max_score": None,
            "min_score": None,
            "requires_human_review": True,
            "review_reason": "no_matching_sources",
        }

    scores = [coerce_score(source.get("score")) for source in sources]
    numeric_scores = [score for score in scores if score is not None]
    if not numeric_scores:
        return {
            "confidence_level": "unscored",
            "max_score": None,
            "min_score": None,
            "requires_human_review": True,
            "review_reason": "retrieval_sources_are_unscored",
        }

    max_score = max(numeric_scores)
    min_score = min(numeric_scores)
    if max_score >= KNOWLEDGE_CONFIDENCE_HIGH_THRESHOLD:
        confidence_level = "high"
        requires_human_review = False
        review_reason = "strong_source_match"
    elif max_score >= KNOWLEDGE_CONFIDENCE_MEDIUM_THRESHOLD:
        confidence_level = "medium"
        requires_human_review = False
        review_reason = "usable_source_match"
    else:
        confidence_level = "low"
        requires_human_review = True
        review_reason = "low_retrieval_score"

    return {
        "confidence_level": confidence_level,
        "max_score": round(max_score, 6),
        "min_score": round(min_score, 6),
        "requires_human_review": requires_human_review,
        "review_reason": review_reason,
    }


def knowledge_guardrail_decision(
    *,
    context: dict[str, object],
    input_value: str,
    knowledge_diagnostics: dict[str, object],
) -> dict[str, object]:
    mode = knowledge_guardrail_mode(context)
    requires_strict_knowledge = input_requires_strict_knowledge(input_value)
    triggered = (
        knowledge_diagnostics.get("enabled") is True
        and knowledge_diagnostics.get("requires_human_review") is True
        and mode == "strict"
        and requires_strict_knowledge
    )
    return {
        "mode": mode,
        "triggered": triggered,
        "skipped_model_call": triggered,
        "reason": knowledge_diagnostics.get("review_reason") or knowledge_diagnostics.get("reason"),
        "requires_strict_knowledge": requires_strict_knowledge,
        "keyword_matched": requires_strict_knowledge,
    }


def knowledge_guardrail_mode(context: dict[str, object]) -> str:
    raw_value = context.get("knowledge_guardrail_mode", context.get("knowledge_guardrail"))
    if raw_value is None:
        return KNOWLEDGE_GUARDRAIL_DEFAULT_MODE
    if isinstance(raw_value, bool):
        return "strict" if raw_value else "off"
    normalized = str(raw_value).strip().lower()
    if normalized in {"0", "disabled", "false", "none", "off"}:
        return "off"
    if normalized in {"advisory", "warn", "warning"}:
        return "advisory"
    return "strict"


def input_requires_strict_knowledge(value: str) -> bool:
    normalized = value.strip().lower()
    return bool(normalized) and any(
        keyword in normalized for keyword in KNOWLEDGE_GUARDRAIL_REQUIRED_KEYWORDS
    )


def agent_runtime_adapter_mode(*, execution: str, gateway_called: bool, mock_adapter: bool) -> str:
    if execution == "media_gateway":
        return "media_gateway"
    if gateway_called:
        return "mock_gateway" if mock_adapter else "live_gateway"
    return "local_runtime"


def agent_runtime_status(adapter_mode: str) -> str:
    if adapter_mode == "live_gateway":
        return "real_model_call"
    if adapter_mode == "mock_gateway":
        return "mock_model_call"
    if adapter_mode == "media_gateway":
        return "media_generation_task"
    return "local_runtime"


def runtime_route_attempts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def agent_run_runtime_summary(
    *,
    metadata: dict[str, object],
    model_key: str | None,
    request_id: str | None,
    total_tokens: int,
    source_count: int,
) -> dict[str, object]:
    runtime = metadata.get("runtime_evidence")
    runtime_evidence = runtime if isinstance(runtime, dict) else {}
    knowledge = metadata.get("knowledge")
    knowledge_diagnostics = knowledge if isinstance(knowledge, dict) else {}
    route_attempts = runtime_route_attempts(runtime_evidence.get("route_attempts"))
    gateway_called = runtime_evidence.get("llm_gateway_called") is True
    mock_adapter = runtime_evidence.get("mock_adapter") is True
    execution = str(runtime_evidence.get("execution") or "-")
    adapter_mode = agent_runtime_adapter_mode(
        execution=execution,
        gateway_called=gateway_called,
        mock_adapter=mock_adapter,
    )
    return {
        "status": agent_runtime_status(adapter_mode),
        "adapter_mode": adapter_mode,
        "execution": execution,
        "gateway_called": gateway_called,
        "mock_adapter": mock_adapter,
        "provider_key": runtime_evidence.get("provider_key") or metadata.get("provider_key"),
        "model_key": runtime_evidence.get("model_key") or model_key,
        "request_id": request_id,
        "total_tokens": total_tokens,
        "route_attempt_count": len(route_attempts),
        "fallback_attempt_count": runtime_evidence.get("fallback_attempt_count", 0),
        "selected_route_reason": runtime_evidence.get("selected_route_reason"),
        "knowledge_source_count": knowledge_diagnostics.get("source_count", source_count),
        "knowledge_confidence": knowledge_diagnostics.get("confidence_level"),
        "requires_human_review": knowledge_diagnostics.get("requires_human_review") is True,
    }


def is_greeting_intent(value: str) -> bool:
    normalized = value.strip().lower().strip("!！。.,，?？~～ ")
    return normalized in {
        "hi",
        "hello",
        "hey",
        "你好",
        "您好",
        "在吗",
        "嗨",
        "哈喽",
        "hello there",
        "hi there",
    }


def knowledge_guardrail_answer(knowledge_diagnostics: dict[str, object]) -> str:
    reason = str(
        knowledge_diagnostics.get("review_reason")
        or knowledge_diagnostics.get("reason")
        or "unknown"
    )
    base_names = knowledge_base_names_from_diagnostics(knowledge_diagnostics)
    base_text = f"已检查知识库：{base_names}。" if base_names else "已检查已绑定的企业知识库。"
    reason_text = {
        "low_retrieval_score": "当前检索结果相关性偏低。",
        "no_matching_sources": "当前没有检索到足够匹配的知识库片段。",
        "retrieval_sources_are_unscored": "当前检索结果缺少可信分数。",
    }.get(reason, "当前知识库证据不足。")
    return (
        "您好，已经收到您的问题。为了避免给客户错误承诺，"
        f"{base_text}{reason_text}"
        "请客服先人工确认订单、商品状态和店铺政策后再回复客户。\n\n"
        "客服备注：资料匹配不足，建议人工确认后再发送。"
    )


def knowledge_base_names_from_diagnostics(knowledge_diagnostics: dict[str, object]) -> str:
    per_base = knowledge_diagnostics.get("per_base")
    if not isinstance(per_base, list):
        return ""
    names: list[str] = []
    for item in per_base:
        if not isinstance(item, dict):
            continue
        name = item.get("knowledge_base_name") or item.get("knowledge_base_id")
        if name:
            names.append(str(name))
    return "、".join(names[:5])


def coerce_score(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(cast(Any, value))
    except (TypeError, ValueError):
        return None


def agent_instance_diagnostics_from_context(context: dict[str, object]) -> dict[str, object]:
    raw_agent_id = context.get("agent_id")
    if not raw_agent_id:
        return {"enabled": False, "reason": "no_agent_instance_context"}

    diagnostics: dict[str, object] = {"enabled": True, "agent_id": str(raw_agent_id)}
    field_map = {
        "agent_instance_slug": "slug",
        "agent_instance_name": "name",
        "module_key": "module_key",
        "department_id": "department_id",
        "visibility": "visibility",
        "channel_id": "channel_id",
    }
    for source_field, target_field in field_map.items():
        value = context.get(source_field)
        if value not in (None, ""):
            diagnostics[target_field] = str(value)
    return diagnostics


def format_knowledge_context(sources: list[dict[str, object]]) -> str:
    if not sources:
        return "未检索到匹配的企业知识库片段。"
    lines: list[str] = []
    for index, source in enumerate(sources, start=1):
        source_name = (
            source.get("source_name") or source.get("document_id") or source.get("chunk_id")
        )
        score = source.get("score")
        text = truncate_knowledge_source_text(str(source.get("text") or "").strip())
        lines.append(f"[{index}] 来源：{source_name}；相关度：{score}\n{text}")
    return "\n\n".join(lines)


def truncate_knowledge_source_text(text: str) -> str:
    if len(text) <= MAX_KNOWLEDGE_CONTEXT_SOURCE_CHARS:
        return text
    return f"{text[:MAX_KNOWLEDGE_CONTEXT_SOURCE_CHARS]}..."


def dedupe_sources(sources: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[tuple[object, object, object]] = set()
    result: list[dict[str, object]] = []
    for source in sources:
        key = (source.get("knowledge_base_id"), source.get("document_id"), source.get("chunk_id"))
        if key not in seen:
            seen.add(key)
            result.append(source)
    return result
