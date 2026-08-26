from datetime import datetime, timezone
import unittest
from uuid import uuid4

from app.models.agent_module import AgentInstance, AgentModule, TenantAgentModule
from app.models.audit_log import AuditLog
from app.schemas.license import AgentModuleState, LicenseStatus, LicenseStatusResponse
from app.services.agent_instance_reconcile_service import (
    reconcile_agent_instances_for_license_status,
)


def make_license_status(
    *,
    status: LicenseStatus = LicenseStatus.ACTIVE,
    allowed_modules: list[str] | None = None,
) -> LicenseStatusResponse:
    return LicenseStatusResponse(
        status=status,
        license_type="enterprise",
        customer_name="AgentHive Test",
        deployment_id=uuid4(),
        install_id=uuid4(),
        machine_fingerprint_hash="sha256:test",
        allowed_modules=allowed_modules or [],
        allowed_features=["feature.agent_catalog"],
        maintenance_until=None,
        expires_at=None,
        activated_at=datetime.now(timezone.utc),
        module_count=len(allowed_modules or []),
        feature_count=1,
    )


class AgentInstanceReconcileServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_reconcile_disables_only_instances_that_are_no_longer_runnable(self):
        tenant_id = uuid4()
        actor_id = uuid4()
        enabled_module = AgentModule(
            module_key="agent.customer_service",
            name="Customer Service",
            category="customer_success",
            priority="P0",
            version="0.1.0",
            manifest={},
            is_active=True,
        )
        disabled_module = AgentModule(
            module_key="agent.finance",
            name="Finance",
            category="finance",
            priority="P2",
            version="0.1.0",
            manifest={},
            is_active=True,
        )
        runnable_tenant_module = TenantAgentModule(
            tenant_id=tenant_id,
            module_id=enabled_module.id,
            state=AgentModuleState.ENABLED.value,
        )
        runnable_instance = AgentInstance(
            tenant_id=tenant_id,
            name="Runnable",
            slug="runnable",
            agent_key="customer_service",
            module_key=enabled_module.module_key,
            status="active",
        )
        stale_instance = AgentInstance(
            tenant_id=tenant_id,
            name="Stale",
            slug="stale",
            agent_key="finance",
            module_key=disabled_module.module_key,
            status="active",
            metadata_json={"existing": "kept"},
        )
        session = FakeReconcileSession(
            modules=[enabled_module, disabled_module],
            tenant_modules=[runnable_tenant_module],
            instances=[runnable_instance, stale_instance],
        )

        disabled_count = await reconcile_agent_instances_for_license_status(
            session,
            tenant_id=tenant_id,
            license_status=make_license_status(
                allowed_modules=[enabled_module.module_key, disabled_module.module_key],
            ),
            actor_id=actor_id,
            request_id="req-reconcile",
            reason="license_activation",
        )

        self.assertEqual(1, disabled_count)
        self.assertEqual("active", runnable_instance.status)
        self.assertEqual("disabled", stale_instance.status)
        self.assertEqual("kept", stale_instance.metadata_json["existing"])
        self.assertEqual(
            "license_activation", stale_instance.metadata_json["runtime_disabled_reason"]
        )
        audit_events = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual(1, len(audit_events))
        self.assertEqual("agent.instance.runtime_disable", audit_events[0].action)
        self.assertEqual(stale_instance.id, audit_events[0].resource_id)

    async def test_inactive_license_disables_all_active_instances(self):
        tenant_id = uuid4()
        instance = AgentInstance(
            tenant_id=tenant_id,
            name="Customer Service",
            slug="customer-service",
            agent_key="customer_service",
            module_key="agent.customer_service",
            status="active",
        )
        session = FakeReconcileSession(modules=[], tenant_modules=[], instances=[instance])

        disabled_count = await reconcile_agent_instances_for_license_status(
            session,
            tenant_id=tenant_id,
            license_status=make_license_status(status=LicenseStatus.INACTIVE),
            reason="license_deactivated",
        )

        self.assertEqual(1, disabled_count)
        self.assertEqual("disabled", instance.status)
        self.assertEqual("license_deactivated", instance.metadata_json["runtime_disabled_reason"])


class FakeReconcileSession:
    def __init__(self, *, modules, tenant_modules, instances):
        self.modules = modules
        self.tenant_modules = tenant_modules
        self.instances = instances
        self.added = []

    async def execute(self, statement):
        statement_text = str(statement)
        if "tenant_agent_modules" in statement_text:
            return FakeScalarsAllResult(self.tenant_modules)
        if "agent_modules" in statement_text:
            return FakeScalarsAllResult(self.modules)
        if "agent_instances" in statement_text:
            return FakeScalarsAllResult(self.instances)
        return FakeScalarsAllResult([])

    def add(self, row):
        self.added.append(row)


class FakeScalarsAllResult:
    def __init__(self, values):
        self.values = list(values)

    def scalars(self):
        return self

    def all(self):
        return self.values


if __name__ == "__main__":
    unittest.main()
