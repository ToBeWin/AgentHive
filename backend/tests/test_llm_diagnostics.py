from datetime import datetime, timezone
import json
import unittest
from uuid import uuid4

from app.llm.diagnostics import (
    connection_test_audit_details,
    connection_test_history_item,
    selected_route_attempt,
)
from app.llm.schemas import LLMAdapterType
from app.models.audit_log import AuditLog
from app.schemas.llm import LLMConnectionTestRequest, LLMConnectionTestResponse


class LLMConnectionDiagnosticsTests(unittest.TestCase):
    def test_audit_details_redact_temporary_connection_secrets(self) -> None:
        payload = LLMConnectionTestRequest(
            provider_key="openai_compatible",
            model_key="private-chat",
            base_url="https://internal-llm.example/v1",
            api_key="sk-temporary-secret",
        )
        response = LLMConnectionTestResponse(
            ok=False,
            provider_key="openai_compatible",
            adapter_type=LLMAdapterType.OPENAI_COMPATIBLE,
            model_key="private-chat",
            latency_ms=17,
            checked_at=datetime.now(timezone.utc),
            message="Probe to https://internal-llm.example/v1 failed with sk-temporary-secret.",
            diagnostics={
                "route_attempts": [
                    {
                        "attempt": 1,
                        "provider_key": "openai_compatible",
                        "status": "error",
                        "error_message": "provider returned sk-temporary-secret",
                    }
                ]
            },
        )

        details = connection_test_audit_details(payload, response=response)
        serialized = json.dumps(details)

        self.assertIn("[REDACTED_BASE_URL]", details["message"])
        self.assertIn("[REDACTED_API_KEY]", details["message"])
        self.assertNotIn("https://internal-llm.example/v1", serialized)
        self.assertNotIn("sk-temporary-secret", serialized)
        self.assertNotIn("error_message", details["route_attempts"][0])

    def test_history_mapping_coerces_untrusted_audit_json(self) -> None:
        event = AuditLog(
            tenant_id=uuid4(),
            actor_id=uuid4(),
            action="llm.connection_test",
            status="success",
            details={
                "ok": "yes",
                "provider_key": 123,
                "latency_ms": "42",
                "status_code": "200",
                "live_network_call": "false",
                "temporary_api_key_provided": True,
            },
        )

        item = connection_test_history_item(event)

        self.assertTrue(item.ok)
        self.assertEqual("123", item.provider_key)
        self.assertEqual(42, item.latency_ms)
        self.assertEqual(200, item.status_code)
        self.assertFalse(item.live_network_call)
        self.assertTrue(item.temporary_api_key_provided)
        self.assertFalse(item.temporary_base_url_provided)

    def test_selected_route_attempt_requires_matching_successful_deployment(self) -> None:
        deployment_id = uuid4()
        attempts = [
            {"deployment_id": str(deployment_id), "status": "error"},
            {"deployment_id": str(uuid4()), "status": "success"},
            {"deployment_id": str(deployment_id), "status": "success", "latency_ms": 9},
        ]

        selected = selected_route_attempt(attempts, deployment_id)

        self.assertEqual(9, selected["latency_ms"] if selected else None)


if __name__ == "__main__":
    unittest.main()
