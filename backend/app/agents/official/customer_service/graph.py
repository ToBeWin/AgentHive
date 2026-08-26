import re
import warnings
from functools import lru_cache
from typing import Any, Literal, TypedDict, cast

from langchain_core._api.deprecation import LangChainPendingDeprecationWarning

with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore",
        message=r"The default value of `allowed_objects`.*",
        category=LangChainPendingDeprecationWarning,
    )
    from langgraph.graph import END, StateGraph


CustomerServiceIntent = Literal["knowledge_query", "general", "escalation_risk", "complaint"]


class CustomerServiceGraphState(TypedDict, total=False):
    query: str
    sources: list[dict[str, Any]]
    intent: CustomerServiceIntent
    selected_source: dict[str, Any]
    relevance_score: int
    answer: str
    requires_human: bool
    confidence: float
    graph_trace: list[dict[str, str]]


ESCALATION_KEYWORDS = ("投诉", "律师", "起诉", "赔偿", "12315", "差评", "举报", "工商")
COMPLAINT_KEYWORDS = ("不满", "太差", "骗人", "假货", "态度差", "生气", "愤怒")
GENERAL_KEYWORDS = ("你好", "在吗", "您好", "有人吗", "hello", "hi")
KNOWLEDGE_KEYWORDS = (
    "订单",
    "商品",
    "售后",
    "退款",
    "退货",
    "换货",
    "物流",
    "发货",
    "签收",
    "赔付",
    "价格",
    "优惠",
    "库存",
    "地址",
    "发票",
    "保修",
    "尺码",
    "质量",
    "平台",
    "店铺",
)


def run_customer_service_mock_graph(
    *,
    query: str,
    sources: list[dict[str, Any]],
) -> CustomerServiceGraphState:
    return cast(
        CustomerServiceGraphState,
        customer_service_graph().invoke(
            {
                "query": query,
                "sources": sources,
                "requires_human": False,
                "graph_trace": [],
            },
        ),
    )


def run_customer_service_prep(
    *,
    query: str,
    sources: list[dict[str, Any]],
) -> CustomerServiceGraphState:
    """Run classify → retrieve → confidence gate without drafting the final answer."""
    state: CustomerServiceGraphState = {
        "query": query,
        "sources": sources,
        "requires_human": False,
        "graph_trace": [],
    }
    state = {**state, **_classify_intent(state)}
    state = {**state, **_select_knowledge_source(state)}
    state = {**state, **_check_confidence(state)}
    return state


@lru_cache(maxsize=1)
def customer_service_graph() -> Any:
    workflow = StateGraph(CustomerServiceGraphState)
    workflow.add_node("classify_intent", _classify_intent)
    workflow.add_node("select_knowledge_source", _select_knowledge_source)
    workflow.add_node("draft_answer", _draft_answer)
    workflow.add_node("check_confidence", _check_confidence)
    workflow.add_node("escalate_to_human", _escalate_to_human)

    workflow.set_entry_point("classify_intent")
    workflow.add_edge("classify_intent", "select_knowledge_source")
    workflow.add_edge("select_knowledge_source", "draft_answer")
    workflow.add_edge("draft_answer", "check_confidence")
    workflow.add_conditional_edges(
        "check_confidence",
        _route_after_confidence,
        {"escalate": "escalate_to_human", "end": END},
    )
    workflow.add_edge("escalate_to_human", END)
    return workflow.compile()


def _append_trace(
    state: CustomerServiceGraphState, *, node: str, detail: str
) -> list[dict[str, str]]:
    trace = list(state.get("graph_trace") or [])
    trace.append({"node": node, "detail": detail})
    return trace


def _classify_intent(state: CustomerServiceGraphState) -> CustomerServiceGraphState:
    query = state.get("query", "")
    lowered = query.lower()

    if any(keyword in query for keyword in ESCALATION_KEYWORDS):
        intent: CustomerServiceIntent = "escalation_risk"
        detail = "检测到高风险或监管类诉求，优先建议人工介入。"
    elif any(keyword in query for keyword in COMPLAINT_KEYWORDS):
        intent = "complaint"
        detail = "检测到投诉情绪，回复需更谨慎并保留升级空间。"
    elif any(keyword in query for keyword in KNOWLEDGE_KEYWORDS) or any(
        token in lowered for token in ("order", "refund", "shipping", "return")
    ):
        intent = "knowledge_query"
        detail = "识别为业务知识查询，优先检索知识库。"
    elif any(keyword in query for keyword in GENERAL_KEYWORDS) and len(query.strip()) <= 12:
        intent = "general"
        detail = "识别为寒暄或开场，无需强制引用知识库。"
    else:
        intent = "knowledge_query"
        detail = "默认按业务问答处理，尝试匹配知识库。"

    return {
        "intent": intent,
        "graph_trace": _append_trace(state, node="classify_intent", detail=detail),
    }


