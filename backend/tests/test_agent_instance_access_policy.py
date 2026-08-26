import unittest
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.api.deps import Principal
from app.models.agent_module import AgentInstance
from app.models.channel import ChannelConfig
from app.models.knowledge import KnowledgeBase
from app.models.llm import LLMDeployment, LLMModel
from app.schemas.agents import AgentInstanceCreateRequest, AgentInstanceUpdateRequest
from app.services.agent_runtime_service import AgentRunAuthorization
from app.services.agent_runtime_service import (
    ActiveModelDeploymentIndex,
    _apply_agent_instance_defaults,
    _canonicalize_agent_governance_context,
    _can_read_agent_instance,
    _can_write_agent_instance,
    _normalize_agent_instance_department,
    _normalize_agent_instance_owner,
    _workbench_agent_instance_response,
    create_agent_instance,
    list_agent_instances,
    list_workbench_agent_instances,
    update_agent_instance,
)
from app.schemas.agents import AgentRunRequest


class AgentInstanceAccessPolicyTest(unittest.IsolatedAsyncioTestCase):
    def test_tenant_agent_is_readable_but_not_writable_by_non_owner(self) -> None:
        principal = Principal(
            tenant_id=uuid4(), user_id=uuid4(), permissions={"agents:read", "agents:write"}
        )
        instance = AgentInstance(
            tenant_id=principal.tenant_id,
            name="Tenant Bot",
            slug="tenant-bot",
            agent_key="customer_service",
            module_key="agent.customer_service",
            visibility="tenant",
            owner_user_id=uuid4(),
            created_by=uuid4(),
        )

        self.assertTrue(_can_read_agent_instance(instance, principal, set()))
        self.assertFalse(_can_write_agent_instance(instance, principal, set()))

    def test_private_agent_is_limited_to_owner_or_creator(self) -> None:
        tenant_id = uuid4()
        owner_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=owner_id, permissions={"agents:read"})
        other = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:read"})
        instance = AgentInstance(
            tenant_id=tenant_id,
            name="Private Bot",
            slug="private-bot",
            agent_key="customer_service",
            module_key="agent.customer_service",
            visibility="private",
            owner_user_id=owner_id,
        )

        self.assertTrue(_can_read_agent_instance(instance, principal, set()))
        self.assertFalse(_can_read_agent_instance(instance, other, set()))

    def test_department_agent_requires_department_membership(self) -> None:
        tenant_id = uuid4()
        department_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:read"})
        instance = AgentInstance(
            tenant_id=tenant_id,
            name="Department Bot",
            slug="department-bot",
            agent_key="customer_service",
            module_key="agent.customer_service",
            visibility="department",
            department_id=department_id,
        )

        self.assertTrue(_can_read_agent_instance(instance, principal, {department_id}))
        self.assertFalse(_can_read_agent_instance(instance, principal, {uuid4()}))

    def test_tenant_admin_can_read_and_write_every_instance(self) -> None:
        principal = Principal(tenant_id=uuid4(), user_id=uuid4(), permissions={"tenant.admin"})
        instance = AgentInstance(
            tenant_id=principal.tenant_id,
            name="Any Bot",
            slug="any-bot",
            agent_key="customer_service",
            module_key="agent.customer_service",
            visibility="private",
            owner_user_id=uuid4(),
        )

        self.assertTrue(_can_read_agent_instance(instance, principal, set()))
        self.assertTrue(_can_write_agent_instance(instance, principal, set()))

    async def test_workbench_instances_only_return_active_visible_agents_for_chat_user(
        self,
    ) -> None:
        tenant_id = uuid4()
        user_id = uuid4()
        department_id = uuid4()
        visible_kb_id = uuid4()
        inaccessible_kb_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=user_id, permissions={"chat:write"})
        visible_tenant = AgentInstance(
            id=uuid4(),
            tenant_id=tenant_id,
            name="Tenant Active",
            slug="tenant-active",
            agent_key="customer_service",
            module_key="agent.customer_service",
            status="active",
            visibility="tenant",
            owner_user_id=uuid4(),
            model_routing_key="default-chat",
            config={"knowledge_base_ids": [str(visible_kb_id), str(inaccessible_kb_id)]},
        )
        visible_department = AgentInstance(
            id=uuid4(),
            tenant_id=tenant_id,
            name="Department Active",
            slug="department-active",
            agent_key="copywriting",
            module_key="agent.copywriting",
            status="active",
            visibility="department",
            department_id=department_id,
            owner_user_id=uuid4(),
        )
        inaccessible_private = AgentInstance(
            id=uuid4(),
            tenant_id=tenant_id,
            name="Private Active",
            slug="private-active",
            agent_key="hr_screening",
            module_key="agent.hr_screening",
            status="active",
            visibility="private",
            owner_user_id=uuid4(),
        )
        disabled_tenant = AgentInstance(
            id=uuid4(),
            tenant_id=tenant_id,
            name="Tenant Disabled",
            slug="tenant-disabled",
            agent_key="data_analyst",
            module_key="agent.data_analyst",
            status="disabled",
            visibility="tenant",
            owner_user_id=user_id,
        )
        visible_kb = KnowledgeBase(
            id=visible_kb_id,
            tenant_id=tenant_id,
            name="After-sales SOP",
            description="Customer service policy",
            visibility="tenant",
            document_count=3,
            tags=["support"],
        )
        inaccessible_kb = KnowledgeBase(
            id=inaccessible_kb_id,
            tenant_id=tenant_id,
            name="Leadership Private",
            visibility="private",
            document_count=1,
            metadata_json={"owner_user_id": str(uuid4())},
        )
        model = LLMModel(
            id=uuid4(),
            provider_key="openai-compatible",
            model_key="gpt-4o-mini",
            display_name="GPT-4o mini",
        )
        deployment = LLMDeployment(
            id=uuid4(),
            tenant_id=tenant_id,
            provider_id=uuid4(),
            model_id=model.id,
            deployment_name="Default Chat",
            routing_key="default-chat",
            is_active=True,
        )
        session = FakeAgentInstanceListSession(
            instances=[visible_tenant, visible_department, inaccessible_private, disabled_tenant],
            deployment_rows=[(deployment, model)],
            knowledge_bases=[visible_kb, inaccessible_kb],
            member_department_ids={department_id},
        )

        response = await list_workbench_agent_instances(session, principal)

        self.assertEqual(
            ["Tenant Active", "Department Active"], [item.name for item in response.agents]
        )
        self.assertTrue(all(item.status == "active" for item in response.agents))
        self.assertTrue(response.agents[0].runnable)
        self.assertEqual("ready", response.agents[0].readiness)
        self.assertEqual("default-chat", response.agents[0].model_profile)
        self.assertEqual("configured", response.agents[0].model_policy)
        self.assertTrue(response.agents[0].model_available)
        self.assertTrue(response.agents[0].knowledge_enabled)
        self.assertEqual(2, response.agents[0].knowledge_base_count)
        self.assertEqual(
            ["After-sales SOP"], [base.name for base in response.agents[0].knowledge_bases]
        )
        self.assertEqual(3, response.agents[0].knowledge_bases[0].document_count)
        exposed_fields = set(response.agents[0].model_dump())
        self.assertFalse(
            {
                "system_prompt",
                "config",
                "metadata",
                "model_key",
                "model_routing_key",
                "owner_user_id",
                "created_by",
                "tenant_id",
            }
            & exposed_fields
        )

    def test_workbench_agent_response_marks_missing_configuration_without_exposing_config(
        self,
    ) -> None:
        instance = AgentInstance(
            id=uuid4(),
            tenant_id=uuid4(),
            name="Customer Bot",
            slug="customer-bot",
            agent_key="customer_service",
            module_key="agent.customer_service",
            status="active",
            visibility="tenant",
            config={},
        )

        from app.services.agent_runtime_service import _workbench_agent_instance_response

        response = _workbench_agent_instance_response(instance)

        self.assertFalse(response.runnable)
        self.assertEqual("needs_configuration", response.readiness)
        self.assertIn("model_policy_not_configured", response.readiness_reasons)
        self.assertIn("knowledge_not_bound", response.readiness_reasons)
        self.assertEqual("system_default", response.model_policy)
        self.assertIsNone(response.model_profile)
        self.assertEqual("customer", response.category)
        self.assertEqual("customer_service", response.workflow_profile)
        self.assertEqual(0, response.knowledge_base_count)
        exposed_fields = set(response.model_dump())
        self.assertFalse(
            {"config", "metadata", "system_prompt", "model_key", "model_routing_key"}
            & exposed_fields
        )

    def test_workbench_agent_response_uses_module_key_profile_without_name_guessing(self) -> None:
        instance = AgentInstance(
            id=uuid4(),
            tenant_id=uuid4(),
            name="North Region Assistant",
            slug="north-region-assistant",
            agent_key="customized",
            module_key="agent.finance",
            status="active",
            visibility="tenant",
            config={},
        )

        response = _workbench_agent_instance_response(instance)

        self.assertEqual("finance", response.category)
        self.assertEqual("finance", response.workflow_profile)

    def test_workbench_agent_response_unknown_profile_falls_back_to_general(self) -> None:
        instance = AgentInstance(
            id=uuid4(),
            tenant_id=uuid4(),
            name="Custom Internal Assistant",
            slug="custom-internal-assistant",
            agent_key="custom_internal",
            module_key="agent.custom_internal",
            status="active",
            visibility="tenant",
            config={},
        )

        response = _workbench_agent_instance_response(instance)

        self.assertEqual("general", response.category)
        self.assertEqual("general", response.workflow_profile)

    def test_workbench_agent_response_marks_inactive_model_route_without_exposing_route_key(
        self,
    ) -> None:
        instance = AgentInstance(
            id=uuid4(),
            tenant_id=uuid4(),
            name="Customer Bot",
            slug="customer-bot",
            agent_key="copywriting",
            module_key="agent.copywriting",
            status="active",
            visibility="tenant",
            model_routing_key="missing-route",
        )

        response = _workbench_agent_instance_response(
            instance,
            model_index=ActiveModelDeploymentIndex(
                routing_keys=frozenset({"default-chat"}),
                model_keys=frozenset({"gpt-4o-mini"}),
            ),
        )

        self.assertFalse(response.runnable)
        self.assertFalse(response.model_available)
        self.assertEqual("needs_configuration", response.readiness)
        self.assertIn("model_route_unavailable", response.readiness_reasons)
        exposed_fields = set(response.model_dump())
        self.assertFalse(
            {"config", "metadata", "system_prompt", "model_key", "model_routing_key"}
            & exposed_fields
        )

    async def test_admin_agent_instances_include_readiness_summary_for_publish_review(self) -> None:
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        instance = AgentInstance(
            id=uuid4(),
            tenant_id=tenant_id,
            name="Draft Review Bot",
            slug="draft-review-bot",
            agent_key="copywriting",
            module_key="agent.copywriting",
            status="active",
            visibility="tenant",
            model_routing_key="missing-route",
        )
        session = FakeAgentInstanceListSession(
            active_only=False,
            instances=[instance],
            member_department_ids=set(),
            deployment_rows=[],
        )

        response = await list_agent_instances(session, principal)

        self.assertEqual(1, len(response.agents))
        self.assertFalse(response.agents[0].runnable)
        self.assertFalse(response.agents[0].model_available)
        self.assertIn("model_route_unavailable", response.agents[0].readiness_reasons)

    async def test_department_normalization_rejects_cross_scope_assignment(self) -> None:
        tenant_id = uuid4()
        allowed_department_id = uuid4()
        requested_department_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        session = FakeDepartmentSession(
            existing_department_id=requested_department_id,
            member_department_ids={allowed_department_id},
        )

        with self.assertRaises(HTTPException) as raised:
            await _normalize_agent_instance_department(
                session,
                principal,
                "department",
                requested_department_id,
            )

        self.assertEqual(403, raised.exception.status_code)

    def test_owner_normalization_rejects_non_admin_owner_reassignment(self) -> None:
        principal = Principal(tenant_id=uuid4(), user_id=uuid4(), permissions={"agents:write"})

        with self.assertRaises(HTTPException) as raised:
            _normalize_agent_instance_owner(principal, uuid4())

        self.assertEqual(403, raised.exception.status_code)

    async def test_agent_run_defaults_reject_inaccessible_instance(self) -> None:
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        instance = AgentInstance(
            id=uuid4(),
            tenant_id=tenant_id,
            name="Private Bot",
            slug="private-bot",
            agent_key="customer_service",
            module_key="agent.customer_service",
            visibility="private",
            owner_user_id=uuid4(),
            config={"knowledge_base_ids": ["kb-default"]},
        )
        payload = AgentRunRequest(input="hello", context={"agent_id": str(instance.id)})

        with self.assertRaises(HTTPException) as raised:
            await _apply_agent_instance_defaults(
                FakeAgentInstanceAccessSession(instance, member_department_ids=set()),
                payload,
                principal,
                agent_key="customer_service",
                required_module="agent.customer_service",
            )

        self.assertEqual(403, raised.exception.status_code)

    async def test_agent_run_defaults_reject_disabled_instance(self) -> None:
        tenant_id = uuid4()
        owner_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=owner_id, permissions={"agents:write"})
        instance = AgentInstance(
            id=uuid4(),
            tenant_id=tenant_id,
            name="Disabled Bot",
            slug="disabled-bot",
            agent_key="customer_service",
            module_key="agent.customer_service",
            status="disabled",
            visibility="tenant",
            owner_user_id=owner_id,
            config={"knowledge_base_ids": ["kb-default"]},
        )
        payload = AgentRunRequest(input="hello", context={"agent_id": str(instance.id)})

        with self.assertRaises(HTTPException) as raised:
            await _apply_agent_instance_defaults(
                FakeAgentInstanceAccessSession(instance, member_department_ids=set()),
                payload,
                principal,
                agent_key="customer_service",
                required_module="agent.customer_service",
            )

        self.assertEqual(403, raised.exception.status_code)
        self.assertIn("active", str(raised.exception.detail))

    async def test_agent_run_defaults_reject_module_mismatch(self) -> None:
        tenant_id = uuid4()
        owner_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=owner_id, permissions={"agents:write"})
        instance = AgentInstance(
            id=uuid4(),
            tenant_id=tenant_id,
            name="Mismatched Bot",
            slug="mismatched-bot",
            agent_key="customer_service",
            module_key="agent.finance",
            status="active",
            visibility="tenant",
            owner_user_id=owner_id,
        )
        payload = AgentRunRequest(input="hello", context={"agent_id": str(instance.id)})

        with self.assertRaises(HTTPException) as raised:
            await _apply_agent_instance_defaults(
                FakeAgentInstanceAccessSession(instance, member_department_ids=set()),
                payload,
                principal,
                agent_key="customer_service",
                required_module="agent.customer_service",
            )

        self.assertEqual(409, raised.exception.status_code)
        self.assertIn("module", str(raised.exception.detail))

    async def test_agent_run_defaults_merge_active_instance(self) -> None:
        tenant_id = uuid4()
        owner_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=owner_id, permissions={"agents:write"})
        instance = AgentInstance(
            id=uuid4(),
            tenant_id=tenant_id,
            name="Active Bot",
            slug="active-bot",
            agent_key="customer_service",
            module_key="agent.customer_service",
            status="active",
            visibility="tenant",
            owner_user_id=owner_id,
            model_key="qwen-plus",
            model_routing_key="cost-control",
            config={"knowledge_top_k": 5},
        )
        payload = AgentRunRequest(input="hello", context={"agent_id": str(instance.id)})

        result = await _apply_agent_instance_defaults(
            FakeAgentInstanceAccessSession(instance, member_department_ids=set()),
            payload,
            principal,
            agent_key="customer_service",
            required_module="agent.customer_service",
        )

        self.assertEqual("qwen-plus", result.model_key)
        self.assertEqual("cost-control", result.routing_key)
        self.assertEqual(5, result.context["knowledge_top_k"])
        self.assertEqual("active-bot", result.context["agent_instance_slug"])
        self.assertEqual("agent.customer_service", result.context["module_key"])

    async def test_agent_run_defaults_rejects_unready_instance_for_employee_runtime(self) -> None:
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"chat:write"})
        instance = AgentInstance(
            id=uuid4(),
            tenant_id=tenant_id,
            name="Unready Bot",
            slug="unready-bot",
            agent_key="copywriting",
            module_key="agent.copywriting",
            status="active",
            visibility="tenant",
            model_routing_key="missing-route",
        )
        payload = AgentRunRequest(input="hello", context={"agent_id": str(instance.id)})

        with self.assertRaises(HTTPException) as raised:
            await _apply_agent_instance_defaults(
                FakeAgentInstanceAccessSession(
                    instance,
                    member_department_ids=set(),
                    deployment_rows=[],
                ),
                payload,
                principal,
                agent_key="copywriting",
                required_module="agent.copywriting",
            )

        self.assertEqual(409, raised.exception.status_code)
        self.assertEqual("agent_instance_not_ready", raised.exception.detail["code"])
        self.assertIn("model_route_unavailable", raised.exception.detail["reasons"])

    async def test_agent_run_defaults_allows_unready_instance_for_admin_diagnostics(self) -> None:
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        instance = AgentInstance(
            id=uuid4(),
            tenant_id=tenant_id,
            name="Diagnostic Bot",
            slug="diagnostic-bot",
            agent_key="copywriting",
            module_key="agent.copywriting",
            status="active",
            visibility="tenant",
            model_routing_key="missing-route",
        )
        payload = AgentRunRequest(input="hello", context={"agent_id": str(instance.id)})
        session = FakeAgentInstanceAccessSession(
            instance,
            member_department_ids=set(),
            deployment_rows=[],
        )

        result = await _apply_agent_instance_defaults(
            session,
            payload,
            principal,
            agent_key="copywriting",
            required_module="agent.copywriting",
        )

        self.assertEqual("missing-route", result.routing_key)
        self.assertEqual(2, session.execute_count)

    async def test_agent_run_context_rejects_department_outside_user_scope(self) -> None:
        tenant_id = uuid4()
        user_id = uuid4()
        department_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=user_id, permissions={"agents:write"})
        payload = AgentRunRequest(input="hello", context={"department_id": str(department_id)})
        session = FakeSequenceSession(
            [
                FakeScalarOneOrNoneResult(department_id),
                FakeScalarOneOrNoneResult(None),
            ]
        )

        with self.assertRaises(HTTPException) as raised:
            await _canonicalize_agent_governance_context(session, payload, principal)

        self.assertEqual(403, raised.exception.status_code)

    async def test_agent_run_context_rejects_channel_agent_mismatch(self) -> None:
        tenant_id = uuid4()
        channel_agent_id = uuid4()
        requested_agent_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        channel = ChannelConfig(
            id=uuid4(),
            tenant_id=tenant_id,
            name="Web Widget",
            channel_type="web_widget",
            channel_key="web-demo",
            agent_id=channel_agent_id,
        )
        payload = AgentRunRequest(
            input="hello",
            context={"agent_id": str(requested_agent_id), "channel_id": str(channel.id)},
        )
        session = FakeSequenceSession([FakeScalarOneOrNoneResult(channel)])

        with self.assertRaises(HTTPException) as raised:
            await _canonicalize_agent_governance_context(session, payload, principal)

        self.assertEqual(409, raised.exception.status_code)

    async def test_agent_instance_update_rechecks_license_before_activation(self) -> None:
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        instance = AgentInstance(
            id=uuid4(),
            tenant_id=tenant_id,
            name="Draft Bot",
            slug="draft-bot",
            agent_key="customer_service",
            module_key="agent.customer_service",
            status="draft",
            visibility="tenant",
            owner_user_id=principal.user_id,
        )
        session = FakeAgentInstanceUpdateSession()

        with (
            patch(
                "app.services.agent_runtime_service._get_agent_instance",
                new=AsyncMock(return_value=instance),
            ),
            patch(
                "app.services.agent_runtime_service._authorize_agent_run",
                new=AsyncMock(
                    side_effect=HTTPException(
                        status_code=403,
                        detail="Enable this Agent module before running it.",
                    )
                ),
            ) as authorize,
            patch(
                "app.services.agent_runtime_service.record_audit_event", new=AsyncMock()
            ) as audit,
        ):
            with self.assertRaises(HTTPException) as raised:
                await update_agent_instance(
                    session,
                    principal,
                    instance.id,
                    AgentInstanceUpdateRequest(status="active"),
                )

        self.assertEqual(403, raised.exception.status_code)
        authorize.assert_awaited_once()
        audit.assert_not_awaited()
        self.assertFalse(session.committed)

    async def test_agent_instance_update_allows_activation_after_license_check(self) -> None:
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        instance = AgentInstance(
            id=uuid4(),
            tenant_id=tenant_id,
            name="Draft Bot",
            slug="draft-bot",
            agent_key="customer_service",
            module_key="agent.customer_service",
            status="draft",
            visibility="tenant",
            owner_user_id=principal.user_id,
        )
        session = FakeAgentInstanceUpdateSession()
        authorization = AgentRunAuthorization(
            license_gate="enforced",
            licensed=True,
            installed=True,
            enabled=True,
            reason="active_license_and_enabled_module",
        )

        with (
            patch(
                "app.services.agent_runtime_service._get_agent_instance",
                new=AsyncMock(return_value=instance),
            ),
            patch(
                "app.services.agent_runtime_service._authorize_agent_run",
                new=AsyncMock(return_value=authorization),
            ) as authorize,
            patch(
                "app.services.agent_runtime_service.record_audit_event", new=AsyncMock()
            ) as audit,
        ):
            response = await update_agent_instance(
                session,
                principal,
                instance.id,
                AgentInstanceUpdateRequest(status="active"),
            )

        self.assertEqual("active", response.status)
        authorize.assert_awaited_once()
        audit.assert_awaited_once()
        audit_details = audit.await_args.kwargs["details"]
        self.assertEqual("enforced", audit_details["license_gate"])
        self.assertEqual("active_license_and_enabled_module", audit_details["license_gate_reason"])
        self.assertTrue(audit_details["licensed"])
        self.assertTrue(audit_details["installed"])
        self.assertTrue(audit_details["enabled"])
        self.assertTrue(session.committed)

    async def test_agent_instance_create_audit_records_license_gate_evidence(self) -> None:
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        session = FakeAgentInstanceCreateSession()
        authorization = AgentRunAuthorization(
            license_gate="enforced",
            licensed=True,
            installed=True,
            enabled=True,
            reason="active_license_and_enabled_module",
        )
        agent = FakeRegisteredAgent(required_module="agent.customer_service")

        with (
            patch("app.services.agent_runtime_service.agent_registry.get", return_value=agent),
            patch(
                "app.services.agent_runtime_service._authorize_agent_run",
                new=AsyncMock(return_value=authorization),
            ),
            patch("app.services.agent_runtime_service.ensure_license_capacity", new=AsyncMock()),
            patch(
                "app.services.agent_runtime_service._validate_agent_instance_knowledge_config",
                new=AsyncMock(),
            ),
            patch(
                "app.services.agent_runtime_service._normalize_agent_instance_department",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.services.agent_runtime_service._ensure_agent_slug_available", new=AsyncMock()
            ),
            patch(
                "app.services.agent_runtime_service.record_audit_event", new=AsyncMock()
            ) as audit,
        ):
            response = await create_agent_instance(
                session,
                principal,
                AgentInstanceCreateRequest(name="Customer Service", agent_key="customer_service"),
                request_id="req-create-agent",
            )

        self.assertEqual("active", response.status)
        self.assertEqual("agent.customer_service", response.module_key)
        audit.assert_awaited_once()
        audit_details = audit.await_args.kwargs["details"]
        self.assertEqual("customer_service", audit_details["agent_key"])
        self.assertEqual("agent.customer_service", audit_details["module_key"])
        self.assertEqual("enforced", audit_details["license_gate"])
        self.assertEqual("active_license_and_enabled_module", audit_details["license_gate_reason"])
        self.assertTrue(audit_details["licensed"])
        self.assertTrue(audit_details["installed"])
        self.assertTrue(audit_details["enabled"])
        self.assertTrue(session.committed)


