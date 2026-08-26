from typing import Any
from uuid import UUID
import json

import httpx

from app.channels.base import BaseChannelAdapter, _string_or_none
from app.schemas.channel import (
    ChannelType,
    InboundMessage,
    OutboundDeliveryResult,
    OutboundMessage,
    SignatureVerification,
)


class FeishuChannelAdapter(BaseChannelAdapter):
    channel_type = ChannelType.FEISHU
    signature_method = "feishu-encrypt-key-signature"

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
        raw_event = payload.get("event")
        event: dict[str, Any] = raw_event if isinstance(raw_event, dict) else payload
        raw_message = event.get("message")
        message: dict[str, Any] = raw_message if isinstance(raw_message, dict) else {}
        raw_sender = event.get("sender")
        sender: dict[str, Any] = raw_sender if isinstance(raw_sender, dict) else {}
        raw_sender_id = sender.get("sender_id")
        sender_id: dict[str, Any] = raw_sender_id if isinstance(raw_sender_id, dict) else {}
        return self._build_message(
            tenant_id=tenant_id,
            channel_id=channel_id,
            channel_key=channel_key,
            external_user_id=_first_string(
                sender_id.get("open_id"),
                sender_id.get("user_id"),
                event.get("open_id"),
                payload.get("open_id"),
            ),
            external_message_id=_first_string(message.get("message_id"), payload.get("message_id")),
            conversation_key=_first_string(message.get("chat_id"), payload.get("chat_id")),
            message_type=self._message_type(
                message.get("message_type") or payload.get("message_type")
            ),
            text=_first_string(message.get("content"), payload.get("content")),
            payload=payload,
            signature=signature,
            request_id=request_id,
            trace_id=headers.get("x-request-id") or headers.get("x-tt-logid"),
        )

    async def _send_outbound_via_vendor(
        self,
        *,
        channel_config: dict[str, Any],
        message: OutboundMessage,
        request_id: str | None,
    ) -> OutboundDeliveryResult:
        """Send via Feishu OpenAPI /im/v1/messages.

        Required config (one of):
          - feishu_tenant_access_token: pre-fetched token (1h lifetime). When
            absent, the token refresh service is used if ``feishu_app_id`` +
            ``feishu_app_secret`` are configured (see channel_token_service).
          - feishu_app_id + feishu_app_secret: credentials for dynamic token
            refresh via /auth/v3/tenant_access_token/internal.
          - feishu_receive_id_type: one of "open_id" / "user_id" / "union_id" /
            "email" / "chat_id" (default "open_id").
        Recipient resolution: prefer `feishu_receive_id`, fall back to
        `message.external_user_id`. When `feishu_receive_id_type == "chat_id"`,
        falls back to `message.conversation_key`.
        Optional:
          - feishu_api_base_url: override (default
            https://open.feishu.cn/open-apis).
          - outbound_timeout_seconds: per-request timeout.
        """

        # Prefer static token; fall back to dynamic refresh when refresh
        # credentials (feishu_app_id + feishu_app_secret) are present.
        # ``get_access_token`` returns None when neither path yields a token.
        token = _string_or_none(channel_config.get("feishu_tenant_access_token"))
        if not token:
            from app.services.channel_token_service import get_access_token

            token = await get_access_token(
                message.channel_id,
                ChannelType.FEISHU,
                channel_config,
                request_id=request_id,
            )
        receive_id_type = (
            _string_or_none(channel_config.get("feishu_receive_id_type")) or "open_id"
        ).lower()
        receive_id = _string_or_none(channel_config.get("feishu_receive_id"))
        if not receive_id:
            if receive_id_type == "chat_id":
                receive_id = message.conversation_key
            else:
                receive_id = message.external_user_id
        if not token or not receive_id:
            return OutboundDeliveryResult(
                attempted=False,
                delivered=False,
                mode="vendor_api_not_configured",
                details={
                    "reason": "missing_feishu_token_or_recipient",
                    "channel_type": self.channel_type.value,
                },
            )

        base_url = (
            _string_or_none(channel_config.get("feishu_api_base_url"))
            or "https://open.feishu.cn/open-apis"
        ).rstrip("/")
        target_url = f"{base_url}/im/v1/messages"
        # Feishu requires `content` to be a JSON-encoded string.
        content_field = json.dumps({"text": message.text or ""}, ensure_ascii=False)
        payload: dict[str, Any] = {
            "receive_id": receive_id,
            "msg_type": "text",
            "content": content_field,
        }
        params = {"receive_id_type": receive_id_type}
        headers = {
            "content-type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {token}",
        }
        timeout = float(channel_config.get("outbound_timeout_seconds") or 8.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    target_url, json=payload, params=params, headers=headers
                )
        except httpx.HTTPError as exc:
            return OutboundDeliveryResult(
                attempted=True,
                delivered=False,
                mode="vendor_api_feishu",
                target=target_url,
                error=exc.__class__.__name__,
            )

        delivered = False
        details: dict[str, Any] = {}
        if 200 <= response.status_code < 300:
            try:
                body = response.json()
            except ValueError:
                body = {}
            details["feishu_response"] = body
            # Feishu envelope: {"code":0,"msg":"success","data":{...}}.
            code = body.get("code")
            delivered = code == 0
            if not delivered:
                details["feishu_code"] = code
                details["feishu_msg"] = body.get("msg")
        return OutboundDeliveryResult(
            attempted=True,
            delivered=delivered,
            mode="vendor_api_feishu",
            status_code=response.status_code,
            target=target_url,
            details=details,
        )


def _first_string(*values: object) -> str | None:
    for value in values:
        if value is not None:
            return str(value)
    return None
