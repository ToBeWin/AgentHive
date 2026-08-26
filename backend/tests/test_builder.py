"""Unit tests for the low-code Agent Builder.

Covers:
- Config schema validation (routing target required, fallback dedupe,
  escalation message pairing).
- Renderer output (brand guard, style hints, language hints, KB/tool counts).
- Validator behaviour against a stubbed session: missing deployment,
  inactive deployment, policy denial, max_tokens overflow, MCP server
  not active, soft warnings.
- Engine: compile raises on ERROR issues; preview returns rendered + report.
- ConfigurableAgent runtime: greeting shortcut, builder_config missing
  fallback, normal run via stubbed gateway.
- Registry: ConfigurableAgent is registered under the ``custom_builder`` key.
"""

from __future__ import annotations

import unittest
from decimal import Decimal
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4


from app.agents.builder.config import (
    AgentBuilderConfig,
    AgentBuilderPreviewRequest,
    ResponseStyle,
    SupportedLanguage,
)
from app.agents.builder.engine import (
    BuilderValidationError,
    builder_config_to_instance_metadata,
    compile_builder_config,
    preview_builder_config,
    validate_builder_config,
)
from app.agents.builder.renderer import render_builder_config
from app.agents.custom_builder.agent import ConfigurableAgent
from app.agents.registry import agent_registry
from app.api.deps import Principal
from app.schemas.agents import AgentRunRequest
from app.schemas.llm import LLMUsageResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config(**overrides: Any) -> AgentBuilderConfig:
    base: dict[str, Any] = {
        "name": "售后小妹",
        "system_prompt": "你是店铺售后助手，回答退换货问题。",
        "routing_key": "default-chat",
    }
    base.update(overrides)
    return AgentBuilderConfig.model_validate(base)


def _principal(*, tenant_id: UUID | None = None) -> Principal:
    from app.core.security import Permission

    class _P:
        def __init__(self) -> None:
            self.tenant_id = tenant_id or uuid4()
            self.user_id = uuid4()
            self.permissions = {Permission.AGENTS_WRITE}
            self.is_tenant_admin = True
            self.role = "tenant_admin"

    return _P()  # type: ignore[return-value]


class _FakeScalars:
    def __init__(self, items: list[Any] | None = None) -> None:
        self._items = items or []

    def all(self):
        return self._items

    def first(self):
        return self._items[0] if self._items else None


class _FakeResult:
    def __init__(self, items: list[Any] | None = None) -> None:
        self._items = items or []
        self._scalars = _FakeScalars(self._items)

    def scalars(self):
        return self._scalars

    def first(self):
        return self._items[0] if self._items else None


