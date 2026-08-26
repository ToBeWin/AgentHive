import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.api.deps import Principal
from app.api.v1.media import read_media_models
from app.core.security import Permission
from app.media.schemas import MediaProviderType


class MediaApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_employee_media_models_hide_provider_diagnostics(self) -> None:
        principal = Principal(
            tenant_id=uuid4(),
            user_id=uuid4(),
            permissions={Permission.AGENTS_READ.value, Permission.CHAT_WRITE.value},
        )

        with patch(
            "app.api.v1.media.media_provider_diagnostics",
            new=AsyncMock(return_value=_provider_diagnostics()),
        ):
            models = await read_media_models(session=None, principal=principal)

        self.assertTrue(models)
        self.assertTrue(all(model.status == "active" for model in models))
        self.assertTrue(all(model.configuration_issues == [] for model in models))
        self.assertTrue(all(model.configuration_hint is None for model in models))
        self.assertNotIn("volcengine/seedance-2.0", {model.model_key for model in models})

    async def test_model_admin_media_models_include_provider_diagnostics(self) -> None:
        principal = Principal(
            tenant_id=uuid4(),
            user_id=uuid4(),
            permissions={Permission.MODELS_READ.value},
        )

        with patch(
            "app.api.v1.media.media_provider_diagnostics",
            new=AsyncMock(return_value=_provider_diagnostics()),
        ):
            models = await read_media_models(session=None, principal=principal)

        model_by_key = {model.model_key: model for model in models}
        self.assertEqual("not_configured", model_by_key["volcengine/seedance-2.0"].status)
        self.assertEqual(
            ["VOLCENGINE_SEEDANCE_API_KEY"],
            model_by_key["volcengine/seedance-2.0"].configuration_issues,
        )
        self.assertIn(
            "VOLCENGINE_SEEDANCE_API_KEY",
            model_by_key["volcengine/seedance-2.0"].configuration_hint or "",
        )


def _provider_diagnostics() -> dict[MediaProviderType, list[str]]:
    return {
        MediaProviderType.OPENAI_IMAGES: [],
        MediaProviderType.NANO_BANANA: [],
        MediaProviderType.VOLCENGINE_SEEDANCE: ["VOLCENGINE_SEEDANCE_API_KEY"],
        MediaProviderType.OPENAI_COMPATIBLE_MEDIA: ["MEDIA_OPENAI_COMPATIBLE_BASE_URL"],
        MediaProviderType.CUSTOM: ["MEDIA_CUSTOM_PROVIDER_URL"],
    }


if __name__ == "__main__":
    unittest.main()
