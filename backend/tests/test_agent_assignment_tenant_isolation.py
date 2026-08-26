from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.agent_assignments import _validate_assignment_users


class _ScalarResult:
    def __init__(self, values: list[object]) -> None:
        self._values = values

    def scalars(self) -> "_ScalarResult":
        return self

    def all(self) -> list[object]:
        return self._values


class _UserLookupSession:
    def __init__(self, matched_user_ids: list[object]) -> None:
        self._matched_user_ids = matched_user_ids

    async def execute(self, _statement: object) -> _ScalarResult:
        return _ScalarResult(self._matched_user_ids)


@pytest.mark.asyncio
async def test_assignment_targets_must_all_belong_to_the_current_tenant() -> None:
    local_user_id = uuid4()
    cross_tenant_user_id = uuid4()
    session = _UserLookupSession([local_user_id])

    with pytest.raises(HTTPException) as raised:
        await _validate_assignment_users(
            session,  # type: ignore[arg-type]
            tenant_id=uuid4(),
            user_ids=[local_user_id, cross_tenant_user_id],
        )

    assert raised.value.status_code == 422
    assert "unavailable users" in str(raised.value.detail)


@pytest.mark.asyncio
async def test_assignment_targets_reject_duplicate_user_ids() -> None:
    user_id = uuid4()
    session = _UserLookupSession([user_id])

    with pytest.raises(HTTPException) as raised:
        await _validate_assignment_users(
            session,  # type: ignore[arg-type]
            tenant_id=uuid4(),
            user_ids=[user_id, user_id],
        )

    assert raised.value.status_code == 422


@pytest.mark.asyncio
async def test_assignment_targets_accept_complete_tenant_scoped_match() -> None:
    user_ids = [uuid4(), uuid4()]
    session = _UserLookupSession(list(reversed(user_ids)))

    await _validate_assignment_users(
        session,  # type: ignore[arg-type]
        tenant_id=uuid4(),
        user_ids=user_ids,
    )
