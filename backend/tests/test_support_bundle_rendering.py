from __future__ import annotations

from app.health.support_bundle_rendering import (
    support_bundle_acceptance_checklist,
    support_bundle_delivery_summary,
    support_bundle_readme,
)


def _report() -> dict[str, object]:
    return {
        "generated_at": "2026-08-26T12:00:00+00:00",
        "delivery": {
            "status": "ready_with_warnings",
            "summary": "Ready with a | escaped warning",
            "blocker_count": 0,
            "warning_count": 1,
            "blockers": [],
            "warnings": [
                {
                    "id": "ragflow",
                    "label": "Optional RAGFlow integration",
                    "component": "ragflow",
                    "status": "degraded",
                    "message": "Probe pending",
                }
            ],
        },
        "diagnostics": {
            "info": {"name": "AgentHive", "version": "1.0", "edition": "private"},
            "readiness": {
                "status": "healthy",
                "components": {
                    "zebra": {"status": "healthy", "message": "z|line\nnext"},
                    "alpha": {"status": "degraded", "message": "a"},
                    "database": {"status": "healthy", "message": "ok"},
                },
            },
            "connection_acceptance": {
                "status": "healthy",
                "summary": "Live probe available",
                "providers": ["qwen"],
                "latest_live_probe": {"provider_key": "qwen", "status_code": 200},
            },
            "knowledge_acceptance": {
                "status": "healthy",
                "summary": "Cited sources available",
                "agents": ["customer_service"],
                "latest_knowledge_run": {"agent_key": "customer_service", "source_count": 2},
            },
        },
    }


def test_support_bundle_readme_uses_delivery_snapshot() -> None:
    readme = support_bundle_readme(_report())

    assert "- Product: AgentHive 1.0" in readme
    assert "- Delivery status: ready_with_warnings" in readme
    assert "Do not manually add API keys" in readme


def test_acceptance_checklist_renders_connection_and_knowledge_evidence() -> None:
    checklist = support_bundle_acceptance_checklist(_report())

    assert "- Acceptance decision: conditional_pass" in checklist
    assert "- [x] **PostgreSQL business database** (`database`): healthy - ok" in checklist
    assert "Latest live provider probe:" in checklist
    assert "Latest knowledge-backed Agent run:" in checklist
    assert "No issues reported." in checklist


def test_delivery_summary_preserves_sorted_components_and_markdown_escaping() -> None:
    summary = support_bundle_delivery_summary(_report())

    assert summary.index("| alpha |") < summary.index("| zebra |")
    assert "| zebra | healthy | z\\|line next |" in summary
    assert "Optional RAGFlow integration" in summary
