from __future__ import annotations

import unittest
from collections.abc import Awaitable, Callable
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import Principal
from app.services.org_admin_service import (
    list_cost_centers,
    list_departments,
    list_roles,
    list_users,
)


class OrgAdminReadFailureTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.principal = Principal(
            user_id=UUID("00000000-0000-4000-8000-000000000111"),
            tenant_id=UUID("00000000-0000-4000-8000-000000000211"),
            permissions={"tenant.admin"},
        )

    async def test_department_list_storage_failure_returns_503(self) -> None:
        await self._assert_storage_failure(list_departments)

    async def test_cost_center_list_storage_failure_returns_503(self) -> None:
        await self._assert_storage_failure(list_cost_centers)

    async def test_user_list_storage_failure_returns_503(self) -> None:
        await self._assert_storage_failure(list_users)

    async def test_role_list_storage_failure_returns_503(self) -> None:
        await self._assert_storage_failure(list_roles)

    async def _assert_storage_failure(
        self,
        service: Callable[[FailingSession, Principal], Awaitable[object]],
    ) -> None:
        session = FailingSession()

        with self.assertRaises(HTTPException) as raised:
            await service(session, self.principal)

        self.assertEqual(503, raised.exception.status_code)
        self.assertTrue(session.rolled_back)


class FailingSession:
    def __init__(self) -> None:
        self.rolled_back = False

    async def execute(self, _statement: object) -> object:
        raise SQLAlchemyError("storage unavailable")

    async def rollback(self) -> None:
        self.rolled_back = True


if __name__ == "__main__":
    unittest.main()
