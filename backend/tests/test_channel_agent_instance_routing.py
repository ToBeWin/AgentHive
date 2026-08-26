from datetime import datetime, timezone
from decimal import Decimal
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.schemas.agents import AgentRunResponse
from app.schemas.channel import (
    ChannelMessageDirection,
    ChannelMessageType,
    ChannelStatus,
    ChannelType,
    InboundMessage,
    SignatureVerification,
)
from app.schemas.llm import LLMUsageResponse
from app.services.channel_service import ChannelRecord, _process_inbound_message


class ChannelAgentInstanceRoutingTest(unittest.IsolatedAsyncioTestCase):
    async def test_inbound_message_passes_channel_agent_instance_to_agent_runtime(self) -> None:
        agent_id = uuid4()
        channel = ChannelRecord(
            id=uuid4(),
            tenant_id=uuid4(),
            name="Web Widget",
            channel_type=ChannelType.WEB_WIDGET,
            channel_key="web-demo",
            agent_id=agent_id,
            created_by=uuid4(),
            status=ChannelStatus.ACTIVE,
            config={
                "agent_key": "customer_service",
                "agent_context": {"knowledge_top_k": 2},
            },
            secret=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        normalized = InboundMessage(
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            channel_type=channel.channel_type,
            channel_key=channel.channel_key,
            direction=ChannelMessageDirection.INBOUND,
            external_user_id="buyer-1",
            conversation_key="web:buyer-1",
            message_type=ChannelMessageType.TEXT,
            text="客户想换码",
            raw_payload={},
            signature=SignatureVerification(),
            received_at=datetime.now(timezone.utc),
        )
        response = AgentRunResponse(
            answer="可以换码。",
            usage=LLMUsageResponse(
                input_tokens=1,
                output_tokens=1,
                total_tokens=2,
                cost_usd=Decimal("0"),
            ),
            model_key="qwen-plus",
            request_id="run-channel-test",
            metadata={},
        )

        with patch(
            "app.services.channel_service.run_agent", new=AsyncMock(return_value=response)
        ) as mocked_run:
            result = await _process_inbound_message(
                FakeRollbackSession(),
                channel=channel,
                normalized=normalized,
                request_id="request-1",
                dry_run=True,
            )

        self.assertTrue(result.routed)
        mocked_run.assert_awaited_once()
        run_payload = mocked_run.await_args.args[2]
        self.assertEqual(str(agent_id), run_payload.context["agent_id"])
        self.assertEqual(2, run_payload.context["knowledge_top_k"])
        self.assertEqual(str(channel.id), run_payload.context["channel_id"])
        self.assertEqual("channel_gateway", result.runtime_evidence["channel_execution"])
        self.assertEqual(str(channel.id), result.runtime_evidence["channel_id"])
        self.assertTrue(result.runtime_evidence["routed"])
        self.assertEqual("customer_service", result.runtime_evidence["agent_key"])
        self.assertEqual("qwen-plus", result.runtime_evidence["model_key"])

    async def test_inbound_media_agent_result_exposes_media_job_metadata(self) -> None:
        media_job_id = uuid4()
        channel = ChannelRecord(
            id=uuid4(),
            tenant_id=uuid4(),
            name="Web Widget",
            channel_type=ChannelType.WEB_WIDGET,
            channel_key="web-media",
            agent_id=None,
            created_by=uuid4(),
            status=ChannelStatus.ACTIVE,
            config={"agent_key": "image_generation"},
            secret=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        normalized = InboundMessage(
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            channel_type=channel.channel_type,
            channel_key=channel.channel_key,
            direction=ChannelMessageDirection.INBOUND,
            external_user_id="buyer-media",
            conversation_key="web:buyer-media",
            message_type=ChannelMessageType.TEXT,
            text="生成一张商品图",
            raw_payload={},
            signature=SignatureVerification(),
            received_at=datetime.now(timezone.utc),
        )
        response = AgentRunResponse(
            answer="已创建图片生成任务。",
            usage=LLMUsageResponse(
                input_tokens=0, output_tokens=0, total_tokens=0, cost_usd=Decimal("0")
            ),
            model_key="google/nano-banana",
            request_id="run-channel-media",
            metadata={
                "provider_key": "nano_banana",
                "media_generation_job": {
                    "id": str(media_job_id),
                    "kind": "image",
                    "status": "queued",
                    "provider_key": "nano_banana",
                    "model_key": "google/nano-banana",
                    "routing_key": "image-generation",
                    "dispatch": {"queued": True, "task_id": "celery-image-1"},
                },
            },
        )

        with patch("app.services.channel_service.run_agent", new=AsyncMock(return_value=response)):
            result = await _process_inbound_message(
                FakeRollbackSession(),
                channel=channel,
                normalized=normalized,
                request_id="request-media",
                dry_run=True,
            )

        self.assertTrue(result.routed)
        self.assertEqual(str(media_job_id), result.metadata["media_generation_job"]["id"])
        self.assertEqual(
            "celery-image-1", result.metadata["media_generation_job"]["dispatch"]["task_id"]
        )
        self.assertEqual("channel_gateway", result.runtime_evidence["channel_execution"])
        self.assertEqual("nano_banana", result.runtime_evidence["provider_key"])
        self.assertEqual("google/nano-banana", result.runtime_evidence["model_key"])
        self.assertEqual(str(media_job_id), result.runtime_evidence["media_generation_job"]["id"])

    async def test_inbound_agent_runtime_exception_returns_safe_error_code(self) -> None:
        channel = ChannelRecord(
            id=uuid4(),
            tenant_id=uuid4(),
            name="Web Widget",
            channel_type=ChannelType.WEB_WIDGET,
            channel_key="web-demo",
            agent_id=None,
            created_by=uuid4(),
            status=ChannelStatus.ACTIVE,
            config={"agent_key": "customer_service"},
            secret=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        normalized = InboundMessage(
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            channel_type=channel.channel_type,
            channel_key=channel.channel_key,
            direction=ChannelMessageDirection.INBOUND,
            external_user_id="buyer-1",
            conversation_key="web:buyer-1",
            message_type=ChannelMessageType.TEXT,
            text="客户想换码",
            raw_payload={},
            signature=SignatureVerification(),
            received_at=datetime.now(timezone.utc),
        )
        sensitive_error = "provider failed with api_key=sk-test and base_url=https://llm.internal"

        with patch(
            "app.services.channel_service.run_agent",
            new=AsyncMock(side_effect=RuntimeError(sensitive_error)),
        ):
            result = await _process_inbound_message(
                FakeRollbackSession(),
                channel=channel,
                normalized=normalized,
                request_id="request-1",
                dry_run=True,
            )

        self.assertFalse(result.routed)
        self.assertEqual("customer_service", result.agent_key)
        self.assertEqual("processing_exception", result.error)
        self.assertEqual("channel_gateway", result.runtime_evidence["channel_execution"])
        self.assertFalse(result.runtime_evidence["routed"])
        self.assertEqual("processing_exception", result.runtime_evidence["error"])
        self.assertNotIn("sk-test", str(result))
        self.assertNotIn("llm.internal", str(result))


class FakeRollbackSession:
    async def rollback(self) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