class FakeDepartmentSession:
    def __init__(self, *, existing_department_id, member_department_ids):
        self.existing_department_id = existing_department_id
        self.member_department_ids = member_department_ids
        self.execute_count = 0

    async def execute(self, _statement):
        self.execute_count += 1
        if self.execute_count == 1:
            return FakeScalarOneOrNoneResult(self.existing_department_id)
        return FakeScalarsAllResult(self.member_department_ids)


class FakeAgentInstanceAccessSession:
    def __init__(self, instance: AgentInstance, *, member_department_ids, deployment_rows=None):
        self.instance = instance
        self.member_department_ids = member_department_ids
        self.deployment_rows = list(deployment_rows or [])
        self.execute_count = 0

    async def execute(self, _statement):
        self.execute_count += 1
        if self.execute_count == 1:
            return FakeScalarOneOrNoneResult(self.instance)
        if self.execute_count == 2:
            return FakeScalarsAllResult(self.member_department_ids)
        return FakeRowsAllResult(self.deployment_rows)

    async def rollback(self):
        return None


class FakeAgentInstanceListSession:
    def __init__(
        self,
        *,
        instances,
        member_department_ids,
        active_only=True,
        knowledge_bases=None,
        deployment_rows=None,
    ):
        self.active_only = active_only
        self.instances = instances
        self.member_department_ids = member_department_ids
        self.knowledge_bases = list(knowledge_bases or [])
        self.deployment_rows = list(deployment_rows or [])
        self.execute_count = 0
        self.rolled_back = False

    async def execute(self, _statement):
        self.execute_count += 1
        if self.execute_count == 1:
            instances = (
                [item for item in self.instances if item.status == "active"]
                if self.active_only
                else self.instances
            )
            return FakeScalarsAllResult(instances)
        if self.execute_count == 2:
            return FakeScalarsAllResult(self.member_department_ids)
        if self.execute_count == 3:
            return FakeScalarsAllResult(self.knowledge_bases)
        return FakeRowsAllResult(self.deployment_rows)

    async def rollback(self):
        self.rolled_back = True


class FakeScalarOneOrNoneResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeScalarsAllResult:
    def __init__(self, values):
        self.values = list(values)

    def scalars(self):
        return self

    def all(self):
        return self.values


class FakeRowsAllResult:
    def __init__(self, values):
        self.values = list(values)

    def all(self):
        return self.values


class FakeSequenceSession:
    def __init__(self, execute_results):
        self.execute_results = list(execute_results)

    async def execute(self, _statement):
        if not self.execute_results:
            raise AssertionError("Unexpected execute call.")
        return self.execute_results.pop(0)


class FakeAgentInstanceUpdateSession:
    def __init__(self):
        self.committed = False
        self.refreshed = False

    async def commit(self):
        self.committed = True

    async def refresh(self, _instance):
        self.refreshed = True


class FakeAgentInstanceCreateSession(FakeAgentInstanceUpdateSession):
    def __init__(self):
        super().__init__()
        self.added = []
        self.flushed = False

    def add(self, row):
        self.added.append(row)

    async def flush(self):
        self.flushed = True


class FakeAgentDefinition:
    def __init__(self, *, required_module: str):
        self.required_module = required_module


class FakeRegisteredAgent:
    def __init__(self, *, required_module: str):
        self.definition = FakeAgentDefinition(required_module=required_module)


if __name__ == "__main__":
    unittest.main()
