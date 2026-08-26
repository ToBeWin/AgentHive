from decimal import Decimal
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.agents.langchain_runtime import render_chat_prompt_messages
from app.agents.official.customer_service.agent import CustomerServiceAgent
from app.agents.official.customer_service.graph import (
    run_customer_service_mock_graph,
    run_customer_service_prep,
)
from app.agents.runtime_dependencies import agent_runtime_dependency_status
from app.api.deps import Principal
from app.schemas.agents import AgentRunRequest
from app.schemas.llm import LLMChatResponse, LLMUsageResponse


class AgentOrchestrationRuntimeTests(unittest.TestCase):
    def test_langchain_prompt_renderer_builds_gateway_messages(self) -> None:
        messages = render_chat_prompt_messages(
            system_prompt="你是 {role}。",
            user_prompt="任务：{task}",
            variables={"role": "客服助手", "task": "回答换货规则"},
        )

        self.assertEqual("system", messages[0].role)
        self.assertIn("客服助手", messages[0].content)
        self.assertEqual("user", messages[1].role)
        self.assertIn("回答换货规则", messages[1].content)

    def test_langgraph_customer_service_graph_selects_relevant_source(self) -> None:
        state = run_customer_service_mock_graph(
            query="客户说鞋子尺码偏小，想换大一码",
            sources=[
                {"source_name": "sop.md", "text": "客户咨询物流延迟时，先表达歉意并确认订单号。"},
                {"source_name": "sop.md", "text": "客户申请退款时，先核验商品状态和签收时间。"},
                {
                    "source_name": "sop.md",
                    "text": "鞋子尺码偏小需要换大一码时，若客户签收后7天内、商品未穿着、吊牌和包装完整，可以引导客户发起换货。",
                },
            ],
        )

        self.assertIn("尺码偏小", state["answer"])
        self.assertFalse(state["requires_human"])
        self.assertIn("换大一码", state["selected_source"]["text"])
        self.assertGreaterEqual(len(state.get("graph_trace") or []), 4)

    def test_langgraph_customer_service_prep_flags_escalation_risk(self) -> None:
        state = run_customer_service_prep(
            query="我要投诉你们，准备找律师起诉",
            sources=[{"source_name": "sop.md", "text": "退款需要先核验订单状态。"}],
        )

        self.assertEqual("escalation_risk", state["intent"])
        self.assertTrue(state["requires_human"])
        self.assertLess(float(state["confidence"] or 1), 0.55)
        self.assertTrue(
            any(step["node"] == "check_confidence" for step in state.get("graph_trace") or [])
        )

    def test_runtime_dependencies_are_installed_in_development_environment(self) -> None:
        status = agent_runtime_dependency_status()

        self.assertEqual("healthy", status["status"])
        self.assertEqual([], status["details"]["missing"])


class CustomerServiceRuntimeEvidenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_customer_service_agent_exposes_llm_gateway_runtime_evidence(self) -> None:
        deployment_id = uuid4()
        response = LLMChatResponse(
            request_id="llm-customer-1",
            model_key="deepseek-v4-flash",
            content="您好，可以先核验订单状态后回复客户。",
            usage=LLMUsageResponse(
                input_tokens=12,
                output_tokens=8,
                total_tokens=20,
                cost_usd=Decimal("0.0002"),
            ),
            provider_key="deepseek",
            deployment_id=deployment_id,
            finish_reason="stop",
            metadata={
                "fallback_attempt_count": 1,
                "mock": False,
                "route_attempts": [
                    {"attempt": 1, "provider_key": "mimo", "status": "error"},
                    {"attempt": 2, "provider_key": "deepseek", "status": "success"},
                ],
                "selected_route_reason": "fallback",
            },
        )

        with patch(
            "app.agents.official.customer_service.agent.run_gateway_chat",
            new=AsyncMock(return_value=response),
        ):
            result = await CustomerServiceAgent().run(
                AgentRunRequest(
                    input="客户问订单什么时候发货", context={}, routing_key="customer-service"
                ),
                Principal(tenant_id=uuid4(), user_id=uuid4(), permissions={"agents:write"}),
                request_id="agent-customer-1",
                session=object(),
            )

        evidence = result.metadata["runtime_evidence"]
        self.assertEqual("llm_gateway", evidence["execution"])
        self.assertTrue(evidence["llm_gateway_called"])
        self.assertEqual("customer_service", evidence["agent_key"])
        self.assertEqual("deepseek", evidence["provider_key"])
        self.assertEqual("deepseek-v4-flash", evidence["model_key"])
        self.assertEqual(str(deployment_id), evidence["deployment_id"])
        self.assertEqual(1, evidence["fallback_attempt_count"])
        self.assertEqual("fallback", evidence["selected_route_reason"])
        self.assertEqual(2, len(evidence["route_attempts"]))
        self.assertFalse(evidence["mock_adapter"])
        self.assertEqual("knowledge_query", evidence["langgraph_intent"])
        self.assertIsInstance(evidence["langgraph_trace"], list)
        self.assertGreaterEqual(len(evidence["langgraph_trace"]), 3)


if __name__ == "__main__":
    unittest.main()
