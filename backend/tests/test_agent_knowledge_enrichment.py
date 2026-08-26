import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

from app.api.deps import Principal
from app.agents.official.customer_service.agent import CustomerServiceAgent
from app.models.agent_module import AgentInstance
from app.models.knowledge import KnowledgeBase
from app.rag.schemas import RAGEngineType
from app.schemas.agents import AgentRunRequest, AgentRunResponse
from app.schemas.knowledge import KnowledgeBaseVisibility
from app.schemas.knowledge import RetrievalSourceResponse, RetrievalTestResponse
from app.schemas.llm import LLMUsageResponse
from app.services.agent_runtime_service import (
    AgentRunAuthorization,
    MAX_KNOWLEDGE_CONTEXT_SOURCE_CHARS,
    _apply_agent_instance_defaults,
    _agent_instance_diagnostics_from_context,
    _agent_run_audit_details,
    _record_agent_run_audit,
    _enrich_with_knowledge_context,
    _format_knowledge_context,
    _knowledge_confidence_diagnostics,
    _knowledge_guardrail_answer,
    _knowledge_base_ids_from_context,
    _validate_agent_instance_knowledge_config,
    run_agent,
)


class AgentKnowledgeEnrichmentTest(unittest.IsolatedAsyncioTestCase):
    async def test_customer_service_mock_answer_prefers_relevant_knowledge_source(self) -> None:
        answer = CustomerServiceAgent()._mock_knowledge_answer(
            AgentRunRequest(input="客户问鞋子尺码偏小，想换大一码，店铺规则怎么回复？"),
            [
                {"source_name": "sop.md", "text": "客户咨询物流延迟时，先表达歉意并确认订单号。"},
                {"source_name": "sop.md", "text": "客户申请退款时，先核验商品状态和签收时间。"},
                {
                    "source_name": "sop.md",
                    "text": "鞋子尺码偏小需要换大一码时，若客户签收后7天内、商品未穿着、吊牌和包装完整，可以引导客户发起换货。",
                },
            ],
        )

        self.assertIn("尺码偏小", answer)
        self.assertIn("换大一码", answer)

    async def test_customer_service_answer_strips_run_diagnostics_for_general_probe(self) -> None:
        answer = CustomerServiceAgent()._clean_answer(
            "是的，我在线，随时为您服务。\n客服备注：知识库内容均不涉及此问题，无需引用。",
            AgentRunRequest(input="你是否在线？"),
        )

        self.assertEqual("是的，我在线，随时为您服务。", answer)

    async def test_customer_service_answer_falls_back_when_diagnostic_note_has_no_reply(
        self,
    ) -> None:
        answer = CustomerServiceAgent()._clean_answer(
            "客服备注：知识库内容均不涉及此问题，无需引用。",
            AgentRunRequest(input="你是否在线？"),
        )

        self.assertEqual("我在线，随时可以协助处理客户服务问题。", answer)

    async def test_customer_service_answer_keeps_business_note_for_customer_issue(self) -> None:
        answer = CustomerServiceAgent()._clean_answer(
            "您好，建议先核对订单状态。\n客服备注：请确认订单号和物流轨迹。",
            AgentRunRequest(input="客户说订单物流一直没有更新，怎么回复？"),
        )

        self.assertIn("客服备注", answer)
        self.assertIn("物流轨迹", answer)

    async def test_agent_instance_knowledge_config_validates_accessible_base(self) -> None:
        principal = Principal(
            tenant_id=uuid4(),
            user_id=uuid4(),
            permissions={"tenant.admin", "agents:write"},
        )
        base = KnowledgeBase(
            id=uuid4(),
            tenant_id=principal.tenant_id,
            name="售后政策",
            visibility=KnowledgeBaseVisibility.TENANT.value,
            department_ids=[],
            rag_engine=RAGEngineType.PGVECTOR.value,
            retrieval_config={},
            status="active",
            document_count=1,
            tags=[],
            metadata_json={"owner_user_id": str(principal.user_id)},
        )

        await _validate_agent_instance_knowledge_config(
            FakeKnowledgeBindingSession(base),
            principal,
            {"knowledge_base_ids": [str(base.id)]},
        )

    async def test_agent_instance_knowledge_config_rejects_missing_base(self) -> None:
        principal = Principal(
            tenant_id=uuid4(),
            user_id=uuid4(),
            permissions={"tenant.admin", "agents:write"},
        )

        with self.assertRaises(Exception) as raised:
            await _validate_agent_instance_knowledge_config(
                FakeKnowledgeBindingSession(None),
                principal,
                {"knowledge_base_ids": [str(uuid4())]},
            )

        self.assertIn("Knowledge base not found", str(raised.exception))

    async def test_agent_instance_defaults_are_applied_before_retrieval(self) -> None:
        tenant_id = uuid4()
        instance = AgentInstance(
            id=uuid4(),
            tenant_id=tenant_id,
            name="售后客服",
            slug="after-sales",
            agent_key="customer_service",
            module_key="agent.customer_service",
            status="active",
            config={"knowledge_base_ids": ["kb-default"], "knowledge_top_k": 4},
            model_routing_key="customer-service-route",
            model_key="qwen-plus",
        )
        payload = AgentRunRequest(
            input="客户想换码",
            context={"agent_id": str(instance.id), "knowledge_top_k": 2},
        )

        enriched = await _apply_agent_instance_defaults(
            FakeAgentInstanceSession(instance),
            payload,
            Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"}),
            agent_key="customer_service",
            required_module="agent.customer_service",
        )

        self.assertEqual(["kb-default"], enriched.context["knowledge_base_ids"])
        self.assertEqual(2, enriched.context["knowledge_top_k"])
        self.assertEqual("after-sales", enriched.context["agent_instance_slug"])
        self.assertEqual("tenant", enriched.context["visibility"])
        self.assertEqual("customer-service-route", enriched.routing_key)
        self.assertEqual("qwen-plus", enriched.model_key)

    async def test_agent_instance_defaults_do_not_override_explicit_knowledge_ids(self) -> None:
        tenant_id = uuid4()
        instance = AgentInstance(
            id=uuid4(),
            tenant_id=tenant_id,
            name="售后客服",
            slug="after-sales",
            agent_key="customer_service",
            module_key="agent.customer_service",
            status="active",
            config={"knowledge_base_ids": ["kb-default"]},
        )
        payload = AgentRunRequest(
            input="客户想换码",
            context={"agent_id": str(instance.id), "knowledge_base_ids": ["kb-explicit"]},
        )

        enriched = await _apply_agent_instance_defaults(
            FakeAgentInstanceSession(instance),
            payload,
            Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"}),
            agent_key="customer_service",
            required_module="agent.customer_service",
        )

        self.assertEqual(["kb-explicit"], enriched.context["knowledge_base_ids"])

    async def test_run_agent_applies_instance_model_route_and_context_before_official_agent(
        self,
    ) -> None:
        tenant_id = uuid4()
        user_id = uuid4()
        department_id = uuid4()
        knowledge_base_id = uuid4()
        instance = AgentInstance(
            id=uuid4(),
            tenant_id=tenant_id,
            name="MiMo 售后客服",
            slug="mimo-after-sales",
            agent_key="customer_service",
            module_key="agent.customer_service",
            status="active",
            visibility="department",
            department_id=department_id,
            owner_user_id=user_id,
            model_key="mimo-v2.5-pro",
            model_routing_key="mimo-after-sales-route",
            config={
                "knowledge_base_ids": [str(knowledge_base_id)],
                "knowledge_guardrail_mode": "advisory",
                "knowledge_top_k": 4,
                "workflow_key": "agentWorkflowCustomerReply",
            },
        )
        principal = Principal(
            tenant_id=tenant_id,
            user_id=user_id,
            permissions={"tenant.admin", "agents:write", "knowledge:read"},
        )
        authorization = AgentRunAuthorization(
            license_gate="enforced",
            licensed=True,
            installed=True,
            enabled=True,
            reason="active_license_and_enabled_module",
        )
        retrieval = RetrievalTestResponse(
            knowledge_base_id=knowledge_base_id,
            query="客户说鞋子尺码偏小，想换大一码",
            engine=RAGEngineType.PGVECTOR,
            elapsed_ms=8,
            results=[],
            diagnostics={
                "knowledge_base_name": "售后政策",
                "knowledge_base_visibility": "department",
            },
        )
        agent = FakeGuardrailAgent(required_module="agent.customer_service")

        with (
            patch("app.services.agent_runtime_service.agent_registry.get", return_value=agent),
            patch(
                "app.services.agent_runtime_service._authorize_agent_run",
                new=AsyncMock(return_value=authorization),
            ),
            patch(
                "app.services.agent_runtime_service.run_retrieval_test",
                new=AsyncMock(return_value=retrieval),
            ) as retrieve,
            patch(
                "app.services.agent_runtime_service._record_agent_run_audit", new=AsyncMock()
            ) as audit,
            patch(
                "app.services.agent_runtime_service._record_knowledge_retrieve_audit",
                new=AsyncMock(),
            ),
        ):
            response = await run_agent(
                session=FakeAgentInstanceSession(instance),
                agent_key="customer_service",
                payload=AgentRunRequest(
                    input="客户说鞋子尺码偏小，想换大一码",
                    context={"agent_id": str(instance.id)},
                ),
                principal=principal,
                request_id="req-instance-route",
            )

        self.assertEqual(1, agent.run_count)
        self.assertIsNotNone(agent.last_payload)
        assert agent.last_payload is not None
        self.assertEqual("mimo-v2.5-pro", agent.last_payload.model_key)
        self.assertEqual("mimo-after-sales-route", agent.last_payload.routing_key)
        self.assertEqual(str(instance.id), agent.last_payload.context["agent_id"])
        self.assertEqual("mimo-after-sales", agent.last_payload.context["agent_instance_slug"])
        self.assertEqual(str(department_id), agent.last_payload.context["department_id"])
        self.assertEqual([str(knowledge_base_id)], agent.last_payload.context["knowledge_base_ids"])
        self.assertEqual("advisory", agent.last_payload.context["knowledge_guardrail_mode"])
        self.assertEqual(4, agent.last_payload.context["knowledge_top_k"])
        self.assertEqual("agentWorkflowCustomerReply", agent.last_payload.context["workflow_key"])
        retrieve.assert_awaited_once()
        retrieval_payload = retrieve.await_args.args[2]
        self.assertEqual(4, retrieval_payload.top_k)
        self.assertEqual("mimo-v2.5-pro", response.model_key)
        self.assertEqual("mimo-after-sales", response.metadata["agent_instance"]["slug"])
        self.assertEqual("advisory", response.metadata["knowledge"]["guardrail"]["mode"])
        self.assertFalse(response.metadata["knowledge"]["guardrail"]["triggered"])
        audit.assert_awaited_once()

    async def test_enrich_with_knowledge_context_adds_sources_and_diagnostics(self) -> None:
        tenant_id = uuid4()
        user_id = uuid4()
        kb_id = uuid4()
        document_id = uuid4()
        principal = Principal(
            tenant_id=tenant_id,
            user_id=user_id,
            permissions={"knowledge:read"},
        )
        retrieval = RetrievalTestResponse(
            knowledge_base_id=kb_id,
            query="客户问七天无理由怎么退货",
            engine=RAGEngineType.PGVECTOR,
            elapsed_ms=12,
            results=[
                RetrievalSourceResponse(
                    chunk_id="chunk-1",
                    document_id=document_id,
                    source_name="售后政策.md",
                    score=0.86,
                    text="签收后七天内未使用且包装完整，可以申请无理由退货。",
                    metadata={"chunk_index": 0},
                )
            ],
            diagnostics={
                "knowledge_base_name": "售后政策",
                "knowledge_base_visibility": "tenant",
                "retrieval_mode": "text_chunk_fallback",
            },
            checked_at=datetime.now(timezone.utc),
        )

        with (
            patch(
                "app.services.agent_runtime_service.run_retrieval_test",
                new=AsyncMock(return_value=retrieval),
            ) as mocked_retrieve,
            patch(
                "app.services.agent_runtime_service.record_audit_event", new=AsyncMock()
            ) as mocked_audit,
        ):
            enriched, sources, diagnostics = await _enrich_with_knowledge_context(
                session=object(),
                payload=AgentRunRequest(
                    input="客户问七天无理由怎么退货",
                    context={
                        "agent_id": str(uuid4()),
                        "conversation_id": str(uuid4()),
                        "knowledge_base_id": str(kb_id),
                        "knowledge_top_k": 3,
                    },
                ),
                principal=principal,
                agent_key="customer_service",
                request_id="req-knowledge-1",
            )

        mocked_retrieve.assert_awaited_once()
        mocked_audit.assert_awaited_once()
        audit_kwargs = mocked_audit.await_args.kwargs
        self.assertEqual("knowledge.retrieve", audit_kwargs["action"])
        self.assertEqual("knowledge_base", audit_kwargs["resource_type"])
        self.assertEqual(kb_id, audit_kwargs["resource_id"])
        self.assertEqual("req-knowledge-1", audit_kwargs["request_id"])
        self.assertEqual("customer_service", audit_kwargs["details"]["agent_key"])
        self.assertEqual(1, audit_kwargs["details"]["source_count"])
        self.assertEqual(0.86, audit_kwargs["details"]["max_score"])
        self.assertEqual(1, len(sources))
        self.assertIn("knowledge_context", enriched.context)
        self.assertIn("售后政策.md", str(enriched.context["knowledge_context"]))
        self.assertEqual("sources_found", diagnostics["reason"])
        self.assertEqual(1, diagnostics["source_count"])
        self.assertEqual("high", diagnostics["confidence_level"])
        self.assertEqual(0.86, diagnostics["max_score"])
        self.assertFalse(diagnostics["requires_human_review"])
        self.assertEqual("售后政策", sources[0]["knowledge_base_name"])
        self.assertEqual(1, sources[0]["rank"])
        self.assertEqual(
            [
                {
                    "knowledge_base_id": str(kb_id),
                    "knowledge_base_name": "售后政策",
                    "knowledge_base_visibility": "tenant",
                    "engine": "pgvector",
                    "source_count": 1,
                    "elapsed_ms": 12,
                }
            ],
            diagnostics["per_base"],
        )

    async def test_enrich_with_knowledge_context_handles_empty_retrieval(self) -> None:
        kb_id = uuid4()
        principal = Principal(
            tenant_id=uuid4(),
            user_id=uuid4(),
            permissions={"knowledge:read"},
        )
        retrieval = RetrievalTestResponse(
            knowledge_base_id=kb_id,
            query="有没有保价",
            engine=RAGEngineType.PGVECTOR,
            elapsed_ms=5,
            results=[],
        )

        with (
            patch(
                "app.services.agent_runtime_service.run_retrieval_test",
                new=AsyncMock(return_value=retrieval),
            ),
            patch("app.services.agent_runtime_service.record_audit_event", new=AsyncMock()),
        ):
            enriched, sources, diagnostics = await _enrich_with_knowledge_context(
                session=object(),
                payload=AgentRunRequest(
                    input="有没有保价", context={"knowledge_base_ids": [str(kb_id)]}
                ),
                principal=principal,
            )

        self.assertEqual([], sources)
        self.assertIn("未检索到匹配", str(enriched.context["knowledge_context"]))
        self.assertEqual("no_matching_sources", diagnostics["reason"])
        self.assertEqual("no_match", diagnostics["confidence_level"])
        self.assertTrue(diagnostics["requires_human_review"])
        self.assertEqual("no_matching_sources", diagnostics["review_reason"])

    async def test_agent_run_strict_knowledge_guardrail_skips_model_call_when_sources_are_missing(
        self,
    ) -> None:
        kb_id = uuid4()
        principal = Principal(
            tenant_id=uuid4(),
            user_id=uuid4(),
            permissions={"agents:write", "knowledge:read"},
        )
        retrieval = RetrievalTestResponse(
            knowledge_base_id=kb_id,
            query="客户问能不能赔偿 500 元",
            engine=RAGEngineType.PGVECTOR,
            elapsed_ms=7,
            results=[],
            diagnostics={"knowledge_base_name": "售后政策", "knowledge_base_visibility": "tenant"},
        )
        authorization = AgentRunAuthorization(
            license_gate="enforced",
            licensed=True,
            installed=True,
            enabled=True,
            reason="active_license_and_enabled_module",
        )
        agent = FakeGuardrailAgent(required_module="agent.customer_service")

        with (
            patch("app.services.agent_runtime_service.agent_registry.get", return_value=agent),
            patch(
                "app.services.agent_runtime_service._authorize_agent_run",
                new=AsyncMock(return_value=authorization),
            ),
            patch(
                "app.services.agent_runtime_service.run_retrieval_test",
                new=AsyncMock(return_value=retrieval),
            ),
            patch(
                "app.services.agent_runtime_service._record_agent_run_audit", new=AsyncMock()
            ) as audit,
            patch(
                "app.services.agent_runtime_service._record_knowledge_retrieve_audit",
                new=AsyncMock(),
            ),
        ):
            response = await run_agent(
                session=object(),
                agent_key="customer_service",
                payload=AgentRunRequest(
                    input="客户问能不能赔偿 500 元",
                    context={"knowledge_base_id": str(kb_id)},
                    routing_key="customer-service",
                ),
                principal=principal,
                request_id="req-guardrail",
            )

        self.assertEqual(0, agent.run_count)
        self.assertIn("资料匹配不足", response.answer)
        self.assertNotIn("low_retrieval_score", response.answer)
        self.assertEqual(0, response.usage.total_tokens)
        self.assertEqual("customer-service", response.model_key)
        self.assertEqual("req-guardrail", response.request_id)
        self.assertEqual("no_match", response.metadata["knowledge"]["confidence_level"])
        self.assertTrue(response.metadata["knowledge"]["requires_human_review"])
        self.assertTrue(response.metadata["knowledge"]["guardrail"]["triggered"])
        self.assertTrue(response.metadata["knowledge"]["guardrail"]["skipped_model_call"])
        self.assertEqual("knowledge_guardrail", response.metadata["runtime_evidence"]["execution"])
        self.assertFalse(response.metadata["runtime_evidence"]["llm_gateway_called"])
        self.assertEqual(
            "knowledge_guardrail", response.metadata["runtime_evidence"]["local_response"]
        )
        self.assertEqual("agenthive-local", response.metadata["runtime_evidence"]["provider_key"])
        self.assertEqual("customer-service", response.metadata["runtime_evidence"]["model_key"])
        self.assertEqual("local_runtime", response.metadata["runtime_summary"]["status"])
        self.assertEqual("local_runtime", response.metadata["runtime_summary"]["adapter_mode"])
        self.assertFalse(response.metadata["runtime_summary"]["gateway_called"])
        self.assertEqual("no_match", response.metadata["runtime_summary"]["knowledge_confidence"])
        self.assertTrue(response.metadata["runtime_summary"]["requires_human_review"])
        audit.assert_awaited_once()

    async def test_customer_service_greeting_skips_knowledge_and_model_call(self) -> None:
        principal = Principal(
            tenant_id=uuid4(),
            user_id=uuid4(),
            permissions={"agents:write", "knowledge:read"},
        )
        authorization = AgentRunAuthorization(
            license_gate="enforced",
            licensed=True,
            installed=True,
            enabled=True,
            reason="active_license_and_enabled_module",
        )
        agent = FakeGuardrailAgent(required_module="agent.customer_service")

        with (
            patch("app.services.agent_runtime_service.agent_registry.get", return_value=agent),
            patch(
                "app.services.agent_runtime_service._authorize_agent_run",
                new=AsyncMock(return_value=authorization),
            ),
            patch(
                "app.services.agent_runtime_service.run_retrieval_test", new=AsyncMock()
            ) as retrieve,
            patch(
                "app.services.agent_runtime_service._record_agent_run_audit", new=AsyncMock()
            ) as audit,
        ):
            response = await run_agent(
                session=object(),
                agent_key="customer_service",
                payload=AgentRunRequest(
                    input="hello",
                    context={"knowledge_base_id": str(uuid4())},
                    routing_key="customer-service",
                ),
                principal=principal,
                request_id="req-greeting",
            )

        self.assertEqual(0, agent.run_count)
        retrieve.assert_not_awaited()
        self.assertIn("电商客服助手", response.answer)
        self.assertIn("客户问题", response.answer)
        self.assertEqual(0, response.usage.total_tokens)
        self.assertEqual("greeting_intent", response.metadata["knowledge"]["reason"])
        self.assertFalse(response.metadata["knowledge"]["guardrail"]["triggered"])
        self.assertEqual("local_response", response.metadata["runtime_evidence"]["execution"])
        self.assertFalse(response.metadata["runtime_evidence"]["llm_gateway_called"])
        self.assertEqual("greeting_intent", response.metadata["runtime_evidence"]["local_response"])
        self.assertEqual("agenthive-local", response.metadata["runtime_evidence"]["provider_key"])
        self.assertEqual("customer-service", response.metadata["runtime_evidence"]["model_key"])
        self.assertEqual("local_runtime", response.metadata["runtime_summary"]["status"])
        self.assertEqual("local_runtime", response.metadata["runtime_summary"]["adapter_mode"])
        self.assertFalse(response.metadata["runtime_summary"]["gateway_called"])
        audit.assert_awaited_once()

    async def test_agent_run_advisory_knowledge_guardrail_allows_model_call(self) -> None:
        kb_id = uuid4()
        principal = Principal(
            tenant_id=uuid4(),
            user_id=uuid4(),
            permissions={"agents:write", "knowledge:read"},
        )
        retrieval = RetrievalTestResponse(
            knowledge_base_id=kb_id,
            query="客户问能不能赔偿 500 元",
            engine=RAGEngineType.PGVECTOR,
            elapsed_ms=7,
            results=[],
            diagnostics={"knowledge_base_name": "售后政策", "knowledge_base_visibility": "tenant"},
        )
        authorization = AgentRunAuthorization(
            license_gate="enforced",
            licensed=True,
            installed=True,
            enabled=True,
            reason="active_license_and_enabled_module",
        )
        agent = FakeGuardrailAgent(required_module="agent.customer_service")

        with (
            patch("app.services.agent_runtime_service.agent_registry.get", return_value=agent),
            patch(
                "app.services.agent_runtime_service._authorize_agent_run",
                new=AsyncMock(return_value=authorization),
            ),
            patch(
                "app.services.agent_runtime_service.run_retrieval_test",
                new=AsyncMock(return_value=retrieval),
            ),
            patch("app.services.agent_runtime_service._record_agent_run_audit", new=AsyncMock()),
            patch(
                "app.services.agent_runtime_service._record_knowledge_retrieve_audit",
                new=AsyncMock(),
            ),
        ):
            response = await run_agent(
                session=object(),
                agent_key="customer_service",
                payload=AgentRunRequest(
                    input="客户问能不能赔偿 500 元",
                    context={
                        "knowledge_base_id": str(kb_id),
                        "knowledge_guardrail_mode": "advisory",
                    },
                ),
                principal=principal,
                request_id="req-advisory",
            )

        self.assertEqual(1, agent.run_count)
        self.assertEqual("model answer", response.answer)
        self.assertFalse(response.metadata["knowledge"]["guardrail"]["triggered"])
        self.assertEqual("advisory", response.metadata["knowledge"]["guardrail"]["mode"])

    async def test_low_retrieval_for_non_policy_task_allows_model_call(self) -> None:
        kb_id = uuid4()
        principal = Principal(
            tenant_id=uuid4(),
            user_id=uuid4(),
            permissions={"agents:write", "knowledge:read"},
        )
        retrieval = RetrievalTestResponse(
            knowledge_base_id=kb_id,
            query="请继续优化上一次结果，让它更适合直接使用。",
            engine=RAGEngineType.PGVECTOR,
            elapsed_ms=7,
            results=[],
            diagnostics={"knowledge_base_name": "售后政策", "knowledge_base_visibility": "tenant"},
        )
        authorization = AgentRunAuthorization(
            license_gate="enforced",
            licensed=True,
            installed=True,
            enabled=True,
            reason="active_license_and_enabled_module",
        )
        agent = FakeGuardrailAgent(required_module="agent.customer_service")

        with (
            patch("app.services.agent_runtime_service.agent_registry.get", return_value=agent),
            patch(
                "app.services.agent_runtime_service._authorize_agent_run",
                new=AsyncMock(return_value=authorization),
            ),
            patch(
                "app.services.agent_runtime_service.run_retrieval_test",
                new=AsyncMock(return_value=retrieval),
            ),
            patch("app.services.agent_runtime_service._record_agent_run_audit", new=AsyncMock()),
            patch(
                "app.services.agent_runtime_service._record_knowledge_retrieve_audit",
                new=AsyncMock(),
            ),
        ):
            response = await run_agent(
                session=object(),
                agent_key="customer_service",
                payload=AgentRunRequest(
                    input="请继续优化上一次结果，让它更适合直接使用。",
                    context={"knowledge_base_id": str(kb_id)},
                    model_key="mimo-v2.5-pro",
                    routing_key="mimo-v2.5-pro",
                ),
                principal=principal,
                request_id="req-non-policy",
            )

        self.assertEqual(1, agent.run_count)
        self.assertEqual("model answer", response.answer)
        self.assertEqual("mimo-v2.5-pro", response.model_key)
        self.assertFalse(response.metadata["knowledge"]["guardrail"]["triggered"])
        self.assertFalse(response.metadata["knowledge"]["guardrail"]["requires_strict_knowledge"])

    def test_knowledge_guardrail_answer_hides_internal_reason_codes(self) -> None:
        answer = _knowledge_guardrail_answer(
            AgentRunRequest(input="hello", context={}),
            {
                "review_reason": "low_retrieval_score",
                "per_base": [{"knowledge_base_name": "Customer Service SOP"}],
            },
        )

        self.assertIn("资料匹配不足", answer)
        self.assertNotIn("low_retrieval_score", answer)
        self.assertNotIn("未调用大模型", answer)

    def test_knowledge_confidence_gate_flags_low_score_for_human_review(self) -> None:
        diagnostics = _knowledge_confidence_diagnostics(
            [
                {"source_name": "售后政策.md", "score": 0.12},
                {"source_name": "商品说明.md", "score": 0.08},
            ]
        )

        self.assertEqual("low", diagnostics["confidence_level"])
        self.assertEqual(0.12, diagnostics["max_score"])
        self.assertEqual(0.08, diagnostics["min_score"])
        self.assertTrue(diagnostics["requires_human_review"])
        self.assertEqual("low_retrieval_score", diagnostics["review_reason"])

    def test_knowledge_confidence_gate_flags_unscored_sources_for_review(self) -> None:
        diagnostics = _knowledge_confidence_diagnostics(
            [
                {"source_name": "售后政策.md", "score": None},
            ]
        )

        self.assertEqual("unscored", diagnostics["confidence_level"])
        self.assertIsNone(diagnostics["max_score"])
        self.assertTrue(diagnostics["requires_human_review"])

    def test_knowledge_base_ids_are_deduplicated_and_limited(self) -> None:
        ids = [uuid4() for _ in range(6)]
        parsed = _knowledge_base_ids_from_context(
            {
                "knowledge_base_id": str(ids[0]),
                "knowledge_base_ids": [str(ids[0]), *[str(item) for item in ids[1:]]],
            }
        )

        self.assertEqual([UUID(str(item)) for item in ids[:5]], parsed)

    def test_knowledge_context_truncates_long_source_text(self) -> None:
        context = _format_knowledge_context(
            [
                {
                    "chunk_id": "chunk-long",
                    "source_name": "长文档.txt",
                    "score": 0.5,
                    "text": "A" * (MAX_KNOWLEDGE_CONTEXT_SOURCE_CHARS + 100),
                }
            ]
        )

        self.assertIn("长文档.txt", context)
        self.assertIn("...", context)
        self.assertLess(len(context), MAX_KNOWLEDGE_CONTEXT_SOURCE_CHARS + 80)

    def test_agent_instance_diagnostics_use_readable_runtime_context(self) -> None:
        diagnostics = _agent_instance_diagnostics_from_context(
            {
                "agent_id": str(uuid4()),
                "agent_instance_slug": "after-sales",
                "agent_instance_name": "售后客服",
                "department_id": str(uuid4()),
                "visibility": "department",
            }
        )

        self.assertTrue(diagnostics["enabled"])
        self.assertEqual("售后客服", diagnostics["name"])
        self.assertEqual("after-sales", diagnostics["slug"])
        self.assertEqual("department", diagnostics["visibility"])

    def test_agent_run_audit_details_capture_governance_without_prompt_copy(self) -> None:
        agent_id = uuid4()
        knowledge_base_id = uuid4()
        details = _agent_run_audit_details(
            agent_key="customer_service",
            payload=AgentRunRequest(
                input="客户手机号是 13800000000，想换码",
                context={
                    "agent_id": str(agent_id),
                    "agent_instance_name": "售后客服",
                    "department_id": str(uuid4()),
                    "knowledge_base_ids": [str(knowledge_base_id)],
                    "source": "admin_console",
                },
                model_key="qwen-plus",
                routing_key="customer-service",
                max_tokens=256,
            ),
            response=AgentRunResponse(
                answer="可以换码。",
                usage=LLMUsageResponse(
                    input_tokens=100,
                    output_tokens=50,
                    total_tokens=150,
                    cost_usd=Decimal("0.0015"),
                ),
                model_key="qwen-plus",
                request_id="run-1",
                sources=[
                    {"knowledge_base_id": str(knowledge_base_id), "source_name": "售后政策.md"}
                ],
                metadata={
                    "required_module": "agent.customer_service",
                    "agent_instance": {
                        "enabled": True,
                        "agent_id": str(agent_id),
                        "name": "售后客服",
                        "slug": "after-sales",
                    },
                    "knowledge": {
                        "enabled": True,
                        "source_count": 1,
                        "knowledge_base_ids": [str(knowledge_base_id)],
                        "confidence_level": "high",
                        "requires_human_review": False,
                    },
                    "runtime_evidence": {
                        "execution": "llm_gateway",
                        "llm_gateway_called": True,
                        "provider_key": "qwen",
                        "model_key": "qwen-plus",
                        "request_id": "run-1",
                        "fallback_attempt_count": 0,
                        "route_attempts": [
                            {
                                "attempt": 1,
                                "provider_key": "qwen",
                                "model_key": "qwen-plus",
                                "status": "success",
                            }
                        ],
                        "mock_adapter": False,
                    },
                },
            ),
            authorization=AgentRunAuthorization(
                license_gate="enforced",
                licensed=True,
                installed=True,
                enabled=True,
                reason="enabled",
            ),
        )

        self.assertEqual("customer_service", details["agent_key"])
        self.assertEqual("qwen-plus", details["model_key"])
        self.assertEqual("customer-service", details["routing_key"])
        self.assertEqual("agent.customer_service", details["required_module"])
        self.assertEqual("0.0015", details["usage"]["cost_usd"])
        self.assertEqual(150, details["usage"]["total_tokens"])
        self.assertEqual("售后客服", details["agent_instance"]["name"])
        self.assertEqual(1, details["knowledge"]["source_count"])
        self.assertEqual("high", details["knowledge"]["confidence_level"])
        self.assertFalse(details["knowledge"]["requires_human_review"])
        self.assertEqual("real_model_call", details["runtime_summary"]["status"])
        self.assertEqual("live_gateway", details["runtime_summary"]["adapter_mode"])
        self.assertEqual("qwen", details["runtime_summary"]["provider_key"])
        self.assertEqual("qwen-plus", details["runtime_summary"]["model_key"])
        self.assertEqual(1, details["runtime_summary"]["route_attempt_count"])
        self.assertEqual(1, details["runtime_summary"]["knowledge_source_count"])
        self.assertIn("knowledge_base_ids", details["context_keys"])
        self.assertNotIn("客户手机号", str(details))
        self.assertNotIn("13800000000", str(details))

    async def test_record_agent_run_audit_adds_agent_instance_event(self) -> None:
        tenant_id = uuid4()
        user_id = uuid4()
        agent_id = uuid4()
        session = FakeAuditSession()

        await _record_agent_run_audit(
            session,
            principal=Principal(tenant_id=tenant_id, user_id=user_id, permissions={"agents:write"}),
            agent_key="customer_service",
            payload=AgentRunRequest(
                input="客户想换码",
                context={"agent_id": str(agent_id), "agent_instance_name": "售后客服"},
            ),
            response=AgentRunResponse(
                answer="可以换码。",
                usage=LLMUsageResponse(
                    input_tokens=10,
                    output_tokens=5,
                    total_tokens=15,
                    cost_usd=Decimal("0.0002"),
                ),
                model_key="qwen-plus",
                request_id="run-2",
                sources=[],
                metadata={
                    "agent_instance": {
                        "enabled": True,
                        "agent_id": str(agent_id),
                        "name": "售后客服",
                    },
                    "knowledge": {"enabled": False, "reason": "no_knowledge_base_context"},
                },
            ),
            authorization=AgentRunAuthorization(
                license_gate="enforced",
                licensed=True,
                installed=True,
                enabled=True,
                reason="enabled",
            ),
            request_id="request-2",
        )

        self.assertEqual(1, len(session.added))
        event = session.added[0]
        self.assertEqual("agent.run", event.action)
        self.assertEqual("agent_instance", event.resource_type)
        self.assertEqual(agent_id, event.resource_id)
        self.assertEqual(user_id, event.actor_id)
        self.assertEqual("0.0002", event.details["usage"]["cost_usd"])


