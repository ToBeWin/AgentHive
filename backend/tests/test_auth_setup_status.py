import unittest

from app.services.auth_service import get_setup_status


class AuthSetupStatusTest(unittest.IsolatedAsyncioTestCase):
    async def test_setup_status_reports_available_when_database_count_succeeds(self) -> None:
        response = await get_setup_status(FakeSetupStatusSession(tenant_count=1))

        self.assertTrue(response.initialized)
        self.assertTrue(response.setup_available)
        self.assertEqual(1, response.tenant_count)
        self.assertEqual("healthy", response.diagnostics["status"])

    async def test_setup_status_returns_structured_unavailable_when_database_fails(self) -> None:
        response = await get_setup_status(
            FakeSetupStatusSession(error=OSError("database unavailable"))
        )

        self.assertFalse(response.initialized)
        self.assertFalse(response.setup_available)
        self.assertEqual(0, response.tenant_count)
        self.assertIn("database is unavailable", response.message)
        self.assertEqual("database", response.diagnostics["component"])
        self.assertEqual("unhealthy", response.diagnostics["status"])
        self.assertEqual("OSError", response.diagnostics["error_type"])


class FakeSetupStatusSession:
    def __init__(self, *, tenant_count: int = 0, error: Exception | None = None):
        self.tenant_count = tenant_count
        self.error = error

    async def scalar(self, _statement):
        if self.error is not None:
            raise self.error
        return self.tenant_count


if __name__ == "__main__":
    unittest.main()
