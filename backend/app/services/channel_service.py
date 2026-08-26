from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, cast
from uuid import UUID, uuid4

from cryptography.fernet import InvalidToken
from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.channels import get_channel_adapter
from app.api.deps import Principal
from app.core.secrets import decrypt_secret, encrypt_secret
from app.core.security import Permission
from app.models.channel import ChannelConfig
from app.models.conversation import ConversationMessage, ConversationSession
from app.models.base import utc_now
from app.schemas.agents import AgentRunRequest
from app.schemas.channel import (
    ChannelCreateRequest,
    ChannelCreateResponse,
    ChannelListResponse,
    ChannelMessageType,
    ChannelPollMessage,
    ChannelPollResponse,
    ChannelProcessingResult,
    ChannelPushMode,
    ChannelPushRequest,
    ChannelPushResponse,
    ChannelResponse,
    ChannelSecretPromoteResponse,
    ChannelSecretRotateRequest,
    ChannelSecretRotateResponse,
    ChannelStatus,
    ChannelStatusUpdateRequest,
    ChannelTestRequest,
    ChannelTestResponse,
    ChannelType,
    InboundMessage,
    OutboundDeliveryResult,
    OutboundMessage,
    SignatureVerification,
    WebhookAckResponse,
)
from app.services.agent_runtime_service import run_agent
from app.services.audit_service import record_audit_event
from app.services.license_service import get_license_status_for_tenant


@dataclass
class ChannelRecord:
    id: UUID
    tenant_id: UUID
    name: str
    channel_type: ChannelType
    channel_key: str
    agent_id: UUID | None
    created_by: UUID | None
    status: ChannelStatus
    config: dict[str, Any]
    secret: str | None
    created_at: datetime
    updated_at: datetime
    secret_configured: bool | None = None
    secret_error: str | None = None
    previous_secret: str | None = None


_channels_by_tenant: dict[UUID, dict[UUID, ChannelRecord]] = {}
_channel_index: dict[tuple[ChannelType, str], ChannelRecord] = {}

CHANNEL_FEATURE_KEYS: dict[ChannelType, str] = {
    ChannelType.DINGTALK: "channel.dingtalk",
    ChannelType.FEISHU: "channel.feishu",
    ChannelType.REST_API: "channel.rest_api",
    ChannelType.WEB_WIDGET: "channel.web_widget",
    ChannelType.WECOM: "channel.wecom",
}


async def list_channels_for_tenant(
    session: AsyncSession,
    *,
    tenant_id: UUID,
) -> ChannelListResponse:
    try:
        result = await session.execute(
            select(ChannelConfig)
            .where(ChannelConfig.tenant_id == tenant_id)
            .order_by(cast(Any, ChannelConfig.created_at))
        )
        channels = [_record_from_row(row) for row in result.scalars().all()]
        _cache_channels(channels)
    except (OSError, SQLAlchemyError):
        channels = sorted(
            _channels_by_tenant.get(tenant_id, {}).values(),
            key=lambda channel: channel.created_at,
        )
    return ChannelListResponse(channels=[_to_response(channel) for channel in channels])


async def create_channel_for_tenant(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    request: ChannelCreateRequest,
    actor_id: UUID | None,
    request_id: str | None = None,
) -> ChannelCreateResponse:
    now = datetime.now(timezone.utc)
    await _ensure_channel_feature_licensed(
        session,
        tenant_id=tenant_id,
        channel_type=request.channel_type,
    )
    try:
        existing = await session.execute(
            select(ChannelConfig.id).where(
                ChannelConfig.channel_type == request.channel_type.value,
                ChannelConfig.channel_key == request.channel_key,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Channel key already exists for this channel type.",
            )
    except SQLAlchemyError:
        await session.rollback()
    channel = ChannelRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        name=request.name,
        channel_type=request.channel_type,
        channel_key=request.channel_key,
        agent_id=request.agent_id,
        created_by=actor_id,
        status=request.status,
        config=dict(request.config),
        secret=request.secret,
        created_at=now,
        updated_at=now,
        secret_configured=bool(request.secret),
    )
    try:
        row = ChannelConfig(
            id=channel.id,
            tenant_id=tenant_id,
            name=request.name,
            channel_type=request.channel_type.value,
            channel_key=request.channel_key,
            agent_id=request.agent_id,
            created_by=actor_id,
            status=request.status.value,
            config=dict(request.config),
            secret_ref=encrypt_secret(request.secret) if request.secret else None,
            secret_configured=bool(request.secret),
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        await session.flush()
    except (OSError, SQLAlchemyError):
        await session.rollback()
    _cache_channel(channel)

    await record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        request_id=request_id,
        action="channel.create",
        resource_type="channel",
        resource_id=channel.id,
        details={
            "channel_type": channel.channel_type.value,
            "channel_key": channel.channel_key,
            "agent_id": str(channel.agent_id) if channel.agent_id else None,
            "secret_configured": _channel_secret_configured(channel),
            "config_keys": sorted(channel.config.keys()),
        },
    )
    await _commit_audit_best_effort(session)
    return ChannelCreateResponse(channel=_to_response(channel), message="Channel created.")


async def _ensure_channel_feature_licensed(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    channel_type: ChannelType,
) -> None:
    feature_key = CHANNEL_FEATURE_KEYS[channel_type]
    license_status = await get_license_status_for_tenant(session, tenant_id=tenant_id)
    if feature_key not in license_status.allowed_features:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Channel type requires licensed feature: {feature_key}.",
        )


