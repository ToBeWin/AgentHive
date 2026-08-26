from datetime import datetime, timezone
from decimal import Decimal
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.api.deps import Principal
from app.core.security import Permission
from app.models.conversation import ConversationMessage, ConversationSession
from app.schemas.agents import AgentRunResponse
from app.schemas.chat import ChatMessageCreateRequest
from app.schemas.llm import LLMUsageResponse
from app.services.chat_service import send_chat_message


class ChatAgentRuntimeBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_send_chat_message_routes_agent_session_through_agent_runtime(self) -> None:
        tenant_id = uuid4()
        user_id = uuid4()
        agent_id = uuid4()
        department_id = uuid4()
        conversation_id = uuid4()
        deployment_id = uuid4()
        conversation = ConversationSession(
            id=conversation_id,
            tenant_id=tenant_id,
            title="New AgentHive conversation",
            agent_id=agent_id,
            department_id=department_id,
            user_id=user_id,
            source="workbench",
            metadata_json={
                "agent_key": "customer_service",
                "agent_context": {
                    "knowledge_base_ids": [str(uuid4())],
                    "knowledge_top_k": 3,
                    "agent_instance_slug": "customer-success",
                },
            },
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session = FakeChatRuntimeSession(
            [
                FakeScalarOneOrNoneResult(conversation),
                FakeScalarAllResult([]),
            ]
        )
        agent_response = AgentRunResponse(
            answer="已根据知识库生成客户回复。",
            usage=LLMUsageResponse(
                input_tokens=12,
                output_tokens=8,
                total_tokens=20,
                cost_usd=Decimal("0.000020"),
            ),
            model_key="deepseek-v4-flash",
            request_id="run-agent-chat",
            sources=[
                {
                    "knowledge_base_name": "Customer Service SOP",
                    "source_name": "returns.md",
                    "score": 0.91,
                }
            ],
            metadata={
                "provider_key": "deepseek",
                "knowledge": {
                    "enabled": True,
                    "source_count": 1,
                    "confidence_level": "high",
                },
                "runtime_evidence": {
                    "execution": "llm_gateway",
                    "llm_gateway_called": True,
                    "provider_key": "deepseek",
                    "model_key": "deepseek-v4-flash",
                    "request_id": "run-agent-chat",
                    "fallback_attempt_count": 0,
                    "selected_route_reason": "priority_route",
                    "route_attempts": [
                        {
                            "attempt": 1,
                            "deployment_id": str(deployment_id),
                            "model_key": "deepseek-v4-flash",
                            "provider_key": "deepseek",
                            "routing_key": "cost-chat",
                            "status": "success",
                        }
                    ],
                },
            },
        )

        with (
            patch(
                "app.services.chat_service.run_agent", new=AsyncMock(return_value=agent_response)
            ) as mocked_run,
            patch("app.services.chat_service.record_audit_event", new=AsyncMock()) as mocked_audit,
        ):
            result = await send_chat_message(
                session,
                Principal(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    permissions={Permission.TENANT_ADMIN.value, Permission.CHAT_WRITE.value},
                ),
                conversation_id,
                ChatMessageCreateRequest(
                    content="客户要求退货，帮我回复",
                    metadata={
                        "workflow_key": "agentWorkflowCustomerReply",
                        "agent_context": {
                            "locale": "zh-CN",
                            "task_title": "退货回复",
                            "unsafe_override": "must_not_pass_to_agent",
                        },
                    },
                ),
                request_id="req-chat-agent",
            )

        mocked_run.assert_awaited_once()
        run_args = mocked_run.await_args.args
        agent_key = run_args[1]
        run_payload = run_args[2]
        self.assertEqual("customer_service", agent_key)
        self.assertEqual("客户要求退货，帮我回复", run_payload.input)
        self.assertEqual(str(agent_id), run_payload.context["agent_id"])
        self.assertEqual(str(conversation_id), run_payload.context["conversation_id"])
        self.assertEqual(str(department_id), run_payload.context["department_id"])
        self.assertEqual("workbench", run_payload.context["source"])
        self.assertEqual(3, run_payload.context["knowledge_top_k"])
        self.assertEqual("zh-CN", run_payload.context["locale"])
        self.assertEqual("退货回复", run_payload.context["task_title"])
        self.assertNotIn("unsafe_override", run_payload.context)

        self.assertEqual("已根据知识库生成客户回复。", result.assistant_message.content)
        self.assertEqual("deepseek-v4-flash", result.model_key)
        self.assertEqual("deepseek", result.provider_key)
        self.assertEqual(20, result.usage.total_tokens)
        self.assertEqual(1, len(result.sources))
        self.assertEqual("agent_runtime", result.metadata["chat_execution"])
        self.assertEqual("real_model_call", result.metadata["runtime_summary"]["status"])
        self.assertEqual("live_gateway", result.metadata["runtime_summary"]["adapter_mode"])
        self.assertTrue(result.metadata["runtime_summary"]["gateway_called"])
        self.assertFalse(result.metadata["runtime_summary"]["mock_adapter"])
        self.assertEqual("deepseek", result.metadata["runtime_summary"]["provider_key"])
        self.assertEqual("deepseek-v4-flash", result.metadata["runtime_summary"]["model_key"])
        self.assertEqual(1, result.metadata["runtime_summary"]["route_attempt_count"])
        self.assertEqual(1, result.metadata["runtime_summary"]["knowledge_source_count"])
        self.assertEqual("deepseek", result.metadata["runtime_evidence"]["provider_key"])
        self.assertEqual("agent_runtime", result.metadata["runtime_evidence"]["chat_execution"])
        self.assertEqual(
            "priority_route", result.metadata["runtime_evidence"]["selected_route_reason"]
        )
        self.assertEqual(0, result.metadata["runtime_evidence"]["fallback_attempt_count"])
        self.assertEqual(
            [
                {
                    "attempt": 1,
                    "deployment_id": str(deployment_id),
                    "model_key": "deepseek-v4-flash",
                    "provider_key": "deepseek",
                    "routing_key": "cost-chat",
                    "status": "success",
                }
            ],
            result.metadata["runtime_evidence"]["route_attempts"],
        )
        self.assertIn("agent_concurrency", result.metadata["runtime_evidence"])
        self.assertEqual(
            "agentWorkflowCustomerReply", conversation.metadata_json["last_task"]["workflow_key"]
        )

        added_messages = [row for row in session.added if isinstance(row, ConversationMessage)]
        self.assertEqual(["user", "assistant"], [row.role for row in added_messages])
        self.assertEqual("deepseek-v4-flash", added_messages[1].model_key)
        self.assertEqual("deepseek", added_messages[1].provider_key)
        self.assertEqual(20, added_messages[1].total_tokens)
        self.assertEqual("agent_runtime", added_messages[1].metadata_json["chat_execution"])
        self.assertEqual(
            "real_model_call", added_messages[1].metadata_json["runtime_summary"]["status"]
        )
        self.assertEqual(
            "live_gateway", added_messages[1].metadata_json["runtime_summary"]["adapter_mode"]
        )
        self.assertEqual(
            str(deployment_id),
            added_messages[1].metadata_json["runtime_evidence"]["route_attempts"][0][
                "deployment_id"
            ],
        )
        self.assertEqual(
            "cost-chat",
            added_messages[1].metadata_json["runtime_evidence"]["route_attempts"][0]["routing_key"],
        )
        self.assertEqual(1, session.commits)
        mocked_audit.assert_awaited_once()
        audit_details = mocked_audit.await_args.kwargs["details"]
        self.assertEqual("deepseek-v4-flash", audit_details["model_key"])
        self.assertEqual("deepseek", audit_details["provider_key"])
        self.assertEqual(20, audit_details["total_tokens"])
        self.assertEqual("agent_runtime", audit_details["runtime"]["execution"])
        self.assertTrue(audit_details["runtime"]["llm_gateway_called"])
        self.assertEqual("priority_route", audit_details["runtime"]["selected_route_reason"])
        self.assertEqual(0, audit_details["runtime"]["fallback_attempt_count"])
        self.assertEqual(str(deployment_id), audit_details["runtime"]["deployment_id"])
        self.assertEqual("cost-chat", audit_details["runtime"]["routing_key"])
        self.assertEqual(
            [
                {
                    "attempt": 1,
                    "deployment_id": str(deployment_id),
                    "model_key": "deepseek-v4-flash",
                    "provider_key": "deepseek",
                    "routing_key": "cost-chat",
                    "status": "success",
                    "error_code": None,
                }
            ],
            audit_details["runtime"]["route_attempts"],
        )


class FakeChatRuntimeSession:
    def __init__(self, execute_results: list[object]) -> None:
        self.execute_results = list(execute_results)
        self.added: list[object] = []
        self.commits = 0

    async def execute(self, _statement: object) -> object:
        if not self.execute_results:
            raise AssertionError("Unexpected execute call.")
        return self.execute_results.pop(0)

    def add(self, row: object) -> None:
        self.added.append(row)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        return None


class FakeScalarOneOrNoneResult:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object:
        return self.value


class FakeScalarAllResult:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def scalars(self) -> "FakeScalarAllResult":
        return self

    def all(self) -> list[object]:
        return self.values


if __name__ == "__main__":
    unittest.main()
