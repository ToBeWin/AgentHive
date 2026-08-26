#!/usr/bin/env python3
"""HTTP smoke checks for a running AgentHive deployment."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TENANT = "demo"
DEFAULT_EMAIL = "admin@example.com"
DEFAULT_PASSWORD = "AgentHive123!"


@dataclass
class SmokeContext:
    base_url: str
    token: str | None = None


class SmokeFailure(RuntimeError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AgentHive HTTP smoke checks.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"Backend base URL. Default: {DEFAULT_BASE_URL}")
    parser.add_argument("--tenant", default=DEFAULT_TENANT, help=f"Tenant slug. Default: {DEFAULT_TENANT}")
    parser.add_argument("--email", default=DEFAULT_EMAIL, help=f"Admin email. Default: {DEFAULT_EMAIL}")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Admin password.")
    parser.add_argument("--strict-readiness", action="store_true", help="Fail on readiness warnings, not only blockers.")
    parser.add_argument("--skip-agent-run", action="store_true", help="Skip official Agent run smoke check.")
    parser.add_argument("--timeout", type=float, default=60.0, help="HTTP timeout in seconds.")
    args = parser.parse_args()

    ctx = SmokeContext(base_url=args.base_url.rstrip("/"))
    checks: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, message: str) -> None:
        checks.append((name, ok, message))
        mark = "OK" if ok else "FAIL"
        print(f"[{mark}] {name}: {message}")

    try:
        setup = request_json(ctx, "GET", "/api/v1/auth/setup-status", timeout=args.timeout)
        assert_true(setup.get("diagnostics", {}).get("status") == "healthy", "setup database is not healthy")
        assert_true(setup.get("initialized") is True, "tenant bootstrap is not initialized")
        record("setup-status", True, f"tenant_count={setup.get('tenant_count')}")

        readiness = request_json(ctx, "GET", "/api/v1/health/readiness", timeout=args.timeout, allow_error_status=True)
        delivery = readiness.get("delivery") or {}
        blocker_count = int(delivery.get("blocker_count") or 0)
        warning_count = int(delivery.get("warning_count") or 0)
        assert_true(blocker_count == 0, f"readiness has {blocker_count} blocker(s)")
        if args.strict_readiness:
            assert_true(warning_count == 0, f"readiness has {warning_count} warning(s)")
        record(
            "readiness",
            True,
            f"status={delivery.get('status') or readiness.get('status')}, blockers={blocker_count}, warnings={warning_count}",
        )

        auth = request_json(
            ctx,
            "POST",
            "/api/v1/auth/login",
            body={"tenant_slug": args.tenant, "email": args.email, "password": args.password},
            timeout=args.timeout,
        )
        token = auth.get("access_token")
        assert_true(isinstance(token, str) and len(token) > 20, "login did not return an access token")
        ctx.token = token
        user = auth.get("user") or {}
        permissions = user.get("permissions") or []
        assert_true("tenant.admin" in permissions, "demo admin is missing tenant.admin permission")
        record("login", True, f"user={user.get('email')}, permissions={len(permissions)}")

        modules = request_json(ctx, "GET", "/api/v1/agent-modules", timeout=args.timeout)
        module_items = modules.get("modules") or []
        assert_true(len(module_items) >= 11, f"expected at least 11 Agent modules, got {len(module_items)}")
        enabled_modules = [
            item.get("id") or item.get("module_key")
            for item in module_items
            if item.get("runtime_state") == "enabled" or item.get("state") == "enabled" or item.get("enabled") is True
        ]
        record("agent-modules", True, f"modules={len(module_items)}, enabled={len(enabled_modules)}")

        catalog = request_json(ctx, "GET", "/api/v1/agents/catalog", timeout=args.timeout)
        catalog_keys = {item.get("agent_key") for item in catalog.get("agents") or []}
        for required_agent in {"customer_service", "image_generation", "video_generation"}:
            assert_true(required_agent in catalog_keys, f"missing Agent catalog entry: {required_agent}")
        record("agent-catalog", True, f"agents={len(catalog_keys)}")

        instances = request_json(ctx, "GET", "/api/v1/agents/instances", timeout=args.timeout)
        agent_instances = instances.get("agents") or []
        active_agents = [item for item in agent_instances if item.get("status") == "active"]
        assert_true(active_agents, "no active Agent instance found")
        selected_agent = active_agents[0]
        record("agent-instances", True, f"active={len(active_agents)}, selected={selected_agent.get('slug')}")

        providers = request_json(ctx, "GET", "/api/v1/models/providers", timeout=args.timeout)
        provider_items = providers.get("providers") or []
        configured_providers = [item for item in provider_items if item.get("credential_configured")]
        assert_true(configured_providers, "no configured model provider found")
        record("model-providers", True, f"providers={len(provider_items)}, configured={len(configured_providers)}")

        deployments = request_json(ctx, "GET", "/api/v1/models/deployments", timeout=args.timeout)
        deployment_items = deployments.get("deployments") or []
        active_deployments = [item for item in deployment_items if item.get("status") == "active"]
        assert_true(active_deployments, "no active model deployment found")
        record("model-deployments", True, f"active={len(active_deployments)}")

        media_models = request_json(ctx, "GET", "/api/v1/media/models", timeout=args.timeout)
        assert_true(isinstance(media_models, list) and len(media_models) >= 5, "media model catalog is incomplete")
        active_media = [item for item in media_models if item.get("status") == "active"]
        record("media-model-catalog", True, f"models={len(media_models)}, active={len(active_media)}")

        bases = request_json(ctx, "GET", "/api/v1/knowledge/bases", timeout=args.timeout)
        knowledge_bases = bases.get("bases") or []
        assert_true(knowledge_bases, "no knowledge base found")
        knowledge_base = knowledge_bases[0]
        kb_id = knowledge_base.get("id")
        record("knowledge-bases", True, f"bases={len(knowledge_bases)}, selected={knowledge_base.get('name')}")

        documents = request_json(ctx, "GET", f"/api/v1/knowledge/bases/{kb_id}/documents", timeout=args.timeout)
        document_items = documents.get("documents") or []
        indexed_documents = [item for item in document_items if item.get("status") == "indexed"]
        assert_true(indexed_documents, "no indexed knowledge document found")
        record("knowledge-documents", True, f"indexed={len(indexed_documents)}")

        retrieval = request_json(
            ctx,
            "POST",
            f"/api/v1/knowledge/bases/{kb_id}/retrieval-test",
            body={"query": "客户申请退款需要怎么处理？", "top_k": 3, "include_raw_chunks": False},
            timeout=args.timeout,
        )
        results = retrieval.get("results") or []
        assert_true(results, "retrieval returned no sources")
        record("knowledge-retrieval", True, f"results={len(results)}, engine={retrieval.get('engine')}")

        sessions = request_json(
            ctx,
            "POST",
            "/api/v1/chat/sessions",
            body={"title": f"Smoke check {int(time.time())}", "agent_id": selected_agent.get("id")},
            timeout=args.timeout,
        )
        conversation_id = sessions.get("id")
        assert_true(isinstance(conversation_id, str), "chat session did not return id")
        record("chat-session", True, f"id={conversation_id}")

        chat = request_json(
            ctx,
            "POST",
            f"/api/v1/chat/sessions/{conversation_id}/messages",
            body={"content": "客户签收后想换大一码，应该怎么处理？", "max_tokens": 256},
            timeout=args.timeout,
        )
        assert_true(chat.get("assistant_message", {}).get("content"), "chat assistant message is empty")
        record("chat-message", True, f"model={chat.get('model_key')}, sources={len(chat.get('sources') or [])}")
        chat_runtime = runtime_summary_from(chat, nested_message_key="assistant_message")
        record("chat-runtime", True, require_live_runtime_summary(chat_runtime, "chat message"))

        if not args.skip_agent_run:
            run_response = request_json(
                ctx,
                "POST",
                "/api/v1/agents/customer_service/run",
                body={"input": "客户咨询物流延迟，客服怎么回复？", "max_tokens": 256},
                timeout=args.timeout,
            )
            assert_true(run_response.get("answer"), "Agent run answer is empty")
            run_runtime = runtime_summary_from(run_response)
            assert_true(
                run_runtime.get("model_key") == run_response.get("model_key"),
                "Agent run runtime summary model does not match response model",
            )
            record(
                "agent-run",
                True,
                f"model={run_response.get('model_key')}, sources={len(run_response.get('sources') or [])}",
            )
            record("agent-run-runtime", True, require_live_runtime_summary(run_runtime, "Agent run"))

    except SmokeFailure as exc:
        record("smoke", False, str(exc))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        record("http", False, f"{exc.code} {exc.reason}: {detail[:500]}")
    except urllib.error.URLError as exc:
        record("network", False, str(exc.reason))

    failed = [item for item in checks if not item[1]]
    print("")
    print(f"Smoke summary: {len(checks) - len(failed)}/{len(checks)} checks passed")
    return 1 if failed else 0


def request_json(
    ctx: SmokeContext,
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    timeout: float,
    allow_error_status: bool = False,
) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if ctx.token:
        headers["Authorization"] = f"Bearer {ctx.token}"
    request = urllib.request.Request(f"{ctx.base_url}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return parse_json_response(response.read())
    except urllib.error.HTTPError as exc:
        if allow_error_status:
            return parse_json_response(exc.read())
        raise


def parse_json_response(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise SmokeFailure(f"response is not JSON: {raw[:200]!r}") from exc


def runtime_summary_from(response: dict[str, Any], *, nested_message_key: str | None = None) -> dict[str, Any]:
    metadata = response.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    summary = metadata.get("runtime_summary")
    if isinstance(summary, dict):
        return summary
    if nested_message_key:
        nested = response.get(nested_message_key)
        nested_metadata = nested.get("metadata") if isinstance(nested, dict) else None
        if isinstance(nested_metadata, dict):
            nested_summary = nested_metadata.get("runtime_summary")
            if isinstance(nested_summary, dict):
                return nested_summary
    raise SmokeFailure("runtime_summary is missing from model response")


def require_live_runtime_summary(summary: dict[str, Any], label: str) -> str:
    assert_true(summary.get("status") == "real_model_call", f"{label} did not report a live model call")
    assert_true(summary.get("adapter_mode") == "live_gateway", f"{label} did not use the live gateway adapter")
    assert_true(summary.get("gateway_called") is True, f"{label} did not pass through AgentHive Gateway")
    assert_true(summary.get("mock_adapter") is False, f"{label} used the mock adapter")
    provider = str(summary.get("provider_key") or "")
    model = str(summary.get("model_key") or "")
    request_id = str(summary.get("request_id") or "")
    assert_true(provider not in {"", "-"}, f"{label} runtime provider is missing")
    assert_true(model not in {"", "-"}, f"{label} runtime model is missing")
    assert_true(request_id not in {"", "-"}, f"{label} runtime request_id is missing")
    return f"{provider}/{model}, request={request_id}, attempts={summary.get('route_attempt_count')}"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


if __name__ == "__main__":
    sys.exit(main())
