import base64
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException

from app.core import install_identity
from app.models.audit_log import AuditLog
from app.models.license import License, LicenseActivation
from app.models.tenant import Tenant
from app.schemas.license import LicenseActivationRequest, LicenseStatus
from app.services.license_service import get_activation_request
from app.services.license_service import (
    _activation_data_from_payload,
    _deactivate_license_activations,
    _enforce_license_capacity,
    _inactive_license_status,
    _load_current_license,
    _status_from_record,
    _supersede_active_licenses,
    activate_license_for_tenant,
    deactivate_license_for_tenant,
    get_activation_request_for_tenant,
)


class LicenseActivationRequestTest(unittest.IsolatedAsyncioTestCase):
    def test_activation_request_exports_verifiable_request_code(self) -> None:
        tenant_id = uuid4()

        with tempfile.TemporaryDirectory() as temp_dir:
            original_path = install_identity.settings.install_id_path
            install_identity.settings.install_id_path = str(
                Path(temp_dir) / "install-identity.json"
            )
            try:
                request = get_activation_request(tenant_id)
            finally:
                install_identity.settings.install_id_path = original_path

        decoded = base64.urlsafe_b64decode(request.request_code.encode("ascii"))
        document = json.loads(decoded.decode("utf-8"))

        self.assertEqual(sha256(decoded).hexdigest(), request.request_hash)
        self.assertEqual("agenthive.offline_activation_request.v1", request.request_format)
        self.assertEqual("AgentHive", document["product"])
        self.assertEqual(str(tenant_id), document["tenant_id"])
        self.assertEqual(str(request.deployment_id), document["deployment_id"])
        self.assertEqual(str(request.install_id), document["install_id"])
        self.assertEqual(request.machine_fingerprint_hash, document["machine_fingerprint_hash"])
        self.assertEqual(request.request_id, document["request_id"])

    async def test_activation_request_export_records_safe_audit(self) -> None:
        tenant_id = uuid4()
        actor_id = uuid4()
        session = FakeAuditSession()

        with tempfile.TemporaryDirectory() as temp_dir:
            original_path = install_identity.settings.install_id_path
            install_identity.settings.install_id_path = str(
                Path(temp_dir) / "install-identity.json"
            )
            try:
                request = await get_activation_request_for_tenant(
                    session,
                    tenant_id=tenant_id,
                    actor_id=actor_id,
                    request_id="req-export-license",
                    ip_address="127.0.0.1",
                    user_agent="AgentHive Test",
                )
            finally:
                install_identity.settings.install_id_path = original_path

        self.assertEqual(1, session.commits)
        self.assertEqual(1, len(session.added))
        event = session.added[0]
        self.assertIsInstance(event, AuditLog)
        self.assertEqual("license.activation_request.export", event.action)
        self.assertEqual(tenant_id, event.tenant_id)
        self.assertEqual(actor_id, event.actor_id)
        self.assertEqual(request.request_id, event.details["activation_request_id"])
        self.assertEqual(request.request_hash, event.details["activation_request_hash"])
        self.assertEqual(str(request.deployment_id), event.details["deployment_id"])
        self.assertEqual(str(request.install_id), event.details["install_id"])
        self.assertTrue(event.details["machine_fingerprint_hash_present"])
        self.assertNotIn(request.request_code, json.dumps(event.details))
        self.assertNotIn(request.machine_fingerprint_hash, json.dumps(event.details))

    def test_license_status_reports_runtime_identity_mismatch_issues(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            original_path = install_identity.settings.install_id_path
            install_identity.settings.install_id_path = str(
                Path(temp_dir) / "install-identity.json"
            )
            try:
                current_identity = install_identity.get_install_identity()
                license_record = License(
                    tenant_id=uuid4(),
                    license_key_hash="hash",
                    license_type="enterprise",
                    customer_name="AgentHive Test",
                    status=LicenseStatus.ACTIVE.value,
                    deployment_id=uuid4(),
                    install_id=uuid4(),
                    machine_fingerprint_hash="0" * 64,
                    allowed_modules=["agent.customer_service"],
                    allowed_features=["feature.agent_catalog"],
                    max_users=100,
                    max_agents=20,
                    max_kb_size_gb=Decimal("30.5"),
                )

                status = _status_from_record(license_record)
            finally:
                install_identity.settings.install_id_path = original_path

        self.assertEqual(LicenseStatus.MISMATCH, status.status)
        self.assertEqual([], status.allowed_modules)
        self.assertEqual([], status.allowed_features)
        self.assertEqual(current_identity.deployment_id, status.runtime_deployment_id)
        self.assertIn("deployment_id_mismatch", status.verification_issues)
        self.assertIn("install_id_mismatch", status.verification_issues)
        self.assertIn("machine_fingerprint_mismatch", status.verification_issues)
        self.assertEqual(100, status.max_users)
        self.assertEqual(20, status.max_agents)
        self.assertEqual(Decimal("30.5"), status.max_kb_size_gb)

    def test_inactive_license_status_exposes_runtime_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            original_path = install_identity.settings.install_id_path
            install_identity.settings.install_id_path = str(
                Path(temp_dir) / "install-identity.json"
            )
            try:
                status = _inactive_license_status()
            finally:
                install_identity.settings.install_id_path = original_path

        self.assertEqual(LicenseStatus.INACTIVE, status.status)
        self.assertEqual(status.deployment_id, status.runtime_deployment_id)
        self.assertEqual(status.install_id, status.runtime_install_id)
        self.assertEqual(status.machine_fingerprint_hash, status.runtime_machine_fingerprint_hash)
        self.assertEqual(["no_active_license"], status.verification_issues)

    def test_license_capacity_allows_under_limit(self) -> None:
        status = _inactive_license_status().model_copy(
            update={
                "status": LicenseStatus.ACTIVE,
                "max_users": 3,
                "max_agents": 2,
            }
        )

        _enforce_license_capacity(
            resource="users",
            current_count=2,
            increment=1,
            license_status=status,
        )
        _enforce_license_capacity(
            resource="agents",
            current_count=1,
            increment=1,
            license_status=status,
        )

    def test_license_capacity_blocks_over_limit(self) -> None:
        status = _inactive_license_status().model_copy(
            update={
                "status": LicenseStatus.ACTIVE,
                "max_users": 1,
            }
        )

        with self.assertRaises(Exception) as raised:
            _enforce_license_capacity(
                resource="users",
                current_count=1,
                increment=1,
                license_status=status,
            )

        self.assertIn("License capacity exceeded", str(raised.exception))

    def test_license_capacity_blocks_knowledge_storage_over_limit(self) -> None:
        status = _inactive_license_status().model_copy(
            update={
                "status": LicenseStatus.ACTIVE,
                "max_kb_size_gb": Decimal("0.01"),
            }
        )

        with self.assertRaises(HTTPException) as raised:
            _enforce_license_capacity(
                resource="knowledge_storage_bytes",
                current_count=10 * 1024 * 1024,
                increment=2 * 1024 * 1024,
                license_status=status,
            )

        self.assertEqual(403, raised.exception.status_code)
        self.assertIn("knowledge storage", str(raised.exception.detail))

    def test_license_capacity_rejects_unknown_knowledge_document_size(self) -> None:
        status = _inactive_license_status().model_copy(
            update={
                "status": LicenseStatus.ACTIVE,
                "max_kb_size_gb": Decimal("1.0"),
            }
        )

        with self.assertRaises(HTTPException) as raised:
            _enforce_license_capacity(
                resource="knowledge_storage_bytes",
                current_count=0,
                increment=0,
                license_status=status,
            )

        self.assertEqual(422, raised.exception.status_code)
        self.assertIn("document size is required", str(raised.exception.detail))

    def test_invalid_signed_license_signature_is_rejected_before_activation_data(self) -> None:
        public_key_pem = _test_public_key_pem()
        document = {
            "payload": {
                "schema_version": 1,
                "product": "AgentHive",
                "license_id": "lic-invalid-signature",
                "license_type": "enterprise",
                "customer_name": "AgentHive Test",
                "deployment_id": str(uuid4()),
                "install_id": str(uuid4()),
                "machine_fingerprint_hash": "a" * 64,
                "allowed_modules": ["agent.customer_service"],
                "allowed_features": ["feature.agent_catalog"],
                "issued_at": datetime.now(timezone.utc).isoformat(),
            },
            "signature_alg": "Ed25519",
            "signature": base64.b64encode(b"invalid-signature").decode("ascii"),
        }

        with patch(
            "app.services.license_service._load_license_public_key", return_value=public_key_pem
        ):
            with self.assertRaises(HTTPException) as raised:
                _activation_data_from_payload(json.dumps(document), datetime.now(timezone.utc))

        self.assertEqual(400, raised.exception.status_code)
        self.assertIn("signature_verification_failed", str(raised.exception.detail))

    async def test_failed_license_activation_records_redacted_failure_audit(self) -> None:
        public_key_pem = _test_public_key_pem()
        tenant_id = uuid4()
        actor_id = uuid4()
        tenant = Tenant(id=tenant_id, name="AgentHive Buyer", slug="buyer")
        invalid_license = json.dumps(
            {
                "payload": {
                    "schema_version": 1,
                    "product": "AgentHive",
                    "license_id": "lic-invalid-signature",
                    "license_type": "enterprise",
                    "customer_name": "AgentHive Test",
                    "deployment_id": str(uuid4()),
                    "install_id": str(uuid4()),
                    "machine_fingerprint_hash": "a" * 64,
                    "allowed_modules": ["agent.customer_service"],
                    "allowed_features": ["feature.agent_catalog"],
                    "issued_at": datetime.now(timezone.utc).isoformat(),
                },
                "signature_alg": "Ed25519",
                "signature": base64.b64encode(b"invalid-signature").decode("ascii"),
            }
        )
        session = FakeLicenseActivationSession(
            tenant=tenant,
            active_licenses=[],
            activations_by_license_id={},
        )

        with patch(
            "app.services.license_service._load_license_public_key", return_value=public_key_pem
        ):
            with self.assertRaises(HTTPException) as raised:
                await activate_license_for_tenant(
                    session,
                    LicenseActivationRequest(
                        license_key=invalid_license,
                        activation_code="offline-secret-code",
                    ),
                    tenant_id=tenant_id,
                    actor_id=actor_id,
                    request_id="req-license-failure",
                    ip_address="127.0.0.1",
                    user_agent="AgentHive Test",
                )

        self.assertEqual(400, raised.exception.status_code)
        self.assertEqual(1, session.commits)
        self.assertEqual(1, session.rollbacks)
        self.assertFalse(any(isinstance(row, License) for row in session.added))
        event = session.added[0]
        self.assertIsInstance(event, AuditLog)
        self.assertEqual("license.activate", event.action)
        self.assertEqual("failure", event.status)
        self.assertEqual(tenant_id, event.tenant_id)
        self.assertEqual(actor_id, event.actor_id)
        self.assertEqual(400, event.details["status_code"])
        self.assertEqual("signed_license_json", event.details["license_input_format"])
        self.assertEqual("offline", event.details["activation_mode"])
        self.assertIn("signature_verification_failed", event.details["reason"])
        self.assertNotIn("offline-secret-code", json.dumps(event.details))
        self.assertNotIn(invalid_license, json.dumps(event.details))

    async def test_current_license_query_prefers_active_license_over_newer_failed_attempts(
        self,
    ) -> None:
        session = FakeLicenseQuerySession()

        await _load_current_license(session, uuid4())

        order_by = [str(clause) for clause in session.statement._order_by_clauses]
        self.assertEqual("licenses.status = :status_1 DESC", order_by[0])
        self.assertEqual("licenses.created_at DESC", order_by[1])

    async def test_deactivate_license_activations_closes_open_activation_rows(self) -> None:
        tenant_id = uuid4()
        license_id = uuid4()
        now = datetime.now(timezone.utc)
        open_activation = LicenseActivation(
            tenant_id=tenant_id,
            license_id=license_id,
            deployment_id=uuid4(),
            install_id=uuid4(),
            machine_fingerprint_hash="a" * 64,
            status=LicenseStatus.ACTIVE.value,
        )
        already_closed = LicenseActivation(
            tenant_id=tenant_id,
            license_id=license_id,
            deployment_id=uuid4(),
            install_id=uuid4(),
            machine_fingerprint_hash="b" * 64,
            status=LicenseStatus.INACTIVE.value,
            deactivated_at=now,
        )
        session = FakeActivationSession([open_activation, already_closed])

        closed_count = await _deactivate_license_activations(
            session,
            tenant_id=tenant_id,
            license_id=license_id,
            deactivated_at=now,
        )

        self.assertEqual(1, closed_count)
        self.assertEqual(LicenseStatus.INACTIVE.value, open_activation.status)
        self.assertEqual(now, open_activation.deactivated_at)
        self.assertEqual(now, open_activation.updated_at)
        self.assertEqual(now, already_closed.deactivated_at)

    async def test_supersede_active_licenses_inactivates_previous_active_license_and_activation(
        self,
    ) -> None:
        tenant_id = uuid4()
        license_id = uuid4()
        now = datetime.now(timezone.utc)
        active_license = License(
            id=license_id,
            tenant_id=tenant_id,
            license_key_hash="old-hash",
            license_type="enterprise",
            customer_name="AgentHive Test",
            status=LicenseStatus.ACTIVE.value,
            deployment_id=uuid4(),
            install_id=uuid4(),
            machine_fingerprint_hash="a" * 64,
            allowed_modules=["agent.customer_service"],
            allowed_features=["feature.agent_catalog"],
        )
        activation = LicenseActivation(
            tenant_id=tenant_id,
            license_id=license_id,
            deployment_id=active_license.deployment_id,
            install_id=active_license.install_id,
            machine_fingerprint_hash=active_license.machine_fingerprint_hash,
            status=LicenseStatus.ACTIVE.value,
        )
        session = FakeSupersedeSession([active_license], {license_id: [activation]})

        superseded = await _supersede_active_licenses(
            session,
            tenant_id=tenant_id,
            deactivated_at=now,
        )

        self.assertEqual(1, len(superseded))
        self.assertEqual(license_id, superseded[0].license_id)
        self.assertEqual("enterprise", superseded[0].license_type)
        self.assertEqual("AgentHive Test", superseded[0].customer_name)
        self.assertEqual(1, superseded[0].deactivated_activation_count)
        self.assertEqual(LicenseStatus.INACTIVE.value, active_license.status)
        self.assertEqual(now, active_license.updated_at)
        self.assertEqual(LicenseStatus.INACTIVE.value, activation.status)
        self.assertEqual(now, activation.deactivated_at)

    async def test_activate_license_records_supersede_audit_for_previous_active_license(
        self,
    ) -> None:
        tenant_id = uuid4()
        actor_id = uuid4()
        old_license = License(
            tenant_id=tenant_id,
            license_key_hash="old-hash",
            license_type="standard",
            customer_name="Old Customer",
            status=LicenseStatus.ACTIVE.value,
            deployment_id=uuid4(),
            install_id=uuid4(),
            machine_fingerprint_hash="a" * 64,
            allowed_modules=["agent.customer_service"],
            allowed_features=["feature.agent_catalog"],
        )
        old_activation = LicenseActivation(
            tenant_id=tenant_id,
            license_id=old_license.id,
            deployment_id=old_license.deployment_id,
            install_id=old_license.install_id,
            machine_fingerprint_hash=old_license.machine_fingerprint_hash,
            status=LicenseStatus.ACTIVE.value,
        )
        tenant = Tenant(id=tenant_id, name="AgentHive Buyer", slug="buyer")
        session = FakeLicenseActivationSession(
            tenant=tenant,
            active_licenses=[old_license],
            activations_by_license_id={old_license.id: [old_activation]},
        )

        with patch(
            "app.services.license_service.reconcile_agent_instances_for_license_status",
            AsyncMock(return_value=2),
        ) as reconcile:
            response = await activate_license_for_tenant(
                session,
                LicenseActivationRequest(license_key="enterprise-active-key"),
                tenant_id=tenant_id,
                actor_id=actor_id,
                request_id="req-license-replace",
                ip_address="127.0.0.1",
                user_agent="AgentHive Test",
            )

        self.assertEqual(LicenseStatus.ACTIVE, response.status)
        self.assertEqual(LicenseStatus.INACTIVE.value, old_license.status)
        self.assertEqual(LicenseStatus.INACTIVE.value, old_activation.status)
        self.assertIsNotNone(old_activation.deactivated_at)
        self.assertEqual(1, session.flushes)
        self.assertEqual(1, session.commits)

        audit_events = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual(
            ["license.supersede", "license.activate"], [event.action for event in audit_events]
        )
        supersede_event = audit_events[0]
        activate_event = audit_events[1]
        new_license = next(
            row for row in session.added if isinstance(row, License) and row.id != old_license.id
        )

        self.assertEqual(old_license.id, supersede_event.resource_id)
        self.assertEqual(actor_id, supersede_event.actor_id)
        self.assertEqual(str(new_license.id), supersede_event.details["replacement_license_id"])
        self.assertEqual("active", supersede_event.details["previous_status"])
        self.assertEqual("inactive", supersede_event.details["next_status"])
        self.assertEqual(1, supersede_event.details["deactivated_activation_count"])
        self.assertEqual(new_license.id, activate_event.resource_id)
        self.assertEqual(1, activate_event.details["superseded_license_count"])
        self.assertEqual(2, activate_event.details["disabled_agent_instance_count"])
        reconcile.assert_awaited_once()

    async def test_deactivate_without_active_license_records_noop_audit(self) -> None:
        tenant_id = uuid4()
        actor_id = uuid4()
        session = FakeAuditSession()

        with (
            patch(
                "app.services.license_service._load_current_license", AsyncMock(return_value=None)
            ),
            patch(
                "app.services.license_service.reconcile_agent_instances_for_license_status",
                AsyncMock(return_value=1),
            ) as reconcile,
        ):
            response = await deactivate_license_for_tenant(
                session,
                tenant_id=tenant_id,
                actor_id=actor_id,
                request_id="req-license-noop",
                ip_address="127.0.0.1",
                user_agent="AgentHive Test",
            )

        self.assertEqual(LicenseStatus.INACTIVE, response.status)
        self.assertEqual(1, session.commits)
        self.assertEqual(1, len(session.added))
        event = session.added[0]
        self.assertIsInstance(event, AuditLog)
        self.assertEqual("license.deactivate", event.action)
        self.assertEqual("success", event.status)
        self.assertEqual(tenant_id, event.tenant_id)
        self.assertEqual(actor_id, event.actor_id)
        self.assertEqual("no_active_license", event.details["result"])
        self.assertEqual(1, event.details["disabled_agent_instance_count"])
        reconcile.assert_awaited_once()


def _test_public_key_pem() -> str:
    private_key = Ed25519PrivateKey.generate()
    return (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )


class FakeLicenseQuerySession:
    def __init__(self):
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return FakeScalarOneOrNoneResult(None)


class FakeScalarOneOrNoneResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeActivationSession:
    def __init__(self, rows):
        self.rows = rows
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        open_rows = [row for row in self.rows if row.deactivated_at is None]
        return FakeScalarsAllResult(open_rows)


class FakeSupersedeSession:
    def __init__(self, active_licenses, activations_by_license_id):
        self.active_licenses = list(active_licenses)
        self.activations_by_license_id = activations_by_license_id
        self.execute_count = 0

    async def execute(self, _statement):
        self.execute_count += 1
        if self.execute_count == 1:
            return FakeScalarsAllResult(self.active_licenses)
        license_id = self.active_licenses[self.execute_count - 2].id
        open_rows = [
            row
            for row in self.activations_by_license_id.get(license_id, [])
            if row.deactivated_at is None
        ]
        return FakeScalarsAllResult(open_rows)


class FakeLicenseActivationSession(FakeSupersedeSession):
    def __init__(self, *, tenant, active_licenses, activations_by_license_id):
        super().__init__(active_licenses, activations_by_license_id)
        self.tenant = tenant
        self.added = []
        self.flushes = 0
        self.commits = 0
        self.rollbacks = 0

    async def get(self, _model, _id):
        return self.tenant

    def add(self, row):
        self.added.append(row)

    async def flush(self):
        self.flushes += 1

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class FakeAuditSession:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, row):
        self.added.append(row)

    async def commit(self):
        self.commits += 1


class FakeScalarsAllResult:
    def __init__(self, values):
        self.values = list(values)

    def scalars(self):
        return self

    def all(self):
        return self.values


if __name__ == "__main__":
    unittest.main()
