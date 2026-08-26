#!/usr/bin/env python3
"""Guard Agent runtime evidence from regressing into opaque demo responses."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "backend" / "app" / "services" / "agent_runtime_service.py"
SMOKE = ROOT / "scripts" / "smoke_http.py"
TESTS = ROOT / "backend" / "tests" / "test_agent_knowledge_enrichment.py"


def main() -> None:
    service = SERVICE.read_text(encoding="utf-8")
    smoke = SMOKE.read_text(encoding="utf-8")
    tests = TESTS.read_text(encoding="utf-8")

    require(
        'final_response.metadata["runtime_summary"] = _agent_run_runtime_summary(final_response)'
        in service,
        "Agent runtime responses must attach runtime_summary before audit and API return.",
    )
    require(
        '"runtime_summary": runtime_summary if isinstance(runtime_summary, dict) else {}'
        in service,
        "Agent run audit details must include runtime_summary for operator diagnostics.",
    )
    for token in (
        "real_model_call",
        "mock_model_call",
        "media_generation_task",
        "local_runtime",
    ):
        require(token in service, f"Runtime summary must classify {token}.")

    for token in (
        'response.metadata["runtime_summary"]["status"]',
        'details["runtime_summary"]["status"]',
        "real_model_call",
        "live_gateway",
        "local_runtime",
        "knowledge_confidence",
    ):
        require(token in tests, f"Agent runtime evidence tests must cover {token}.")

    for token in (
        "chat-runtime",
        "agent-run-runtime",
        "require_live_runtime_summary",
        "runtime_summary_from",
        'summary.get("status") == "real_model_call"',
        'summary.get("adapter_mode") == "live_gateway"',
        'summary.get("gateway_called") is True',
        'summary.get("mock_adapter") is False',
    ):
        require(token in smoke, f"HTTP smoke checks must verify live runtime evidence: {token}.")

    print("Agent runtime evidence verification passed.")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


if __name__ == "__main__":
    main()
