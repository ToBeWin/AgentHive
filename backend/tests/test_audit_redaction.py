from uuid import uuid4
from datetime import datetime, timezone
import csv
import io
import json
import unittest

from app.models.audit_log import AuditLog
from app.services.audit_service import record_audit_event
from app.services.audit_query_service import (
    _audit_log_filters,
    _to_audit_log_item,
    audit_logs_to_csv,
    audit_logs_to_json,
    export_audit_logs_json,
)
from app.services.audit_redaction import REDACTED, redact_audit_details


class FakeAuditSession:
    def __init__(self):
        self.added = []

    def add(self, row):
        self.added.append(row)


class FakeAuditExportSession:
    def __init__(self, rows):
        self.rows = rows
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, _statement):
        return FakeScalarsAllResult(self.rows)

    def add(self, row):
        self.added.append(row)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class FakeScalarsAllResult:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return self.rows


class AuditRedactionTests(unittest.IsolatedAsyncioTestCase):
    def test_audit_filters_include_created_at_range(self):
        principal = type(
            "PrincipalStub",
            (),
            {"tenant_id": uuid4()},
        )()
        created_from = datetime(2026, 6, 1, tzinfo=timezone.utc)
        created_to = datetime(2026, 6, 12, tzinfo=timezone.utc)

        filters = _audit_log_filters(
            principal,
            created_from=created_from,
            created_to=created_to,
        )
        compiled_filters = " ".join(str(filter_) for filter_ in filters)

        self.assertIn("audit_logs.created_at >= ", compiled_filters)
        self.assertIn("audit_logs.created_at <= ", compiled_filters)

    def test_redacts_nested_sensitive_keys_without_mutating_safe_values(self):
        details = {
            "provider_key": "qwen",
            "api_key": "sk-live-secret",
            "nested": {
                "Authorization": "Bearer token",
                "safe": "visible",
                "items": [
                    {"license_key": "agenthive-license"},
                    {"count": 3, "secret_ref": "encrypted"},
                ],
            },
        }

        redacted = redact_audit_details(details)

        self.assertEqual("qwen", redacted["provider_key"])
        self.assertEqual(REDACTED, redacted["api_key"])
        self.assertEqual(REDACTED, redacted["nested"]["Authorization"])
        self.assertEqual("visible", redacted["nested"]["safe"])
        self.assertEqual(REDACTED, redacted["nested"]["items"][0]["license_key"])
        self.assertEqual(REDACTED, redacted["nested"]["items"][1]["secret_ref"])
        self.assertEqual(3, redacted["nested"]["items"][1]["count"])

    def test_model_token_usage_fields_are_not_treated_as_auth_tokens(self):
        redacted = redact_audit_details(
            {
                "max_tokens": 1024,
                "total_tokens": 2048,
                "token_limit": 10000,
                "token": "jwt-like-value",
                "secret_configured": True,
            }
        )

        self.assertEqual(1024, redacted["max_tokens"])
        self.assertEqual(2048, redacted["total_tokens"])
        self.assertEqual(10000, redacted["token_limit"])
        self.assertEqual(REDACTED, redacted["token"])
        self.assertTrue(redacted["secret_configured"])

    def test_audit_log_item_returns_redacted_details(self):
        row = AuditLog(
            tenant_id=uuid4(),
            action="models.credential.upsert",
            details={
                "owner_type": "tenant",
                "masked_secret": "sk-...cret",
                "api_key": "sk-raw",
            },
        )

        item = _to_audit_log_item(row)

        self.assertEqual("tenant", item.details["owner_type"])
        self.assertEqual(REDACTED, item.details["masked_secret"])
        self.assertEqual(REDACTED, item.details["api_key"])

    def test_audit_csv_export_uses_redacted_details(self):
        row = AuditLog(
            id=uuid4(),
            tenant_id=uuid4(),
            request_id="req-1",
            actor_id=uuid4(),
            actor_type="user",
            action="models.credential.upsert",
            resource_type="llm_credential",
            resource_id=uuid4(),
            status="success",
            ip_address="127.0.0.1",
            user_agent="AgentHive Test",
            details={"api_key": "sk-raw", "token_limit": 100},
            created_at=datetime(2026, 6, 12, tzinfo=timezone.utc),
        )

        csv_body = audit_logs_to_csv([_to_audit_log_item(row)])
        exported = next(csv.DictReader(io.StringIO(csv_body)))
        exported_details = json.loads(exported["details_json"])

        self.assertIn("details_json", csv_body)
        self.assertEqual(REDACTED, exported_details["api_key"])
        self.assertEqual(100, exported_details["token_limit"])
        self.assertNotIn("sk-raw", csv_body)

    def test_audit_json_export_uses_redacted_details(self):
        row = AuditLog(
            id=uuid4(),
            tenant_id=uuid4(),
            request_id="req-1",
            actor_id=uuid4(),
            actor_type="user",
            action="models.credential.upsert",
            resource_type="llm_credential",
            resource_id=uuid4(),
            status="success",
            details={"license_key": "raw-license", "total_tokens": 42},
            created_at=datetime(2026, 6, 12, tzinfo=timezone.utc),
        )

        json_body = audit_logs_to_json([_to_audit_log_item(row)])
        exported = json.loads(json_body)

        self.assertEqual("agenthive.audit.export.v1", exported["format"])
        self.assertEqual(REDACTED, exported["items"][0]["details"]["license_key"])
        self.assertEqual(42, exported["items"][0]["details"]["total_tokens"])
        self.assertNotIn("raw-license", json_body)

    async def test_record_audit_event_redacts_before_persistence(self):
        session = FakeAuditSession()

        event = await record_audit_event(
            session,
            tenant_id=uuid4(),
            action="security.test",
            details={
                "authorization": "Bearer raw-token",
                "token_limit": 100,
                "nested": {"api_key": "sk-raw"},
            },
        )

        self.assertIs(event, session.added[0])
        self.assertEqual(REDACTED, event.details["authorization"])
        self.assertEqual(100, event.details["token_limit"])
        self.assertEqual(REDACTED, event.details["nested"]["api_key"])

    async def test_audit_export_records_summary_audit_without_rows(self):
        tenant_id = uuid4()
        actor_id = uuid4()
        created_from = datetime(2026, 6, 1, tzinfo=timezone.utc)
        row = AuditLog(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action="license.activate",
            status="success",
            details={"license_key": "raw-license"},
            created_at=datetime(2026, 6, 12, tzinfo=timezone.utc),
        )
        principal = type("PrincipalStub", (), {"tenant_id": tenant_id, "user_id": actor_id})()
        session = FakeAuditExportSession([row])

        body = await export_audit_logs_json(
            session,
            principal,
            action="license.activate",
            actor_id=actor_id,
            resource_type=None,
            status_filter="success",
            request_id=None,
            created_from=created_from,
            created_to=None,
            limit=500,
            request_id_for_audit="req-audit-export",
            ip_address="127.0.0.1",
            user_agent="AgentHive Test",
        )

        self.assertIn("agenthive.audit.export.v1", body)
        audit_events = [item for item in session.added if isinstance(item, AuditLog)]
        self.assertEqual(1, len(audit_events))
        event = audit_events[0]
        self.assertEqual("audit.logs.export", event.action)
        self.assertEqual("req-audit-export", event.request_id)
        self.assertEqual("json", event.details["format"])
        self.assertEqual(1, event.details["item_count"])
        self.assertEqual(500, event.details["limit"])
        self.assertEqual("license.activate", event.details["filters"]["action"])
        self.assertEqual(str(actor_id), event.details["filters"]["actor_id"])
        self.assertEqual(created_from.isoformat(), event.details["filters"]["created_from"])
        self.assertNotIn("raw-license", json.dumps(event.details))
        self.assertEqual(1, session.commits)


if __name__ == "__main__":
    unittest.main()
