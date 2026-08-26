from abc import ABC, abstractmethod
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx

from app.schemas.channel import (
    ChannelAttachment,
    ChannelMessageDirection,
    ChannelMessageType,
    ChannelType,
    InboundMessage,
    OutboundDeliveryResult,
    OutboundMessage,
    SignatureVerification,
)


class BaseChannelAdapter(ABC):
    channel_type: ChannelType
    signature_method = "not_implemented"
    signature_max_skew_seconds = 300

    async def verify_signature(
        self,
        *,
        payload: dict[str, Any],
        headers: dict[str, str],
        secret: str | None,
    ) -> SignatureVerification:
        if not secret:
            return SignatureVerification(
                checked=False,
                valid=False,
                method=self.signature_method,
                reason="No channel secret configured.",
            )
        return self._verify_agenthive_hmac(payload=payload, headers=headers, secret=secret)

    def _verify_agenthive_hmac(
        self,
        *,
        payload: dict[str, Any],
        headers: dict[str, str],
        secret: str,
    ) -> SignatureVerification:
        normalized_headers = {key.lower(): value for key, value in headers.items()}
        signature = normalized_headers.get("x-agenthive-signature") or normalized_headers.get(
            "x-agenthive-signature-256"
        )
        timestamp = normalized_headers.get("x-agenthive-timestamp")
        nonce = normalized_headers.get("x-agenthive-nonce")
        method = f"{self.signature_method}+hmac-sha256"

        if not signature or not timestamp or not nonce:
            return SignatureVerification(
                checked=True,
                valid=False,
                method=method,
                reason=(
                    "Missing X-AgentHive-Signature, X-AgentHive-Timestamp, "
                    "or X-AgentHive-Nonce header."
                ),
            )

        timestamp_seconds = _parse_timestamp_seconds(timestamp)
        if timestamp_seconds is None:
            return SignatureVerification(
                checked=True,
                valid=False,
                method=method,
                reason="Invalid X-AgentHive-Timestamp header.",
            )

        skew_seconds = abs(int(time.time()) - timestamp_seconds)
        if skew_seconds > self.signature_max_skew_seconds:
            return SignatureVerification(
                checked=True,
                valid=False,
                method=method,
                reason="Webhook timestamp is outside the allowed replay window.",
                details={
                    "max_skew_seconds": self.signature_max_skew_seconds,
                    "skew_seconds": skew_seconds,
                },
            )

        canonical_payload = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
        signing_base = f"{timestamp}.{nonce}.{canonical_payload}".encode("utf-8")
        expected = hmac.new(secret.encode("utf-8"), signing_base, hashlib.sha256).hexdigest()
        provided = signature.removeprefix("sha256=").strip()
        valid = hmac.compare_digest(expected, provided)
        return SignatureVerification(
            checked=True,
            valid=valid,
            method=method,
            reason="Signature verified." if valid else "Signature mismatch.",
            details={
                "timestamp": timestamp,
                "nonce_present": bool(nonce),
                "max_skew_seconds": self.signature_max_skew_seconds,
                "skew_seconds": skew_seconds,
            },
        )

    @abstractmethod
    async def normalize_inbound(
        self,
        *,
        tenant_id: UUID | None,
        channel_id: UUID | None,
        channel_key: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        signature: SignatureVerification,
        request_id: str | None,
    ) -> InboundMessage:
        """Convert a vendor webhook payload into AgentHive's UnifiedMessage."""

    async def send_outbound(
        self,
        *,
        channel_config: dict[str, Any],
        message: OutboundMessage,
        request_id: str | None,
    ) -> OutboundDeliveryResult:
        outbound_mode = _string_or_none(channel_config.get("outbound_mode")) or "outbound_webhook"
        if outbound_mode == "vendor_api":
            return await self._send_outbound_via_vendor(
                channel_config=channel_config,
                message=message,
                request_id=request_id,
            )
        return await self._send_outbound_via_webhook(
            channel_config=channel_config,
            message=message,
            request_id=request_id,
        )

    async def _send_outbound_via_vendor(
        self,
        *,
        channel_config: dict[str, Any],
        message: OutboundMessage,
        request_id: str | None,
    ) -> OutboundDeliveryResult:
        """Direct call to vendor send_message API.

        Base implementation is not supported: subclasses (WeCom/DingTalk/Feishu)
        override this to call the vendor's official outbound endpoint. Returning
        not_configured here keeps the contract explicit for channels that have
        no vendor API (e.g. web_widget, rest_api).
        """

        return OutboundDeliveryResult(
            attempted=False,
            delivered=False,
            mode="vendor_api_not_supported",
            details={
                "reason": "vendor_api_not_supported_for_channel",
                "channel_type": self.channel_type.value,
            },
        )

    async def _send_outbound_via_webhook(
        self,
        *,
        channel_config: dict[str, Any],
        message: OutboundMessage,
        request_id: str | None,
    ) -> OutboundDeliveryResult:
        outbound_url = _string_or_none(channel_config.get("outbound_webhook_url"))
        if not outbound_url:
            return OutboundDeliveryResult(
                attempted=False,
                delivered=False,
                mode="not_configured",
                details={"reason": "outbound_webhook_url_not_configured"},
            )

        payload = {
            "channel_key": message.channel_key,
            "channel_type": message.channel_type.value,
            "conversation_key": message.conversation_key,
            "external_user_id": message.external_user_id,
            "message_type": message.message_type.value,
            "request_id": request_id or message.request_id,
            "text": message.text,
            "trace_id": message.trace_id,
        }
        headers = {"content-type": "application/json"}
        secret = _string_or_none(channel_config.get("outbound_webhook_secret"))
        if secret:
            timestamp = str(int(time.time()))
            nonce = hashlib.sha256(
                f"{timestamp}:{message.conversation_key}:{request_id}".encode()
            ).hexdigest()[:24]
            canonical_payload = json.dumps(
                payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            )
            signing_base = f"{timestamp}.{nonce}.{canonical_payload}".encode("utf-8")
            signature = hmac.new(secret.encode("utf-8"), signing_base, hashlib.sha256).hexdigest()
            headers.update(
                {
                    "x-agenthive-nonce": nonce,
                    "x-agenthive-signature": f"sha256={signature}",
                    "x-agenthive-timestamp": timestamp,
                }
            )
        try:
            async with httpx.AsyncClient(
                timeout=float(channel_config.get("outbound_timeout_seconds") or 8.0)
            ) as client:
                response = await client.post(outbound_url, json=payload, headers=headers)
            return OutboundDeliveryResult(
                attempted=True,
                delivered=200 <= response.status_code < 300,
                mode="outbound_webhook",
                status_code=response.status_code,
                target=outbound_url,
            )
        except httpx.HTTPError as exc:
            return OutboundDeliveryResult(
                attempted=True,
                delivered=False,
                mode="outbound_webhook",
                target=outbound_url,
                error=exc.__class__.__name__,
            )

    def _message_type(self, value: object) -> ChannelMessageType:
        if isinstance(value, str):
            normalized = value.lower()
            for message_type in ChannelMessageType:
                if message_type.value == normalized:
                    return message_type
        return ChannelMessageType.UNKNOWN

    def _attachments(self, payload: dict[str, Any]) -> list[ChannelAttachment]:
        raw_attachments = payload.get("attachments") or payload.get("files") or []
        if not isinstance(raw_attachments, list):
            return []

        attachments: list[ChannelAttachment] = []
        for item in raw_attachments:
            if not isinstance(item, dict):
                continue
            attachments.append(
                ChannelAttachment(
                    id=_string_or_none(item.get("id") or item.get("media_id")),
                    type=_string_or_none(item.get("type")) or "file",
                    name=_string_or_none(item.get("name") or item.get("filename")),
                    url=_string_or_none(item.get("url") or item.get("download_url")),
                    content_type=_string_or_none(item.get("content_type")),
                    size_bytes=_int_or_none(item.get("size_bytes") or item.get("size")),
                    metadata={
                        key: value
                        for key, value in item.items()
                        if key
                        not in {
                            "id",
                            "media_id",
                            "type",
                            "name",
                            "filename",
                            "url",
                            "download_url",
                            "content_type",
                            "size",
                            "size_bytes",
                        }
                    },
                )
            )
        return attachments

    def _build_message(
        self,
        *,
        tenant_id: UUID | None,
        channel_id: UUID | None,
        channel_key: str,
        external_user_id: str | None,
        external_message_id: str | None,
        conversation_key: str | None,
        message_type: ChannelMessageType,
        text: str | None,
        payload: dict[str, Any],
        signature: SignatureVerification,
        request_id: str | None,
        trace_id: str | None = None,
    ) -> InboundMessage:
        fallback_user = external_user_id or "unknown-user"
        return InboundMessage(
            tenant_id=tenant_id,
            channel_id=channel_id,
            channel_type=self.channel_type,
            channel_key=channel_key,
            direction=ChannelMessageDirection.INBOUND,
            external_user_id=external_user_id,
            external_message_id=external_message_id,
            conversation_key=conversation_key
            or f"{self.channel_type.value}:{channel_key}:{fallback_user}",
            message_type=message_type,
            text=text,
            attachments=self._attachments(payload),
            raw_payload=payload,
            signature=signature,
            trace_id=trace_id,
            request_id=request_id,
            received_at=datetime.now(timezone.utc),
        )


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if not isinstance(value, (str, bytes, bytearray, int, float)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_timestamp_seconds(value: str) -> int | None:
    try:
        timestamp = int(value)
    except ValueError:
        return None
    if timestamp > 10_000_000_000:
        timestamp = timestamp // 1000
    return timestamp
