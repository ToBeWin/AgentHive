import hashlib
import hmac
import json
import time
import unittest
from datetime import datetime, timezone
from uuid import uuid4

from app.channels.rest_api import RestAPIChannelAdapter
from app.models.audit_log import AuditLog
from app.schemas.channel import ChannelStatus, ChannelType
from app.services.channel_service import (
    ChannelRecord,
    _cache_channel,
    _channel_index,
    _channels_by_tenant,
    receive_channel_webhook,
)


class ChannelSignatureTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        _channels_by_tenant.clear()
        _channel_index.clear()

    async def test_agenthive_hmac_signature_verifies_canonical_payload(self) -> None:
        adapter = RestAPIChannelAdapter()
        secret = "channel-secret"
        payload = {"text": "hello", "external_user_id": "buyer-1"}
        timestamp = str(int(time.time()))
        nonce = "nonce-1"
        signature = _sign(secret=secret, timestamp=timestamp, nonce=nonce, payload=payload)

        result = await adapter.verify_signature(
            payload=payload,
            headers={
                "X-AgentHive-Timestamp": timestamp,
                "X-AgentHive-Nonce": nonce,
                "X-AgentHive-Signature": f"sha256={signature}",
            },
            secret=secret,
        )

        self.assertTrue(result.checked)
        self.assertTrue(result.valid)
        self.assertEqual("Signature verified.", result.reason)
        self.assertEqual("agenthive-rest-shared-secret+hmac-sha256", result.method)

    async def test_agenthive_hmac_signature_requires_headers_when_secret_exists(self) -> None:
        adapter = RestAPIChannelAdapter()

        result = await adapter.verify_signature(
            payload={"text": "hello"},
            headers={},
            secret="channel-secret",
        )

        self.assertTrue(result.checked)
        self.assertFalse(result.valid)
        self.assertIn("Missing X-AgentHive-Signature", result.reason or "")

    async def test_invalid_signature_webhook_is_not_routed(self) -> None:
        channel = ChannelRecord(
            id=uuid4(),
            tenant_id=uuid4(),
            name="REST API",
            channel_type=ChannelType.REST_API,
            channel_key="signed-api",
            agent_id=None,
            created_by=uuid4(),
            status=ChannelStatus.ACTIVE,
            config={"agent_key": "customer_service"},
            secret="channel-secret",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        _cache_channel(channel)
        session = FakeChannelSession()

        response = await receive_channel_webhook(
            session,
            channel_type=ChannelType.REST_API,
            channel_key=channel.channel_key,
            payload={"text": "hello", "external_user_id": "buyer-1"},
            headers={
                "x-agenthive-timestamp": str(int(time.time())),
                "x-agenthive-nonce": "nonce-1",
                "x-agenthive-signature": "sha256=invalid",
            },
            request_id="request-1",
        )

        self.assertFalse(response.accepted)
        self.assertEqual("Webhook signature verification failed.", response.message)
        self.assertIsNotNone(response.processing)
        self.assertEqual("invalid_signature", response.processing.error)
        self.assertFalse(response.processing.routed)
        self.assertEqual(
            "channel_gateway", response.processing.runtime_evidence["channel_execution"]
        )
        self.assertFalse(response.processing.runtime_evidence["routed"])
        self.assertFalse(response.processing.runtime_evidence["signature_valid"])
        self.assertEqual("invalid_signature", response.processing.runtime_evidence["error"])

        audit_events = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual(
            ["channel.webhook.received", "channel.webhook.processed"],
            [row.action for row in audit_events],
        )
        self.assertEqual("failure", audit_events[1].status)
        self.assertEqual("invalid_signature", audit_events[1].details["error"])
        self.assertFalse(audit_events[1].details["routed"])
        self.assertNotIn("hello", str(audit_events[0].details))
        self.assertNotIn("channel-secret", str(audit_events[0].details))
        self.assertNotIn("sha256=invalid", str(audit_events[0].details))


class FakeChannelSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.committed = False
        self.rolled_back = False

    async def execute(self, *_args: object, **_kwargs: object) -> object:
        raise OSError("database unavailable")

    def add(self, value: object) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


def _sign(*, secret: str, timestamp: str, nonce: str, payload: dict[str, object]) -> str:
    canonical_payload = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    signing_base = f"{timestamp}.{nonce}.{canonical_payload}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), signing_base, hashlib.sha256).hexdigest()


if __name__ == "__main__":
    unittest.main()
