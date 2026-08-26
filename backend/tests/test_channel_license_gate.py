from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4
import unittest

from fastapi import HTTPException

from app.models.channel import ChannelConfig
from app.schemas.channel import ChannelStatus, ChannelStatusUpdateRequest, ChannelType
from app.schemas.license import LicenseStatus, LicenseStatusResponse
from app.services.channel_service import (
    CHANNEL_FEATURE_KEYS,
    ChannelRecord,
    _cache_channel,
    _channel_index,
    _channels_by_tenant,
    _ensure_channel_feature_licensed,
    _record_from_row,
    _to_response,
    update_channel_status_for_tenant,
)


def make_license_status(*, allowed_features: list[str]) -> LicenseStatusResponse:
    return LicenseStatusResponse(
        status=LicenseStatus.ACTIVE,
        license_type="enterprise",
        customer_name="AgentHive Test",
        deployment_id=uuid4(),
        install_id=uuid4(),
        machine_fingerprint_hash="sha256:test",
        allowed_modules=[],
        allowed_features=allowed_features,
        maintenance_until=None,
        expires_at=None,
        activated_at=datetime.now(timezone.utc),
        module_count=0,
        feature_count=len(allowed_features),
    )


class ChannelLicenseGateTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        _channels_by_tenant.clear()
        _channel_index.clear()

    async def test_channel_feature_gate_allows_licensed_channel_type(self) -> None:
        license_status = make_license_status(
            allowed_features=[CHANNEL_FEATURE_KEYS[ChannelType.WEB_WIDGET]],
        )

        with patch(
            "app.services.channel_service.get_license_status_for_tenant",
            AsyncMock(return_value=license_status),
        ):
            await _ensure_channel_feature_licensed(
                object(),
                tenant_id=uuid4(),
                channel_type=ChannelType.WEB_WIDGET,
            )

    async def test_channel_feature_gate_blocks_unlicensed_channel_type(self) -> None:
        license_status = make_license_status(
            allowed_features=[CHANNEL_FEATURE_KEYS[ChannelType.WEB_WIDGET]],
        )

        with patch(
            "app.services.channel_service.get_license_status_for_tenant",
            AsyncMock(return_value=license_status),
        ):
            with self.assertRaises(HTTPException) as raised:
                await _ensure_channel_feature_licensed(
                    object(),
                    tenant_id=uuid4(),
                    channel_type=ChannelType.WECOM,
                )

        self.assertEqual(403, raised.exception.status_code)
        self.assertIn("channel.wecom", str(raised.exception.detail))

    async def test_channel_status_update_disables_cached_channel_and_records_audit(self) -> None:
        channel = ChannelRecord(
            id=uuid4(),
            tenant_id=uuid4(),
            name="REST API",
            channel_type=ChannelType.REST_API,
            channel_key="rest-main",
            agent_id=None,
            created_by=uuid4(),
            status=ChannelStatus.ACTIVE,
            config={"agent_key": "customer_service"},
            secret=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        _cache_channel(channel)
        session = FakeChannelSession()

        updated = await update_channel_status_for_tenant(
            session,
            tenant_id=channel.tenant_id,
            channel_id=channel.id,
            request=ChannelStatusUpdateRequest(status=ChannelStatus.DISABLED),
            actor_id=channel.created_by,
            request_id="request-1",
        )

        self.assertEqual(ChannelStatus.DISABLED, updated.status)
        self.assertEqual(
            ChannelStatus.DISABLED, _channels_by_tenant[channel.tenant_id][channel.id].status
        )
        self.assertTrue(session.committed)
        self.assertEqual(1, len(session.added))

    async def test_broken_channel_secret_degrades_to_error_response(self) -> None:
        row = ChannelConfig(
            id=uuid4(),
            tenant_id=uuid4(),
            name="REST API",
            channel_type=ChannelType.REST_API.value,
            channel_key="rest-broken-secret",
            agent_id=None,
            created_by=uuid4(),
            status=ChannelStatus.ACTIVE.value,
            config={"agent_key": "customer_service"},
            secret_ref="not-a-fernet-token",
            secret_configured=True,
        )

        channel = _record_from_row(row)
        response = _to_response(channel)

        self.assertEqual(ChannelStatus.ERROR, channel.status)
        self.assertIsNone(channel.secret)
        self.assertEqual("decrypt_failed", channel.secret_error)
        self.assertTrue(response.secret_configured)
        self.assertEqual(ChannelStatus.ERROR, response.status)
        self.assertEqual("error", response.config["secret_health"]["status"])
        self.assertEqual("save_new_secret", response.config["secret_health"]["action"])


class FakeChannelSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.committed = False
        self.rolled_back = False

    async def get(self, *_args: object, **_kwargs: object) -> object:
        raise OSError("database unavailable")

    async def execute(self, *_args: object, **_kwargs: object) -> object:
        raise OSError("database unavailable")

    def add(self, value: object) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


if __name__ == "__main__":
    unittest.main()
