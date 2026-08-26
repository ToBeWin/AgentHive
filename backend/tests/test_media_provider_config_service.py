import unittest
from uuid import uuid4

from fastapi import HTTPException

from app.api.deps import Principal
from app.core.secrets import encrypt_secret
from app.media.schemas import MediaProviderType
from app.models.llm import LLMCredential, LLMProvider
from app.services.media_provider_config_service import (
    ensure_media_provider_configured,
    media_provider_configuration_issues,
    media_provider_diagnostics,
    resolve_database_media_provider_adapter,
)


class FakeAllResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeMediaProviderConfigSession:
    def __init__(self, rows):
        self.rows = rows

    async def execute(self, _statement):
        return FakeAllResult(self.rows)


def make_principal() -> Principal:
    return Principal(
        tenant_id=uuid4(),
        user_id=uuid4(),
        permissions={"models:read"},
    )


def make_provider_credential(
    principal: Principal,
    *,
    provider_key: str = "nano_banana",
    base_url: str = "https://media.example.test",
    owner_type: str = "tenant",
    owner_id=None,
) -> tuple[LLMProvider, LLMCredential]:
    provider = LLMProvider(
        tenant_id=principal.tenant_id,
        provider_key=provider_key,
        name="Nano Banana",
        adapter_type="openai_compatible",
        base_url=base_url,
        config={},
    )
    credential = LLMCredential(
        tenant_id=principal.tenant_id,
        provider_id=provider.id,
        owner_type=owner_type,
        owner_id=owner_id,
        display_name="Tenant Media Key",
        secret_ref=encrypt_secret("sk-live-media-secret"),
        masked_secret="sk-l...cret",
    )
    return provider, credential


class MediaProviderConfigServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_media_provider_diagnostics_uses_database_credentials(self):
        principal = make_principal()
        rows = [make_provider_credential(principal)]
        session = FakeMediaProviderConfigSession(rows)

        diagnostics = await media_provider_diagnostics(session, principal)

        self.assertEqual([], diagnostics[MediaProviderType.NANO_BANANA])
        self.assertIn(
            "VOLCENGINE_SEEDANCE_API_KEY", diagnostics[MediaProviderType.VOLCENGINE_SEEDANCE]
        )

    async def test_resolve_database_media_provider_adapter_decrypts_scoped_credential(self):
        principal = make_principal()
        department_id = uuid4()
        tenant_row = make_provider_credential(principal, base_url="https://tenant.example.test")
        department_row = make_provider_credential(
            principal,
            base_url="https://department.example.test",
            owner_type="department",
            owner_id=department_id,
        )
        session = FakeMediaProviderConfigSession([tenant_row, department_row])

        adapter = await resolve_database_media_provider_adapter(
            session,
            principal,
            MediaProviderType.NANO_BANANA,
            department_id=department_id,
            user_id=principal.user_id,
        )

        self.assertIsNotNone(adapter)
        assert adapter is not None
        self.assertEqual(MediaProviderType.NANO_BANANA, adapter.provider_type)
        self.assertEqual("https://department.example.test", adapter.base_url)
        self.assertEqual("sk-live-media-secret", adapter.api_key)

    async def test_configuration_issues_are_cleared_by_department_database_credential(self):
        principal = make_principal()
        department_id = uuid4()
        rows = [
            make_provider_credential(
                principal,
                provider_key="volcengine_seedance",
                base_url="https://seedance.example.test",
                owner_type="department",
                owner_id=department_id,
            )
        ]
        session = FakeMediaProviderConfigSession(rows)

        issues = await media_provider_configuration_issues(
            session,
            principal,
            MediaProviderType.VOLCENGINE_SEEDANCE,
            department_id=department_id,
            user_id=principal.user_id,
        )

        self.assertEqual([], issues)

    async def test_ensure_media_provider_configured_raises_actionable_conflict(self):
        principal = make_principal()
        session = FakeMediaProviderConfigSession([])

        with self.assertRaises(HTTPException) as error:
            await ensure_media_provider_configured(
                session, principal, MediaProviderType.VOLCENGINE_SEEDANCE
            )

        self.assertEqual(409, error.exception.status_code)
        self.assertIn("VOLCENGINE_SEEDANCE_API_KEY", error.exception.detail)


if __name__ == "__main__":
    unittest.main()