async def update_channel_status_for_tenant(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    channel_id: UUID,
    request: ChannelStatusUpdateRequest,
    actor_id: UUID | None,
    request_id: str | None = None,
) -> ChannelResponse:
    channel = await _get_tenant_channel(session, tenant_id, channel_id)
    previous_status = channel.status
    now = datetime.now(timezone.utc)

    try:
        row = await session.get(ChannelConfig, channel_id)
        if row is not None and row.tenant_id == tenant_id:
            row.status = request.status.value
            row.updated_at = now
            await session.flush()
    except (OSError, SQLAlchemyError):
        await session.rollback()

    updated = replace(channel, status=request.status, updated_at=now)
    _cache_channel(updated)

    await record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        request_id=request_id,
        action="channel.status.update",
        resource_type="channel",
        resource_id=channel_id,
        details={
            "channel_type": updated.channel_type.value,
            "channel_key": updated.channel_key,
            "previous_status": previous_status.value,
            "status": updated.status.value,
        },
    )
    await _commit_audit_best_effort(session)
    return _to_response(updated)


async def test_channel_for_tenant(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    channel_id: UUID,
    request: ChannelTestRequest,
) -> ChannelTestResponse:
    channel = await _get_tenant_channel(session, tenant_id, channel_id)
    adapter = get_channel_adapter(channel.channel_type)
    payload = {
        "message_type": "text",
        "text": request.text,
        "external_user_id": request.external_user_id,
        "conversation_key": request.conversation_key or f"test:{channel.channel_key}",
        **request.raw_payload,
    }
    if channel.secret_error:
        normalized = await adapter.normalize_inbound(
            tenant_id=tenant_id,
            channel_id=channel.id,
            channel_key=channel.channel_key,
            payload=payload,
            headers={},
            signature=SignatureVerification(
                checked=True,
                valid=False,
                method="agenthive-secret-store",
                reason="Channel signing secret cannot be decrypted. Save a new secret before testing.",
            ),
            request_id=None,
        )
        return ChannelTestResponse(
            ok=False,
            channel_id=channel.id,
            normalized_message=normalized,
            processing=ChannelProcessingResult(
                routed=False,
                runtime_evidence=_channel_runtime_evidence(
                    channel=channel,
                    normalized=normalized,
                    routed=False,
                    error="channel_secret_unavailable",
                ),
                error="channel_secret_unavailable",
            ),
            message="Channel signing secret cannot be decrypted. Save a new secret before testing.",
        )
    signature = await adapter.verify_signature(payload=payload, headers={}, secret=channel.secret)
    normalized = await adapter.normalize_inbound(
        tenant_id=tenant_id,
        channel_id=channel.id,
        channel_key=channel.channel_key,
        payload=payload,
        headers={},
        signature=signature,
        request_id=None,
    )
    processing = await _process_inbound_message(
        session,
        channel=channel,
        normalized=normalized,
        request_id=None,
        dry_run=True,
    )
    return ChannelTestResponse(
        ok=True,
        channel_id=channel.id,
        normalized_message=normalized,
        processing=processing,
        message="Channel adapter normalized the test message.",
    )


async def push_to_channel_for_tenant(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    channel_id: UUID,
    request: ChannelPushRequest,
    actor_id: UUID | None,
    request_id: str | None = None,
) -> ChannelPushResponse:
    """Proactively push a message to a channel recipient.

    Two modes:
      * DIRECT: deliver ``request.text`` verbatim via the channel's configured
        outbound path (vendor_api or outbound_webhook). No agent runtime call.
      * AGENT: invoke the agent (channel-configured or ``request.agent_key``
        override) with ``request.text`` as input, then deliver the agent's
        response.

    The channel must be ACTIVE. Vendor API credentials must be present for
    DIRECT delivery; AGENT mode falls back to no delivery if the agent
    succeeds but outbound is not configured (callers can still see the
    response_text in that case).
    """

    channel = await _get_tenant_channel(session, tenant_id, channel_id)
    if channel.status != ChannelStatus.ACTIVE:
        await _record_push_audit(
            session,
            channel=channel,
            request=request,
            actor_id=actor_id,
            request_id=request_id,
            delivered=False,
            agent_invoked=False,
            error="channel_disabled",
            outbound_delivery=None,
        )
        await _commit_audit_best_effort(session)
        return ChannelPushResponse(
            channel_id=channel.id,
            channel_type=channel.channel_type,
            channel_key=channel.channel_key,
            mode=request.mode,
            delivered=False,
            conversation_key=_push_conversation_key(channel, request),
            request_id=request_id,
            error="channel_disabled",
            message="Channel is not active.",
        )

    conversation_key = _push_conversation_key(channel, request)
    agent_invoked = False
    agent_key: str | None = None
    response_text: str | None = None
    error: str | None = None
    run_request_id: str | None = request_id

    if request.mode == ChannelPushMode.AGENT:
        agent_key = _resolve_push_agent_key(channel, request)
        principal = Principal(
            tenant_id=channel.tenant_id,
            user_id=actor_id or UUID("00000000-0000-4000-8000-000000000001"),
            permissions={
                Permission.AGENTS_WRITE.value,
                Permission.KNOWLEDGE_READ.value,
                Permission.MODELS_READ.value,
                Permission.BUDGETS_READ.value,
            },
        )
        try:
            response = await run_agent(
                session,
                agent_key,
                AgentRunRequest(
                    input=request.text,
                    context={
                        **_dict_config(channel.config.get("agent_context")),
                        **({"agent_id": str(channel.agent_id)} if channel.agent_id else {}),
                        "channel_id": str(channel.id),
                        "channel_type": channel.channel_type.value,
                        "conversation_key": conversation_key,
                        "external_user_id": request.external_user_id,
                        "source": f"channel_push.{channel.channel_type.value}",
                        "push_mode": "agent",
                    },
                    max_tokens=int(channel.config.get("max_tokens") or 512),
                    model_key=request.model_key or _string_or_none(channel.config.get("model_key")),
                    routing_key=_string_or_none(channel.config.get("routing_key")),
                ),
                principal,
                request_id=request_id,
            )
            agent_invoked = True
            response_text = response.answer
            run_request_id = response.request_id
        except Exception as exc:
            await session.rollback()
            error = _safe_processing_error(str(exc))
            await _record_push_audit(
                session,
                channel=channel,
                request=request,
                actor_id=actor_id,
                request_id=request_id,
                delivered=False,
                agent_invoked=True,
                agent_key=agent_key,
                error=error,
                outbound_delivery=None,
            )
            await _commit_audit_best_effort(session)
            return ChannelPushResponse(
                channel_id=channel.id,
                channel_type=channel.channel_type,
                channel_key=channel.channel_key,
                mode=request.mode,
                delivered=False,
                agent_invoked=True,
                agent_key=agent_key,
                conversation_key=conversation_key,
                request_id=request_id,
                error=error,
                message="Agent runtime failed; no outbound delivery attempted.",
            )
        outbound_text = response_text or ""
    else:
        outbound_text = request.text

    outbound_message = OutboundMessage(
        tenant_id=channel.tenant_id,
        channel_id=channel.id,
        channel_type=channel.channel_type,
        channel_key=channel.channel_key,
        external_user_id=request.external_user_id,
        external_message_id=None,
        conversation_key=conversation_key,
        message_type=ChannelMessageType.TEXT,
        text=outbound_text,
        raw_payload={
            "source": "agenthive.channel_push",
            "push_mode": request.mode.value,
            **(request.metadata if request.metadata else {}),
        },
        trace_id=None,
        request_id=run_request_id,
        received_at=datetime.now(timezone.utc),
    )
    adapter = get_channel_adapter(channel.channel_type)
    outbound_delivery = await adapter.send_outbound(
        channel_config=channel.config,
        message=outbound_message,
        request_id=run_request_id,
    )

    await _record_push_audit(
        session,
        channel=channel,
        request=request,
        actor_id=actor_id,
        request_id=request_id,
        delivered=outbound_delivery.delivered,
        agent_invoked=agent_invoked,
        agent_key=agent_key,
        response_text=response_text,
        error=None if outbound_delivery.delivered else None,
        outbound_delivery=outbound_delivery,
    )
    await _commit_audit_best_effort(session)

    message = (
        "Message delivered."
        if outbound_delivery.delivered
        else "Outbound attempted but not delivered."
    )
    return ChannelPushResponse(
        channel_id=channel.id,
        channel_type=channel.channel_type,
        channel_key=channel.channel_key,
        mode=request.mode,
        delivered=outbound_delivery.delivered,
        agent_invoked=agent_invoked,
        agent_key=agent_key,
        response_text=response_text,
        conversation_key=conversation_key,
        outbound_delivery=outbound_delivery,
        request_id=run_request_id,
        error=None,
        message=message,
    )


