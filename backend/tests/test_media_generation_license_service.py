import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.api.deps import Principal
from app.media.schemas import MediaGenerationKind
from app.services.media_generation_license_service import (
    ensure_media_generation_module_runnable,
    media_generation_module_key,
)


class MediaGenerationLicenseServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_media_generation_kind_maps_to_agent_module_keys(self):
        self.assertEqual(
            "agent.image_generation", media_generation_module_key(MediaGenerationKind.IMAGE)
        )
        self.assertEqual("agent.video_generation", media_generation_module_key("video"))

    async def test_ensure_media_generation_module_runnable_delegates_to_agent_module_gate(self):
        principal = Principal(tenant_id=uuid4(), user_id=uuid4(), permissions={"agents:write"})
        session = object()

        with patch(
            "app.services.media_generation_license_service.ensure_agent_module_runnable_for_tenant",
            new_callable=AsyncMock,
        ) as module_gate:
            module_key = await ensure_media_generation_module_runnable(
                session,
                principal,
                MediaGenerationKind.VIDEO,
            )

        self.assertEqual("agent.video_generation", module_key)
        module_gate.assert_awaited_once_with(
            session,
            tenant_id=principal.tenant_id,
            module_key="agent.video_generation",
            usage_label="media generation",
        )


if __name__ == "__main__":
    unittest.main()
