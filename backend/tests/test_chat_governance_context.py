import unittest
from uuid import uuid4

from fastapi import HTTPException

from app.api.deps import Principal
from app.models.channel import ChannelConfig
from app.schemas.chat import ChatSessionCreateRequest
from app.services.chat_service import create_chat_session


class ChatGovernanceContextTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_session_accepts_agent_instance_id_alias(self) -> None:
        agent_id = uuid4()
        payload = ChatSessionCreateRequest(agent_instance_id=agent_id)

        self.assertEqual(agent_id, payload.agent_id)

    async def test_create_session_rejects_conflicting_agent_aliases(self) -> None:
        with self.assertRaises(ValueError):
            ChatSessionCreateRequest(agent_id=uuid4(), agent_instance_id=uuid4())

    async def test_create_session_rejects_department_outside_user_scope(self) -> None:
        tenant_id = uuid4()
        user_id = uuid4()
        department_id = uuid4()
        session = FakeGovernanceSession(
            [
                FakeScalarOneOrNoneResult(department_id),
                FakeScalarOneOrNoneResult(None),
            ]
        )

        with self.assertRaises(HTTPException) as raised:
            await create_chat_session(
                session,
                Principal(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    permissions={"chat:write"},
                ),
                ChatSessionCreateRequest(department_id=department_id),
                request_id="request-1",
            )

        self.assertEqual(403, raised.exception.status_code)
        self.assertEqual([], session.added)

    async def test_create_session_rejects_agent_mismatch_with_channel_binding(self) -> None:
        tenant_id = uuid4()
        channel_agent_id = uuid4()
        requested_agent_id = uuid4()
        channel = ChannelConfig(
            id=uuid4(),
            tenant_id=tenant_id,
            name="Web Widget",
            channel_type="web_widget",
            channel_key="web-demo",
            agent_id=channel_agent_id,
        )
        session = FakeGovernanceSession([FakeScalarOneOrNoneResult(channel)])

        with self.assertRaises(HTTPException) as raised:
            await create_chat_session(
                session,
                Principal(
                    tenant_id=tenant_id,
                    user_id=uuid4(),
                    permissions={"chat:write"},
                ),
                ChatSessionCreateRequest(
                    agent_id=requested_agent_id,
                    channel_id=channel.id,
                ),
                request_id="request-1",
            )

        self.assertEqual(409, raised.exception.status_code)
        self.assertEqual([], session.added)


class FakeGovernanceSession:
    def __init__(self, execute_results: list[object]) -> None:
        self.execute_results = list(execute_results)
        self.added: list[object] = []

    async def execute(self, _statement: object) -> object:
        if not self.execute_results:
            raise AssertionError("Unexpected execute call.")
        return self.execute_results.pop(0)

    def add(self, row: object) -> None:
        self.added.append(row)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class FakeScalarOneOrNoneResult:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object:
        return self.value


if __name__ == "__main__":
    unittest.main()