def _push_conversation_key(channel: ChannelRecord, request: ChannelPushRequest) -> str:
    if request.conversation_key:
        return request.conversation_key
    return f"{channel.channel_type.value}:{channel.channel_key}:{request.external_user_id}"


def _resolve_push_agent_key(channel: ChannelRecord, request: ChannelPushRequest) -> str:
    if request.agent_key and request.agent_key.strip():
        return request.agent_key.strip()
    return _agent_key_for_channel(channel)


async def _record_push_audit(
    session: AsyncSession,
    *,
    channel: ChannelRecord,
    request: ChannelPushRequest,
    actor_id: UUID | None,
    request_id: str | None,
    delivered: bool,
    agent_invoked: bool,
    agent_key: str | None = None,
    response_text: str | None = None,
    error: str | None = None,
    outbound_delivery: OutboundDeliveryResult | None = None,
) -> None:
    await record_audit_event(
        session,
        tenant_id=channel.tenant_id,
        actor_id=actor_id,
        request_id=request_id,
        action="channel.push",
        resource_type="channel",
        resource_id=channel.id,
        status="success" if delivered and not error else "failure",
        details={
            "channel_type": channel.channel_type.value,
            "channel_key": channel.channel_key,
            "channel_status": channel.status.value,
            "push_mode": request.mode.value,
            "conversation_key": _push_conversation_key(channel, request),
            "external_user_id_present": bool(request.external_user_id),
            "agent_invoked": agent_invoked,
            "agent_key": agent_key,
            "response_present": response_text is not None,
            "delivered": delivered,
            "outbound_delivery": outbound_delivery.model_dump(mode="json")
            if outbound_delivery
            else None,
            "error": error,
            "caller_metadata_keys": sorted(request.metadata.keys()) if request.metadata else [],
        },
    )


async def rotate_channel_secret_for_tenant(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    channel_id: UUID,
    request: ChannelSecretRotateRequest,
    actor_id: UUID | None,
    request_id: str | None = None,
) -> ChannelSecretRotateResponse:
    """Rotate a Channel's webhook signing secret with a dual-secret window.

    The current ``secret_ref`` is moved to ``previous_secret_ref`` (so in-flight
    requests signed with the old secret still validate during the transition),
    and ``new_secret`` becomes the primary. Call
    ``promote_channel_secret_for_tenant`` after the transition window to drop
    the previous secret.
    """

    channel = await _get_tenant_channel(session, tenant_id, channel_id)
    old_secret = channel.secret
    old_secret_ref: str | None = None
    now = datetime.now(timezone.utc)

    try:
        row = await session.get(ChannelConfig, channel_id)
        if row is not None and row.tenant_id == tenant_id:
            old_secret_ref = row.secret_ref
            row.previous_secret_ref = old_secret_ref
            row.secret_ref = encrypt_secret(request.new_secret) if request.new_secret else None
            row.secret_configured = bool(row.secret_ref)
            row.updated_at = now
            await session.flush()
    except (OSError, SQLAlchemyError):
        await session.rollback()

    updated = replace(
        channel,
        secret=request.new_secret,
        previous_secret=old_secret,
        secret_configured=bool(request.new_secret),
        updated_at=now,
    )
    _cache_channel(updated)

    await record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        request_id=request_id,
        action="channel.secret.rotate",
        resource_type="channel",
        resource_id=channel_id,
        status="success",
        details={
            "channel_type": channel.channel_type.value,
            "channel_key": channel.channel_key,
            "previous_secret_staged": old_secret is not None,
        },
    )
    await _commit_audit_best_effort(session)

    return ChannelSecretRotateResponse(
        channel_id=channel_id,
        rotated=True,
        previous_secret_staged=old_secret is not None,
        message="Secret rotated. The previous secret remains valid during the transition window; call /secret/promote to finalize.",
    )


