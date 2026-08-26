from __future__ import annotations

from app.agents.runtime_diagnostics import (
    agent_run_runtime_summary,
    dedupe_sources,
    format_knowledge_context,
    input_requires_strict_knowledge,
    is_greeting_intent,
    knowledge_confidence_diagnostics,
    knowledge_guardrail_decision,
)


def test_knowledge_confidence_classifies_scored_and_unscored_sources() -> None:
    assert knowledge_confidence_diagnostics([])["confidence_level"] == "no_match"
    assert knowledge_confidence_diagnostics([{"score": "invalid"}])["confidence_level"] == "unscored"

    diagnostics = knowledge_confidence_diagnostics([{"score": "0.8"}, {"score": 0.5}])

    assert diagnostics == {
        "confidence_level": "high",
        "max_score": 0.8,
        "min_score": 0.5,
        "requires_human_review": False,
        "review_reason": "strong_source_match",
    }


def test_strict_knowledge_guardrail_only_blocks_weak_policy_questions() -> None:
    diagnostics = {"enabled": True, "requires_human_review": True, "review_reason": "no_match"}

    decision = knowledge_guardrail_decision(
        context={"knowledge_guardrail_mode": "strict"},
        input_value="退款政策是什么？",
        knowledge_diagnostics=diagnostics,
    )

    assert input_requires_strict_knowledge("退款政策是什么？") is True
    assert decision["triggered"] is True
    assert knowledge_guardrail_decision(
        context={"knowledge_guardrail_mode": "advisory"},
        input_value="退款政策是什么？",
        knowledge_diagnostics=diagnostics,
    )["triggered"] is False


def test_runtime_summary_and_greeting_mapping_keep_runtime_evidence_shape() -> None:
    summary = agent_run_runtime_summary(
        metadata={
            "runtime_evidence": {
                "execution": "agent_run",
                "llm_gateway_called": True,
                "route_attempts": [{"status": "error"}, "invalid", {"status": "success"}],
                "provider_key": "qwen",
            },
            "knowledge": {"source_count": 2, "confidence_level": "medium"},
        },
        model_key="qwen-plus",
        request_id="request-1",
        total_tokens=42,
        source_count=1,
    )

    assert summary["status"] == "real_model_call"
    assert summary["adapter_mode"] == "live_gateway"
    assert summary["route_attempt_count"] == 2
    assert summary["knowledge_source_count"] == 2
    assert is_greeting_intent("  您好！ ") is True
    assert is_greeting_intent("请帮我查订单") is False


def test_context_formatter_truncates_and_deduplicates_by_knowledge_identity() -> None:
    source = {
        "knowledge_base_id": "base-1",
        "document_id": "document-1",
        "chunk_id": "chunk-1",
        "source_name": "policy.md",
        "score": 0.9,
        "text": "x" * 2001,
    }

    sources = dedupe_sources([source, {**source, "text": "later duplicate"}])
    context = format_knowledge_context(sources)

    assert sources == [source]
    assert "[1] 来源：policy.md；相关度：0.9" in context
    assert context.endswith("...")
