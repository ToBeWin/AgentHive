from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ChannelType(StrEnum):
    WECOM = "wecom"
    DINGTALK = "dingtalk"
    FEISHU = "feishu"
    WEB_WIDGET = "web_widget"
    REST_API = "rest_api"


class ChannelStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    TESTING = "testing"
    ERROR = "error"


class ChannelMessageDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class ChannelMessageType(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    AUDIO = "audio"
    VIDEO = "video"
    EVENT = "event"
    UNKNOWN = "unknown"


class SignatureVerification(BaseModel):
    checked: bool = False
    valid: bool = False
    method: str | None = None
    reason: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ChannelAttachment(BaseModel):
    id: str | None = None
    type: str = Field(default="file", max_length=40)
    name: str | None = Field(default=None, max_length=255)
    url: str | None = None
    content_type: str | None = Field(default=None, max_length=120)
    size_bytes: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UnifiedMessage(BaseModel):
    tenant_id: UUID | None = None
    channel_id: UUID | None = None
    channel_type: ChannelType
    channel_key: str | None = Field(default=None, max_length=120)
    direction: ChannelMessageDirection
    external_user_id: str | None = Field(default=None, max_length=255)
    external_message_id: str | None = Field(default=None, max_length=255)
    conversation_key: str = Field(min_length=1, max_length=500)
    message_type: ChannelMessageType = ChannelMessageType.UNKNOWN
    text: str | None = None
    attachments: list[ChannelAttachment] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    signature: SignatureVerification = Field(default_factory=SignatureVerification)
    trace_id: str | None = Field(default=None, max_length=120)
    request_id: str | None = Field(default=None, max_length=120)
    received_at: datetime


class InboundMessage(UnifiedMessage):
    direction: ChannelMessageDirection = ChannelMessageDirection.INBOUND


class OutboundMessage(UnifiedMessage):
    direction: ChannelMessageDirection = ChannelMessageDirection.OUTBOUND


class OutboundDeliveryResult(BaseModel):
    attempted: bool = False
    delivered: bool = False
    mode: str = Field(default="not_configured", max_length=80)
    status_code: int | None = None
    target: str | None = Field(default=None, max_length=500)
    error: str | None = Field(default=None, max_length=200)
    details: dict[str, Any] = Field(default_factory=dict)


class ChannelCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    channel_type: ChannelType
    channel_key: str = Field(min_length=1, max_length=120)
    agent_id: UUID | None = None
    status: ChannelStatus = ChannelStatus.ACTIVE
    config: dict[str, Any] = Field(default_factory=dict)
    secret: str | None = Field(default=None, min_length=1, max_length=4096)


class ChannelStatusUpdateRequest(BaseModel):
    status: ChannelStatus


class ChannelProcessingResult(BaseModel):
    routed: bool
    agent_key: str | None = None
    conversation_id: UUID | None = None
    response_text: str | None = None
    outbound_delivery: OutboundDeliveryResult | None = None
    request_id: str | None = None
    model_key: str | None = None
    runtime_evidence: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ChannelResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    channel_type: ChannelType
    channel_key: str
    agent_id: UUID | None
    status: ChannelStatus
    webhook_path: str
    config: dict[str, Any] = Field(default_factory=dict)
    secret_configured: bool
    created_at: datetime
    updated_at: datetime


class ChannelListResponse(BaseModel):
    channels: list[ChannelResponse]


class ChannelCreateResponse(BaseModel):
    channel: ChannelResponse
    message: str


class ChannelTestRequest(BaseModel):
    text: str = Field(default="AgentHive channel test message.", max_length=2000)
    external_user_id: str = Field(default="agenthive-test-user", max_length=255)
    conversation_key: str | None = Field(default=None, max_length=500)
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class ChannelTestResponse(BaseModel):
    ok: bool
    channel_id: UUID
    normalized_message: InboundMessage
    processing: ChannelProcessingResult | None = None
    message: str


class WebhookAckResponse(BaseModel):
    accepted: bool
    channel_type: ChannelType
    channel_key: str
    tenant_id: UUID | None = None
    channel_id: UUID | None = None
    message_id: str | None = None
    conversation_key: str | None = None
    signature: SignatureVerification
    request_id: str | None = None
    trace_id: str | None = None
    processing: ChannelProcessingResult | None = None
    message: str


class ChannelPushMode(StrEnum):
    """How an outbound push should be produced.

    DIRECT: deliver the caller-supplied ``text`` as-is without invoking the
        agent runtime. Use for system notifications, marketing blasts, or
        any pre-rendered content.
    AGENT: invoke the channel's configured agent (or ``agent_key`` override)
        with ``text`` as input, then deliver the agent's response. Use for
        proactive outreach that needs LLM reasoning.
    """

    DIRECT = "direct"
    AGENT = "agent"


class ChannelPushRequest(BaseModel):
    """Request body for ``POST /api/v1/channels/{channel_id}/push``.

    Required:
      external_user_id: target recipient on the vendor side (UserID / open_id /
        chat_id depending on channel type). Ignored for WebWidget/RestAPI which
        do not support vendor_api outbound.
      text: payload text. For DIRECT mode this is the message sent verbatim;
        for AGENT mode this is the user input fed to the agent runtime.

    Optional:
      mode: push mode, defaults to DIRECT.
      conversation_key: stable conversation identifier; defaults to
        ``{channel_type}:{channel_key}:{external_user_id}``.
      agent_key: override the channel's configured agent_key (AGENT mode only).
      model_key: override the channel's configured model_key (AGENT mode only).
      metadata: arbitrary caller metadata; surfaced in audit + delivery details.
    """

    external_user_id: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1, max_length=12000)
    mode: ChannelPushMode = ChannelPushMode.DIRECT
    conversation_key: str | None = Field(default=None, max_length=500)
    agent_key: str | None = Field(default=None, max_length=120)
    model_key: str | None = Field(default=None, max_length=120)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChannelPushResponse(BaseModel):
    """Response for the push endpoint.

    ``delivered`` reflects only the vendor API call result. ``agent_invoked``
    is True when AGENT mode ran the agent runtime (regardless of success).
    ``error`` carries a safe (non-leaky) error code on failure.
    """

    channel_id: UUID
    channel_type: ChannelType
    channel_key: str
    mode: ChannelPushMode
    delivered: bool
    agent_invoked: bool = False
    agent_key: str | None = None
    response_text: str | None = None
    conversation_key: str
    outbound_delivery: OutboundDeliveryResult | None = None
    request_id: str | None = None
    error: str | None = None
    message: str