async def promote_channel_secret_for_tenant(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    channel_id: UUID,
    actor_id: UUID | None,
    request_id: str | None = None,
) -> ChannelSecretPromoteResponse:
    """Finalize a secret rotation by dropping the staged previous secret.

    After this call, only the current (rotated) secret is accepted. Requests
    still signed with the old secret will be rejected.
    """

    channel = await _get_tenant_channel(session, tenant_id, channel_id)
    had_previous = channel.previous_secret is not None
    now = datetime.now(timezone.utc)

    try:
        row = await session.get(ChannelConfig, channel_id)
        if row is not None and row.tenant_id == tenant_id:
            row.previous_secret_ref = None
            row.updated_at = now
            await session.flush()
    except (OSError, SQLAlchemyError):
        await session.rollback()

    updated = replace(channel, previous_secret=None, updated_at=now)
    _cache_channel(updated)

    await record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        request_id=request_id,
        action="channel.secret.promote",
        resource_type="channel",
        resource_id=channel_id,
        status="success",
        details={
            "channel_type": channel.channel_type.value,
            "channel_key": channel.channel_key,
            "previous_secret_dropped": had_previous,
        },
    )
    await _commit_audit_best_effort(session)

    return ChannelSecretPromoteResponse(
        channel_id=channel_id,
        promoted=True,
        message="Previous secret dropped. Only the current secret is now accepted."
        if had_previous
        else "No previous secret was staged; nothing to promote.",
    )


_POLL_ROLES = ("assistant", "agent")


def _select_matching_sessions(
    sessions: list[ConversationSession],
    external_user_id: str,
    conversation_key: str | None,
) -> tuple[list[UUID], str | None]:
    """Pick sessions whose metadata matches the external user (and optional
    conversation_key). Returns (matching_ids, resolved_conversation_key)."""

    matching_ids: list[UUID] = []
    resolved_key = conversation_key
    for conv in sessions:
        meta = conv.metadata_json or {}
        if meta.get("external_user_id") != external_user_id:
            continue
        if conversation_key is not None and meta.get("conversation_key") != conversation_key:
            continue
        if resolved_key is None and meta.get("conversation_key"):
            resolved_key = meta["conversation_key"]
        matching_ids.append(conv.id)
    return matching_ids, resolved_key


def _build_session_key_map(sessions: list[ConversationSession]) -> dict[UUID, str]:
    return {conv.id: (conv.metadata_json or {}).get("conversation_key") or "" for conv in sessions}


def _paginate_messages(
    rows: list[ConversationMessage],
    *,
    matching_session_ids: list[UUID],
    after: UUID | None,
    limit: int,
    session_key_map: dict[UUID, str],
) -> tuple[list[ChannelPollMessage], bool, UUID | None]:
    """Apply conversation-id + cursor + limit filtering in Python.

    The DB query already enforces tenant + role + ordering; this helper
    narrows to the matching sessions and applies pagination so the logic is
    unit-testable without a live database.
    """

    matching_set = set(matching_session_ids)
    filtered = [r for r in rows if r.conversation_id in matching_set]
    if after is not None:
        filtered = [r for r in filtered if r.id > after]
    has_more = len(filtered) > limit
    page = filtered[:limit] if has_more else filtered
    messages = [
        ChannelPollMessage(
            message_id=r.id,
            conversation_id=r.conversation_id,
            conversation_key=session_key_map.get(r.conversation_id, ""),
            role=r.role,
            content=r.content,
            created_at=r.created_at,
            request_id=r.request_id,
            model_key=r.model_key,
        )
        for r in page
    ]
    next_cursor = messages[-1].message_id if messages and has_more else None
    return messages, has_more, next_cursor


async def poll_channel_messages_for_tenant(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    channel_id: UUID,
    external_user_id: str,
    conversation_key: str | None = None,
    after: UUID | None = None,
    limit: int = 50,
) -> ChannelPollResponse:
    """Poll outbound messages for a Web Widget / REST API Channel client.

    Returns assistant messages addressed to ``external_user_id`` on the given
    channel, optionally scoped to a specific ``conversation_key``. ``after`` is
    a message-id cursor: only messages newer than that id are returned.

    The channel's webhook signing secret must be presented by the caller
    (verified in the API layer) so this service assumes the caller is
    authorized.
    """

    limit = max(1, min(limit, 200))
    channel = await _get_tenant_channel(session, tenant_id, channel_id)

    try:
        result = await session.execute(
            select(ConversationSession)
            .where(
                ConversationSession.tenant_id == tenant_id,
                ConversationSession.channel_id == channel_id,
                cast(Any, ConversationSession.deleted_at).is_(None),
            )
            .order_by(cast(Any, ConversationSession.updated_at).desc())
            .limit(100)
        )
        sessions = list(result.scalars().all())
    except (OSError, SQLAlchemyError):
        await session.rollback()
        sessions = []

    matching_session_ids, resolved_conversation_key = _select_matching_sessions(
        sessions, external_user_id, conversation_key
    )
    session_key_map = _build_session_key_map(sessions)

    rows: list[ConversationMessage] = []
    if matching_session_ids:
        try:
            stmt = (
                select(ConversationMessage)
                .where(
                    ConversationMessage.tenant_id == tenant_id,
                    cast(Any, ConversationMessage.conversation_id).in_(matching_session_ids),
                    cast(Any, ConversationMessage.role).in_(_POLL_ROLES),
                )
                .order_by(
                    cast(Any, ConversationMessage.created_at).asc(),
                    cast(Any, ConversationMessage.id).asc(),
                )
                .limit(limit + 1)
            )
            if after is not None:
                stmt = stmt.where(ConversationMessage.id > after)
            msg_result = await session.execute(stmt)
            rows = list(msg_result.scalars().all())
        except (OSError, SQLAlchemyError):
            await session.rollback()
            rows = []

    messages, has_more, next_cursor = _paginate_messages(
        rows,
        matching_session_ids=matching_session_ids,
        after=after,
        limit=limit,
        session_key_map=session_key_map,
    )

    return ChannelPollResponse(
        channel_id=channel_id,
        channel_type=channel.channel_type,
        external_user_id=external_user_id,
        conversation_key=resolved_conversation_key or conversation_key or "",
        messages=messages,
        next_cursor=next_cursor,
        has_more=has_more,
    )


