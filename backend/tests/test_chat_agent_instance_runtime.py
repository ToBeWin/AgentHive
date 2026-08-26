from datetime import datetime, timezone
from decimal import Decimal
import json
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import HTTPException

from app.api.deps import Principal
from app.models.audit_log import AuditLog
from app.models.agent_module import AgentInstance
from app.models.conversation import ConversationSession
from app.services.agent_runtime_service import AgentRunAuthorization
from app.schemas.agents import AgentRunResponse
from app.schemas.chat import ChatMessageCreateRequest
from app.schemas.llm import LLMUsageResponse
from app.services.chat_service import send_chat_message, stream_chat_message


class ChatAgentInstanceRuntimeTest(unittest.IsolatedAsyncioTestCase):
    async def test_stream_chat_message_emits_status_events_and_single_final_delta(self) -> None:
        tenant_id = uuid4()
        user_id = uuid4()
        conversation_id = uuid4()
        now = datetime.now(timezone.utc)

        async def fake_gateway_stream(*_args, **_kwargs):
            yield "我在，可以继续处理。"

        with patch("app.services.chat_service.run_gateway_chat_stream", new=fake_gateway_stream):
            chunks = [
                chunk
                async for chunk in stream_chat_message(
                    FakeChatSession(
                        ConversationSession(
                            id=conversation_id,
                            tenant_id=tenant_id,
                            title="stream",
                            user_id=user_id,
                            source="chat_console",
                            metadata_json={},
                            created_at=now,
                            updated_at=now,
                        )
                    ),
                    Principal(tenant_id=tenant_id, user_id=user_id, permissions={"chat:write"}),
                    conversation_id,
                    ChatMessageCreateRequest(content="你还在吗"),
                    request_id="request-stream",
                )
            ]

        events = [_decode_sse(chunk) for chunk in chunks]
        self.assertEqual(
            ["status", "status", "delta", "status", "metadata", "done"],
            [event for event, _ in events],
        )
        self.assertEqual("accepted", events[0][1]["stage"])
        self.assertEqual("runtime", events[1][1]["stage"])
        self.assertEqual("我在，可以继续处理。", events[2][1]["content"])
        self.assertEqual("persisted", events[3][1]["stage"])
        self.assertIn("message_id", events[5][1])

    async def test_stream_chat_message_emits_structured_error_event(self) -> None:
        tenant_id = uuid4()
        user_id = uuid4()
        conversation_id = uuid4()
        now = datetime.now(timezone.utc)
        error = HTTPException(
            status_code=429,
            detail={
                "code": "agent_concurrency_limited",
                "message": "Agent execution concurrency limit exceeded. Please retry shortly.",
                "scope": "user",
                "limits": {"tenant": 40, "user": 4, "agent": 12},
                "request_id": "request-limited",
                "retry_after_seconds": 1,
            },
            headers={"Retry-After": "1"},
        )

        async def raising_gateway_stream(*_args, **_kwargs):
            raise error
            yield  # unreachable — makes this an async generator

        with patch("app.services.chat_service.run_gateway_chat_stream", new=raising_gateway_stream):
            chunks = [
                chunk
                async for chunk in stream_chat_message(
                    FakeChatSession(
                        ConversationSession(
                            id=conversation_id,
                            tenant_id=tenant_id,
                            title="stream",
                            user_id=user_id,
                            source="chat_console",
                            metadata_json={},
                            created_at=now,
                            updated_at=now,
                        )
                    ),
                    Principal(tenant_id=tenant_id, user_id=user_id, permissions={"chat:write"}),
                    conversation_id,
                    ChatMessageCreateRequest(content="继续处理"),
                    request_id="request-limited",
                )
            ]

        events = [_decode_sse(chunk) for chunk in chunks]
        self.assertEqual(["status", "status", "status", "error"], [event for event, _ in events])
        self.assertEqual("failed", events[2][1]["state"])
        self.assertEqual(429, events[3][1]["status"])
        self.assertEqual("agent_concurrency_limited", events[3][1]["detail"]["code"])
        self.assertEqual("user", events[3][1]["detail"]["scope"])
        self.assertEqual(1, events[3][1]["detail"]["retry_after_seconds"])

    async def test_bound_chat_session_runs_agent_runtime(self) -> None:
        tenant_id = uuid4()
        user_id = uuid4()
        conversation_id = uuid4()
        agent_id = uuid4()
        department_id = uuid4()
        channel_id = uuid4()
        knowledge_base_id = uuid4()
        forged_agent_id = uuid4()
        forged_department_id = uuid4()
        conversation = ConversationSession(
            id=conversation_id,
            tenant_id=tenant_id,
            title="售后客服会话",
            agent_id=agent_id,
            channel_id=channel_id,
            user_id=user_id,
            department_id=department_id,
            source="chat_console",
            metadata_json={
                "agent_key": "customer_service",
                "agent_context": {
                    "knowledge_base_ids": [str(knowledge_base_id)],
                    "knowledge_guardrail_mode": "strict",
                    "knowledge_top_k": 5,
                },
            },
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        agent_response = AgentRunResponse(
            answer="可以换码。",
            usage=LLMUsageResponse(
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
                cost_usd=Decimal("0.0001"),
            ),
            model_key="qwen-plus",
            request_id="run-chat-agent",
            sources=[{"source_name": "售后政策.md", "score": 0.9}],
            metadata={
                "knowledge": {
                    "confidence_level": "high",
                    "enabled": True,
                    "max_score": 0.9,
                    "requires_human_review": False,
                    "review_reason": "strong_source_match",
                    "source_count": 1,
                },
                "license_gate": "enforced",
                "provider_key": "qwen",
            },
        )
        session = FakeChatSession(conversation)

        with patch(
            "app.services.chat_service.run_agent", new=AsyncMock(return_value=agent_response)
        ) as mocked_run:
            result = await send_chat_message(
                session,
                Principal(tenant_id=tenant_id, user_id=user_id, permissions={"chat:write"}),
                conversation_id,
                ChatMessageCreateRequest(
                    content="客户想换码",
                    max_tokens=512,
                    metadata={
                        "agent_context": {
                            "agent_id": str(forged_agent_id),
                            "department_id": str(forged_department_id),
                            "channel_id": str(uuid4()),
                            "knowledge_base_ids": [],
                            "knowledge_guardrail_mode": "off",
                            "knowledge_top_k": 1,
                            "workflow_key": "agentWorkflowCustomerReply",
                        }
                    },
                ),
                request_id="request-1",
            )

        mocked_run.assert_awaited_once()
        run_payload = mocked_run.await_args.args[2]
        self.assertEqual(str(agent_id), run_payload.context["agent_id"])
        self.assertEqual(str(conversation_id), run_payload.context["conversation_id"])
        self.assertEqual(str(department_id), run_payload.context["department_id"])
        self.assertEqual(str(channel_id), run_payload.context["channel_id"])
        self.assertEqual([str(knowledge_base_id)], run_payload.context["knowledge_base_ids"])
        self.assertEqual("strict", run_payload.context["knowledge_guardrail_mode"])
        self.assertEqual(5, run_payload.context["knowledge_top_k"])
        self.assertEqual("agentWorkflowCustomerReply", run_payload.context["workflow_key"])
        self.assertEqual("可以换码。", result.assistant_message.content)
        self.assertEqual("qwen", result.provider_key)
        self.assertEqual([{"source_name": "售后政策.md", "score": 0.9}], result.sources)
        self.assertEqual("agent_runtime", result.metadata["chat_execution"])
        self.assertEqual(
            [{"source_name": "售后政策.md", "score": 0.9}], result.metadata["agent_sources"]
        )
        self.assertEqual("high", result.metadata["knowledge"]["confidence_level"])
        self.assertEqual("agent_runtime", result.metadata["runtime_evidence"]["execution"])
        self.assertEqual("agent_runtime", result.metadata["runtime_evidence"]["chat_execution"])
        self.assertTrue(result.metadata["runtime_evidence"]["llm_gateway_called"])
        self.assertEqual("qwen", result.metadata["runtime_evidence"]["provider_key"])
        self.assertEqual("qwen-plus", result.metadata["runtime_evidence"]["model_key"])
        self.assertEqual(15, result.metadata["runtime_evidence"]["total_tokens"])
        self.assertTrue(result.metadata["runtime_evidence"]["agent_concurrency"]["enabled"])
        self.assertTrue(result.metadata["runtime_evidence"]["agent_concurrency"]["acquired"])
        self.assertEqual(
            40, result.metadata["runtime_evidence"]["agent_concurrency"]["limits"]["tenant"]
        )
        self.assertEqual(
            1, result.metadata["runtime_evidence"]["agent_concurrency"]["active"]["tenant"]
        )
        self.assertEqual(
            result.metadata["agent_concurrency"],
            result.metadata["runtime_evidence"]["agent_concurrency"],
        )
        self.assertFalse(result.assistant_message.metadata["knowledge"]["requires_human_review"])
        self.assertEqual(
            result.metadata["agent_concurrency"],
            result.assistant_message.metadata["agent_concurrency"],
        )
        audit_events = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual("chat.message.send", audit_events[0].action)
        self.assertEqual(
            result.metadata["agent_concurrency"], audit_events[0].details["agent_concurrency"]
        )
        self.assertEqual("客户想换码", conversation.metadata_json["last_task"]["title"])
        self.assertEqual("completed", conversation.metadata_json["last_task"]["status"])
        self.assertEqual(
            "agentWorkflowCustomerReply", conversation.metadata_json["last_task"]["workflow_key"]
        )
        self.assertEqual("qwen-plus", conversation.metadata_json["last_task"]["model_key"])
        self.assertEqual("qwen", conversation.metadata_json["last_task"]["provider_key"])
        self.assertEqual(15, conversation.metadata_json["last_task"]["total_tokens"])

    async def test_bound_chat_session_exposes_media_generation_job_provider(self) -> None:
        tenant_id = uuid4()
        user_id = uuid4()
        conversation_id = uuid4()
        agent_id = uuid4()
        conversation = ConversationSession(
            id=conversation_id,
            tenant_id=tenant_id,
            title="图片生成会话",
            agent_id=agent_id,
            channel_id=None,
            user_id=user_id,
            department_id=None,
            source="chat_console",
            metadata_json={"agent_key": "image_generation"},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        agent_response = AgentRunResponse(
            answer="已创建图片生成任务。",
            usage=LLMUsageResponse(
                input_tokens=0, output_tokens=0, total_tokens=0, cost_usd=Decimal("0")
            ),
            model_key="google/nano-banana",
            request_id="run-chat-media-agent",
            sources=[],
            metadata={
                "media_generation_job": {
                    "id": str(uuid4()),
                    "kind": "image",
                    "status": "queued",
                    "provider_key": "nano_banana",
                    "model_key": "google/nano-banana",
                    "dispatch": {"queued": True, "task_id": "celery-image-1"},
                }
            },
        )
        session = FakeChatSession(conversation)

        with patch(
            "app.services.chat_service.run_agent", new=AsyncMock(return_value=agent_response)
        ):
            result = await send_chat_message(
                session,
                Principal(tenant_id=tenant_id, user_id=user_id, permissions={"chat:write"}),
                conversation_id,
                ChatMessageCreateRequest(content="生成一张商品图", max_tokens=512),
                request_id="request-media",
            )

        self.assertEqual("nano_banana", result.provider_key)
        self.assertEqual("nano_banana", result.assistant_message.provider_key)
        self.assertEqual(
            "celery-image-1", result.metadata["media_generation_job"]["dispatch"]["task_id"]
        )
        self.assertEqual("agent_runtime", result.metadata["runtime_evidence"]["execution"])
        self.assertEqual("nano_banana", result.metadata["runtime_evidence"]["provider_key"])
        self.assertEqual("google/nano-banana", result.metadata["runtime_evidence"]["model_key"])

    async def test_bound_chat_session_rejects_unready_agent_instance_before_llm_runtime(
        self,
    ) -> None:
        tenant_id = uuid4()
        user_id = uuid4()
        conversation_id = uuid4()
        agent_id = uuid4()
        conversation = ConversationSession(
            id=conversation_id,
            tenant_id=tenant_id,
            title="文案会话",
            agent_id=agent_id,
            channel_id=None,
            user_id=user_id,
            department_id=None,
            source="chat_console",
            metadata_json={"agent_key": "copywriting"},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        instance = AgentInstance(
            id=agent_id,
            tenant_id=tenant_id,
            name="Copy Bot",
            slug="copy-bot",
            agent_key="copywriting",
            module_key="agent.copywriting",
            status="active",
            visibility="tenant",
            model_routing_key="missing-route",
        )
        session = FakeQueuedChatSession(
            [
                FakeExecuteResult(conversation),
                FakeExecuteResult(rows=[]),
                FakeExecuteResult(rows=[]),
                FakeExecuteResult(instance),
                FakeExecuteResult(rows=[]),
                FakeExecuteResult(rows=[]),
            ]
        )

        with (
            patch(
                "app.services.agent_runtime_service._authorize_agent_run",
                new=AsyncMock(
                    return_value=AgentRunAuthorization(
                        license_gate="enforced",
                        licensed=True,
                        installed=True,
                        enabled=True,
                        reason="active_license_and_enabled_module",
                    )
                ),
            ),
            patch("app.services.chat_service.run_gateway_chat", new=AsyncMock()) as gateway_chat,
        ):
            with self.assertRaises(HTTPException) as raised:
                await send_chat_message(
                    session,
                    Principal(tenant_id=tenant_id, user_id=user_id, permissions={"chat:write"}),
                    conversation_id,
                    ChatMessageCreateRequest(content="起草客户回复"),
                    request_id="request-unready-agent",
                )

        self.assertEqual(409, raised.exception.status_code)
        self.assertEqual("agent_instance_not_ready", raised.exception.detail["code"])
        self.assertIn("model_route_unavailable", raised.exception.detail["reasons"])
        gateway_chat.assert_not_awaited()
        self.assertEqual([], session.added)


class FakeChatSession:
    def __init__(self, conversation: ConversationSession):
        self.conversation = conversation
        self.added = []
        self.execute_count = 0

    async def execute(self, _statement):
        self.execute_count += 1
        if self.execute_count == 1:
            return FakeExecuteResult(self.conversation)
        return FakeExecuteResult()

    async def get(self, _model, _id):
        return self.conversation

    def add(self, row):
        self.added.append(row)

    async def commit(self):
        return None

    async def rollback(self):
        return None


class FakeQueuedChatSession(FakeChatSession):
    def __init__(self, execute_results):
        self.execute_results = list(execute_results)
        self.added = []
        self.execute_count = 0

    async def execute(self, _statement):
        self.execute_count += 1
        if not self.execute_results:
            raise AssertionError("Unexpected execute call.")
        return self.execute_results.pop(0)

    async def get(self, _model, _id):
        raise AssertionError("Unexpected get call.")


class FakeExecuteResult:
    def __init__(self, scalar_value=None, rows=None):
        self.scalar_value = scalar_value
        self.rows = list(rows or [])

    def scalar_one_or_none(self):
        return self.scalar_value

    def scalars(self):
        return self

    def all(self):
        return self.rows


def _decode_sse(chunk: str) -> tuple[str, dict]:
    lines = chunk.strip().splitlines()
    event = next(
        line.replace("event:", "", 1).strip() for line in lines if line.startswith("event:")
    )
    data = "\n".join(
        line.replace("data:", "", 1).strip() for line in lines if line.startswith("data:")
    )
    return event, json.loads(data)


if __name__ == "__main__":
    unittest.main()
