from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_permission
from app.core.database import get_session
from app.core.security import Permission
from app.schemas.channel import (
    ChannelCreateRequest,
    ChannelCreateResponse,
    ChannelListResponse,
    ChannelPollResponse,
    ChannelPushRequest,
    ChannelPushResponse,
    ChannelResponse,
    ChannelSecretPromoteResponse,
    ChannelSecretRotateRequest,
    ChannelSecretRotateResponse,
    ChannelStatusUpdateRequest,
    ChannelTestRequest,
    ChannelTestResponse,
    ChannelType,
    WebhookAckResponse,
)
from app.services.channel_service import (
    create_channel_for_tenant,
    list_channels_for_tenant,
    poll_channel_messages_for_tenant,
    promote_channel_secret_for_tenant,
    push_to_channel_for_tenant,
    receive_channel_webhook,
    rotate_channel_secret_for_tenant,
    test_channel_for_tenant,
    update_channel_status_for_tenant,
)

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("", response_model=ChannelListResponse)
async def read_channels(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.CHANNELS_READ))],
) -> ChannelListResponse:
    return await list_channels_for_tenant(session, tenant_id=principal.tenant_id)


@router.post("", response_model=ChannelCreateResponse)
async def create_channel(
    request: Request,
    payload: ChannelCreateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.CHANNELS_WRITE))],
) -> ChannelCreateResponse:
    return await create_channel_for_tenant(
        session,
        tenant_id=principal.tenant_id,
        request=payload,
        actor_id=principal.user_id,
        request_id=getattr(request.state, "request_id", None),
    )


@router.patch("/{channel_id}/status", response_model=ChannelResponse)
async def update_channel_status(
    channel_id: UUID,
    payload: ChannelStatusUpdateRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.CHANNELS_WRITE))],
) -> ChannelResponse:
    return await update_channel_status_for_tenant(
        session,
        tenant_id=principal.tenant_id,
        channel_id=channel_id,
        request=payload,
        actor_id=principal.user_id,
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/{channel_id}/test", response_model=ChannelTestResponse)
async def test_channel(
    channel_id: UUID,
    payload: ChannelTestRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.CHANNELS_WRITE))],
) -> ChannelTestResponse:
    return await test_channel_for_tenant(
        session,
        tenant_id=principal.tenant_id,
        channel_id=channel_id,
        request=payload,
    )


