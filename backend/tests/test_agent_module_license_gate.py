from datetime import datetime, timezone
from uuid import uuid4
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.models.agent_module import AgentModule, TenantAgentModule
from app.models.audit_log import AuditLog
from app.schemas.license import AgentModuleState, LicenseStatus, LicenseStatusResponse
from app.services.agent_module_service import (
    _effective_db_state,
    _ensure_license_allows_module,
    _missing_module_dependencies,
    _missing_required_features,
    _record_module_audit,
    _row_to_catalog_entry,
    disable_agent_module_for_tenant,
    enable_agent_module_for_tenant,
    get_agent_module,
    install_agent_module_for_tenant,
)
from app.services.license_service import _build_authorized_module


def make_license(
    *,
    status: LicenseStatus = LicenseStatus.ACTIVE,
    allowed_modules: list[str] | None = None,
    allowed_features: list[str] | None = None,
) -> LicenseStatusResponse:
    return LicenseStatusResponse(
        status=status,
        license_type="enterprise",
        customer_name="AgentHive Test",
        deployment_id=uuid4(),
        install_id=uuid4(),
        machine_fingerprint_hash="sha256:test",
        allowed_modules=allowed_modules or [],
        allowed_features=allowed_features or [],
        maintenance_until=None,
        expires_at=None,
        activated_at=datetime.now(timezone.utc),
        module_count=len(allowed_modules or []),
        feature_count=len(allowed_features or []),
    )


def make_module(*, dependencies: list[str] | None = None) -> AgentModule:
    return AgentModule(
        module_key="agent.finance",
        name="Finance Agent",
        category="finance",
        priority="P2",
        description="Finance assistant",
        version="0.1.0",
        manifest={
            "scenario": "finance qa",
            "required_features": ["feature.agent_catalog", "feature.model_budget"],
            "dependencies": dependencies or [],
        },
        is_active=True,
    )


class FakeAuditSession:
    def __init__(self):
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, row):
        self.added.append(row)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class AgentModuleLicenseGateTests(unittest.TestCase):
    def test_missing_required_feature_blocks_module_action(self):
        license_status = make_license(
            allowed_modules=["agent.finance"],
            allowed_features=["feature.agent_catalog"],
        )

        with self.assertRaises(HTTPException) as raised:
            _ensure_license_allows_module(
                "agent.finance",
                ["feature.agent_catalog", "feature.model_budget"],
                license_status,
            )

        self.assertEqual(403, raised.exception.status_code)
        self.assertIn("feature.model_budget", str(raised.exception.detail))

    def test_expired_license_reports_expired_before_module_membership(self):
        license_status = make_license(status=LicenseStatus.EXPIRED)

        with self.assertRaises(HTTPException) as raised:
            _ensure_license_allows_module("agent.finance", [], license_status)

        self.assertEqual(403, raised.exception.status_code)
        self.assertIn("expired", str(raised.exception.detail))

    def test_catalog_entry_exposes_missing_features(self):
        license_status = make_license(
            allowed_modules=["agent.finance"],
            allowed_features=["feature.agent_catalog"],
        )
        module = make_module()
        state = _effective_db_state(module, {}, license_status)

        entry = _row_to_catalog_entry(module, state, license_status)

        self.assertTrue(entry.licensed)
        self.assertEqual(["feature.model_budget"], entry.missing_features)
        self.assertEqual(
            ["feature.model_budget"],
            _missing_required_features(entry.required_features, license_status),
        )

    def test_catalog_entry_exposes_missing_dependencies(self):
        license_status = make_license(
            allowed_modules=["agent.finance", "agent.report_writer"],
            allowed_features=["feature.agent_catalog", "feature.model_budget"],
        )
        module = make_module(dependencies=["agent.report_writer"])
        state = _effective_db_state(module, {}, license_status)

        entry = _row_to_catalog_entry(module, state, license_status)

        self.assertEqual(["agent.report_writer"], entry.dependencies)
        self.assertEqual(["agent.report_writer"], entry.missing_dependencies)

    def test_dependency_state_rules_distinguish_install_from_enable(self):
        dependencies = ["agent.report_writer"]
        dependency_states = {"agent.report_writer": AgentModuleState.DISABLED}

        missing_for_install = _missing_module_dependencies(
            dependencies,
            dependency_states,
            require_enabled=False,
        )
        missing_for_enable = _missing_module_dependencies(
            dependencies,
            dependency_states,
            require_enabled=True,
        )

        self.assertEqual([], missing_for_install)
        self.assertEqual(["agent.report_writer"], missing_for_enable)

    def test_catalog_entry_treats_installed_dependency_as_satisfied(self):
        license_status = make_license(
            allowed_modules=["agent.finance", "agent.report_writer"],
            allowed_features=["feature.agent_catalog", "feature.model_budget"],
        )
        module = make_module(dependencies=["agent.report_writer"])
        dependency = AgentModule(
            module_key="agent.report_writer",
            name="Report Writer",
            category="operations",
            priority="P1",
            description="Report writer",
            version="0.1.0",
            manifest={},
            is_active=True,
        )
        tenant_states = {
            dependency.id: TenantAgentModule(
                tenant_id=uuid4(),
                module_id=dependency.id,
                state=AgentModuleState.INSTALLED.value,
            )
        }
        state = _effective_db_state(module, {}, license_status)

        entry = _row_to_catalog_entry(
            module,
            state,
            license_status,
            tenant_states=tenant_states,
            module_by_key={dependency.module_key: dependency},
        )

        self.assertEqual([], entry.missing_dependencies)

    def test_license_scope_reports_authorized_but_not_installed_module(self):
        license_status = make_license(
            allowed_modules=["agent.finance"],
            allowed_features=["feature.agent_catalog", "feature.model_budget"],
        )

        module = _build_authorized_module(
            module_id="agent.finance",
            name="Finance Agent",
            license_status=license_status,
            tenant_module_state=None,
        )

        self.assertTrue(module.licensed)
        self.assertFalse(module.installed)
        self.assertFalse(module.enabled)
        self.assertEqual(AgentModuleState.NOT_INSTALLED, module.state)

    def test_license_scope_reports_enabled_tenant_module(self):
        license_status = make_license(
            allowed_modules=["agent.finance"],
            allowed_features=["feature.agent_catalog", "feature.model_budget"],
        )

        module = _build_authorized_module(
            module_id="agent.finance",
            name="Finance Agent",
            license_status=license_status,
            tenant_module_state=AgentModuleState.ENABLED,
        )

        self.assertTrue(module.licensed)
        self.assertTrue(module.installed)
        self.assertTrue(module.enabled)
        self.assertEqual(AgentModuleState.ENABLED, module.state)

    def test_license_scope_keeps_expired_entitlement_visible(self):
        license_status = make_license(
            status=LicenseStatus.EXPIRED,
            allowed_modules=["agent.finance"],
            allowed_features=["feature.agent_catalog", "feature.model_budget"],
        )

        module = _build_authorized_module(
            module_id="agent.finance",
            name="Finance Agent",
            license_status=license_status,
            tenant_module_state=AgentModuleState.ENABLED,
        )

        self.assertTrue(module.licensed)
        self.assertTrue(module.installed)
        self.assertFalse(module.enabled)
        self.assertEqual(AgentModuleState.EXPIRED, module.state)

    def test_media_generation_module_exposes_model_capability_contract(self):
        detail = get_agent_module("agent.video_generation")

        self.assertIn("feature.media_generation", detail.required_features)
        self.assertIn("video_generation", detail.recommended_model_capabilities)
        self.assertIn("media_gateway", detail.recommended_orchestration_runtimes)
        self.assertEqual("video", detail.default_config["generation_kind"])


