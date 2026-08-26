import base64
import hashlib
import hmac
import time
from typing import Any
from urllib.parse import quote_plus
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


class DingTalkChannelAdapter(BaseChannelAdapter):
    channel_type = ChannelType.DINGTALK
    signature_method = "dingtalk-timestamp-sign"

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
        text_payload = payload.get("text")
        text = (
            text_payload.get("content")
            if isinstance(text_payload, dict)
            else payload.get("content")
        )
        sender_id = payload.get("senderStaffId") or payload.get("senderId") or payload.get("userid")
        conversation_id = payload.get("conversationId") or payload.get("conversation_key")
        return self._build_message(
            tenant_id=tenant_id,
            channel_id=channel_id,
            channel_key=channel_key,
            external_user_id=str(sender_id) if sender_id is not None else None,
            external_message_id=_string(payload.get("msgId") or payload.get("messageId")),
            conversation_key=str(conversation_id) if conversation_id is not None else None,
            message_type=self._message_type(payload.get("msgtype") or payload.get("messageType")),
            text=str(text) if text is not None else None,
            payload=payload,
            signature=signature,
            request_id=request_id,
            trace_id=headers.get("x-request-id") or headers.get("x-dingtalk-trace-id"),
        )

    async def _send_outbound_via_vendor(
        self,
        *,
        channel_config: dict[str, Any],
        message: OutboundMessage,
        request_id: str | None,
    ) -> OutboundDeliveryResult:
        """Send via DingTalk.

        Supports two outbound kinds, chosen by config `dingtalk_outbound_kind`:
          - "robot_webhook" (default): custom group robot inbound webhook.
            Requires `dingtalk_robot_webhook_url` (full webhook URL incl.
            access_token query param). Optional `dingtalk_robot_secret`
            enables the timestamp+sign HMAC signature DingTalk expects.
          - "work_notice": enterprise internal app work notification.
            Requires `dingtalk_access_token`, `dingtalk_agent_id`, and
            recipient (message.external_user_id or `dingtalk_userid_list`).
        """

        kind = (
            _string_or_none(channel_config.get("dingtalk_outbound_kind")) or "robot_webhook"
        ).lower()
        if kind == "work_notice":
            return await self._send_work_notice(
                channel_config=channel_config,
                message=message,
                request_id=request_id,
            )
        return await self._send_robot_webhook(
            channel_config=channel_config,
            message=message,
            request_id=request_id,
        )

    async def _send_robot_webhook(
        self,
        *,
        channel_config: dict[str, Any],
        message: OutboundMessage,
        request_id: str | None,
    ) -> OutboundDeliveryResult:
        webhook_url = _string_or_none(channel_config.get("dingtalk_robot_webhook_url"))
        if not webhook_url:
            return OutboundDeliveryResult(
                attempted=False,
                delivered=False,
                mode="vendor_api_not_configured",
                details={
                    "reason": "missing_dingtalk_robot_webhook_url",
                    "channel_type": self.channel_type.value,
                },
            )

        secret = _string_or_none(channel_config.get("dingtalk_robot_secret"))
        target_url = webhook_url
        if secret:
            # DingTalk robot signature: timestamp+"\n"+secret, HMAC-SHA256,
            # then base64 + URL-encode. Append timestamp & sign to webhook URL.
            timestamp = str(int(round(time.time() * 1000)))
            string_to_sign = f"{timestamp}\n{secret}"
            hmac_code = hmac.new(
                secret.encode("utf-8"),
                string_to_sign.encode("utf-8"),
                digestmod=hashlib.sha256,
            ).digest()
            sign = quote_plus(base64.b64encode(hmac_code).decode("utf-8"))
            separator = "&" if "?" in target_url else "?"
            target_url = f"{target_url}{separator}timestamp={timestamp}&sign={sign}"

        payload = {
            "msgtype": "text",
            "text": {"content": message.text or ""},
        }
        timeout = float(channel_config.get("outbound_timeout_seconds") or 8.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(target_url, json=payload)
        except httpx.HTTPError as exc:
            return OutboundDeliveryResult(
                attempted=True,
                delivered=False,
                mode="vendor_api_dingtalk_robot",
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
            details["dingtalk_response"] = body
            # DingTalk robot returns {"errcode":0,"errmsg":"ok"} on success.
            errcode = body.get("errcode")
            delivered = errcode == 0
            if not delivered:
                details["dingtalk_errcode"] = errcode
                details["dingtalk_errmsg"] = body.get("errmsg")
        return OutboundDeliveryResult(
            attempted=True,
            delivered=delivered,
            mode="vendor_api_dingtalk_robot",
            status_code=response.status_code,
            target=target_url,
            details=details,
        )

    async def _send_work_notice(
        self,
        *,
        channel_config: dict[str, Any],
        message: OutboundMessage,
        request_id: str | None,
    ) -> OutboundDeliveryResult:
        agent_id = channel_config.get("dingtalk_agent_id")
        userid_list = (
            _string_or_none(channel_config.get("dingtalk_userid_list")) or message.external_user_id
        )
        # Prefer static token; fall back to dynamic refresh when refresh
        # credentials (dingtalk_app_key + dingtalk_app_secret) are present.
        access_token = _string_or_none(channel_config.get("dingtalk_access_token"))
        if not access_token:
            from app.services.channel_token_service import get_access_token

            access_token = await get_access_token(
                message.channel_id,
                ChannelType.DINGTALK,
                channel_config,
                request_id=request_id,
            )
        if not access_token or agent_id is None or not userid_list:
            return OutboundDeliveryResult(
                attempted=False,
                delivered=False,
                mode="vendor_api_not_configured",
                details={
                    "reason": "missing_dingtalk_work_notice_credentials",
                    "channel_type": self.channel_type.value,
                },
            )

        base_url = (
            _string_or_none(channel_config.get("dingtalk_api_base_url"))
            or "https://oapi.dingtalk.com"
        ).rstrip("/")
        target_url = f"{base_url}/topapi/message/corpconversation/asyncsend_v2"
        params = {"access_token": access_token}
        payload = {
            "agent_id": str(agent_id),
            "userid_list": userid_list,
            "msg": {
                "msgtype": "text",
                "text": {"content": message.text or ""},
            },
        }
        timeout = float(channel_config.get("outbound_timeout_seconds") or 8.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(target_url, json=payload, params=params)
        except httpx.HTTPError as exc:
            return OutboundDeliveryResult(
                attempted=True,
                delivered=False,
                mode="vendor_api_dingtalk_work_notice",
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
            details["dingtalk_response"] = body
            errcode = body.get("errcode")
            delivered = errcode == 0
            if not delivered:
                details["dingtalk_errcode"] = errcode
                details["dingtalk_errmsg"] = body.get("errmsg")
        return OutboundDeliveryResult(
            attempted=True,
            delivered=delivered,
            mode="vendor_api_dingtalk_work_notice",
            status_code=response.status_code,
            target=target_url,
            details=details,
        )


def _string(value: object) -> str | None:
    return str(value) if value is not None else None