class _FakeSession:
    """Minimal AsyncSession stub — returns canned rows for ``execute``."""

    def __init__(self, *, rows: list[Any] | None = None, first_row: Any = None) -> None:
        # ``first_row`` (if provided) takes precedence and is returned as the
        # single ``first()`` result; otherwise the rows list is used.
        self._rows = rows or []
        self._first_row = first_row
        self.added: list[Any] = []
        self.committed = 0
        self.flushed = 0

    async def execute(self, *_args: Any, **_kwargs: Any) -> _FakeResult:
        if self._first_row is not None:
            return _FakeResult([self._first_row])
        return _FakeResult(self._rows)

    def add(self, value: Any) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        self.flushed += 1

    async def commit(self) -> None:
        self.committed += 1

    async def rollback(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Config schema tests
# ---------------------------------------------------------------------------


class BuilderConfigSchemaTests(unittest.TestCase):
    def test_requires_routing_target(self) -> None:
        with self.assertRaises(ValueError):
            AgentBuilderConfig(
                name="x",
                system_prompt="x",
            )

    def test_routing_key_only_is_valid(self) -> None:
        cfg = _config()
        self.assertEqual(cfg.routing_key, "default-chat")

    def test_deployment_id_only_is_valid(self) -> None:
        cfg = _config(deployment_id=uuid4(), routing_key=None)
        self.assertIsNotNone(cfg.deployment_id)

    def test_fallback_deployment_ids_deduped_preserving_order(self) -> None:
        d1, d2 = uuid4(), uuid4()
        cfg = _config(fallback_deployment_ids=[d1, d2, d1, d2, d2])
        self.assertEqual(cfg.fallback_deployment_ids, [d1, d2])

    def test_confidence_threshold_requires_escalation_message(self) -> None:
        with self.assertRaises(ValueError):
            AgentBuilderConfig(
                name="x",
                system_prompt="x",
                routing_key="default-chat",
                confidence_threshold=0.5,
            )

    def test_confidence_threshold_with_message_is_valid(self) -> None:
        cfg = _config(
            confidence_threshold=0.5,
            escalation_message="请转人工",
        )
        self.assertEqual(cfg.confidence_threshold, 0.5)

    def test_temperature_bounds(self) -> None:
        with self.assertRaises(ValueError):
            _config(temperature=3.0)
        with self.assertRaises(ValueError):
            _config(temperature=-0.1)
        # Valid bounds.
        _config(temperature=0.0)
        _config(temperature=2.0)

    def test_response_style_and_language_defaults(self) -> None:
        cfg = _config()
        self.assertEqual(cfg.response_style, ResponseStyle.FORMAL)
        self.assertEqual(cfg.language, SupportedLanguage.AUTO)


# ---------------------------------------------------------------------------
# Renderer tests
# ---------------------------------------------------------------------------


class BuilderRendererTests(unittest.TestCase):
    def test_brand_guard_present(self) -> None:
        rendered = render_builder_config(_config())
        self.assertIn("AgentHive", rendered.system_prompt)
        # The brand guard explicitly forbids these variants; they appear in
        # the prohibition clause, which is the correct behaviour.
        self.assertIn("禁止写成", rendered.system_prompt)

    def test_style_hint_injected(self) -> None:
        rendered = render_builder_config(_config(response_style=ResponseStyle.CONCISE))
        self.assertIn("简洁直接", rendered.system_prompt)

    def test_language_hint_injected(self) -> None:
        rendered = render_builder_config(_config(language=SupportedLanguage.EN))
        self.assertIn("英文", rendered.system_prompt)

    def test_knowledge_and_tool_counts_in_prompt(self) -> None:
        rendered = render_builder_config(
            _config(
                knowledge_base_ids=[uuid4(), uuid4()],
                mcp_server_keys=["kb-search", "crm-lookup"],
            )
        )
        self.assertIn("知识库：2 个", rendered.system_prompt)
        self.assertIn("MCP 工具服务器：2 个", rendered.system_prompt)

    def test_escalation_clause_added_when_threshold_set(self) -> None:
        rendered = render_builder_config(
            _config(
                confidence_threshold=0.6,
                escalation_message="请联系人工",
            )
        )
        self.assertIn("60%", rendered.system_prompt)
        self.assertIn("请联系人工", rendered.system_prompt)

    def test_default_fallback_message(self) -> None:
        rendered = render_builder_config(_config())
        self.assertTrue(rendered.fallback_message)

    def test_runtime_metadata_carries_source(self) -> None:
        rendered = render_builder_config(_config())
        self.assertEqual(rendered.runtime_metadata["source"], "low_code_builder")
        self.assertEqual(rendered.runtime_metadata["response_style"], "formal")


# ---------------------------------------------------------------------------
# Validator tests (stubbed DB + policy engine)
# ---------------------------------------------------------------------------


class BuilderValidatorTests(unittest.IsolatedAsyncioTestCase):
    async def test_validate_passes_with_routing_key_only_no_policies(self) -> None:
        # No policy rules + routing_key set → engine returns explicit_route allow.
        session = _FakeSession()
        report = await validate_builder_config(session, _principal(), _config())
        self.assertTrue(report.ok)
        # Should still produce a soft warning (no KB / no tools).
        codes = {issue.code for issue in report.issues}
        self.assertIn("no_knowledge_or_tools", codes)

    async def test_validate_fails_when_deployment_not_found(self) -> None:
        # _FakeSession returns empty rows → deployment lookup misses.
        session = _FakeSession()
        report = await validate_builder_config(
            session,
            _principal(),
            _config(deployment_id=uuid4(), routing_key=None),
        )
        self.assertFalse(report.ok)
        codes = {issue.code for issue in report.issues}
        self.assertIn("deployment_not_found", codes)

    async def test_validate_fails_when_deployment_inactive(self) -> None:
        deployment_id = uuid4()

        class _Dep:
            def __init__(self) -> None:
                self.is_active = False

        # ``first()`` returns a row whose [0] is the inactive deployment.
        session = _FakeSession(first_row=(_Dep(), None, None))

        # Patch the policy loader to return no rules so the validator
        # only reports the deployment issue (the policy engine would
        # otherwise receive tuple rows from the shared fake session).
        async def _no_rules(*_args: Any, **_kwargs: Any) -> list:
            return []

        with patch(
            "app.agents.builder.validator._load_policy_rules",
            new=_no_rules,
        ):
            report = await validate_builder_config(
                session,
                _principal(),
                _config(deployment_id=deployment_id, routing_key=None),
            )
        self.assertFalse(report.ok)
        codes = {issue.code for issue in report.issues}
        self.assertIn("deployment_inactive", codes)

    async def test_validate_records_mcp_server_not_active(self) -> None:
        # Patch mcp_service.list_mcp_servers_for_tenant to return empty list.
        from app.schemas.mcp import McpServerListResponse

        async def _empty_list(*_args: Any, **_kwargs: Any) -> McpServerListResponse:
            return McpServerListResponse(servers=[])

        with patch(
            "app.services.mcp_service.list_mcp_servers_for_tenant",
            new=_empty_list,
        ):
            session = _FakeSession()
            report = await validate_builder_config(
                session,
                _principal(),
                _config(mcp_server_keys=["missing-server"]),
            )
        codes = {issue.code for issue in report.issues}
        self.assertIn("mcp_server_not_active", codes)
        self.assertFalse(report.ok)

    async def test_max_tokens_exceeds_policy_blocks_compile(self) -> None:
        # Build a policy rule that allows the route but caps max_tokens at 256.
        from app.llm.policy import ModelPolicyRule

        rule = ModelPolicyRule(
            id=uuid4(),
            name="cap-256",
            scope_type="tenant",
            scope_id=None,
            effect="allow",
            allowed_models=(),
            allowed_routing_keys=("default-chat",),
            default_model_key=None,
            default_routing_key="default-chat",
            max_tokens=256,
            priority=10,
        )

        async def _fake_load_rules(*_args: Any, **_kwargs: Any) -> list[ModelPolicyRule]:
            return [rule]

        with patch(
            "app.agents.builder.validator._load_policy_rules",
            new=_fake_load_rules,
        ):
            session = _FakeSession()
            report = await validate_builder_config(
                session,
                _principal(),
                _config(max_tokens=1024),
            )
        self.assertFalse(report.ok)
        codes = {issue.code for issue in report.issues}
        self.assertIn("max_tokens_exceeds_policy", codes)


# ---------------------------------------------------------------------------
# Engine tests
# ---------------------------------------------------------------------------


class BuilderEngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_preview_returns_rendered_and_report(self) -> None:
        session = _FakeSession()
        rendered, report = await preview_builder_config(
            session,
            _principal(),
            AgentBuilderPreviewRequest(config=_config()),
        )
        self.assertTrue(report.ok)
        self.assertIn("AgentHive", rendered.system_prompt)

    async def test_compile_raises_on_error_issues(self) -> None:
        # Force an ERROR by referencing a missing deployment.
        session = _FakeSession()
        with self.assertRaises(BuilderValidationError) as ctx:
            await compile_builder_config(
                session,
                _principal(),
                _config(deployment_id=uuid4(), routing_key=None),
            )
        self.assertFalse(ctx.exception.report.ok)

    async def test_compile_succeeds_with_routing_key_only(self) -> None:
        session = _FakeSession()
        rendered = await compile_builder_config(session, _principal(), _config())
        self.assertIn("AgentHive", rendered.system_prompt)

    def test_builder_config_to_instance_metadata_round_trip(self) -> None:
        cfg = _config(knowledge_base_ids=[uuid4()], mcp_server_keys=["s1"])
        rendered = render_builder_config(cfg)
        metadata = builder_config_to_instance_metadata(cfg, rendered)
        self.assertIn("config", metadata)
        self.assertIn("rendered", metadata)
        self.assertEqual(metadata["config"]["name"], cfg.name)
        self.assertEqual(metadata["rendered"]["response_style"], "formal")


# ---------------------------------------------------------------------------
# ConfigurableAgent runtime tests
# ---------------------------------------------------------------------------


class ConfigurableAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_builder_config_returns_safe_fallback(self) -> None:
        agent = ConfigurableAgent()
        payload = AgentRunRequest(input="hello")
        response = await agent.run(payload, _principal())
        self.assertTrue(response.metadata["fallback"])
        self.assertEqual(response.metadata["fallback_reason"], "builder_config_missing")
        self.assertTrue(response.metadata["skipped_model_call"])

    async def test_greeting_shortcut_skips_llm(self) -> None:
        agent = ConfigurableAgent()
        cfg = _config(greeting_message="你好，我是售后小妹，请问有什么可以帮您？")
        payload = AgentRunRequest(
            input="你好",
            context={"builder_config": {"config": cfg.model_dump(mode="json")}},
        )
        response = await agent.run(payload, _principal())
        self.assertEqual(response.answer, cfg.greeting_message)
        self.assertTrue(response.metadata["greeting_intent"])
        self.assertTrue(response.metadata["skipped_model_call"])

    async def test_normal_run_invokes_gateway_and_returns_answer(self) -> None:
        agent = ConfigurableAgent()
        cfg = _config()
        payload = AgentRunRequest(
            input="我的订单还没到",
            context={"builder_config": {"config": cfg.model_dump(mode="json")}},
        )

        async def _fake_run_gateway(request, principal, **_kwargs):
            # run_gateway_chat returns app.schemas.llm.LLMChatResponse, whose
            # ``usage`` is LLMUsageResponse (compatible with AgentRunResponse).
            return type(
                "_ChatResponse",
                (),
                {
                    "request_id": "req-1",
                    "model_key": request.model_key or "default-model",
                    "content": "请提供订单号，我帮您查询。",
                    "usage": LLMUsageResponse(
                        input_tokens=10,
                        output_tokens=20,
                        total_tokens=30,
                        cost_usd=Decimal("0.001"),
                    ),
                    "provider_key": "openai",
                    "deployment_id": uuid4(),
                    "finish_reason": "stop",
                    "metadata": {},
                },
            )()

        with patch(
            "app.agents.custom_builder.agent.run_gateway_chat",
            new=_fake_run_gateway,
        ):
            response = await agent.run(payload, _principal())
        self.assertIn("订单号", response.answer)
        self.assertEqual(response.usage.total_tokens, 30)
        self.assertEqual(response.metadata["builder_config_name"], cfg.name)
        self.assertTrue(response.metadata["runtime_evidence"]["llm_gateway_called"])

    async def test_invalid_builder_config_returns_safe_fallback(self) -> None:
        agent = ConfigurableAgent()
        payload = AgentRunRequest(
            input="hi",
            context={"builder_config": {"config": {"name": "broken"}}},  # missing system_prompt
        )
        response = await agent.run(payload, _principal())
        self.assertTrue(response.metadata["fallback"])


# ---------------------------------------------------------------------------
# Registry test
# ---------------------------------------------------------------------------


class BuilderRegistryTests(unittest.TestCase):
    def test_configurable_agent_registered(self) -> None:
        agent = agent_registry.get("custom_builder")
        self.assertIsNotNone(agent)
        self.assertIsInstance(agent, ConfigurableAgent)
        self.assertEqual(agent.definition.required_module, "agent.custom_builder")

    def test_configurable_agent_appears_in_catalog(self) -> None:
        agents = agent_registry.list_agents()
        keys = {agent.definition.agent_key for agent in agents}
        self.assertIn("custom_builder", keys)


if __name__ == "__main__":
    unittest.main()
