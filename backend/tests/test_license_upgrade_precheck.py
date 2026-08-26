import unittest
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.schemas.license import LicenseStatus, LicenseStatusResponse
from scripts.check_license_upgrade import evaluate_license_upgrade_status


class LicenseUpgradePrecheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 6, 13, tzinfo=timezone.utc)

    def test_active_license_inside_maintenance_window_allows_upgrade(self) -> None:
        failures = evaluate_license_upgrade_status(
            self._license_status(
                maintenance_until=self.now + timedelta(days=30),
                expires_at=self.now + timedelta(days=365),
            ),
            now=self.now,
        )

        self.assertEqual([], failures)

    def test_missing_maintenance_window_blocks_upgrade(self) -> None:
        failures = evaluate_license_upgrade_status(
            self._license_status(maintenance_until=None),
            now=self.now,
        )

        self.assertIn("maintenance_window_missing", failures)

    def test_expired_maintenance_window_blocks_upgrade(self) -> None:
        failures = evaluate_license_upgrade_status(
            self._license_status(maintenance_until=self.now - timedelta(seconds=1)),
            now=self.now,
        )

        self.assertIn("maintenance_window_expired", failures)

    def test_verification_issue_blocks_upgrade(self) -> None:
        failures = evaluate_license_upgrade_status(
            self._license_status(verification_issues=["install_id_mismatch"]),
            now=self.now,
        )

        self.assertIn("verification_issue_install_id_mismatch", failures)

    def test_non_active_license_blocks_upgrade(self) -> None:
        failures = evaluate_license_upgrade_status(
            self._license_status(status=LicenseStatus.EXPIRED),
            now=self.now,
        )

        self.assertIn("license_status_expired", failures)

    def _license_status(
        self,
        *,
        status: LicenseStatus = LicenseStatus.ACTIVE,
        maintenance_until: datetime | None = datetime(2027, 1, 1, tzinfo=timezone.utc),
        expires_at: datetime | None = None,
        verification_issues: list[str] | None = None,
    ) -> LicenseStatusResponse:
        return LicenseStatusResponse(
            status=status,
            license_type="enterprise",
            customer_name="AgentHive Test Customer",
            deployment_id=UUID("00000000-0000-4000-8000-000000000501"),
            install_id=UUID("00000000-0000-4000-8000-000000000502"),
            machine_fingerprint_hash="sha256:test",
            runtime_deployment_id=UUID("00000000-0000-4000-8000-000000000501"),
            runtime_install_id=UUID("00000000-0000-4000-8000-000000000502"),
            runtime_machine_fingerprint_hash="sha256:test",
            verification_issues=verification_issues or [],
            allowed_modules=["agent.customer_service"],
            allowed_features=["feature.license_offline_activation"],
            maintenance_until=maintenance_until,
            expires_at=expires_at,
            activated_at=self.now,
            max_users=100,
            max_agents=20,
            max_kb_size_gb="50.0",
            module_count=1,
            feature_count=1,
        )


if __name__ == "__main__":
    unittest.main()
