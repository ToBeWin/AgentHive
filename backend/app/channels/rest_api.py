from typing import Any
from uuid import UUID

from app.channels.base import BaseChannelAdapter
from app.schemas.channel import (
    ChannelType,
    InboundMessage,
    OutboundDeliveryResult,
    OutboundMessage,
    SignatureVerification,
)


class RestAPIChannelAdapter(BaseChannelAdapter):
    channel_type = ChannelType.REST_API
    signature_method = "agenthive-rest-shared-secret"

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
        return self._build_message(
            tenant_id=tenant_id,
            channel_id=channel_id,
            channel_key=channel_key,
            external_user_id=_string(payload.get("external_user_id") or payload.get("user_id")),
            external_message_id=_string(payload.get("message_id")),
            conversation_key=_string(payload.get("conversation_key")),
            message_type=self._message_type(payload.get("message_type") or "text"),
            text=_string(payload.get("text") or payload.get("content")),
            payload=payload,
            signature=signature,
            request_id=request_id,
            trace_id=headers.get("x-request-id") or _string(payload.get("trace_id")),
        )

    async def send_outbound(
        self,
        *,
        channel_config: dict[str, Any],
        message: OutboundMessage,
        request_id: str | None,
    ) -> OutboundDeliveryResult:
        if channel_config.get("outbound_webhook_url"):
            return await super().send_outbound(
                channel_config=channel_config,
                message=message,
                request_id=request_id,
            )
        return OutboundDeliveryResult(
            attempted=True,
            delivered=True,
            mode="webhook_ack",
            details={"reason": "rest_api_response_included_in_ack"},
        )


def _string(value: object) -> str | None:
    return str(value) if value is not None else None