@router.post("/{channel_id}/push", response_model=ChannelPushResponse)
async def push_to_channel(
    channel_id: UUID,
    payload: ChannelPushRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.CHANNELS_WRITE))],
) -> ChannelPushResponse:
    """Proactively push a message to a channel recipient.

    Supports two modes via ``payload.mode``:
      * ``direct`` (default): deliver ``payload.text`` verbatim via the
        channel's configured outbound path (vendor_api or outbound_webhook).
      * ``agent``: invoke the channel's agent with ``payload.text`` as input
        and deliver the agent's response.

    Requires the ``channels:write`` permission. The channel must be ACTIVE.
    """

    return await push_to_channel_for_tenant(
        session,
        tenant_id=principal.tenant_id,
        channel_id=channel_id,
        request=payload,
        actor_id=principal.user_id,
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/{channel_id}/secret/rotate",
    response_model=ChannelSecretRotateResponse,
)
async def rotate_channel_secret(
    channel_id: UUID,
    payload: ChannelSecretRotateRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.CHANNELS_WRITE))],
) -> ChannelSecretRotateResponse:
    """Rotate a Channel's webhook signing secret with a dual-secret window.

    The current secret is moved to ``previous_secret`` (still accepted during
    the transition), and ``payload.new_secret`` becomes the primary. Call
    ``POST /{channel_id}/secret/promote`` after the transition window to drop
    the previous secret.

    Requires the ``channels:write`` permission.
    """

    return await rotate_channel_secret_for_tenant(
        session,
        tenant_id=principal.tenant_id,
        channel_id=channel_id,
        request=payload,
        actor_id=principal.user_id,
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/{channel_id}/secret/promote",
    response_model=ChannelSecretPromoteResponse,
)
async def promote_channel_secret(
    channel_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.CHANNELS_WRITE))],
) -> ChannelSecretPromoteResponse:
    """Finalize a secret rotation by dropping the staged previous secret.

    After this call only the current (rotated) secret is accepted. Requires
    the ``channels:write`` permission.
    """

    return await promote_channel_secret_for_tenant(
        session,
        tenant_id=principal.tenant_id,
        channel_id=channel_id,
        actor_id=principal.user_id,
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/webhook/{channel_type}/{channel_key}", response_model=WebhookAckResponse)
async def receive_webhook(
    channel_type: ChannelType,
    channel_key: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: dict[str, Any],
) -> WebhookAckResponse:
    return await receive_channel_webhook(
        session,
        channel_type=channel_type,
        channel_key=channel_key,
        payload=payload,
        headers=dict(request.headers),
        request_id=getattr(request.state, "request_id", None),
    )


@router.get("/poll/{channel_type}/{channel_key}", response_model=ChannelPollResponse)
async def poll_messages(
    channel_type: ChannelType,
    channel_key: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    external_user_id: Annotated[str, Query(min_length=1, max_length=255)],
    conversation_key: Annotated[str | None, Query(max_length=500)] = None,
    after: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ChannelPollResponse:
    """Poll outbound messages for a Web Widget / REST API Channel client.

    Returns assistant messages addressed to ``external_user_id`` on the given
    channel, optionally scoped to a ``conversation_key``. ``after`` is a
    message-id cursor; only messages with id newer than the cursor are
    returned. Use ``next_cursor`` from the previous response for pagination.

    Authentication: the caller must present an ``X-AgentHive-Signature``
    header (HMAC-SHA256 of the canonical query string) signed with the
    Channel's webhook secret. Also accepts the previous secret during a
    rotation window.
    """

    from app.services.channel_service import get_channel_by_key

    channel = await get_channel_by_key(session, channel_type, channel_key)
    if channel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found.")
    if not _verify_poll_signature(request, channel):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing poll signature.",
        )

    return await poll_channel_messages_for_tenant(
        session,
        tenant_id=channel.tenant_id,
        channel_id=channel.id,
        external_user_id=external_user_id,
        conversation_key=conversation_key,
        after=after,
        limit=limit,
    )


def _verify_poll_signature(request: Request, channel: Any) -> bool:
    """Verify the X-AgentHive-Signature header for a poll request.

    The signature is HMAC-SHA256 of ``f"{method}.{path}?{sorted_query}"``
    using the Channel secret (or previous secret during rotation).
    """

    import hashlib
    import hmac

    secret = getattr(channel, "secret", None)
    previous_secret = getattr(channel, "previous_secret", None)
    if not secret and not previous_secret:
        # Channel with no secret configured: allow unauthenticated poll.
        # Operators that want auth must configure a secret.
        return True

    signature_header = request.headers.get("x-agenthive-signature") or request.headers.get(
        "X-AgentHive-Signature"
    )
    if not signature_header:
        return False
    timestamp = request.headers.get("x-agenthive-timestamp") or request.headers.get(
        "X-AgentHive-Timestamp"
    )
    nonce = request.headers.get("x-agenthive-nonce") or request.headers.get("X-AgentHive-Nonce")
    if not timestamp or not nonce:
        return False

    # Canonical query: sorted key=value pairs joined by '&', using the raw
    # query string from the request.
    raw_query = request.url.query
    pairs = sorted(raw_query.split("&")) if raw_query else []
    canonical_query = "&".join(pairs)
    signing_base = f"{timestamp}.{nonce}.{request.method}.{request.url.path}?{canonical_query}"

    for candidate in (secret, previous_secret):
        if not candidate:
            continue
        expected = hmac.new(
            candidate.encode("utf-8"), signing_base.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        provided = signature_header.removeprefix("sha256=").strip()
        if hmac.compare_digest(expected, provided):
            return True
    return False