async def receive_channel_webhook(
    session: AsyncSession,
    *,
    channel_type: ChannelType,
    channel_key: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    request_id: str | None = None,
) -> WebhookAckResponse:
    adapter = get_channel_adapter(channel_type)
    channel = await _get_channel_by_key(session, channel_type, channel_key)
    signature = await adapter.verify_signature(
        payload=payload,
        headers=headers,
        secret=channel.secret if channel and not channel.secret_error else None,
    )
    # Secret rotation: if the current secret fails but a previous secret is
    # still staged (dual-secret window), retry with it so in-flight requests
    # signed with the old secret aren't rejected.
    if (
        channel is not None
        and not signature.valid
        and channel.previous_secret
        and not channel.secret_error
    ):
        previous_signature = await adapter.verify_signature(
            payload=payload,
            headers=headers,
            secret=channel.previous_secret,
        )
        if previous_signature.valid:
            previous_signature.details = {
                **previous_signature.details,
                "rotation_previous_secret_used": True,
            }
            signature = previous_signature
    normalized = await adapter.normalize_inbound(
        tenant_id=channel.tenant_id if channel else None,
        channel_id=channel.id if channel else None,
        channel_key=channel_key,
        payload=payload,
        headers=headers,
        signature=signature,
        request_id=request_id,
    )

    if channel is not None:
        await _record_webhook_audit(
            session,
            channel=channel,
            normalized=normalized,
            request_id=request_id,
            headers=headers,
            payload=payload,
        )
        await _commit_audit_best_effort(session)
        if channel.secret_error:
            processing = ChannelProcessingResult(
                routed=False,
                runtime_evidence=_channel_runtime_evidence(
                    channel=channel,
                    normalized=normalized,
                    routed=False,
                    error="channel_secret_unavailable",
                ),
                error="channel_secret_unavailable",
            )
        elif _channel_secret_configured(channel) and not signature.valid:
            processing = ChannelProcessingResult(
                routed=False,
                runtime_evidence=_channel_runtime_evidence(
                    channel=channel,
                    normalized=normalized,
                    routed=False,
                    error="invalid_signature",
                ),
                error="invalid_signature",
            )
        else:
            processing = await _process_inbound_message(
                session,
                channel=channel,
                normalized=normalized,
                request_id=request_id,
                dry_run=False,
            )
        await _record_webhook_processing_audit(
            session,
            channel=channel,
            normalized=normalized,
            processing=processing,
            request_id=request_id,
        )
        await _commit_audit_best_effort(session)
    else:
        processing = None

    accepted = (
        channel is not None
        and channel.status == ChannelStatus.ACTIVE
        and not channel.secret_error
        and not (_channel_secret_configured(channel) and not signature.valid)
    )
    return WebhookAckResponse(
        accepted=accepted,
        tenant_id=normalized.tenant_id,
        channel_id=normalized.channel_id,
        channel_type=channel_type,
        channel_key=channel_key,
        message_id=normalized.external_message_id,
        conversation_key=normalized.conversation_key,
        signature=signature,
        request_id=request_id,
        trace_id=normalized.trace_id,
        processing=processing,
        message=_webhook_ack_message(channel=channel, signature=signature),
    )


async def _get_tenant_channel(
    session: AsyncSession,
    tenant_id: UUID,
    channel_id: UUID,
) -> ChannelRecord:
    try:
        row = await session.get(ChannelConfig, channel_id)
        if row is not None and row.tenant_id == tenant_id:
            channel = _record_from_row(row)
            _cache_channel(channel)
            return channel
    except (OSError, SQLAlchemyError):
        await session.rollback()

    cached_channel = _channels_by_tenant.get(tenant_id, {}).get(channel_id)
    if cached_channel is not None:
        return cached_channel

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Channel not found.",
    )


async def _get_channel_by_key(
    session: AsyncSession,
    channel_type: ChannelType,
    channel_key: str,
) -> ChannelRecord | None:
    try:
        result = await session.execute(
            select(ChannelConfig).where(
                ChannelConfig.channel_type == channel_type.value,
                ChannelConfig.channel_key == channel_key,
            )
        )
        rows = result.scalars().all()
        if rows:
            channel = _record_from_row(rows[0])
            _cache_channel(channel)
            return channel
    except (OSError, SQLAlchemyError):
        await session.rollback()
    return _channel_index.get((channel_type, channel_key))


async def get_channel_by_key(
    session: AsyncSession,
    channel_type: ChannelType,
    channel_key: str,
) -> ChannelRecord | None:
    """Public wrapper for ``_get_channel_by_key`` (used by API layer)."""

    return await _get_channel_by_key(session, channel_type, channel_key)