def _select_knowledge_source(state: CustomerServiceGraphState) -> CustomerServiceGraphState:
    sources = state.get("sources", [])
    intent = state.get("intent", "knowledge_query")
    if intent == "general":
        return {
            "selected_source": {},
            "relevance_score": 0,
            "graph_trace": _append_trace(
                state, node="select_knowledge_source", detail="寒暄场景跳过知识库检索。"
            ),
        }

    if not sources:
        return {
            "selected_source": {},
            "relevance_score": 0,
            "requires_human": intent in {"knowledge_query", "complaint", "escalation_risk"},
            "graph_trace": _append_trace(
                state,
                node="select_knowledge_source",
                detail="未找到可用知识库片段。",
            ),
        }

    query = state.get("query", "")
    ranked = sorted(
        enumerate(sources),
        key=lambda item: (
            _source_relevance_score(query, str(item[1].get("text") or "")),
            float(item[1].get("score") or 0),
            -item[0],
        ),
        reverse=True,
    )
    best_index, best_source = ranked[0]
    relevance = _source_relevance_score(query, str(best_source.get("text") or ""))
    source_name = best_source.get("source_name") or best_source.get("document_id") or "企业知识库"
    return {
        "selected_source": best_source,
        "relevance_score": relevance,
        "graph_trace": _append_trace(
            state,
            node="select_knowledge_source",
            detail=f"选中来源 {source_name}（相关度 {relevance}，候选 #{best_index + 1}）。",
        ),
    }


def _draft_answer(state: CustomerServiceGraphState) -> CustomerServiceGraphState:
    intent = state.get("intent", "knowledge_query")
    if intent == "general":
        return {
            "answer": "您好，我在线，随时可以协助处理客户服务问题。请问今天需要我帮您处理哪类咨询？",
            "graph_trace": _append_trace(state, node="draft_answer", detail="生成寒暄回复。"),
        }

    selected_source = state.get("selected_source") or {}
    if not selected_source:
        return {
            "answer": (
                "您好，已经收到您的问题。当前知识库没有找到足够明确的规则，"
                "请客服先补充订单号、商品状态和具体诉求，再按店铺政策处理。"
            ),
            "requires_human": True,
            "graph_trace": _append_trace(
                state, node="draft_answer", detail="无匹配知识，生成保守兜底回复。"
            ),
        }

    source_name = (
        selected_source.get("source_name") or selected_source.get("document_id") or "企业知识库"
    )
    source_text = str(selected_source.get("text") or "").strip()
    if len(source_text) > 360:
        source_text = f"{source_text[:360]}..."
    return {
        "answer": (
            "您好，已经收到您的问题。根据店铺当前规则，"
            f"{source_text}\n\n"
            "您可以先安抚客户，并请客户提供订单号、商品状态照片和具体诉求，"
            "再按店铺政策协助处理。\n\n"
            f"客服备注：本回复参考企业知识库来源 1（{source_name}）。"
        ),
        "graph_trace": _append_trace(
            state, node="draft_answer", detail="基于最佳知识片段生成回复草稿。"
        ),
    }


def _check_confidence(state: CustomerServiceGraphState) -> CustomerServiceGraphState:
    intent = state.get("intent", "knowledge_query")
    relevance = int(state.get("relevance_score") or 0)
    has_source = bool(state.get("selected_source"))
    sources = state.get("sources") or []

    confidence = 0.82
    requires_human = bool(state.get("requires_human"))
    detail = "置信度良好，可直接发送。"

    if intent == "escalation_risk":
        confidence = 0.18
        requires_human = True
        detail = "高风险诉求，建议升级人工复核。"
    elif intent == "complaint":
        confidence = 0.42 if has_source else 0.28
        requires_human = True
        detail = "投诉场景需人工关注，自动回复仅作初稿。"
    elif intent == "general":
        confidence = 0.9
        detail = "寒暄场景，无需人工升级。"
    elif not sources:
        confidence = 0.25
        requires_human = True
        detail = "知识库为空，无法支撑自动答复。"
    elif not has_source:
        confidence = 0.32
        requires_human = True
        detail = "未匹配到相关知识片段。"
    elif relevance < 2:
        confidence = 0.48
        requires_human = True
        detail = "知识相关度偏低，建议人工确认后发送。"

    return {
        "confidence": confidence,
        "requires_human": requires_human,
        "graph_trace": _append_trace(
            state,
            node="check_confidence",
            detail=f"{detail}（confidence={confidence:.2f}）",
        ),
    }


def _route_after_confidence(state: CustomerServiceGraphState) -> Literal["escalate", "end"]:
    if state.get("requires_human") and float(state.get("confidence") or 0) < 0.55:
        return "escalate"
    return "end"


def _escalate_to_human(state: CustomerServiceGraphState) -> CustomerServiceGraphState:
    answer = state.get("answer") or (
        "您好，已经收到您的问题。当前情况建议由人工客服继续跟进，"
        "请先记录客户诉求、订单号和联系方式，再按店铺升级流程处理。"
    )
    if "客服备注" not in answer:
        answer = (
            f"{answer}\n\n"
            "客服备注：系统判断该问题置信度不足或存在升级风险，请人工复核后再发送给客户。"
        )
    return {
        "answer": answer,
        "requires_human": True,
        "graph_trace": _append_trace(
            state, node="escalate_to_human", detail="已附加人工升级提示。"
        ),
    }


def _source_relevance_score(query: str, text: str) -> int:
    query_tokens = _relevance_tokens(query)
    if not query_tokens:
        return 0
    text_tokens = _relevance_tokens(text)
    return len(query_tokens & text_tokens)


def _relevance_tokens(value: str) -> set[str]:
    normalized = value.lower()
    tokens = set(re.findall(r"[a-z0-9]+", normalized))
    for sequence in re.findall(r"[\u4e00-\u9fff]+", normalized):
        tokens.update(_character_ngrams(sequence, size=2))
        tokens.update(_character_ngrams(sequence, size=3))
    return tokens


def _character_ngrams(value: str, *, size: int) -> set[str]:
    if len(value) < size:
        return set()
    return {value[index : index + size] for index in range(len(value) - size + 1)}
