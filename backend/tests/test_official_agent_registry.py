import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import HTTPException

from app.agents.official.configured import ConfiguredOfficialAgent, OfficialAgentConfig
from app.agents.orchestration import AgentOrchestrationRuntime
from app.agents.registry import agent_registry
from app.api.deps import Principal
from app.media.schemas import (
    MediaGenerationJobResponse,
    MediaGenerationJobStatus,
    MediaGenerationKind,
    MediaGenerationMode,
    MediaProviderType,
)
from app.schemas.agents import AgentRunRequest
from app.schemas.llm import LLMChatResponse, LLMUsageResponse
from app.services.agent_module_service import list_module_definitions
from app.services.agent_runtime_service import list_agent_catalog


class OfficialAgentRegistryTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_official_module_has_one_registered_runnable_agent(self) -> None:
        module_ids = {definition.id for definition in list_module_definitions()}
        registered_agents = agent_registry.list_agents()
        registered_agent_keys = [agent.definition.agent_key for agent in registered_agents]
        registered_modules = [agent.definition.required_module for agent in registered_agents]

        self.assertEqual(module_ids, set(registered_modules))
        self.assertEqual(len(module_ids), len(registered_modules))
        self.assertEqual(len(module_ids), len(set(registered_modules)))
        self.assertEqual(len(registered_agent_keys), len(set(registered_agent_keys)))

    async def test_agent_catalog_exposes_all_official_modules(self) -> None:
        catalog = await list_agent_catalog()
        module_ids = {definition.id for definition in list_module_definitions()}

        self.assertEqual(module_ids, {agent.required_module for agent in catalog.agents})
        self.assertIn("copywriting", {agent.agent_key for agent in catalog.agents})
        self.assertIn("hr_screening", {agent.agent_key for agent in catalog.agents})
        self.assertIn("image_generation", {agent.agent_key for agent in catalog.agents})
        self.assertIn("video_generation", {agent.agent_key for agent in catalog.agents})

    async def test_registered_agents_cover_module_catalog_contract(self) -> None:
        definitions_by_module = {
            definition.id: definition for definition in list_module_definitions()
        }

        for agent in agent_registry.list_agents():
            definition = definitions_by_module[agent.definition.required_module]
            with self.subTest(agent_key=agent.definition.agent_key):
                self.assertEqual(definition.name, agent.definition.name)
                self.assertEqual(definition.category, agent.definition.category)
                self.assertEqual(definition.version, agent.definition.version)
                self.assertTrue(
                    set(definition.capabilities).issubset(set(agent.definition.capabilities)),
                    f"{agent.definition.agent_key} must expose module capabilities from catalog.",
                )

    async def test_official_agents_declare_orchestration_runtime(self) -> None:
        runtime_by_agent = {
            agent.definition.agent_key: agent.definition.orchestration_runtime
            for agent in agent_registry.list_agents()
        }

        self.assertEqual(AgentOrchestrationRuntime.LANGGRAPH, runtime_by_agent["customer_service"])
        self.assertEqual(
            AgentOrchestrationRuntime.MEDIA_GATEWAY, runtime_by_agent["image_generation"]
        )
        self.assertEqual(
            AgentOrchestrationRuntime.MEDIA_GATEWAY, runtime_by_agent["video_generation"]
        )
        self.assertEqual(AgentOrchestrationRuntime.LANGCHAIN, runtime_by_agent["copywriting"])

    async def test_configured_official_agent_runs_through_llm_gateway(self) -> None:
        agent = ConfiguredOfficialAgent(
            OfficialAgentConfig(
                agent_key="copywriting",
                required_module="agent.copywriting",
                role_prompt="你负责生成营销文案。",
                output_prompt="请输出标题、正文和注意事项。",
            )
        )
        self.assertEqual("文案创作助手", agent.definition.name)
        self.assertIn("tone_variants", agent.definition.capabilities)
        principal = Principal(tenant_id=uuid4(), user_id=uuid4(), permissions={"agents:write"})
        gateway_response = LLMChatResponse(
            request_id="req-copywriting",
            provider_key="qwen",
            deployment_id=None,
            model_key="qwen-plus",
            content="标题：AgentH Hive 新品上新\n正文：突出核心卖点。\nrequest_id: req-hidden",
            finish_reason="stop",
            usage=LLMUsageResponse(
                input_tokens=12,
                output_tokens=8,
                total_tokens=20,
                cost_usd=Decimal("0.0002"),
            ),
            metadata={"provider_key": "qwen", "mock": True},
        )

        with patch(
            "app.agents.official.configured.run_gateway_chat",
            new=AsyncMock(return_value=gateway_response),
        ) as mocked_gateway:
            response = await agent.run(
                AgentRunRequest(
                    input="给保温杯写小红书文案",
                    context={
                        "department_id": str(uuid4()),
                        "knowledge_sources": [{"source_name": "brand.md", "score": 0.91}],
                    },
                    model_key="qwen-plus",
                ),
                principal,
                request_id="req-run",
            )

        mocked_gateway.assert_awaited_once()
        gateway_payload = mocked_gateway.await_args.args[0]
        self.assertEqual("qwen-plus", gateway_payload.model_key)
        self.assertEqual("copywriting", gateway_payload.metadata["agent_key"])
        self.assertEqual("agent.copywriting", gateway_payload.metadata["required_module"])
        self.assertIn("保温杯", gateway_payload.messages[1].content)
        self.assertEqual("标题：AgentHive 新品上新\n正文：突出核心卖点。", response.answer)
        self.assertEqual("copywriting", response.metadata["agent_key"])
        self.assertEqual("agent.copywriting", response.metadata["required_module"])
        self.assertEqual([{"source_name": "brand.md", "score": 0.91}], response.sources)
        runtime = response.metadata["runtime_evidence"]
        self.assertEqual("llm_gateway", runtime["execution"])
        self.assertTrue(runtime["llm_gateway_called"])
        self.assertEqual("qwen", runtime["provider_key"])
        self.assertEqual("qwen-plus", runtime["model_key"])
        self.assertEqual("req-copywriting", runtime["request_id"])
        self.assertEqual(20, runtime["total_tokens"])
        self.assertEqual("0.0002", runtime["cost_usd"])
        self.assertTrue(runtime["mock_adapter"])

    async def test_media_gateway_official_agent_creates_media_generation_job(self) -> None:
        agent = ConfiguredOfficialAgent(
            OfficialAgentConfig(
                agent_key="video_generation",
                required_module="agent.video_generation",
                role_prompt="你负责创建视频任务。",
                output_prompt="请创建视频生成任务。",
            )
        )
        principal = Principal(tenant_id=uuid4(), user_id=uuid4(), permissions={"agents:write"})
        media_job = MediaGenerationJobResponse(
            id=uuid4(),
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            department_id=uuid4(),
            agent_id=uuid4(),
            conversation_id=None,
            request_id="req-video-agent",
            kind=MediaGenerationKind.VIDEO,
            mode=MediaGenerationMode.NATURAL_LANGUAGE,
            status=MediaGenerationJobStatus.QUEUED,
            provider_key="volcengine_seedance",
            provider_type=MediaProviderType.VOLCENGINE_SEEDANCE,
            model_key="volcengine/seedance-2.0",
            routing_key="video-generation",
            prompt="生成一条 8 秒 30fps 1080p 的鞋子上脚视频",
            negative_prompt=None,
            reference_assets=[
                {"kind": "image", "bucket": "agenthive-assets", "object_key": "refs/shoe.png"}
            ],
            request_parameters={},
            normalized_parameters={"duration_seconds": 8, "fps": 30, "resolution": "1080p"},
            output_storage={"driver": "minio", "prefix": "generated/video_generation"},
            outputs=[],
            external_job_id=None,
            error_message=None,
            metadata={"estimated_cost_usd": "0.640000", "estimated_output_count": 1},
            created_at="2026-06-16T00:00:00Z",
            updated_at="2026-06-16T00:00:00Z",
            started_at=None,
            completed_at=None,
        )

        with (
            patch(
                "app.agents.official.configured.run_gateway_chat", new_callable=AsyncMock
            ) as mocked_gateway,
            patch(
                "app.agents.official.configured.create_media_generation_job",
                new=AsyncMock(return_value=media_job),
            ) as mocked_create_job,
            patch(
                "app.agents.official.configured.enqueue_media_generation_job_for_worker",
                new=AsyncMock(return_value=FakeMediaEnqueueResponse(task_id="celery-video-1")),
            ) as mocked_enqueue,
        ):
            response = await agent.run(
                AgentRunRequest(
                    input="生成一条 8 秒 30fps 1080p 的鞋子上脚视频",
                    context={
                        "media_mode": "natural_language",
                        "reference_assets": [
                            {
                                "kind": "image",
                                "bucket": "agenthive-assets",
                                "object_key": "refs/shoe.png",
                            }
                        ],
                        "department_id": str(media_job.department_id),
                        "duration_seconds": 8,
                        "fps": 30,
                        "resolution": "1080p",
                    },
                    routing_key="video-generation",
                ),
                principal,
                request_id="req-video-agent",
                session=object(),
            )

        mocked_gateway.assert_not_awaited()
        mocked_create_job.assert_awaited_once()
        mocked_enqueue.assert_awaited_once()
        media_payload = mocked_create_job.await_args.args[2]
        self.assertEqual(MediaGenerationKind.VIDEO, media_payload.kind)
        self.assertEqual(MediaGenerationMode.NATURAL_LANGUAGE, media_payload.mode)
        self.assertEqual("video-generation", media_payload.routing_key)
        self.assertEqual(8, media_payload.duration_seconds)
        self.assertEqual(30, media_payload.fps)
        self.assertEqual("official_agent_media_gateway", media_payload.metadata["source"])
        self.assertEqual(0, response.usage.total_tokens)
        self.assertEqual("volcengine/seedance-2.0", response.model_key)
        self.assertIn("已创建视频生成任务", response.answer)
        self.assertIn("任务已自动入队", response.answer)
        self.assertEqual(str(media_job.id), response.metadata["media_generation_job"]["id"])
        self.assertEqual("queued", response.metadata["media_generation_job"]["status"])
        self.assertTrue(response.metadata["media_generation_job"]["dispatch"]["queued"])
        self.assertEqual(
            "celery-video-1", response.metadata["media_generation_job"]["dispatch"]["task_id"]
        )
        runtime = response.metadata["runtime_evidence"]
        self.assertEqual("media_gateway", runtime["execution"])
        self.assertFalse(runtime["llm_gateway_called"])
        self.assertEqual("volcengine_seedance", runtime["provider_key"])
        self.assertEqual("volcengine/seedance-2.0", runtime["model_key"])
        self.assertEqual(str(media_job.id), runtime["media_generation_job_id"])
        self.assertTrue(runtime["queued"])
        self.assertEqual("celery-video-1", runtime["queue_task_id"])

    async def test_media_gateway_official_agent_can_create_without_enqueue(self) -> None:
        agent = ConfiguredOfficialAgent(
            OfficialAgentConfig(
                agent_key="image_generation",
                required_module="agent.image_generation",
                role_prompt="你负责创建图片任务。",
                output_prompt="请创建图片生成任务。",
            )
        )
        principal = Principal(tenant_id=uuid4(), user_id=uuid4(), permissions={"agents:write"})
        media_job = MediaGenerationJobResponse(
            id=uuid4(),
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            department_id=None,
            agent_id=None,
            conversation_id=None,
            request_id="req-image-agent",
            kind=MediaGenerationKind.IMAGE,
            mode=MediaGenerationMode.MANUAL_PROMPT,
            status=MediaGenerationJobStatus.QUEUED,
            provider_key="nano_banana",
            provider_type=MediaProviderType.NANO_BANANA,
            model_key="google/nano-banana",
            routing_key="image-generation",
            prompt="生成一张白底商品图",
            negative_prompt=None,
            reference_assets=[],
            request_parameters={},
            normalized_parameters={"image_count": 1},
            output_storage={"driver": "minio", "prefix": "generated/image_generation"},
            outputs=[],
            external_job_id=None,
            error_message=None,
            metadata={"estimated_cost_usd": "0.030000", "estimated_output_count": 1},
            created_at="2026-06-16T00:00:00Z",
            updated_at="2026-06-16T00:00:00Z",
            started_at=None,
            completed_at=None,
        )

        with (
            patch(
                "app.agents.official.configured.create_media_generation_job",
                new=AsyncMock(return_value=media_job),
            ),
            patch(
                "app.agents.official.configured.enqueue_media_generation_job_for_worker",
                new_callable=AsyncMock,
            ) as mocked_enqueue,
        ):
            response = await agent.run(
                AgentRunRequest(
                    input="生成一张白底商品图",
                    context={"media_dispatch_mode": "create_only", "media_mode": "manual_prompt"},
                    routing_key="image-generation",
                ),
                principal,
                request_id="req-image-agent",
                session=object(),
            )

        mocked_enqueue.assert_not_awaited()
        self.assertFalse(response.metadata["media_generation_job"]["dispatch"]["queued"])
        self.assertEqual(
            "created_without_enqueue",
            response.metadata["media_generation_job"]["dispatch"]["reason"],
        )

    async def test_media_gateway_official_agent_reports_queue_unavailable(self) -> None:
        agent = ConfiguredOfficialAgent(
            OfficialAgentConfig(
                agent_key="image_generation",
                required_module="agent.image_generation",
                role_prompt="你负责创建图片任务。",
                output_prompt="请创建图片生成任务。",
            )
        )
        principal = Principal(tenant_id=uuid4(), user_id=uuid4(), permissions={"agents:write"})
        media_job = MediaGenerationJobResponse(
            id=uuid4(),
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            department_id=None,
            agent_id=None,
            conversation_id=None,
            request_id="req-image-queue-down",
            kind=MediaGenerationKind.IMAGE,
            mode=MediaGenerationMode.NATURAL_LANGUAGE,
            status=MediaGenerationJobStatus.QUEUED,
            provider_key="nano_banana",
            provider_type=MediaProviderType.NANO_BANANA,
            model_key="google/nano-banana",
            routing_key="image-generation",
            prompt="生成一张商品图",
            negative_prompt=None,
            reference_assets=[],
            request_parameters={},
            normalized_parameters={"image_count": 1},
            output_storage={"driver": "minio", "prefix": "generated/image_generation"},
            outputs=[],
            external_job_id=None,
            error_message=None,
            metadata={"estimated_cost_usd": "0.030000", "estimated_output_count": 1},
            created_at="2026-06-16T00:00:00Z",
            updated_at="2026-06-16T00:00:00Z",
            started_at=None,
            completed_at=None,
        )

        with (
            patch(
                "app.agents.official.configured.create_media_generation_job",
                new=AsyncMock(return_value=media_job),
            ),
            patch(
                "app.agents.official.configured.enqueue_media_generation_job_for_worker",
                new=AsyncMock(
                    side_effect=HTTPException(
                        status_code=503, detail="Media generation queue is unavailable."
                    )
                ),
            ),
        ):
            response = await agent.run(
                AgentRunRequest(input="生成一张商品图", context={}, routing_key="image-generation"),
                principal,
                request_id="req-image-queue-down",
                session=object(),
            )

        dispatch = response.metadata["media_generation_job"]["dispatch"]
        self.assertFalse(dispatch["queued"])
        self.assertEqual("queue_unavailable", dispatch["reason"])
        self.assertEqual("enqueue_media_generation_job", dispatch["retry_action"])


class FakeMediaEnqueueResponse:
    queued = True

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id


if __name__ == "__main__":
    unittest.main()