def _record_from_row(row: ChannelConfig) -> ChannelRecord:
    secret, secret_error = _decrypt_channel_secret(row)
    previous_secret = _decrypt_previous_secret(row)
    return ChannelRecord(
        id=row.id,
        tenant_id=row.tenant_id,
        name=row.name,
        channel_type=ChannelType(row.channel_type),
        channel_key=row.channel_key,
        agent_id=row.agent_id,
        created_by=row.created_by,
        status=ChannelStatus.ERROR if secret_error else ChannelStatus(row.status),
        config=_channel_config_with_secret_health(dict(row.config), secret_error),
        secret=secret,
        created_at=row.created_at,
        updated_at=row.updated_at,
        secret_configured=bool(row.secret_configured or row.secret_ref),
        secret_error=secret_error,
        previous_secret=previous_secret,
    )


def _cache_channels(channels: list[ChannelRecord]) -> None:
    for channel in channels:
        _cache_channel(channel)


def _cache_channel(channel: ChannelRecord) -> None:
    _channels_by_tenant.setdefault(channel.tenant_id, {})[channel.id] = channel
    _channel_index[(channel.channel_type, channel.channel_key)] = channel


async def _commit_audit_best_effort(session: AsyncSession) -> None:
    try:
        await session.commit()
    except (OSError, SQLAlchemyError):
        await session.rollback()


async def _record_webhook_audit(
    session: AsyncSession,
    *,
    channel: ChannelRecord,
    normalized: InboundMessage,
    request_id: str | None,
    headers: dict[str, str],
    payload: dict[str, Any],
) -> None:
    await record_audit_event(
        session,
        tenant_id=channel.tenant_id,
        actor_type="channel",
        request_id=request_id,
        action="channel.webhook.received",
        resource_type="channel",
        resource_id=channel.id,
        details={
            "channel_type": channel.channel_type.value,
            "channel_key": channel.channel_key,
            "channel_status": channel.status.value,
            "message_type": normalized.message_type.value,
            "conversation_key": normalized.conversation_key,
            "external_message_id_present": normalized.external_message_id is not None,
            "external_user_id_present": normalized.external_user_id is not None,
            "text_present": normalized.text is not None,
            "attachments_count": len(normalized.attachments),
            "secret_configured": _channel_secret_configured(channel),
            "secret_error": channel.secret_error,
            "signature_checked": normalized.signature.checked,
            "signature_valid": normalized.signature.valid,
            "signature_method": normalized.signature.method,
            "signature_reason": normalized.signature.reason,
            "payload_keys": sorted(payload.keys()),
            "header_keys": sorted(_safe_header_keys(headers)),
        },
    )


async def _record_webhook_processing_audit(
    session: AsyncSession,
    *,
    channel: ChannelRecord,
    normalized: InboundMessage,
    processing: ChannelProcessingResult,
    request_id: str | None,
) -> None:
    await record_audit_event(
        session,
        tenant_id=channel.tenant_id,
        actor_type="channel",
        request_id=request_id or processing.request_id,
        action="channel.webhook.processed",
        status="success" if processing.routed else "failure",
        resource_type="channel",
        resource_id=channel.id,
        details={
            "channel_type": channel.channel_type.value,
            "channel_key": channel.channel_key,
            "channel_status": channel.status.value,
            "message_type": normalized.message_type.value,
            "conversation_key": normalized.conversation_key,
            "external_message_id_present": normalized.external_message_id is not None,
            "external_user_id_present": normalized.external_user_id is not None,
            "attachments_count": len(normalized.attachments),
            "signature_checked": normalized.signature.checked,
            "signature_valid": normalized.signature.valid,
            "signature_method": normalized.signature.method,
            "routed": processing.routed,
            "agent_key": processing.agent_key,
            "conversation_id": str(processing.conversation_id)
            if processing.conversation_id
            else None,
            "model_key": processing.model_key,
            "runtime_evidence": {
                key: processing.runtime_evidence.get(key)
                for key in (
                    "channel_execution",
                    "llm_gateway_called",
                    "provider_key",
                    "model_key",
                    "request_id",
                    "signature_checked",
                    "signature_valid",
                    "routed",
                )
                if processing.runtime_evidence.get(key) is not None
            },
            "media_generation_job": _media_generation_job_summary(processing.metadata),
            "response_present": processing.response_text is not None,
            "outbound_delivery": _outbound_delivery_summary(processing),
            "error": _safe_processing_error(processing.error),
        },
    )


