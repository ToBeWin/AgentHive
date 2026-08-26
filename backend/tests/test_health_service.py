import tempfile
import unittest
from datetime import datetime
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from zipfile import ZipFile

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.models.audit_log import AuditLog
from app.media.schemas import MediaProviderType
from app.services import health_service
from app.services.health_service import (
    _build_delivery_assessment,
    _check_frontend,
    _check_license_identity,
    _check_media_generation,
    _check_media_worker,
    _normalize_celery_pings,
    _overall_status,
    _redis_command,
    _with_remediation,
    build_diagnostics_report,
    build_health_report,
    build_support_bundle,
    is_ready,
    record_diagnostics_export_audit,
    record_support_bundle_export_audit,
    redact_diagnostics,
)
from app.services.migration_service import MigrationStatus


class HealthServiceTest(unittest.IsolatedAsyncioTestCase):
    def test_overall_status_requires_all_components_healthy(self) -> None:
        self.assertEqual(
            "healthy",
            _overall_status(
                {
                    "database": {"status": "healthy"},
                    "redis": {"status": "healthy"},
                    "minio": {"status": "healthy"},
                }
            ),
        )
        self.assertEqual(
            "degraded",
            _overall_status(
                {
                    "database": {"status": "healthy"},
                    "license_identity": {"status": "degraded"},
                }
            ),
        )
        self.assertEqual(
            "unhealthy",
            _overall_status(
                {
                    "database": {"status": "healthy"},
                    "redis": {"status": "unhealthy"},
                }
            ),
        )

    def test_readiness_predicate(self) -> None:
        self.assertTrue(is_ready({"status": "healthy"}))
        self.assertFalse(is_ready({"status": "degraded"}))
        self.assertFalse(is_ready({"status": "unhealthy"}))
        self.assertTrue(
            is_ready(
                {
                    "status": "degraded",
                    "delivery": {
                        "status": "ready_with_warnings",
                        "blocker_count": 0,
                        "warning_count": 1,
                    },
                }
            )
        )
        self.assertFalse(
            is_ready(
                {
                    "status": "degraded",
                    "delivery": {
                        "status": "blocked",
                        "blocker_count": 1,
                        "warning_count": 0,
                    },
                }
            )
        )

    def test_delivery_assessment_marks_all_healthy_components_ready(self) -> None:
        delivery = _build_delivery_assessment(
            {
                "database": {"status": "healthy", "message": "ok"},
                "redis": {"status": "healthy", "message": "ok"},
                "minio": {"status": "healthy", "message": "ok"},
                "litellm": {"status": "healthy", "message": "ok"},
                "pgvector": {"status": "healthy", "message": "ok"},
                "production_config": {"status": "healthy", "message": "ok"},
                "license_identity": {"status": "healthy", "message": "ok"},
            }
        )

        self.assertEqual("ready", delivery["status"])
        self.assertEqual(0, delivery["blocker_count"])
        self.assertTrue(all(check["severity"] == "pass" for check in delivery["checks"]))

    def test_delivery_assessment_promotes_critical_degraded_component_to_blocker(self) -> None:
        delivery = _build_delivery_assessment(
            {
                "database": {
                    "status": "degraded",
                    "message": "Database migrations are not current.",
                    "remediation": {"docs_anchor": "deployment.database"},
                },
                "redis": {"status": "healthy", "message": "ok"},
            }
        )

        self.assertEqual("blocked", delivery["status"])
        self.assertEqual(1, delivery["blocker_count"])
        self.assertEqual("database", delivery["blockers"][0]["id"])
        self.assertEqual(
            "deployment.database", delivery["blockers"][0]["remediation"]["docs_anchor"]
        )

    def test_delivery_assessment_allows_noncritical_degraded_warning(self) -> None:
        delivery = _build_delivery_assessment(
            {
                "database": {"status": "healthy", "message": "ok"},
                "external_observability": {"status": "degraded", "message": "not configured"},
            }
        )

        self.assertEqual("ready_with_warnings", delivery["status"])
        self.assertEqual(0, delivery["blocker_count"])
        self.assertEqual(1, delivery["warning_count"])

    def test_redis_command_uses_resp_format(self) -> None:
        self.assertEqual(b"*1\r\n$4\r\nPING\r\n", _redis_command("PING"))
        self.assertEqual(
            b"*2\r\n$4\r\nAUTH\r\n$6\r\nsecret\r\n",
            _redis_command("AUTH", "secret"),
        )

    def test_remediation_is_only_added_to_actionable_statuses(self) -> None:
        healthy = _with_remediation("redis", {"status": "healthy", "message": "ok"})
        unhealthy = _with_remediation("redis", {"status": "unhealthy", "message": "down"})

        self.assertNotIn("remediation", healthy)
        self.assertEqual("deployment.redis", unhealthy["remediation"]["docs_anchor"])
        self.assertIn("REDIS_URL", unhealthy["remediation"]["action"])

    def test_redact_diagnostics_masks_sensitive_keys_and_values(self) -> None:
        redacted = redact_diagnostics(
            {
                "database_url": "postgresql://agenthive:secret@db:5432/agenthive",
                "authorization": "Bearer abc.def-token",
                "nested": {
                    "litellm_master_key": "fixture-master-key-value",
                    "message": "Provider returned bearer testfixturevalue in a response",
                },
                "safe": "http://litellm:4000",
            }
        )

        self.assertEqual("[REDACTED]", redacted["authorization"])
        self.assertEqual("[REDACTED]", redacted["database_url"])
        self.assertEqual("[REDACTED]", redacted["nested"]["litellm_master_key"])
        self.assertEqual("[REDACTED]", redacted["nested"]["message"])
        self.assertEqual("http://litellm:4000", redacted["safe"])

    def test_license_identity_rejects_invalid_public_key_file(self) -> None:
        original_public_key_path = health_service.settings.license_public_key_path
        with tempfile.TemporaryDirectory() as temp_dir:
            invalid_key = Path(temp_dir) / "license-public.pem"
            invalid_key.write_text("not a pem public key", encoding="utf-8")
            health_service.settings.license_public_key_path = str(invalid_key)
            try:
                component = _check_license_identity()
            finally:
                health_service.settings.license_public_key_path = original_public_key_path

        self.assertEqual("unhealthy", component["status"])
        self.assertFalse(component["details"]["license_public_key_valid"])

    def test_license_identity_accepts_valid_ed25519_public_key_file(self) -> None:
        original_public_key_path = health_service.settings.license_public_key_path
        with tempfile.TemporaryDirectory() as temp_dir:
            public_key = Path(temp_dir) / "license-public.pem"
            public_key.write_bytes(_test_ed25519_public_key_pem())
            health_service.settings.license_public_key_path = str(public_key)
            try:
                component = _check_license_identity()
            finally:
                health_service.settings.license_public_key_path = original_public_key_path

        self.assertEqual("healthy", component["status"])
        self.assertTrue(component["details"]["license_public_key_valid"])

    def test_media_generation_readiness_reports_image_and_video_routes(self) -> None:
        diagnostics = {
            MediaProviderType.OPENAI_IMAGES: [],
            MediaProviderType.NANO_BANANA: ["NANO_BANANA_BASE_URL", "NANO_BANANA_API_KEY"],
            MediaProviderType.VOLCENGINE_SEEDANCE: [],
            MediaProviderType.OPENAI_COMPATIBLE_MEDIA: [
                "MEDIA_OPENAI_COMPATIBLE_BASE_URL",
                "MEDIA_OPENAI_COMPATIBLE_API_KEY",
            ],
            MediaProviderType.CUSTOM: ["custom_media_provider_adapter"],
        }
        with patch(
            "app.services.health_service.media_provider_diagnostics_from_settings",
            return_value=diagnostics,
        ):
            component = _check_media_generation()

        self.assertEqual("healthy", component["status"])
        self.assertEqual(2, component["details"]["configured_model_count"])
        self.assertEqual(1, component["details"]["image_model_count"])
        self.assertEqual(1, component["details"]["video_model_count"])
        self.assertIn("volcengine_seedance", component["details"]["configured_provider_types"])

    def test_production_media_generation_warns_without_video_webhook_url(self) -> None:
        original_environment = health_service.settings.environment
        original_webhook_public_url = health_service.settings.media_webhook_public_url
        diagnostics = {
            MediaProviderType.OPENAI_IMAGES: [],
            MediaProviderType.NANO_BANANA: ["NANO_BANANA_BASE_URL", "NANO_BANANA_API_KEY"],
            MediaProviderType.VOLCENGINE_SEEDANCE: [],
            MediaProviderType.OPENAI_COMPATIBLE_MEDIA: [
                "MEDIA_OPENAI_COMPATIBLE_BASE_URL",
                "MEDIA_OPENAI_COMPATIBLE_API_KEY",
            ],
            MediaProviderType.CUSTOM: ["custom_media_provider_adapter"],
        }
        health_service.settings.environment = "production"
        health_service.settings.media_webhook_public_url = None
        try:
            with patch(
                "app.services.health_service.media_provider_diagnostics_from_settings",
                return_value=diagnostics,
            ):
                component = _check_media_generation()
        finally:
            health_service.settings.environment = original_environment
            health_service.settings.media_webhook_public_url = original_webhook_public_url

        self.assertEqual("degraded", component["status"])
        self.assertEqual(1, component["details"]["video_model_count"])
        self.assertFalse(component["details"]["webhook_public_url_configured"])
        self.assertEqual(
            ["MEDIA_WEBHOOK_PUBLIC_URL"], component["details"]["missing_operational_settings"]
        )

    async def test_media_generation_readiness_warns_when_routes_are_missing(self) -> None:
        diagnostics = {
            MediaProviderType.OPENAI_IMAGES: ["OPENAI_IMAGES_BASE_URL", "OPENAI_IMAGES_API_KEY"],
            MediaProviderType.NANO_BANANA: ["NANO_BANANA_BASE_URL", "NANO_BANANA_API_KEY"],
            MediaProviderType.VOLCENGINE_SEEDANCE: [
                "VOLCENGINE_SEEDANCE_BASE_URL",
                "VOLCENGINE_SEEDANCE_API_KEY",
            ],
            MediaProviderType.OPENAI_COMPATIBLE_MEDIA: [
                "MEDIA_OPENAI_COMPATIBLE_BASE_URL",
                "MEDIA_OPENAI_COMPATIBLE_API_KEY",
            ],
            MediaProviderType.CUSTOM: ["custom_media_provider_adapter"],
        }
        with (
            patch(
                "app.services.health_service._check_database",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
            patch(
                "app.services.health_service._check_redis",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
            patch(
                "app.services.health_service._check_minio",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
            patch(
                "app.services.health_service._check_litellm",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
            patch(
                "app.services.health_service._check_pgvector",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
            patch(
                "app.services.health_service._check_license_identity",
                return_value={"status": "healthy"},
            ),
            patch(
                "app.services.health_service.agent_runtime_dependency_status",
                return_value={"status": "healthy"},
            ),
            patch(
                "app.services.health_service.media_provider_diagnostics_from_settings",
                return_value=diagnostics,
            ),
            patch(
                "app.services.health_service._check_media_worker",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
        ):
            report = await build_health_report(deep=True)

        self.assertEqual("degraded", report["status"])
        self.assertEqual("degraded", report["components"]["media_generation"]["status"])
        self.assertEqual("ready_with_warnings", report["delivery"]["status"])
        self.assertEqual("media_generation", report["delivery"]["warnings"][0]["id"])
        self.assertEqual(
            "deployment.media_generation",
            report["components"]["media_generation"]["remediation"]["docs_anchor"],
        )

    async def test_media_worker_reports_healthy_when_celery_worker_responds(self) -> None:
        with patch(
            "app.services.health_service._celery_worker_pings",
            return_value=[{"celery@agenthive-worker": {"ok": "pong"}}],
        ):
            component = await _check_media_worker()

        self.assertEqual("healthy", component["status"])
        self.assertTrue(component["details"]["worker_ping_ok"])
        self.assertEqual(1, component["details"]["worker_count"])
        self.assertEqual(["celery@agenthive-worker"], component["details"]["workers"])

    def test_media_worker_ping_normalizer_accepts_celery_dict_shape(self) -> None:
        workers = _normalize_celery_pings({"celery@agenthive-worker": {"ok": "pong"}})

        self.assertEqual(["celery@agenthive-worker"], workers)

    async def test_media_worker_without_response_is_delivery_warning(self) -> None:
        with (
            patch(
                "app.services.health_service._check_database",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
            patch(
                "app.services.health_service._check_redis",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
            patch(
                "app.services.health_service._check_minio",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
            patch(
                "app.services.health_service._check_litellm",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
            patch(
                "app.services.health_service._check_pgvector",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
            patch(
                "app.services.health_service._check_license_identity",
                return_value={"status": "healthy"},
            ),
            patch(
                "app.services.health_service.agent_runtime_dependency_status",
                return_value={"status": "healthy"},
            ),
            patch(
                "app.services.health_service._check_media_generation",
                return_value={"status": "healthy"},
            ),
            patch("app.services.health_service._celery_worker_pings", return_value=None),
        ):
            report = await build_health_report(deep=True)

        self.assertEqual("degraded", report["status"])
        self.assertEqual("degraded", report["components"]["media_worker"]["status"])
        self.assertEqual("ready_with_warnings", report["delivery"]["status"])
        self.assertIn("media_worker", {item["id"] for item in report["delivery"]["warnings"]})
        self.assertEqual(
            "deployment.media_worker",
            report["components"]["media_worker"]["remediation"]["docs_anchor"],
        )

    async def test_readiness_includes_pgvector_component(self) -> None:
        with (
            patch(
                "app.services.health_service._check_database",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
            patch(
                "app.services.health_service._check_redis",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
            patch(
                "app.services.health_service._check_minio",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
            patch(
                "app.services.health_service._check_litellm",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
            patch(
                "app.services.health_service._check_pgvector",
                new=AsyncMock(return_value={"status": "degraded"}),
            ),
            patch(
                "app.services.health_service._check_license_identity",
                return_value={"status": "healthy"},
            ),
            patch(
                "app.services.health_service.agent_runtime_dependency_status",
                return_value={"status": "healthy"},
            ),
            patch(
                "app.services.health_service._check_media_generation",
                return_value={"status": "healthy"},
            ),
            patch(
                "app.services.health_service._check_media_worker",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
        ):
            report = await build_health_report(deep=True)

        self.assertEqual("degraded", report["status"])
        self.assertIn("pgvector", report["components"])
        self.assertEqual("blocked", report["delivery"]["status"])
        self.assertEqual("pgvector", report["delivery"]["blockers"][0]["id"])
        self.assertIn("production_config", report["components"])
        self.assertEqual(
            "deployment.pgvector", report["components"]["pgvector"]["remediation"]["docs_anchor"]
        )

    async def test_readiness_blocks_when_agent_runtime_dependencies_are_missing(self) -> None:
        with (
            patch(
                "app.services.health_service._check_database",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
            patch(
                "app.services.health_service._check_redis",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
            patch(
                "app.services.health_service._check_minio",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
            patch(
                "app.services.health_service._check_litellm",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
            patch(
                "app.services.health_service._check_pgvector",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
            patch(
                "app.services.health_service._check_license_identity",
                return_value={"status": "healthy"},
            ),
            patch(
                "app.services.health_service.agent_runtime_dependency_status",
                return_value={
                    "status": "unhealthy",
                    "message": "Missing Agent orchestration dependencies: langgraph.",
                    "details": {"missing": ["langgraph"]},
                },
            ),
            patch(
                "app.services.health_service._check_media_generation",
                return_value={"status": "healthy"},
            ),
            patch(
                "app.services.health_service._check_media_worker",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
        ):
            report = await build_health_report(deep=True)

        self.assertEqual("unhealthy", report["status"])
        self.assertIn("agent_runtime", report["components"])
        self.assertEqual("blocked", report["delivery"]["status"])
        self.assertEqual(
            "deployment.agent_runtime",
            report["components"]["agent_runtime"]["remediation"]["docs_anchor"],
        )

    async def test_diagnostics_report_contains_redacted_delivery_package(self) -> None:
        checked_at = "2026-06-13T10:20:30+00:00"
        with (
            patch(
                "app.services.health_service.build_health_report",
                new=AsyncMock(
                    side_effect=[
                        {
                            "status": "healthy",
                            "service": "agenthive-backend",
                            "components": {
                                "litellm": {
                                    "status": "healthy",
                                    "details": {"authorization": "Bearer secret-token"},
                                }
                            },
                        },
                        {
                            "status": "healthy",
                            "service": "agenthive-backend",
                            "components": {},
                            "delivery": {"status": "ready", "blocker_count": 0, "warning_count": 0},
                        },
                    ],
                ),
            ),
            patch(
                "app.services.health_service.build_system_info",
                return_value={"name": "AgentHive", "version": "test"},
            ),
            patch(
                "app.services.llm_service.list_connection_test_history",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        tests=[
                            SimpleNamespace(
                                checked_at=datetime.fromisoformat(checked_at),
                                configuration_source="temporary_request",
                                latency_ms=18,
                                live_network_call=True,
                                model_key="google/nano-banana",
                                ok=True,
                                operation="media_provider_live_probe",
                                probe_path="/models",
                                provider_key="nano_banana",
                                provider_type="nano_banana",
                                selected_route_reason="media_provider_configuration",
                                status="success",
                                status_code=200,
                            )
                        ]
                    )
                ),
            ),
        ):
            report = await build_diagnostics_report(session=object(), principal=object())

        self.assertEqual("AgentHive", report["product"])
        self.assertEqual("deployment_diagnostics", report["report_type"])
        self.assertTrue(report["redacted"])
        self.assertEqual("ready", report["delivery"]["status"])
        self.assertEqual(
            "[REDACTED]",
            report["diagnostics"]["health"]["components"]["litellm"]["details"]["authorization"],
        )
        connection = report["diagnostics"]["connection_acceptance"]
        self.assertEqual("healthy", connection["status"])
        self.assertEqual(1, connection["recent_test_count"])
        self.assertEqual(1, connection["live_network_call_count"])
        self.assertEqual(1, connection["media_live_probe_count"])
        self.assertEqual("nano_banana", connection["latest_media_live_probe"]["provider_key"])
        self.assertEqual(200, connection["latest_media_live_probe"]["status_code"])

    async def test_diagnostics_export_records_summary_audit_without_report_payload(self) -> None:
        tenant_id = uuid4()
        actor_id = uuid4()
        session = FakeAuditSession()
        report = {
            "schema_version": "1.0",
            "redacted": True,
            "delivery": {
                "status": "blocked",
                "blocker_count": 2,
                "warning_count": 1,
            },
            "diagnostics": {
                "readiness": {
                    "status": "unhealthy",
                    "components": {
                        "database": {
                            "status": "unhealthy",
                            "details": {"database_url": "postgresql://u:p@db/x"},
                        },
                        "redis": {"status": "healthy"},
                    },
                },
            },
        }

        await record_diagnostics_export_audit(
            session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            report=report,
            request_id="req-diagnostics-export",
            ip_address="127.0.0.1",
            user_agent="AgentHive Test",
        )

        self.assertEqual(1, session.commits)
        event = session.added[0]
        self.assertIsInstance(event, AuditLog)
        self.assertEqual("system.diagnostics.export", event.action)
        self.assertEqual("system", event.resource_type)
        self.assertEqual("req-diagnostics-export", event.request_id)
        self.assertEqual("1.0", event.details["schema_version"])
        self.assertTrue(event.details["redacted"])
        self.assertEqual("unhealthy", event.details["readiness_status"])
        self.assertEqual("blocked", event.details["delivery_status"])
        self.assertEqual(2, event.details["blocker_count"])
        self.assertEqual(1, event.details["warning_count"])
        self.assertEqual(2, event.details["component_count"])
        self.assertNotIn("postgresql://u:p@db", str(event.details))

    async def test_support_bundle_contains_redacted_diagnostics_and_delivery_summary(self) -> None:
        report = {
            "product": "AgentHive",
            "report_type": "deployment_diagnostics",
            "schema_version": "1.0",
            "generated_at": "2026-06-13T10:20:30.000000+00:00",
            "redacted": True,
            "delivery": {
                "status": "ready_with_warnings",
                "summary": "Delivery is usable with one warning.",
                "blocker_count": 0,
                "warning_count": 1,
                "blockers": [],
                "warnings": [
                    {
                        "id": "ragflow",
                        "label": "Optional RAGFlow integration",
                        "component": "ragflow",
                        "status": "degraded",
                        "message": "RAGFlow is optional.",
                    }
                ],
            },
            "diagnostics": {
                "info": {"name": "AgentHive", "version": "test", "edition": "private-deployment"},
                "readiness": {
                    "status": "healthy",
                    "components": {
                        "litellm": {
                            "status": "healthy",
                            "message": "ok",
                            "details": {"authorization": "[REDACTED]"},
                        }
                    },
                },
                "connection_acceptance": {
                    "status": "healthy",
                    "summary": "1 live provider network call is recorded.",
                    "recent_test_count": 1,
                    "live_network_call_count": 1,
                    "media_live_probe_count": 1,
                    "failed_recent_count": 0,
                    "providers": ["nano_banana"],
                    "latest_live_probe": {
                        "provider_key": "nano_banana",
                        "model_key": "google/nano-banana",
                        "operation": "media_provider_live_probe",
                        "ok": True,
                        "checked_at": "2026-06-13T10:20:30+00:00",
                        "status_code": 200,
                        "probe_path": "/models",
                        "latency_ms": 18,
                    },
                    "latest_media_live_probe": {
                        "provider_key": "nano_banana",
                        "model_key": "google/nano-banana",
                        "operation": "media_provider_live_probe",
                        "ok": True,
                        "checked_at": "2026-06-13T10:20:30+00:00",
                        "status_code": 200,
                        "probe_path": "/models",
                        "latency_ms": 18,
                    },
                    "recent_tests": [],
                },
                "knowledge_acceptance": {
                    "status": "healthy",
                    "summary": "2 knowledge-enabled Agent run(s) are recorded; 2 run(s) returned cited knowledge sources.",
                    "recent_run_count": 3,
                    "knowledge_enabled_run_count": 2,
                    "runs_with_sources_count": 2,
                    "human_review_required_count": 0,
                    "guardrail_triggered_count": 0,
                    "agents": ["customer_service"],
                    "latest_knowledge_run": {
                        "agent_key": "customer_service",
                        "agent_instance_name": "售后客服",
                        "model_key": "qwen-plus",
                        "checked_at": "2026-06-13T10:21:30+00:00",
                        "source_count": 2,
                        "confidence_level": "high",
                        "max_score": 0.91,
                        "requires_human_review": False,
                        "guardrail_mode": "strict",
                    },
                    "recent_runs": [],
                },
            },
        }
        with patch(
            "app.services.health_service.build_diagnostics_report",
            new=AsyncMock(return_value=report),
        ):
            bundle, filename = await build_support_bundle()

        self.assertEqual("agenthive-support-bundle-2026-06-13T10-20-30-000000-00-00.zip", filename)
        with ZipFile(BytesIO(bundle)) as archive:
            self.assertEqual(
                {
                    "README.md",
                    "acceptance-checklist.md",
                    "delivery-summary.md",
                    "diagnostics.json",
                    "manifest.json",
                },
                set(archive.namelist()),
            )
            checklist = archive.read("acceptance-checklist.md").decode("utf-8")
            diagnostics = archive.read("diagnostics.json").decode("utf-8")
            summary = archive.read("delivery-summary.md").decode("utf-8")
            manifest = archive.read("manifest.json").decode("utf-8")

        self.assertIn('"redacted": true', diagnostics)
        self.assertIn("[REDACTED]", diagnostics)
        self.assertIn("AgentHive Acceptance Checklist", checklist)
        self.assertIn("Acceptance decision: conditional_pass", checklist)
        self.assertIn("Open Warnings", checklist)
        self.assertIn("Model and Media Connection Evidence", checklist)
        self.assertIn("media live probes: 1", checklist)
        self.assertIn("HTTP status: 200", checklist)
        self.assertIn("Knowledge Agent Evidence", checklist)
        self.assertIn("runs with sources: 2", checklist)
        self.assertIn("Latest knowledge-backed Agent run", checklist)
        self.assertIn("Sign-off", checklist)
        self.assertIn("Optional RAGFlow integration", summary)
        self.assertIn("Model and Media Connection Evidence", summary)
        self.assertIn("Knowledge Agent Evidence", summary)
        self.assertIn("acceptance-checklist.md", manifest)
        self.assertIn("deployment_support_bundle", manifest)
        self.assertNotIn("sk-", diagnostics)
        self.assertNotIn("sk-", checklist)

    async def test_support_bundle_export_records_audit_summary_only(self) -> None:
        tenant_id = uuid4()
        actor_id = uuid4()
        session = FakeAuditSession()

        await record_support_bundle_export_audit(
            session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            filename="agenthive-support-bundle-test.zip",
            bundle_size_bytes=2048,
            request_id="req-support-bundle",
            ip_address="127.0.0.1",
            user_agent="AgentHive Test",
        )

        self.assertEqual(1, session.commits)
        event = session.added[0]
        self.assertIsInstance(event, AuditLog)
        self.assertEqual("system.support_bundle.export", event.action)
        self.assertEqual("system", event.resource_type)
        self.assertEqual("req-support-bundle", event.request_id)
        self.assertEqual("agenthive-support-bundle-test.zip", event.details["filename"])
        self.assertEqual(2048, event.details["bundle_size_bytes"])
        self.assertTrue(event.details["redacted"])
        self.assertEqual("zip", event.details["format"])

    async def test_database_unhealthy_report_has_message_and_remediation(self) -> None:
        with (
            patch(
                "app.services.health_service.check_database_health",
                new=AsyncMock(return_value={"status": "unhealthy"}),
            ),
            patch(
                "app.services.health_service._check_redis",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
            patch(
                "app.services.health_service._check_minio",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
            patch(
                "app.services.health_service._check_litellm",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
            patch(
                "app.services.health_service._check_pgvector",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
            patch(
                "app.services.health_service._check_license_identity",
                return_value={"status": "healthy"},
            ),
            patch(
                "app.services.health_service.agent_runtime_dependency_status",
                return_value={"status": "healthy"},
            ),
            patch(
                "app.services.health_service._check_media_generation",
                return_value={"status": "healthy"},
            ),
            patch(
                "app.services.health_service._check_media_worker",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
        ):
            report = await build_health_report(deep=True)

        database = report["components"]["database"]
        self.assertEqual("unhealthy", report["status"])
        self.assertEqual("PostgreSQL is not reachable.", database["message"])
        self.assertEqual("deployment.database", database["remediation"]["docs_anchor"])

    async def test_database_readiness_reports_missing_media_runtime_indexes(self) -> None:
        with (
            patch(
                "app.services.health_service.check_database_health",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
            patch(
                "app.services.health_service.get_migration_status",
                new=AsyncMock(
                    return_value=MigrationStatus(
                        current_revision="0014_media_generation_job_runtime_indexes",
                        head_revision="0014_media_generation_job_runtime_indexes",
                        is_current=True,
                        version_table_present=True,
                    )
                ),
            ),
            patch(
                "app.services.health_service._check_media_runtime_indexes",
                new=AsyncMock(
                    return_value={
                        "ready": False,
                        "present_count": 4,
                        "expected_count": 5,
                        "missing": ["ix_media_generation_jobs_provider_external"],
                    }
                ),
            ),
        ):
            result = await health_service._check_database(deep=True)

        self.assertEqual("degraded", result["status"])
        self.assertEqual(
            "Database is reachable, but media generation runtime indexes are missing.",
            result["message"],
        )
        self.assertEqual(
            ["ix_media_generation_jobs_provider_external"],
            result["media_runtime_indexes"]["missing"],
        )

    async def test_unsafe_production_config_participates_in_readiness(self) -> None:
        original_environment = health_service.settings.environment
        original_secret_key = health_service.settings.secret_key
        original_litellm_master_key = health_service.settings.litellm_master_key
        original_minio_secret_key = health_service.settings.minio_secret_key
        original_redis_url = health_service.settings.redis_url
        health_service.settings.environment = "production"
        health_service.settings.secret_key = (
            "agenthive-development-secret-change-me-before-production"
        )
        health_service.settings.litellm_master_key = "sk-change-me-litellm-master-key"
        health_service.settings.minio_secret_key = "agenthive_minio_password"
        health_service.settings.redis_url = "redis://:change-me-redis@redis:6379/0"
        try:
            with (
                patch(
                    "app.services.health_service._check_database",
                    new=AsyncMock(return_value={"status": "healthy"}),
                ),
                patch(
                    "app.services.health_service._check_redis",
                    new=AsyncMock(return_value={"status": "healthy"}),
                ),
                patch(
                    "app.services.health_service._check_minio",
                    new=AsyncMock(return_value={"status": "healthy"}),
                ),
                patch(
                    "app.services.health_service._check_litellm",
                    new=AsyncMock(return_value={"status": "healthy"}),
                ),
                patch(
                    "app.services.health_service._check_pgvector",
                    new=AsyncMock(return_value={"status": "healthy"}),
                ),
                patch(
                    "app.services.health_service._check_license_identity",
                    return_value={"status": "healthy"},
                ),
                patch(
                    "app.services.health_service.agent_runtime_dependency_status",
                    return_value={"status": "healthy"},
                ),
                patch(
                    "app.services.health_service._check_media_generation",
                    return_value={"status": "healthy"},
                ),
                patch(
                    "app.services.health_service._check_media_worker",
                    new=AsyncMock(return_value={"status": "healthy"}),
                ),
            ):
                report = await build_health_report(deep=True)
        finally:
            health_service.settings.environment = original_environment
            health_service.settings.secret_key = original_secret_key
            health_service.settings.litellm_master_key = original_litellm_master_key
            health_service.settings.minio_secret_key = original_minio_secret_key
            health_service.settings.redis_url = original_redis_url

        self.assertEqual("unhealthy", report["status"])
        self.assertEqual("unhealthy", report["components"]["production_config"]["status"])

    async def test_ragflow_is_optional_until_url_is_configured(self) -> None:
        original_url = health_service.settings.ragflow_url
        health_service.settings.ragflow_url = None
        try:
            with (
                patch(
                    "app.services.health_service._check_database",
                    new=AsyncMock(return_value={"status": "healthy"}),
                ),
                patch(
                    "app.services.health_service._check_redis",
                    new=AsyncMock(return_value={"status": "healthy"}),
                ),
                patch(
                    "app.services.health_service._check_minio",
                    new=AsyncMock(return_value={"status": "healthy"}),
                ),
                patch(
                    "app.services.health_service._check_litellm",
                    new=AsyncMock(return_value={"status": "healthy"}),
                ),
                patch(
                    "app.services.health_service._check_pgvector",
                    new=AsyncMock(return_value={"status": "healthy"}),
                ),
                patch(
                    "app.services.health_service._check_license_identity",
                    return_value={"status": "healthy"},
                ),
                patch(
                    "app.services.health_service.agent_runtime_dependency_status",
                    return_value={"status": "healthy"},
                ),
                patch(
                    "app.services.health_service._check_media_generation",
                    return_value={"status": "healthy"},
                ),
                patch(
                    "app.services.health_service._check_media_worker",
                    new=AsyncMock(return_value={"status": "healthy"}),
                ),
            ):
                report = await build_health_report(deep=True)
        finally:
            health_service.settings.ragflow_url = original_url

        self.assertEqual("healthy", report["status"])
        self.assertNotIn("ragflow", report["components"])

    async def test_configured_ragflow_participates_in_readiness(self) -> None:
        original_url = health_service.settings.ragflow_url
        health_service.settings.ragflow_url = "http://ragflow.local"
        try:
            with (
                patch(
                    "app.services.health_service._check_database",
                    new=AsyncMock(return_value={"status": "healthy"}),
                ),
                patch(
                    "app.services.health_service._check_redis",
                    new=AsyncMock(return_value={"status": "healthy"}),
                ),
                patch(
                    "app.services.health_service._check_minio",
                    new=AsyncMock(return_value={"status": "healthy"}),
                ),
                patch(
                    "app.services.health_service._check_litellm",
                    new=AsyncMock(return_value={"status": "healthy"}),
                ),
                patch(
                    "app.services.health_service._check_pgvector",
                    new=AsyncMock(return_value={"status": "healthy"}),
                ),
                patch(
                    "app.services.health_service._check_ragflow",
                    new=AsyncMock(return_value={"status": "unhealthy"}),
                ),
                patch(
                    "app.services.health_service._check_license_identity",
                    return_value={"status": "healthy"},
                ),
                patch(
                    "app.services.health_service.agent_runtime_dependency_status",
                    return_value={"status": "healthy"},
                ),
                patch(
                    "app.services.health_service._check_media_generation",
                    return_value={"status": "healthy"},
                ),
                patch(
                    "app.services.health_service._check_media_worker",
                    new=AsyncMock(return_value={"status": "healthy"}),
                ),
            ):
                report = await build_health_report(deep=True)
        finally:
            health_service.settings.ragflow_url = original_url

        self.assertEqual("unhealthy", report["status"])
        self.assertIn("ragflow", report["components"])

    async def test_litellm_health_reports_unhealthy_for_auth_failure(self) -> None:
        original_base_url = health_service.settings.litellm_base_url
        original_master_key = health_service.settings.litellm_master_key
        health_service.settings.litellm_base_url = "http://litellm.local"
        health_service.settings.litellm_master_key = "bad-key"

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def get(self, _url, headers=None):
                return httpx.Response(401)

        try:
            with patch("app.services.health_service.httpx.AsyncClient", FakeAsyncClient):
                component = await health_service._check_litellm()
        finally:
            health_service.settings.litellm_base_url = original_base_url
            health_service.settings.litellm_master_key = original_master_key

        self.assertEqual("unhealthy", component["status"])
        self.assertEqual(401, component["details"]["status_code"])

    async def test_frontend_health_uses_configured_service_url(self) -> None:
        original_url = health_service.settings.frontend_health_url
        health_service.settings.frontend_health_url = "http://frontend/"

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def get(self, url):
                self.url = url
                return httpx.Response(200)

        try:
            with patch("app.services.health_service.httpx.AsyncClient", FakeAsyncClient):
                component = await _check_frontend()
        finally:
            health_service.settings.frontend_health_url = original_url

        self.assertEqual("healthy", component["status"])
        self.assertEqual("http://frontend/", component["details"]["url"])
        self.assertEqual(200, component["details"]["status_code"])

    async def test_frontend_health_requires_url_in_production(self) -> None:
        original_environment = health_service.settings.environment
        original_url = health_service.settings.frontend_health_url
        health_service.settings.environment = "production"
        health_service.settings.frontend_health_url = ""
        try:
            component = await _check_frontend()
        finally:
            health_service.settings.environment = original_environment
            health_service.settings.frontend_health_url = original_url

        self.assertEqual("not_configured", component["status"])
        self.assertFalse(component["details"]["frontend_health_url_configured"])


def _test_ed25519_public_key_pem() -> bytes:
    return (
        Ed25519PrivateKey.generate()
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )


class FakeAuditSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, item: object) -> None:
        self.added.append(item)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


if __name__ == "__main__":
    unittest.main()