class FakeAgentInstanceSession:
    def __init__(self, instance: AgentInstance):
        self.instance = instance

    async def execute(self, _statement):
        return FakeScalarResult(self.instance)


class FakeScalarResult:
    def __init__(self, instance: AgentInstance):
        self.instance = instance

    def scalar_one_or_none(self):
        return self.instance

    def scalars(self):
        return self

    def all(self):
        return []


class FakeKnowledgeBindingSession:
    def __init__(self, base: KnowledgeBase | None):
        self.base = base

    async def get(self, _model, row_id):
        if self.base is not None and self.base.id == row_id:
            return self.base
        return None

    async def execute(self, _statement):
        return FakeScalarResult(None)


class FakeAuditSession:
    def __init__(self):
        self.added = []

    def add(self, row):
        self.added.append(row)


class FakeGuardrailAgentDefinition:
    def __init__(self, required_module: str):
        self.required_module = required_module


class FakeGuardrailAgent:
    def __init__(self, *, required_module: str):
        self.definition = FakeGuardrailAgentDefinition(required_module)
        self.run_count = 0
        self.last_payload = None

    async def run(self, payload, principal, *, request_id=None, session=None):
        self.run_count += 1
        self.last_payload = payload
        return AgentRunResponse(
            answer="model answer",
            usage=LLMUsageResponse(
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
                cost_usd=Decimal("0.0001"),
            ),
            model_key=payload.model_key or "test-model",
            request_id=request_id or "fake-run",
            sources=[],
            metadata={"required_module": self.definition.required_module},
        )


if __name__ == "__main__":
    unittest.main()
