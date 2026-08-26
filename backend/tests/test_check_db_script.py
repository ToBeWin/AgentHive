import unittest
from pathlib import Path

from scripts.check_db import (
    expected_media_runtime_indexes,
    expected_official_module_keys,
    missing_media_runtime_indexes,
    missing_official_module_keys,
)


class CheckDbScriptTest(unittest.TestCase):
    def test_missing_official_module_keys_reports_exact_missing_modules(self) -> None:
        expected = {"agent.customer_service", "agent.hr_screening", "agent.copywriting"}

        self.assertEqual(
            ["agent.hr_screening"],
            missing_official_module_keys(
                {"agent.customer_service", "agent.copywriting", "agent.unknown"},
                expected,
            ),
        )

    def test_expected_official_module_keys_tracks_current_catalog(self) -> None:
        keys = expected_official_module_keys()

        self.assertIn("agent.customer_service", keys)
        self.assertIn("agent.hr_screening", keys)
        self.assertIn("agent.data_analyst", keys)

    def test_missing_media_runtime_indexes_reports_exact_missing_indexes(self) -> None:
        expected = {"idx_a", "idx_b", "idx_c"}

        self.assertEqual(
            ["idx_b"],
            missing_media_runtime_indexes({"idx_a", "idx_c", "idx_extra"}, expected),
        )

    def test_expected_media_runtime_indexes_match_latest_migration(self) -> None:
        migration_path = (
            Path(__file__).resolve().parents[1]
            / "migrations"
            / "versions"
            / "0014_media_generation_job_runtime_indexes.py"
        )
        migration = migration_path.read_text(encoding="utf-8")

        for index_name in expected_media_runtime_indexes():
            self.assertIn(index_name, migration)


if __name__ == "__main__":
    unittest.main()
