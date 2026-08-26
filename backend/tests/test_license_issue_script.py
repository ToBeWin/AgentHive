import unittest

from app.services.agent_module_service import list_module_definitions
from scripts.license_issue import (
    OFFICIAL_MODULES,
    missing_required_features_for_modules,
    official_module_rows,
    validate_module_feature_coverage,
)


class LicenseIssueScriptTest(unittest.TestCase):
    def test_official_modules_match_agent_module_catalog(self) -> None:
        expected = {definition.id for definition in list_module_definitions()}

        self.assertEqual(expected, set(OFFICIAL_MODULES))
        self.assertEqual(len(expected), len(OFFICIAL_MODULES))

    def test_official_module_rows_include_delivery_metadata(self) -> None:
        rows = official_module_rows()
        finance = next(row for row in rows if row["module_key"] == "agent.finance")

        self.assertEqual("P2", finance["priority"])
        self.assertEqual(
            ["feature.agent_catalog", "feature.model_budget"], finance["required_features"]
        )
        self.assertEqual(["agent.report_writer"], finance["dependencies"])

    def test_missing_required_features_are_detected_before_license_issue(self) -> None:
        missing = missing_required_features_for_modules(
            ["agent.finance"],
            ["feature.agent_catalog"],
        )

        self.assertEqual(["feature.model_budget"], missing)
        with self.assertRaises(SystemExit):
            validate_module_feature_coverage(["agent.finance"], ["feature.agent_catalog"])

    def test_basic_modules_pass_required_feature_check(self) -> None:
        validate_module_feature_coverage(
            ["agent.customer_service", "agent.copywriting"],
            ["feature.agent_catalog", "feature.license_offline_activation"],
        )


if __name__ == "__main__":
    unittest.main()