async def _process_inbound_message(
    session: AsyncSession,
    *,
    channel: ChannelRecord,
    normalized: InboundMessage,
    request_id: str | None,
    dry_run: bool,
) -> ChannelProcessingResult:
    if channel.status != ChannelStatus.ACTIVE:
        return ChannelProcessingResult(
            routed=False,
            runtime_evidence=_channel_runtime_evidence(
                channel=channel,
                normalized=normalized,
                routed=False,
                error="channel_disabled",
            ),
            error="channel_disabled",
        )
    if normalized.message_type.value != "text" or not normalized.text:
        return ChannelProcessingResult(
            routed=False,
            runtime_evidence=_channel_runtime_evidence(
                channel=channel,
                normalized=normalized,
                routed=False,
                error="unsupported_or_empty_message",
            ),
            error="unsupported_or_empty_message",
        )

    agent_key = _agent_key_for_channel(channel)
    principal = Principal(
        tenant_id=channel.tenant_id,
        user_id=channel.created_by or UUID("00000000-0000-4000-8000-000000000001"),
        permissions={
            Permission.AGENTS_WRITE.value,
            Permission.KNOWLEDGE_READ.value,
            Permission.MODELS_READ.value,
            Permission.BUDGETS_READ.value,
        },
    )
    conversation = None
    try:
        if not dry_run:
            conversation = await _get_or_create_channel_conversation(
                session,
                channel=channel,
                normalized=normalized,
            )
            session.add(
                ConversationMessage(
                    tenant_id=channel.tenant_id,
                    conversation_id=conversation.id,
                    role="user",
                    content=normalized.text,
                    user_id=principal.user_id,
                    request_id=request_id,
                    metadata_json={
                        "source": "channel",
                        "channel_type": channel.channel_type.value,
                        "channel_key": channel.channel_key,
                        "external_user_id": normalized.external_user_id,
                        "external_message_id": normalized.external_message_id,
                        "conversation_key": normalized.conversation_key,
                    },
                )
            )
            await session.commit()

        response = await run_agent(
            session,
            agent_key,
            AgentRunRequest(
                input=normalized.text,
                context={
                    **_dict_config(channel.config.get("agent_context")),
                    **({"agent_id": str(channel.agent_id)} if channel.agent_id else {}),
                    "channel_id": str(channel.id),
                    "conversation_id": str(conversation.id) if conversation else None,
                    "conversation_key": normalized.conversation_key,
                    "external_user_id": normalized.external_user_id,
                    "source": f"channel.{channel.channel_type.value}",
                },
                max_tokens=int(channel.config.get("max_tokens") or 512),
                model_key=_string_or_none(channel.config.get("model_key")),
                routing_key=_string_or_none(channel.config.get("routing_key")),
            ),
            principal,
            request_id=request_id,
        )
        outbound_delivery = None
        if conversation is not None:
            session.add(
                ConversationMessage(
                    tenant_id=channel.tenant_id,
                    conversation_id=conversation.id,
                    role="assistant",
                    content=response.answer,
                    user_id=None,
                    request_id=response.request_id,
                    model_key=response.model_key,
                    provider_key=_string_or_none(response.metadata.get("provider_key")),
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    total_tokens=response.usage.total_tokens,
                    cost_usd=response.usage.cost_usd,
                    metadata_json={
                        **response.metadata,
                        "source": "channel",
                        "agent_key": agent_key,
                    },
                )
            )
            conversation.updated_at = utc_now()
            if not dry_run:
                outbound_delivery = await get_channel_adapter(channel.channel_type).send_outbound(
                    channel_config=channel.config,
                    message=_build_outbound_message(
                        channel=channel,
                        normalized=normalized,
                        response_text=response.answer,
                        request_id=response.request_id,
                    ),
                    request_id=response.request_id,
                )
            await record_audit_event(
                session,
                tenant_id=channel.tenant_id,
                actor_type="channel",
                action="channel.message.routed",
                resource_type="conversation",
                resource_id=conversation.id,
                request_id=request_id or response.request_id,
                details={
                    "channel_id": str(channel.id),
                    "channel_type": channel.channel_type.value,
                    "agent_key": agent_key,
                    "model_key": response.model_key,
                    "media_generation_job": _media_generation_job_summary(response.metadata),
                    "outbound_delivery": outbound_delivery.model_dump(mode="json")
                    if outbound_delivery
                    else None,
                    "total_tokens": response.usage.total_tokens,
                },
            )
            await session.commit()
        return ChannelProcessingResult(
            routed=True,
            agent_key=agent_key,
            conversation_id=conversation.id if conversation else None,
            response_text=response.answer,
            outbound_delivery=outbound_delivery,
            request_id=response.request_id,
            model_key=response.model_key,
            runtime_evidence=_channel_runtime_evidence(
                channel=channel,
                normalized=normalized,
                agent_key=agent_key,
                request_id=response.request_id,
                model_key=response.model_key,
                metadata=response.metadata,
                outbound_delivery=outbound_delivery.model_dump(mode="json")
                if outbound_delivery
                else None,
                routed=True,
            ),
            metadata=response.metadata,
        )
    except Exception as exc:
        await session.rollback()
        return ChannelProcessingResult(
            routed=False,
            agent_key=agent_key,
            runtime_evidence=_channel_runtime_evidence(
                channel=channel,
                normalized=normalized,
                agent_key=agent_key,
                request_id=request_id,
                routed=False,
                error=_safe_processing_error(str(exc)),
            ),
            error=_safe_processing_error(str(exc)),
        )


async def _get_or_create_channel_conversation(
    session: AsyncSession,
    *,
    channel: ChannelRecord,
    normalized: InboundMessage,
) -> ConversationSession:
    result = await session.execute(
        select(ConversationSession)
        .where(
            ConversationSession.tenant_id == channel.tenant_id,
            ConversationSession.channel_id == channel.id,
            ConversationSession.source == f"channel.{channel.channel_type.value}",
            cast(Any, ConversationSession.deleted_at).is_(None),
        )
        .order_by(cast(Any, ConversationSession.updated_at).desc())
        .limit(50)
    )
    for conversation in result.scalars().all():
        if conversation.metadata_json.get("conversation_key") == normalized.conversation_key:
            return conversation
    conversation = ConversationSession(
        tenant_id=channel.tenant_id,
        title=_conversation_title(normalized),
        agent_id=channel.agent_id,
        channel_id=channel.id,
        user_id=channel.created_by,
        source=f"channel.{channel.channel_type.value}",
        metadata_json={
            "conversation_key": normalized.conversation_key,
            "external_user_id": normalized.external_user_id,
            "channel_key": channel.channel_key,
        },
    )
    session.add(conversation)
    await session.flush()
    return conversation


def _agent_key_for_channel(channel: ChannelRecord) -> str:
    value = channel.config.get("agent_key") or channel.config.get("default_agent")
    if isinstance(value, str) and value and value != "unassigned":
        return value
    return "customer_service"


def _conversation_title(normalized: InboundMessage) -> str:
    prefix = normalized.external_user_id or normalized.conversation_key
    text = normalized.text or "Channel conversation"
    return f"{prefix}: {text[:80]}"[:160]