class ChannelSecretRotateRequest(BaseModel):
    """Rotate the Channel webhook signing secret.

    The current secret is moved to ``previous_secret`` (kept for a transition
    window so in-flight requests signed with the old secret still validate),
    and ``new_secret`` becomes the primary. Call ``/secret/promote`` after the
    transition window to drop the previous secret.
    """

    new_secret: str = Field(min_length=1, max_length=4096)


class ChannelSecretRotateResponse(BaseModel):
    channel_id: UUID
    rotated: bool
    previous_secret_staged: bool
    message: str


class ChannelSecretPromoteResponse(BaseModel):
    """Finalize a secret rotation by dropping the staged previous secret."""

    channel_id: UUID
    promoted: bool
    message: str


class ChannelPollMessage(BaseModel):
    """A single outbound message returned by the polling endpoint.

    Designed for Web Widget / REST API clients that don't receive pushed
    responses (no outbound webhook / vendor_api). The client polls with a
    cursor (``after``) and receives assistant messages newer than the cursor.
    """

    message_id: UUID
    conversation_id: UUID
    conversation_key: str
    role: str
    content: str
    created_at: datetime
    request_id: str | None = None
    model_key: str | None = None


class ChannelPollResponse(BaseModel):
    """Response for the polling endpoint."""

    channel_id: UUID
    channel_type: ChannelType
    external_user_id: str
    conversation_key: str
    messages: list[ChannelPollMessage]
    next_cursor: UUID | None = None
    has_more: bool = False