class AgentModuleFailureAuditTests(unittest.IsolatedAsyncioTestCase):
    async def test_success_audit_records_module_state_transition(self):
        module = make_module()
        session = FakeAuditSession()
        tenant_id = uuid4()
        actor_id = uuid4()

        await _record_module_audit(
            session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            request_id="req-module-success",
            module=module,
            action="agent_module.enable",
            previous_state=AgentModuleState.INSTALLED.value,
            next_state=AgentModuleState.ENABLED.value,
            message="Agent module enabled.",
        )

        self.assertEqual(1, len(session.added))
        event = session.added[0]
        self.assertEqual("agent_module.enable", event.action)
        self.assertEqual("success", event.status)
        self.assertEqual(module.id, event.resource_id)
        self.assertEqual(module.module_key, event.details["module_key"])
        self.assertEqual(AgentModuleState.INSTALLED.value, event.details["previous_state"])
        self.assertEqual(AgentModuleState.ENABLED.value, event.details["next_state"])
        self.assertEqual("Agent module enabled.", event.details["message"])

    async def test_failed_install_records_failure_audit_without_swallowing_error(self):
        module = make_module()
        session = FakeAuditSession()
        tenant_id = uuid4()
        actor_id = uuid4()

        with (
            patch(
                "app.services.agent_module_service._get_module_row", AsyncMock(return_value=module)
            ),
            patch(
                "app.services.agent_module_service._ensure_db_module_licensed",
                AsyncMock(
                    side_effect=HTTPException(
                        status_code=403,
                        detail="Agent module is not licensed for this deployment.",
                    )
                ),
            ),
        ):
            with self.assertRaises(HTTPException) as raised:
                await install_agent_module_for_tenant(
                    session,
                    module.module_key,
                    tenant_id=tenant_id,
                    actor_id=actor_id,
                    request_id="req-module-denied",
                )

        self.assertEqual(403, raised.exception.status_code)
        self.assertEqual(1, session.commits)
        self.assertEqual(1, session.rollbacks)
        self.assertEqual(1, len(session.added))
        event = session.added[0]
        self.assertIsInstance(event, AuditLog)
        self.assertEqual("agent_module.install", event.action)
        self.assertEqual("failure", event.status)
        self.assertEqual(tenant_id, event.tenant_id)
        self.assertEqual(actor_id, event.actor_id)
        self.assertEqual(module.id, event.resource_id)
        self.assertEqual(module.module_key, event.details["module_key"])
        self.assertEqual(403, event.details["status_code"])
        self.assertIn("not licensed", event.details["reason"])

    async def test_failed_enable_records_dependency_failure_audit(self):
        module = make_module(dependencies=["agent.report_writer"])
        session = FakeAuditSession()
        tenant_id = uuid4()
        actor_id = uuid4()

        with (
            patch(
                "app.services.agent_module_service._get_module_row", AsyncMock(return_value=module)
            ),
            patch(
                "app.services.agent_module_service._ensure_db_module_licensed",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.services.agent_module_service._ensure_db_module_dependencies",
                AsyncMock(
                    side_effect=HTTPException(
                        status_code=409,
                        detail="Agent module requires enabled dependencies: agent.report_writer.",
                    )
                ),
            ),
        ):
            with self.assertRaises(HTTPException) as raised:
                await enable_agent_module_for_tenant(
                    session,
                    module.module_key,
                    tenant_id=tenant_id,
                    actor_id=actor_id,
                    request_id="req-module-dependency",
                )

        self.assertEqual(409, raised.exception.status_code)
        self.assertEqual(1, session.commits)
        self.assertEqual(1, session.rollbacks)
        event = session.added[0]
        self.assertEqual("agent_module.enable", event.action)
        self.assertEqual("failure", event.status)
        self.assertEqual(module.id, event.resource_id)
        self.assertEqual(module.module_key, event.details["module_key"])
        self.assertEqual(409, event.details["status_code"])
        self.assertIn("agent.report_writer", event.details["reason"])

    async def test_failed_disable_records_unknown_module_failure_audit(self):
        session = FakeAuditSession()
        tenant_id = uuid4()
        actor_id = uuid4()
        requested_module_id = "agent.unknown"

        with patch(
            "app.services.agent_module_service._get_module_row",
            AsyncMock(
                side_effect=HTTPException(
                    status_code=404,
                    detail="Agent module not found.",
                )
            ),
        ):
            with self.assertRaises(HTTPException) as raised:
                await disable_agent_module_for_tenant(
                    session,
                    requested_module_id,
                    tenant_id=tenant_id,
                    actor_id=actor_id,
                    request_id="req-module-missing",
                )

        self.assertEqual(404, raised.exception.status_code)
        self.assertEqual(1, session.commits)
        self.assertEqual(1, session.rollbacks)
        event = session.added[0]
        self.assertEqual("agent_module.disable", event.action)
        self.assertEqual("failure", event.status)
        self.assertIsNone(event.resource_id)
        self.assertEqual(requested_module_id, event.details["module_key"])
        self.assertEqual(requested_module_id, event.details["requested_module_id"])
        self.assertEqual(404, event.details["status_code"])
        self.assertIn("not found", event.details["reason"])

    async def test_disable_reconciles_active_agent_instances(self):
        module = make_module()
        tenant_id = uuid4()
        actor_id = uuid4()
        session = FakeAuditSession()
        tenant_module = TenantAgentModule(
            tenant_id=tenant_id,
            module_id=module.id,
            state=AgentModuleState.ENABLED.value,
        )
        license_status = make_license(
            allowed_modules=[module.module_key],
            allowed_features=["feature.agent_catalog", "feature.model_budget"],
        )

        with (
            patch(
                "app.services.agent_module_service._get_module_row", AsyncMock(return_value=module)
            ),
            patch(
                "app.services.agent_module_service._ensure_db_module_licensed",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.services.agent_module_service.get_license_status_for_tenant",
                AsyncMock(return_value=license_status),
            ),
            patch(
                "app.services.agent_module_service._get_or_create_tenant_module",
                AsyncMock(return_value=tenant_module),
            ),
            patch(
                "app.services.agent_module_service.reconcile_agent_instances_for_license_status",
                AsyncMock(return_value=3),
            ) as reconcile,
        ):
            response = await disable_agent_module_for_tenant(
                session,
                module.module_key,
                tenant_id=tenant_id,
                actor_id=actor_id,
                request_id="req-disable-module",
            )

        self.assertEqual(AgentModuleState.DISABLED, response.state)
        self.assertEqual(AgentModuleState.DISABLED.value, tenant_module.state)
        reconcile.assert_awaited_once()
        event = session.added[0]
        self.assertEqual("agent_module.disable", event.action)
        self.assertEqual(3, event.details["disabled_agent_instance_count"])


if __name__ == "__main__":
    unittest.main()
