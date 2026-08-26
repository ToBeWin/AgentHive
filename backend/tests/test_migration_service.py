import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.services.migration_service import MigrationStatus, get_migration_head


class MigrationServiceTest(unittest.TestCase):
    def test_get_migration_head_reads_current_alembic_head(self) -> None:
        self.assertEqual("0019_auth_and_audit_hardening", get_migration_head())

    def test_media_generation_runtime_indexes_cover_production_queries(self) -> None:
        migration_path = (
            Path(__file__).resolve().parents[1]
            / "migrations"
            / "versions"
            / "0014_media_generation_job_runtime_indexes.py"
        )
        migration = migration_path.read_text(encoding="utf-8")

        for index_name in {
            "ix_media_generation_jobs_tenant_user_created",
            "ix_media_generation_jobs_tenant_department_created",
            "ix_media_generation_jobs_running_user_updated",
            "ix_media_generation_jobs_running_department_updated",
            "ix_media_generation_jobs_provider_external",
        }:
            self.assertIn(index_name, migration)
        self.assertIn(
            "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)", migration
        )
        self.assertIn("WHERE status = 'running' AND external_job_id IS NOT NULL", migration)

    def test_migration_status_serializes_for_health_report(self) -> None:
        status = MigrationStatus(
            current_revision="0007_llm_usage_cost_centers",
            head_revision="0007_llm_usage_cost_centers",
            is_current=True,
            version_table_present=True,
        )

        self.assertEqual(
            {
                "current_revision": "0007_llm_usage_cost_centers",
                "head_revision": "0007_llm_usage_cost_centers",
                "is_current": True,
                "version_table_present": True,
            },
            status.as_dict(),
        )


class HealthMigrationReadinessTest(unittest.IsolatedAsyncioTestCase):
    async def test_deep_database_check_marks_migration_mismatch_degraded(self) -> None:
        from app.services import health_service

        with (
            patch(
                "app.services.health_service.check_database_health",
                new=AsyncMock(return_value={"status": "healthy"}),
            ),
            patch(
                "app.services.health_service.get_migration_status",
                new=AsyncMock(
                    return_value=MigrationStatus(
                        current_revision="0006_agent_instances",
                        head_revision="0009_llm_credential_secret_text",
                        is_current=False,
                        version_table_present=True,
                    )
                ),
            ),
            patch(
                "app.services.health_service._check_media_runtime_indexes",
                new=AsyncMock(
                    return_value={
                        "ready": True,
                        "present_count": 5,
                        "expected_count": 5,
                        "missing": [],
                    }
                ),
            ),
        ):
            result = await health_service._check_database(deep=True)

        self.assertEqual("degraded", result["status"])
        self.assertFalse(result["migrations"]["is_current"])


if __name__ == "__main__":
    unittest.main()
