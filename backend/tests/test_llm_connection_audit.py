from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4
import json
import unittest

from fastapi import HTTPException

from app.api.deps import Principal
from app.llm.schemas import ConnectionTestResult, LLMAdapterType
from app.media.providers import MediaProviderProbeResult
from app.models.audit_log import AuditLog
from app.schemas.llm import LLMConnectionTestRequest
from app.services.llm_service import list_connection_test_history, test_model_connection


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


class FakeAuditHistorySession:
    def __init__(self, rows):
        self.rows = rows

    async def execute(self, _statement):
        return FakeAuditHistoryResult(self.rows)


class FakeAuditHistoryResult:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return self.rows


class FakeGateway:
    def __init__(self, result=None, exc=None):
        self.result = result
        self.exc = exc

    async def test_connection(self, _request, _context):
        if self.exc:
            raise self.exc
        return self.result


def make_principal() -> Principal:
    return Principal(
        tenant_id=uuid4(),
        user_id=uuid4(),
        permissions={"models:write"},
    )


class LLMConnectionAuditTests(unittest.IsolatedAsyncioTestCase):
    async def test_successful_connection_test_records_success_audit_summary(self):
        session = FakeAuditSession()
        result = ConnectionTestResult(
            ok=True,
            provider_key="qwen",
            adapter_type=LLMAdapterType.OPENAI_COMPATIBLE,
            model_key="qwen-plus",
            latency_ms=42,
            checked_at=datetime.now(timezone.utc),
            message="Connection healthy.",
            diagnostics={
                "fallback_attempt_count": 1,
                "selected_route_reason": "fallback",
                "route_attempts": [
                    {
                        "attempt": 1,
                        "provider_key": "openai",
                        "model_key": "gpt-4o-mini",
                        "deployment_id": str(uuid4()),
                        "routing_key": "default-chat",
                        "status": "error",
                        "error_message": "raw provider failure",
                    },
                    {
                        "attempt": 2,
                        "provider_key": "qwen",
                        "model_key": "qwen-plus",
                        "deployment_id": str(uuid4()),
                        "routing_key": "qwen-chat",
                        "status": "success",
                        "latency_ms": 42,
                    },
                ],
            },
        )

        with patch(
            "app.services.llm_service._build_gateway",
            AsyncMock(return_value=FakeGateway(result=result)),
        ):
            response = await test_model_connection(
                LLMConnectionTestRequest(provider_key="qwen", model_key="qwen-plus"),
                make_principal(),
                session,
                request_id="req-llm-test-ok",
            )

        self.assertTrue(response.ok)
        self.assertEqual(1, session.commits)
        event = session.added[0]
        self.assertIsInstance(event, AuditLog)
        self.assertEqual("llm.connection_test", event.action)
        self.assertEqual("success", event.status)
        self.assertEqual("qwen", event.details["provider_key"])
        self.assertEqual("qwen-plus", event.details["model_key"])
        self.assertEqual(1, event.details["fallback_attempt_count"])
        self.assertEqual(2, len(event.details["route_attempts"]))
        self.assertNotIn("error_message", event.details["route_attempts"][0])

    async def test_failed_connection_test_result_records_failure_without_temporary_secrets(self):
        session = FakeAuditSession()
        result = ConnectionTestResult(
            ok=False,
            provider_key="openai_compatible",
            adapter_type=LLMAdapterType.OPENAI_COMPATIBLE,
            model_key="private-chat",
            latency_ms=7,
            message="Failed to reach https://internal-llm.example/v1 with sk-temp-secret.",
            diagnostics={"live_network_call": True, "mock_allowed": False},
        )

        with patch(
            "app.services.llm_service._build_gateway",
            AsyncMock(return_value=FakeGateway(result=result)),
        ):
            response = await test_model_connection(
                LLMConnectionTestRequest(
                    provider_key="openai_compatible",
                    model_key="private-chat",
                    base_url="https://internal-llm.example/v1",
                    api_key="sk-temp-secret",
                ),
                make_principal(),
                session,
                request_id="req-llm-test-fail",
            )

        self.assertFalse(response.ok)
        self.assertEqual(1, session.commits)
        event = session.added[0]
        self.assertEqual("failure", event.status)
        exported_details = json.dumps(event.details)
        self.assertTrue(event.details["temporary_api_key_provided"])
        self.assertTrue(event.details["temporary_base_url_provided"])
        self.assertIn("[REDACTED_BASE_URL]", event.details["message"])
        self.assertIn("[REDACTED_API_KEY]", event.details["message"])
        self.assertNotIn("https://internal-llm.example/v1", exported_details)
        self.assertNotIn("sk-temp-secret", exported_details)

    async def test_http_connection_test_error_records_failure_audit_before_reraising(self):
        session = FakeAuditSession()
        exc = HTTPException(
            status_code=403,
            detail="Policy denied temporary endpoint https://internal-llm.example/v1.",
        )

        with patch(
            "app.services.llm_service._build_gateway", AsyncMock(return_value=FakeGateway(exc=exc))
        ):
            with self.assertRaises(HTTPException):
                await test_model_connection(
                    LLMConnectionTestRequest(
                        provider_key="openai_compatible",
                        base_url="https://internal-llm.example/v1",
                    ),
                    make_principal(),
                    session,
                    request_id="req-llm-test-denied",
                )

        self.assertEqual(1, session.rollbacks)
        self.assertEqual(1, session.commits)
        event = session.added[0]
        self.assertEqual("llm.connection_test", event.action)
        self.assertEqual("failure", event.status)
        self.assertEqual(403, event.details["status_code"])
        self.assertIn("[REDACTED_BASE_URL]", event.details["message"])
        self.assertNotIn("https://internal-llm.example/v1", json.dumps(event.details))

    async def test_media_provider_connection_test_uses_configuration_check_without_llm_gateway(
        self,
    ):
        session = FakeAuditSession()

        with patch(
            "app.services.llm_service._build_gateway",
            AsyncMock(side_effect=AssertionError("unused")),
        ):
            response = await test_model_connection(
                LLMConnectionTestRequest(
                    provider_key="nano_banana",
                    model_key="google/nano-banana",
                    base_url="https://media.example.test",
                    api_key="sk-temp-media-secret",
                ),
                make_principal(),
                session,
                request_id="req-media-test-ok",
            )

        self.assertTrue(response.ok)
        self.assertEqual("nano_banana", response.provider_key)
        self.assertEqual("media_provider_configuration_check", response.diagnostics["operation"])
        self.assertFalse(response.diagnostics["live_network_call"])
        self.assertEqual("temporary_request", response.diagnostics["configuration_source"])
        self.assertEqual(1, session.commits)
        event = session.added[0]
        self.assertEqual("success", event.status)
        exported_details = json.dumps(event.details)
        self.assertTrue(event.details["temporary_api_key_provided"])
        self.assertTrue(event.details["temporary_base_url_provided"])
        self.assertNotIn("sk-temp-media-secret", exported_details)
        self.assertNotIn("https://media.example.test", exported_details)

    async def test_media_provider_connection_test_can_run_live_probe(self):
        session = FakeAuditSession()
        probe_result = MediaProviderProbeResult(
            ok=True,
            status_code=200,
            latency_ms=18,
            message="Media provider responded to a live probe.",
            metadata={
                "live_network_call": True,
                "status_code": 200,
                "probe_path": "/models",
            },
        )

        with (
            patch(
                "app.services.llm_service._build_gateway",
                AsyncMock(side_effect=AssertionError("unused")),
            ),
            patch(
                "app.services.llm_service.HTTPMediaProviderAdapter.probe",
                AsyncMock(return_value=probe_result),
            ),
        ):
            response = await test_model_connection(
                LLMConnectionTestRequest(
                    provider_key="nano_banana",
                    model_key="google/nano-banana",
                    base_url="https://media.example.test",
                    api_key="sk-temp-media-secret",
                    live_check=True,
                    probe_path="models",
                ),
                make_principal(),
                session,
                request_id="req-media-live-test-ok",
            )

        self.assertTrue(response.ok)
        self.assertEqual("media_provider_live_probe", response.diagnostics["operation"])
        self.assertTrue(response.diagnostics["live_network_call"])
        self.assertEqual(200, response.diagnostics["status_code"])
        self.assertEqual("/models", response.diagnostics["probe_path"])
        self.assertEqual(18, response.latency_ms)
        event = session.added[0]
        self.assertEqual("success", event.status)
        self.assertEqual("media_provider_live_probe", event.details["operation"])
        self.assertEqual("nano_banana", event.details["provider_type"])
        self.assertEqual("temporary_request", event.details["configuration_source"])
        self.assertEqual("/models", event.details["probe_path"])
        self.assertEqual(200, event.details["status_code"])
        self.assertTrue(event.details["live_network_call"])

    async def test_media_provider_live_probe_failure_records_sanitized_audit(self):
        session = FakeAuditSession()
        probe_result = MediaProviderProbeResult(
            ok=False,
            status_code=401,
            latency_ms=12,
            message="Media provider probe returned HTTP 401.",
            metadata={
                "live_network_call": True,
                "status_code": 401,
                "probe_path": "/models",
            },
        )

        with patch(
            "app.services.llm_service.HTTPMediaProviderAdapter.probe",
            AsyncMock(return_value=probe_result),
        ):
            response = await test_model_connection(
                LLMConnectionTestRequest(
                    provider_key="nano_banana",
                    model_key="google/nano-banana",
                    base_url="https://media.example.test",
                    api_key="sk-temp-media-secret",
                    live_check=True,
                ),
                make_principal(),
                session,
                request_id="req-media-live-test-fail",
            )

        self.assertFalse(response.ok)
        self.assertEqual("media_provider_live_probe", response.diagnostics["operation"])
        self.assertEqual(401, response.diagnostics["status_code"])
        event = session.added[0]
        self.assertEqual("failure", event.status)
        self.assertEqual("media_provider_live_probe", event.details["operation"])
        self.assertEqual("/models", event.details["probe_path"])
        self.assertEqual(401, event.details["status_code"])
        exported_details = json.dumps(event.details)
        self.assertNotIn("sk-temp-media-secret", exported_details)
        self.assertNotIn("https://media.example.test", exported_details)

    async def test_media_provider_connection_test_reports_missing_configuration(self):
        session = FakeAuditSession()

        response = await test_model_connection(
            LLMConnectionTestRequest(
                provider_key="volcengine_seedance",
                model_key="volcengine/seedance-2.0",
            ),
            make_principal(),
            session,
            request_id="req-media-test-missing",
        )

        self.assertFalse(response.ok)
        self.assertEqual(["base_url", "api_key"], response.diagnostics["missing"])
        self.assertEqual(1, session.commits)
        self.assertEqual("failure", session.added[0].status)

    async def test_connection_test_history_maps_recent_audit_events(self):
        principal = make_principal()
        checked_at = datetime.now(timezone.utc)
        event = AuditLog(
            tenant_id=principal.tenant_id,
            request_id="req-history-1",
            actor_id=principal.user_id,
            action="llm.connection_test",
            resource_type="llm_provider",
            status="failure",
            created_at=checked_at,
            updated_at=checked_at,
            details={
                "ok": False,
                "provider_key": "openai_compatible",
                "provider_type": "openai_compatible",
                "deployment_id": str(uuid4()),
                "model_key": "private-chat",
                "adapter_type": "openai_compatible",
                "latency_ms": "31",
                "message": "Connection failed with [REDACTED_BASE_URL].",
                "operation": "media_provider_live_probe",
                "configuration_source": "temporary_request",
                "probe_path": "/models",
                "status_code": "401",
                "fallback_attempt_count": 2,
                "selected_route_reason": "fallback",
                "temporary_api_key_provided": True,
                "temporary_base_url_provided": True,
                "live_network_call": True,
            },
        )

        response = await list_connection_test_history(
            FakeAuditHistorySession([event]),
            principal,
            limit=10,
        )

        self.assertEqual(1, len(response.tests))
        item = response.tests[0]
        self.assertEqual(event.id, item.id)
        self.assertFalse(item.ok)
        self.assertEqual("openai_compatible", item.provider_key)
        self.assertEqual("openai_compatible", item.provider_type)
        self.assertEqual("private-chat", item.model_key)
        self.assertEqual(31, item.latency_ms)
        self.assertEqual("media_provider_live_probe", item.operation)
        self.assertEqual("temporary_request", item.configuration_source)
        self.assertEqual("/models", item.probe_path)
        self.assertEqual(401, item.status_code)
        self.assertTrue(item.temporary_api_key_provided)
        self.assertTrue(item.temporary_base_url_provided)
        self.assertNotIn("internal-llm.example", item.message or "")

    async def test_connection_test_history_includes_deployment_acceptance_events(self):
        principal = make_principal()
        checked_at = datetime.now(timezone.utc)
        deployment_id = uuid4()
        event = AuditLog(
            tenant_id=principal.tenant_id,
            request_id="req-acceptance-history",
            actor_id=principal.user_id,
            action="llm.deployment.acceptance_test",
            resource_type="llm_deployment",
            resource_id=deployment_id,
            status="success",
            created_at=checked_at,
            updated_at=checked_at,
            details={
                "ok": True,
                "provider_key": "deepseek",
                "model_key": "deepseek-v4-flash",
                "deployment_id": str(deployment_id),
                "routing_key": "deepseek-chat",
                "operation": "deployment_acceptance_test",
                "configuration_source": "saved_deployment",
                "latency_ms": 88,
                "message": "AgentHive acceptance check ok.",
                "status_code": 200,
                "selected_route_reason": "direct",
                "live_network_call": True,
            },
        )

        response = await list_connection_test_history(
            FakeAuditHistorySession([event]),
            principal,
            limit=10,
        )

        self.assertEqual(1, len(response.tests))
        item = response.tests[0]
        self.assertTrue(item.ok)
        self.assertEqual("deepseek", item.provider_key)
        self.assertEqual("deepseek-v4-flash", item.model_key)
        self.assertEqual(str(deployment_id), item.deployment_id)
        self.assertEqual("deployment_acceptance_test", item.operation)
        self.assertEqual("saved_deployment", item.configuration_source)
        self.assertEqual(88, item.latency_ms)
        self.assertEqual(200, item.status_code)
        self.assertTrue(item.live_network_call)


if __name__ == "__main__":
    unittest.main()