def _dict_config(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _string_or_none(value: object) -> str | None:
    return str(value) if value not in (None, "") else None


def _safe_processing_error(error: str | None) -> str | None:
    if error in {"invalid_signature", "channel_disabled", "unsupported_or_empty_message"}:
        return error
    if error:
        return "processing_exception"
    return None


def _media_generation_job_summary(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(metadata, dict):
        return None
    media_job = metadata.get("media_generation_job")
    if not isinstance(media_job, dict):
        return None
    dispatch = media_job.get("dispatch")
    dispatch_summary: dict[str, Any] = {}
    if isinstance(dispatch, dict):
        dispatch_summary = {
            key: dispatch.get(key)
            for key in ("mode", "queued", "reason", "task_id", "retry_action")
            if dispatch.get(key) is not None
        }
    return {
        key: media_job.get(key)
        for key in (
            "id",
            "kind",
            "status",
            "provider_key",
            "provider_type",
            "model_key",
            "routing_key",
        )
        if media_job.get(key) is not None
    } | ({"dispatch": dispatch_summary} if dispatch_summary else {})


def _build_outbound_message(
    *,
    channel: ChannelRecord,
    normalized: InboundMessage,
    response_text: str,
    request_id: str | None,
) -> OutboundMessage:
    return OutboundMessage(
        tenant_id=channel.tenant_id,
        channel_id=channel.id,
        channel_type=channel.channel_type,
        channel_key=channel.channel_key,
        external_user_id=normalized.external_user_id,
        external_message_id=None,
        conversation_key=normalized.conversation_key,
        message_type=ChannelMessageType.TEXT,
        text=response_text,
        raw_payload={
            "source": "agenthive.channel_gateway",
            "inbound_message_id": normalized.external_message_id,
        },
        trace_id=normalized.trace_id,
        request_id=request_id,
        received_at=datetime.now(timezone.utc),
    )


def _outbound_delivery_summary(processing: ChannelProcessingResult) -> dict[str, Any] | None:
    if processing.outbound_delivery is None:
        return None
    return processing.outbound_delivery.model_dump(mode="json")


def _channel_runtime_evidence(
    *,
    channel: ChannelRecord,
    normalized: InboundMessage,
    agent_key: str | None = None,
    request_id: str | None = None,
    model_key: str | None = None,
    metadata: dict[str, Any] | None = None,
    outbound_delivery: dict[str, Any] | None = None,
    routed: bool,
    error: str | None = None,
) -> dict[str, Any]:
    metadata = metadata if isinstance(metadata, dict) else {}
    existing = metadata.get("runtime_evidence")
    runtime = existing if isinstance(existing, dict) else {}
    provider_key = runtime.get("provider_key") or metadata.get("provider_key")
    media_job = _media_generation_job_summary(metadata)
    return {
        **runtime,
        "channel_execution": "channel_gateway",
        "channel_id": str(channel.id),
        "channel_type": channel.channel_type.value,
        "channel_key": channel.channel_key,
        "message_type": normalized.message_type.value,
        "conversation_key": normalized.conversation_key,
        "signature_checked": normalized.signature.checked,
        "signature_valid": normalized.signature.valid,
        "signature_method": normalized.signature.method,
        "rotation_previous_secret_used": bool(
            normalized.signature.details.get("rotation_previous_secret_used")
        ),
        "routed": routed,
        "agent_key": agent_key,
        "request_id": request_id or normalized.request_id,
        "model_key": model_key,
        "provider_key": provider_key,
        "llm_gateway_called": bool(runtime.get("llm_gateway_called", routed and media_job is None)),
        "media_generation_job": media_job,
        "outbound_delivery": outbound_delivery,
        "error": error,
    }


def _to_response(channel: ChannelRecord) -> ChannelResponse:
    return ChannelResponse(
        id=channel.id,
        tenant_id=channel.tenant_id,
        name=channel.name,
        channel_type=channel.channel_type,
        channel_key=channel.channel_key,
        agent_id=channel.agent_id,
        status=channel.status,
        webhook_path=f"/api/v1/channels/webhook/{channel.channel_type.value}/{channel.channel_key}",
        config=_sanitize_config(channel.config),
        secret_configured=_channel_secret_configured(channel),
        created_at=channel.created_at,
        updated_at=channel.updated_at,
    )


def _decrypt_channel_secret(row: ChannelConfig) -> tuple[str | None, str | None]:
    if not row.secret_ref:
        return None, None
    try:
        return decrypt_secret(row.secret_ref), None
    except (InvalidToken, ValueError):
        return None, "decrypt_failed"


def _decrypt_previous_secret(row: ChannelConfig) -> str | None:
    if not row.previous_secret_ref:
        return None
    try:
        return decrypt_secret(row.previous_secret_ref)
    except (InvalidToken, ValueError):
        return None


def _channel_config_with_secret_health(
    config: dict[str, Any], secret_error: str | None
) -> dict[str, Any]:
    if not secret_error:
        return config
    return {
        **config,
        "secret_health": {
            "status": "error",
            "reason": secret_error,
            "action": "save_new_secret",
        },
    }


def _channel_secret_configured(channel: ChannelRecord) -> bool:
    return (
        channel.secret_configured
        if channel.secret_configured is not None
        else channel.secret is not None
    )


def _sanitize_config(config: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in config.items():
        if key == "secret_health":
            sanitized[key] = value
        elif _is_sensitive_key(key):
            sanitized[key] = "***"
        else:
            sanitized[key] = value
    return sanitized


def _safe_header_keys(headers: dict[str, str]) -> set[str]:
    return {key for key in headers if not _is_sensitive_key(key)}


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return (
        "secret" in lowered
        or "token" in lowered
        or "authorization" in lowered
        or "signature" in lowered
        or lowered in {"api_key", "apikey", "app_key", "access_key"}
    )


def _webhook_ack_message(
    *,
    channel: ChannelRecord | None,
    signature: object,
) -> str:
    if channel is None:
        return "Webhook received for unknown channel."
    if channel.secret_error:
        return "Webhook signing secret is unavailable. Save a new channel secret."
    if _channel_secret_configured(channel) and getattr(signature, "valid", False) is False:
        return "Webhook signature verification failed."
    if channel.status != ChannelStatus.ACTIVE:
        return "Webhook received, but channel is not active."
    return "Webhook received."
