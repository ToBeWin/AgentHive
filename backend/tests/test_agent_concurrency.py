import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException

from app.core.config import settings
from app.services.agent_concurrency import agent_concurrency_limiter


class AgentConcurrencyLimiterTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        await agent_concurrency_limiter.reset()

    async def asyncTearDown(self) -> None:
        await agent_concurrency_limiter.reset()

    async def test_user_limit_rejects_parallel_agent_run(self) -> None:
        tenant_id = uuid4()
        user_id = uuid4()
        agent_id = uuid4()

        with (
            patch.object(settings, "agent_concurrency_enabled", True),
            patch.object(settings, "agent_concurrency_tenant_limit", 10),
            patch.object(settings, "agent_concurrency_user_limit", 1),
            patch.object(settings, "agent_concurrency_agent_limit", 10),
            patch.object(settings, "agent_concurrency_wait_timeout_seconds", 0),
        ):
            async with agent_concurrency_limiter.acquire(
                tenant_id=tenant_id,
                user_id=user_id,
                agent_id=agent_id,
                request_id="first-run",
            ):
                with self.assertRaises(HTTPException) as raised:
                    async with agent_concurrency_limiter.acquire(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        agent_id=agent_id,
                        request_id="second-run",
                    ):
                        pass

        self.assertEqual(429, raised.exception.status_code)
        self.assertEqual("agent_concurrency_limited", raised.exception.detail["code"])
        self.assertEqual("user", raised.exception.detail["scope"])
        self.assertEqual("second-run", raised.exception.detail["request_id"])
        self.assertEqual(1, raised.exception.detail["retry_after_seconds"])
        self.assertEqual("1", raised.exception.headers["Retry-After"])
        self.assertEqual(
            {"tenant": 10, "user": 1, "agent": 10},
            raised.exception.detail["limits"],
        )

    async def test_slot_is_released_after_context_exits(self) -> None:
        tenant_id = uuid4()
        user_id = uuid4()
        agent_id = uuid4()

        with (
            patch.object(settings, "agent_concurrency_enabled", True),
            patch.object(settings, "agent_concurrency_tenant_limit", 10),
            patch.object(settings, "agent_concurrency_user_limit", 1),
            patch.object(settings, "agent_concurrency_agent_limit", 10),
            patch.object(settings, "agent_concurrency_wait_timeout_seconds", 0),
        ):
            async with agent_concurrency_limiter.acquire(
                tenant_id=tenant_id,
                user_id=user_id,
                agent_id=agent_id,
            ):
                pass
            async with agent_concurrency_limiter.acquire(
                tenant_id=tenant_id,
                user_id=user_id,
                agent_id=agent_id,
            ) as decision:
                self.assertTrue(decision.acquired)
                self.assertEqual(1, decision.active["user"])

    async def test_disabled_limiter_does_not_acquire_slots(self) -> None:
        with patch.object(settings, "agent_concurrency_enabled", False):
            async with agent_concurrency_limiter.acquire(
                tenant_id=uuid4(),
                user_id=uuid4(),
                agent_id=uuid4(),
            ) as decision:
                self.assertFalse(decision.enabled)
                self.assertFalse(decision.acquired)


if __name__ == "__main__":
    unittest.main()
