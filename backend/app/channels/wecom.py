from typing import Any
from uuid import UUID

import httpx

from app.channels.base import BaseChannelAdapter, _string_or_none
from app.schemas.channel import (
    ChannelType,
    InboundMessage,
    OutboundDeliveryResult,
    OutboundMessage,
    SignatureVerification,
)


class WeComChannelAdapter(BaseChannelAdapter):
    channel_type = ChannelType.WECOM
    signature_method = "wecom-token-aeskey"

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
        message_type = self._message_type(payload.get("MsgType") or payload.get("msgtype"))
        text = _nested_text(payload, "Text", "Content") or _nested_text(payload, "text", "content")
        external_user_id = (
            payload.get("FromUserName") or payload.get("from_user") or payload.get("userid")
        )
        external_message_id = payload.get("MsgId") or payload.get("msgid")
        conversation_key = payload.get("ConversationId") or payload.get("conversation_key")
        return self._build_message(
            tenant_id=tenant_id,
            channel_id=channel_id,
            channel_key=channel_key,
            external_user_id=str(external_user_id) if external_user_id is not None else None,
            external_message_id=(
                str(external_message_id) if external_message_id is not None else None
            ),
            conversation_key=str(conversation_key) if conversation_key is not None else None,
            message_type=message_type,
            text=text,
            payload=payload,
            signature=signature,
            request_id=request_id,
            trace_id=headers.get("x-request-id") or headers.get("x-wecom-trace-id"),
        )

    async def _send_outbound_via_vendor(
        self,
        *,
        channel_config: dict[str, Any],
        message: OutboundMessage,
        request_id: str | None,
    ) -> OutboundDeliveryResult:
        """Send a message via WeCom Work /cgi-bin/message/send API.

        Required config (one of):
          - wecom_access_token: pre-fetched access_token (2h lifetime). When
            absent, the token refresh service is used if ``wecom_corp_id`` +
            ``wecom_secret`` are configured (see channel_token_service).
          - wecom_corp_id + wecom_secret: credentials for dynamic token
            refresh via /cgi-bin/gettoken.
          - wecom_agent_id: the agentid integer assigned by WeCom backend.
        Optional:
          - wecom_api_base_url: override (default https://qyapi.weixin.qq.com).
          - wecom_to_user: override recipient UserID. When absent, falls back
            to message.external_user_id.
          - outbound_timeout_seconds: per-request timeout.
        """

        agent_id = channel_config.get("wecom_agent_id")
        # Prefer static token; fall back to dynamic refresh when refresh
        # credentials are present. ``get_access_token`` returns None when
        # neither path yields a token.
        access_token = _string_or_none(channel_config.get("wecom_access_token"))
        if not access_token:
            from app.services.channel_token_service import get_access_token

            access_token = await get_access_token(
                message.channel_id,
                ChannelType.WECOM,
                channel_config,
                request_id=request_id,
            )
        if not access_token or agent_id is None:
            return OutboundDeliveryResult(
                attempted=False,
                delivered=False,
                mode="vendor_api_not_configured",
                details={
                    "reason": "missing_wecom_access_token_or_agent_id",
                    "channel_type": self.channel_type.value,
                },
            )

        base_url = (
            _string_or_none(channel_config.get("wecom_api_base_url"))
            or "https://qyapi.weixin.qq.com"
        ).rstrip("/")
        target_url = f"{base_url}/cgi-bin/message/send"
        to_user = _string_or_none(channel_config.get("wecom_to_user")) or message.external_user_id
        if not to_user:
            return OutboundDeliveryResult(
                attempted=False,
                delivered=False,
                mode="vendor_api_not_configured",
                details={"reason": "missing_recipient_user_id"},
            )

        # WeCom /message/send only supports text in this minimal bridge.
        # Image/file/etc. would require media upload first; left for a follow-up.
        payload: dict[str, Any] = {
            "touser": to_user,
            "msgtype": "text",
            "agentid": int(agent_id),
            "text": {"content": message.text or ""},
        }
        params = {"access_token": access_token}
        timeout = float(channel_config.get("outbound_timeout_seconds") or 8.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(target_url, json=payload, params=params)
        except httpx.HTTPError as exc:
            return OutboundDeliveryResult(
                attempted=True,
                delivered=False,
                mode="vendor_api_wecom",
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
            details["wecom_response"] = body
            errcode = body.get("errcode")
            # WeCom: errcode == 0 means success; anything else is an error
            # with errmsg. Common codes: 40014 (invalid token), 40056 (agent
            # not found), 81013 (user not in agent's visible range).
            delivered = errcode == 0
            if not delivered:
                details["wecom_errcode"] = errcode
                details["wecom_errmsg"] = body.get("errmsg")
        return OutboundDeliveryResult(
            attempted=True,
            delivered=delivered,
            mode="vendor_api_wecom",
            status_code=response.status_code,
            target=target_url,
            details=details,
        )


def _nested_text(payload: dict[str, Any], outer: str, inner: str) -> str | None:
    value = payload.get(outer)
    if isinstance(value, dict) and value.get(inner) is not None:
        return str(value[inner])
    return None
