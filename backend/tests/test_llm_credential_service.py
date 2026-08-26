from uuid import uuid4
import unittest

from fastapi import HTTPException

from app.api.deps import Principal
from app.models.llm import LLMCredential, LLMDeployment, LLMModel, LLMProvider
from app.schemas.llm import LLMCredentialUpsertRequest
from app.services.llm_service import upsert_provider_credential


class FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeCredentialSession:
    def __init__(self, *, owner_exists=True):
        self.provider = None
        self.credential = None
        self.model = None
        self.deployment = None
        self.added = []
        self.execute_count = 0
        self.flushes = 0
        self.commits = 0
        self.owner_exists = owner_exists

    def add(self, row):
        self.added.append(row)
        if isinstance(row, LLMProvider):
            self.provider = row
        elif isinstance(row, LLMCredential):
            self.credential = row
        elif isinstance(row, LLMModel):
            self.model = row
        elif isinstance(row, LLMDeployment):
            self.deployment = row

    async def execute(self, _statement):
        self.execute_count += 1
        if self.execute_count == 1:
            return FakeScalarResult(uuid4() if self.owner_exists else None)
        if self.execute_count == 2:
            return FakeScalarResult(self.provider)
        if self.execute_count == 3:
            return FakeScalarResult(self.credential)
        if self.execute_count == 4:
            return FakeScalarResult(self.model)
        if self.execute_count == 5:
            return FakeScalarResult(self.deployment)
        return FakeScalarResult(None)

    async def flush(self):
        self.flushes += 1

    async def commit(self):
        self.commits += 1


def make_principal() -> Principal:
    return Principal(
        tenant_id=uuid4(),
        user_id=uuid4(),
        permissions={"models:write"},
    )


class LLMCredentialServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_upsert_provider_credential_persists_owner_scope_and_audit_metadata(self):
        session = FakeCredentialSession()
        owner_id = uuid4()

        response = await upsert_provider_credential(
            session,
            provider_key="qwen",
            payload=LLMCredentialUpsertRequest(
                display_name="Sales Department Key",
                api_key="sk-department-secret",
                owner_type="department",
                owner_id=owner_id,
                model_key="qwen-plus",
                routing_key="sales-qwen",
            ),
            principal=make_principal(),
            request_id="req-credential",
        )

        self.assertEqual("department", response.owner_type)
        self.assertEqual(owner_id, response.owner_id)
        self.assertEqual(owner_id, session.credential.owner_id)
        self.assertEqual("department", session.credential.owner_type)
        self.assertNotEqual("sk-department-secret", session.credential.secret_ref)
        self.assertEqual("sk-d...cret", session.credential.masked_secret)
        self.assertEqual(1, session.commits)
        audit_events = [row for row in session.added if row.__class__.__name__ == "AuditLog"]
        self.assertEqual(1, len(audit_events))
        self.assertEqual(str(owner_id), audit_events[0].details["owner_id"])

    async def test_upsert_provider_credential_rejects_unknown_department_owner(self):
        session = FakeCredentialSession(owner_exists=False)

        with self.assertRaises(HTTPException) as raised:
            await upsert_provider_credential(
                session,
                provider_key="qwen",
                payload=LLMCredentialUpsertRequest(
                    display_name="Unknown Department Key",
                    api_key="sk-department-secret",
                    owner_type="department",
                    owner_id=uuid4(),
                    model_key="qwen-plus",
                    routing_key="sales-qwen",
                ),
                principal=make_principal(),
                request_id="req-credential",
            )

        self.assertEqual(404, raised.exception.status_code)
        self.assertIn("department", str(raised.exception.detail))
        self.assertEqual(0, len(session.added))
        self.assertEqual(0, session.commits)

    async def test_upsert_provider_credential_rejects_unknown_user_owner(self):
        session = FakeCredentialSession(owner_exists=False)

        with self.assertRaises(HTTPException) as raised:
            await upsert_provider_credential(
                session,
                provider_key="qwen",
                payload=LLMCredentialUpsertRequest(
                    display_name="Unknown User Key",
                    api_key="sk-user-secret",
                    owner_type="user",
                    owner_id=uuid4(),
                    model_key="qwen-plus",
                    routing_key="user-qwen",
                ),
                principal=make_principal(),
                request_id="req-credential",
            )

        self.assertEqual(404, raised.exception.status_code)
        self.assertIn("user", str(raised.exception.detail))
        self.assertEqual(0, len(session.added))
        self.assertEqual(0, session.commits)

    async def test_upsert_media_provider_credential_creates_media_model_deployment(self):
        session = FakeCredentialSession()
        owner_id = uuid4()

        response = await upsert_provider_credential(
            session,
            provider_key="nano_banana",
            payload=LLMCredentialUpsertRequest(
                display_name="Creative Team Image Key",
                api_key="sk-nano-secret",
                base_url="https://media.example.test",
                owner_type="department",
                owner_id=owner_id,
            ),
            principal=make_principal(),
            request_id="req-media-credential",
        )

        self.assertEqual("nano_banana", response.provider_key)
        self.assertEqual("google/nano-banana", response.model_key)
        self.assertEqual("nano_banana-image", response.routing_key)
        self.assertEqual("image", session.model.model_type)
        self.assertIn("image_generation", session.model.capabilities)
        self.assertEqual("https://media.example.test", response.base_url)

    async def test_upsert_mimo_credential_creates_default_openai_compatible_deployment(self):
        session = FakeCredentialSession()
        owner_id = uuid4()

        response = await upsert_provider_credential(
            session,
            provider_key="mimo",
            payload=LLMCredentialUpsertRequest(
                display_name="Mimo Department Key",
                api_key="sk-mimo-secret",
                base_url="https://mimo.example.test/v1",
                owner_type="department",
                owner_id=owner_id,
            ),
            principal=make_principal(),
            request_id="req-mimo-credential",
        )

        self.assertEqual("mimo", response.provider_key)
        self.assertEqual("mimo-chat", response.model_key)
        self.assertEqual("mimo-chat", response.routing_key)
        self.assertEqual("chat", session.model.model_type)
        self.assertIn("reasoning", session.model.capabilities)
        self.assertEqual("Mimo Department Key", session.credential.display_name)
        self.assertEqual("https://mimo.example.test/v1", response.base_url)


if __name__ == "__main__":
    unittest.main()
