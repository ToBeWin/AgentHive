from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, cast
import csv
import io
import json
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, desc, func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.deps import Principal, is_tenant_admin
from app.core.config import is_development_environment
from app.models.agent_module import AgentInstance
from app.models.channel import ChannelConfig
from app.models.base import utc_now
from app.models.conversation import ConversationMessage, ConversationSession
from app.models.org import Department
from app.models.user import UserDepartment
from app.schemas.chat import (
    ChatMessageCreateRequest,
    ChatMessageCreateResponse,
    ChatMessageListResponse,
    ChatMessageResponse,
    ChatSessionCreateRequest,
    ChatSessionListResponse,
    ChatSessionResponse,
)
from app.schemas.agents import AgentRunRequest, AgentRunResponse
from app.schemas.llm import LLMChatRequest, LLMMessageRequest, LLMUsageResponse
from app.services.agent_concurrency import AgentConcurrencyDecision, agent_concurrency_limiter
from app.services.audit_service import record_audit_event
from app.services.agent_runtime_service import _get_agent_instance
from app.services.agent_runtime_service import run_agent
from app.services.agent_runtime_service import run_agent_stream
from app.services.llm_service import run_gateway_chat, run_gateway_chat_stream

SAFE_MESSAGE_AGENT_CONTEXT_KEYS = {
    "locale",
    "surface",
    "task_id",
    "task_title",
    "workflow_key",
}


_MEMORY_SESSIONS: dict[UUID, ChatSessionResponse] = {}
_MEMORY_MESSAGES: dict[UUID, list[ChatMessageResponse]] = {}


@dataclass(frozen=True)
class ChatGovernanceContext:
    agent_id: UUID | None
    channel_id: UUID | None
    department_id: UUID | None
    metadata: dict[str, object]


async def create_chat_session(
    session: AsyncSession,
    principal: Principal,
    payload: ChatSessionCreateRequest,
    *,
    request_id: str | None = None,
) -> ChatSessionResponse:
    title = payload.title or "New AgentHive conversation"
    try:
        governance = await _resolve_chat_governance_context(session, principal, payload)
        row = ConversationSession(
            tenant_id=principal.tenant_id,
            title=title,
            agent_id=governance.agent_id,
            channel_id=governance.channel_id,
            user_id=principal.user_id,
            department_id=governance.department_id,
            source=payload.source,
            metadata_json=governance.metadata,
        )
        session.add(row)
        await session.flush()
        await record_audit_event(
            session,
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action="chat.session.create",
            resource_type="conversation",
            resource_id=row.id,
            request_id=request_id,
            details={
                "source": payload.source,
                "agent_id": str(governance.agent_id) if governance.agent_id else None,
                "channel_id": str(governance.channel_id) if governance.channel_id else None,
                "department_id": str(governance.department_id)
                if governance.department_id
                else None,
            },
        )
        await session.commit()
        return _session_response(row)
    except (OSError, SQLAlchemyError):
        await session.rollback()
        if not is_development_environment():
            raise
        return _memory_session(principal, payload, title)


async def list_chat_sessions(
    session: AsyncSession,
    principal: Principal,
    *,
    limit: int = 50,
    offset: int = 0,
) -> ChatSessionListResponse:
    try:
        access_filters = await _chat_session_access_filters(session, principal)
        if access_filters is None:
            return ChatSessionListResponse(sessions=[], total=0, limit=limit, offset=offset)
        base_filters: list[Any] = [
            ConversationSession.tenant_id == principal.tenant_id,
            cast(Any, ConversationSession.deleted_at).is_(None),
        ]
        if access_filters:
            base_filters.append(or_(*cast(list[Any], access_filters)))
        total_result = await session.execute(
            select(func.count()).select_from(ConversationSession).where(*base_filters)
        )
        result = await session.execute(
            select(ConversationSession)
            .where(*base_filters)
            .order_by(desc(cast(Any, ConversationSession.updated_at)))
            .limit(limit)
            .offset(offset)
        )
        return ChatSessionListResponse(
            sessions=[_session_response(row) for row in result.scalars().all()],
            total=int(total_result.scalar_one() or 0),
            limit=limit,
            offset=offset,
        )
    except (OSError, SQLAlchemyError):
        memory = [
            item
            for item in _MEMORY_SESSIONS.values()
            if item.tenant_id == principal.tenant_id and item.status == "active"
        ]
        memory.sort(key=lambda item: item.updated_at, reverse=True)
        return ChatSessionListResponse(
            sessions=memory[offset : offset + limit],
            total=len(memory),
            limit=limit,
            offset=offset,
        )


async def list_chat_messages(
    session: AsyncSession,
    principal: Principal,
    conversation_id: UUID,
) -> ChatMessageListResponse:
    await _get_accessible_conversation_session(session, principal, conversation_id)
    return await _list_chat_messages_for_conversation(session, principal, conversation_id)


async def _list_chat_messages_for_conversation(
    session: AsyncSession,
    principal: Principal,
    conversation_id: UUID,
) -> ChatMessageListResponse:
    try:
        result = await session.execute(
            select(ConversationMessage)
            .where(
                ConversationMessage.tenant_id == principal.tenant_id,
                ConversationMessage.conversation_id == conversation_id,
            )
            .order_by(cast(Any, ConversationMessage.created_at))
        )
        return ChatMessageListResponse(
            messages=[_message_response(row) for row in result.scalars().all()]
        )
    except (OSError, SQLAlchemyError):
        return ChatMessageListResponse(messages=list(_MEMORY_MESSAGES.get(conversation_id, [])))


async def send_chat_message(
    session: AsyncSession,
    principal: Principal,
    conversation_id: UUID,
    payload: ChatMessageCreateRequest,
    *,
    request_id: str | None = None,
) -> ChatMessageCreateResponse:
    conversation = await _get_accessible_conversation_session(session, principal, conversation_id)
    history = await _list_chat_messages_for_conversation(session, principal, conversation_id)
    messages = [
        LLMMessageRequest(role=item.role, content=item.content)
        for item in history.messages
        if item.role in {"system", "user", "assistant"}
    ]
    messages.append(LLMMessageRequest(role="user", content=payload.content))

    llm_response = await _run_chat_completion(
        session,
        principal,
        conversation_id,
        payload,
        messages,
        conversation=conversation,
        request_id=request_id,
    )
    try:
        user_row = ConversationMessage(
            tenant_id=principal.tenant_id,
            conversation_id=conversation_id,
            role="user",
            content=payload.content,
            user_id=principal.user_id,
            request_id=llm_response.request_id,
            metadata_json=payload.metadata,
        )
        assistant_row = ConversationMessage(
            tenant_id=principal.tenant_id,
            conversation_id=conversation_id,
            role="assistant",
            content=llm_response.content,
            user_id=None,
            request_id=llm_response.request_id,
            model_key=llm_response.model_key,
            provider_key=llm_response.provider_key,
            input_tokens=llm_response.usage.input_tokens,
            output_tokens=llm_response.usage.output_tokens,
            total_tokens=llm_response.usage.total_tokens,
            cost_usd=llm_response.usage.cost_usd,
            metadata_json=llm_response.metadata,
        )
        session.add(user_row)
        session.add(assistant_row)
        conversation.title = _title_from_first_message(conversation.title, payload.content)
        now = utc_now()
        conversation.updated_at = now
        conversation.metadata_json = _conversation_metadata_with_last_task(
            conversation.metadata_json,
            payload=payload,
            llm_response=llm_response,
            completed_at=now,
        )
        await record_audit_event(
            session,
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action="chat.message.send",
            resource_type="conversation",
            resource_id=conversation_id,
            request_id=request_id or llm_response.request_id,
            details=_chat_message_audit_details(llm_response),
        )
        await session.commit()
        return ChatMessageCreateResponse(
            user_message=_message_response(user_row),
            assistant_message=_message_response(assistant_row),
            request_id=llm_response.request_id,
            provider_key=llm_response.provider_key,
            model_key=llm_response.model_key,
            usage=llm_response.usage,
            sources=_sources_from_llm_metadata(llm_response.metadata),
            metadata=llm_response.metadata,
        )
    except (OSError, SQLAlchemyError):
        await session.rollback()
        if not is_development_environment():
            raise
        return _memory_message_pair(principal, conversation_id, payload, llm_response)


async def stream_chat_message(
    session: AsyncSession,
    principal: Principal,
    conversation_id: UUID,
    payload: ChatMessageCreateRequest,
    *,
    request_id: str | None = None,
) -> AsyncIterator[str]:
    """Stream a chat message turn as SSE events with incremental content deltas.

    Event order:
      1. status (accepted)
      2. status (runtime started)
      3. delta* (incremental content as the LLM emits tokens)
      4. status (knowledge) — when knowledge diagnostics are available
      5. status (persisted)
      6. metadata (full response metadata minus assistant_message body)
      7. done (final message_id)

    Falls back to memory storage in development when the database is
    unavailable, mirroring :func:`send_chat_message`.
    """
    yield _sse("status", {"stage": "accepted", "state": "completed"})
    yield _sse("status", {"stage": "runtime", "state": "started"})

    try:
        conversation = await _get_accessible_conversation_session(
            session, principal, conversation_id
        )
    except HTTPException as exc:
        yield _sse(
            "status",
            {"stage": "runtime", "state": "failed", "request_id": request_id},
        )
        yield _sse(
            "error",
            {"status": exc.status_code, "detail": exc.detail, "request_id": request_id},
        )
        return

    history = await _list_chat_messages_for_conversation(session, principal, conversation_id)
    history_messages = [
        LLMMessageRequest(role=item.role, content=item.content)
        for item in history.messages
        if item.role in {"system", "user", "assistant"}
    ]
    history_messages.append(LLMMessageRequest(role="user", content=payload.content))

    collected_chunks: list[str] = []
    final_agent_response = None
    llm_response = None

    try:
        async with agent_concurrency_limiter.acquire(
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            agent_id=conversation.agent_id if conversation else None,
            request_id=request_id,
        ) as concurrency_decision:
            if conversation and conversation.agent_id:
                agent_key = _agent_key_from_conversation(conversation)
                async for event in run_agent_stream(
                    session,
                    agent_key,
                    AgentRunRequest(
                        input=payload.content,
                        context=_agent_run_context(conversation, conversation_id, payload),
                        model_key=payload.model_key,
                        routing_key=payload.routing_key,
                        max_tokens=payload.max_tokens,
                    ),
                    principal,
                    request_id=request_id,
                ):
                    if event.get("type") == "delta":
                        chunk = str(event.get("content") or "")
                        if chunk:
                            collected_chunks.append(chunk)
                            yield _sse("delta", {"content": chunk})
                    elif event.get("type") == "done":
                        final_agent_response = event.get("response")
                if final_agent_response is None:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Agent streaming completed without a final response.",
                    )
                llm_response = _with_agent_concurrency_evidence(
                    _agent_response_as_llm_response(cast(AgentRunResponse, final_agent_response)),
                    concurrency_decision,
                )
            else:
                gateway_request = LLMChatRequest(
                    model_key=payload.model_key,
                    routing_key=payload.routing_key,
                    messages=history_messages,
                    temperature=payload.temperature,
                    max_tokens=payload.max_tokens,
                    metadata={**payload.metadata, "conversation_id": str(conversation_id)},
                )
                async for delta in run_gateway_chat_stream(
                    gateway_request,
                    principal,
                    session=session,
                    conversation_id=conversation_id,
                    department_id=conversation.department_id if conversation else None,
                    agent_id=conversation.agent_id if conversation else None,
                    channel_id=conversation.channel_id if conversation else None,
                    source="chat_console",
                ):
                    if delta:
                        collected_chunks.append(delta)
                        yield _sse("delta", {"content": delta})
                # Streaming gateway responses carry no token totals; build a
                # minimal llm_response so persistence + audit stay consistent.
                llm_response = _with_agent_concurrency_evidence(
                    SimpleNamespace(
                        content="".join(collected_chunks),
                        deployment_id=None,
                        finish_reason="stop",
                        metadata={
                            "streamed": True,
                            "chat_execution": "llm_gateway",
                            "runtime_evidence": {
                                "execution": "llm_gateway",
                                "chat_execution": "llm_gateway",
                                "llm_gateway_called": True,
                                "streamed": True,
                            },
                        },
                        model_key=payload.model_key or payload.routing_key or "streamed-chat",
                        provider_key="llm_gateway",
                        request_id=request_id or str(uuid4()),
                        usage=LLMUsageResponse(
                            input_tokens=0,
                            output_tokens=0,
                            total_tokens=0,
                            cost_usd=Decimal("0"),
                        ),
                    ),
                    concurrency_decision,
                )
    except HTTPException as exc:
        yield _sse(
            "status",
            {"stage": "runtime", "state": "failed", "request_id": request_id},
        )
        yield _sse(
            "error",
            {"status": exc.status_code, "detail": exc.detail, "request_id": request_id},
        )
        return

    # Persist the user + assistant messages now that the stream has completed.
    try:
        user_row = ConversationMessage(
            tenant_id=principal.tenant_id,
            conversation_id=conversation_id,
            role="user",
            content=payload.content,
            user_id=principal.user_id,
            request_id=llm_response.request_id,
            metadata_json=payload.metadata,
        )
        assistant_row = ConversationMessage(
            tenant_id=principal.tenant_id,
            conversation_id=conversation_id,
            role="assistant",
            content=llm_response.content,
            user_id=None,
            request_id=llm_response.request_id,
            model_key=llm_response.model_key,
            provider_key=llm_response.provider_key,
            input_tokens=llm_response.usage.input_tokens,
            output_tokens=llm_response.usage.output_tokens,
            total_tokens=llm_response.usage.total_tokens,
            cost_usd=llm_response.usage.cost_usd,
            metadata_json=llm_response.metadata,
        )
        session.add(user_row)
        session.add(assistant_row)
        conversation.title = _title_from_first_message(conversation.title, payload.content)
        now = utc_now()
        conversation.updated_at = now
        conversation.metadata_json = _conversation_metadata_with_last_task(
            conversation.metadata_json,
            payload=payload,
            llm_response=llm_response,
            completed_at=now,
        )
        await record_audit_event(
            session,
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action="chat.message.send",
            resource_type="conversation",
            resource_id=conversation_id,
            request_id=request_id or llm_response.request_id,
            details=_chat_message_audit_details(llm_response),
        )
        await session.commit()
        result = ChatMessageCreateResponse(
            user_message=_message_response(user_row),
            assistant_message=_message_response(assistant_row),
            request_id=llm_response.request_id,
            provider_key=llm_response.provider_key,
            model_key=llm_response.model_key,
            usage=llm_response.usage,
            sources=_sources_from_llm_metadata(llm_response.metadata),
            metadata=llm_response.metadata,
        )
    except (OSError, SQLAlchemyError):
        await session.rollback()
        if not is_development_environment():
            yield _sse(
                "status",
                {"stage": "runtime", "state": "failed", "request_id": request_id},
            )
            yield _sse(
                "error",
                {
                    "status": status.HTTP_503_SERVICE_UNAVAILABLE,
                    "detail": "Chat message persistence failed.",
                    "request_id": request_id,
                },
            )
            return
        result = _memory_message_pair(principal, conversation_id, payload, llm_response)

    knowledge = result.metadata.get("knowledge")
    if isinstance(knowledge, dict):
        yield _sse(
            "status",
            {
                "stage": "knowledge",
                "state": "completed",
                "enabled": bool(knowledge.get("enabled")),
                "source_count": knowledge.get("source_count", 0),
                "confidence_level": knowledge.get("confidence_level"),
            },
        )
    yield _sse(
        "status",
        {
            "stage": "persisted",
            "state": "completed",
            "message_id": str(result.assistant_message.id),
            "request_id": result.request_id,
        },
    )
    yield _sse("metadata", result.model_dump(mode="json", exclude={"assistant_message"}))
    yield _sse("done", {"message_id": str(result.assistant_message.id)})


async def _run_chat_completion(
    session: AsyncSession,
    principal: Principal,
    conversation_id: UUID,
    payload: ChatMessageCreateRequest,
    messages: list[LLMMessageRequest],
    *,
    conversation: ConversationSession | None,
    request_id: str | None,
) -> Any:
    async with agent_concurrency_limiter.acquire(
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        agent_id=conversation.agent_id if conversation else None,
        request_id=request_id,
    ) as concurrency_decision:
        if conversation and conversation.agent_id:
            agent_key = _agent_key_from_conversation(conversation)
            agent_response = await run_agent(
                session,
                agent_key,
                AgentRunRequest(
                    input=payload.content,
                    context=_agent_run_context(conversation, conversation_id, payload),
                    model_key=payload.model_key,
                    routing_key=payload.routing_key,
                    max_tokens=payload.max_tokens,
                ),
                principal,
                request_id=request_id,
            )
            return _with_agent_concurrency_evidence(
                _agent_response_as_llm_response(agent_response),
                concurrency_decision,
            )

        return _with_agent_concurrency_evidence(
            await run_gateway_chat(
                LLMChatRequest(
                    model_key=payload.model_key,
                    routing_key=payload.routing_key,
                    messages=messages,
                    temperature=payload.temperature,
                    max_tokens=payload.max_tokens,
                    metadata={**payload.metadata, "conversation_id": str(conversation_id)},
                ),
                principal,
                session=session,
                conversation_id=conversation_id,
                department_id=conversation.department_id if conversation else None,
                agent_id=conversation.agent_id if conversation else None,
                channel_id=conversation.channel_id if conversation else None,
                source="chat_console",
            ),
            concurrency_decision,
        )


async def _resolve_chat_governance_context(
    session: AsyncSession,
    principal: Principal,
    payload: ChatSessionCreateRequest,
) -> ChatGovernanceContext:
    metadata: dict[str, object] = dict(payload.metadata)
    agent_id = payload.agent_id
    department_id = payload.department_id

    channel = await _get_channel_config(session, principal, payload.channel_id)
    if channel is not None:
        if channel.agent_id is not None:
            if agent_id is not None and agent_id != channel.agent_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Chat session agent_id does not match the selected channel.",
                )
            agent_id = channel.agent_id
        _merge_channel_metadata(metadata, channel)

    agent = (
        await _get_agent_instance(session, principal, agent_id, require_write=False)
        if agent_id
        else None
    )
    if agent is not None:
        metadata.setdefault("agent_key", agent.agent_key)
        _merge_agent_instance_metadata(metadata, agent)
        department_id = _resolve_agent_department(agent, department_id)

    if department_id is not None:
        await _assert_department_access(session, principal, department_id)

    return ChatGovernanceContext(
        agent_id=agent_id,
        channel_id=payload.channel_id,
        department_id=department_id,
        metadata=metadata,
    )


async def _get_accessible_conversation_session(
    session: AsyncSession,
    principal: Principal,
    conversation_id: UUID,
) -> ConversationSession:
    result = await session.execute(
        select(ConversationSession).where(
            ConversationSession.tenant_id == principal.tenant_id,
            ConversationSession.id == conversation_id,
            cast(Any, ConversationSession.deleted_at).is_(None),
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found.",
        )
    department_ids = await _principal_department_ids(session, principal)
    if not _can_access_chat_session(conversation, principal, department_ids):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chat session access denied.",
        )
    return conversation


async def _chat_session_access_filters(
    session: AsyncSession,
    principal: Principal,
) -> list[object] | None:
    if is_tenant_admin(principal):
        return []
    filters: list[Any] = [ConversationSession.user_id == principal.user_id]
    department_ids = await _principal_department_ids(session, principal)
    if department_ids:
        filters.append(cast(Any, ConversationSession.department_id).in_(department_ids))
    return filters or None


async def _principal_department_ids(session: AsyncSession, principal: Principal) -> set[UUID]:
    if is_tenant_admin(principal):
        return set()
    result = await session.execute(
        select(UserDepartment.department_id)
        .join(Department, cast(ColumnElement[bool], Department.id == UserDepartment.department_id))
        .where(
            UserDepartment.user_id == principal.user_id,
            Department.tenant_id == principal.tenant_id,
        )
    )
    return set(result.scalars().all())


def _can_access_chat_session(
    conversation: ConversationSession,
    principal: Principal,
    department_ids: set[UUID],
) -> bool:
    if conversation.tenant_id != principal.tenant_id:
        return False
    if conversation.deleted_at is not None:
        return False
    if is_tenant_admin(principal):
        return True
    if conversation.user_id == principal.user_id:
        return True
    return conversation.department_id is not None and conversation.department_id in department_ids


async def _get_channel_config(
    session: AsyncSession,
    principal: Principal,
    channel_id: UUID | None,
) -> ChannelConfig | None:
    if channel_id is None:
        return None
    result = await session.execute(
        select(ChannelConfig).where(
            ChannelConfig.tenant_id == principal.tenant_id,
            ChannelConfig.id == channel_id,
        )
    )
    channel = result.scalar_one_or_none()
    if channel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found.",
        )
    return channel


def _merge_channel_metadata(metadata: dict[str, object], channel: ChannelConfig) -> None:
    if channel.config.get("agent_key") and not metadata.get("agent_key"):
        metadata["agent_key"] = str(channel.config["agent_key"])
    channel_agent_context = _dict_metadata_value(channel.config.get("agent_context"))
    if not channel_agent_context:
        return
    current_agent_context = _dict_metadata_value(metadata.get("agent_context"))
    metadata["agent_context"] = {**channel_agent_context, **current_agent_context}


def _merge_agent_instance_metadata(metadata: dict[str, object], agent: AgentInstance) -> None:
    current_agent_context = _safe_message_agent_context(metadata.get("agent_context"))
    instance_context = {
        **agent.config,
        "agent_id": str(agent.id),
        "module_key": agent.module_key,
        "agent_instance_slug": agent.slug,
        "agent_instance_name": agent.name,
        "visibility": agent.visibility,
    }
    if agent.department_id is not None:
        instance_context["department_id"] = str(agent.department_id)
    metadata["agent_context"] = {**instance_context, **current_agent_context}


def _resolve_agent_department(
    agent: AgentInstance,
    requested_department_id: UUID | None,
) -> UUID | None:
    if agent.department_id is None:
        return requested_department_id
    if requested_department_id is not None and requested_department_id != agent.department_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chat session department_id does not match the selected Agent instance.",
        )
    return agent.department_id


async def _assert_department_access(
    session: AsyncSession,
    principal: Principal,
    department_id: UUID,
) -> None:
    result = await session.execute(
        select(Department.id).where(
            Department.tenant_id == principal.tenant_id,
            Department.id == department_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found.",
        )
    if is_tenant_admin(principal):
        return
    membership = await session.execute(
        select(UserDepartment.department_id)
        .join(Department, cast(ColumnElement[bool], Department.id == UserDepartment.department_id))
        .where(
            UserDepartment.user_id == principal.user_id,
            UserDepartment.department_id == department_id,
            Department.tenant_id == principal.tenant_id,
        )
    )
    if membership.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Department access denied.",
        )


def _agent_run_context(
    conversation: ConversationSession,
    conversation_id: UUID,
    payload: ChatMessageCreateRequest,
) -> dict[str, object]:
    context = {
        **_dict_metadata_value(conversation.metadata_json.get("agent_context")),
        **_safe_message_agent_context(payload.metadata.get("agent_context")),
        "agent_id": str(conversation.agent_id),
        "conversation_id": str(conversation_id),
        "source": conversation.source,
    }
    if conversation.department_id is not None:
        context["department_id"] = str(conversation.department_id)
    if conversation.channel_id is not None:
        context["channel_id"] = str(conversation.channel_id)
    return context


def _agent_key_from_conversation(conversation: ConversationSession) -> str:
    value = conversation.metadata_json.get("agent_key")
    return str(value) if value not in (None, "") else "customer_service"


def _dict_metadata_value(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _safe_message_agent_context(value: object) -> dict[str, object]:
    raw = _dict_metadata_value(value)
    return {key: raw[key] for key in SAFE_MESSAGE_AGENT_CONTEXT_KEYS if key in raw}


def _agent_response_as_llm_response(agent_response: AgentRunResponse) -> SimpleNamespace:
    provider_key = str(
        _provider_key_from_agent_metadata(agent_response.metadata) or "agent_runtime"
    )
    return SimpleNamespace(
        content=agent_response.answer,
        deployment_id=None,
        finish_reason="stop",
        metadata={
            **agent_response.metadata,
            "agent_sources": agent_response.sources,
            "chat_execution": "agent_runtime",
            "runtime_evidence": _chat_runtime_evidence_from_agent_response(
                agent_response, provider_key
            ),
        },
        model_key=agent_response.model_key,
        provider_key=provider_key,
        request_id=agent_response.request_id,
        usage=agent_response.usage,
    )


def _with_agent_concurrency_evidence(llm_response: Any, decision: AgentConcurrencyDecision) -> Any:
    evidence = _agent_concurrency_evidence(decision)
    metadata = dict(getattr(llm_response, "metadata", {}) or {})
    runtime_evidence = metadata.get("runtime_evidence")
    if not isinstance(runtime_evidence, dict):
        runtime_evidence = {}
    runtime_evidence = {
        **runtime_evidence,
        "agent_concurrency": evidence,
    }
    metadata["runtime_evidence"] = runtime_evidence
    metadata["agent_concurrency"] = evidence
    metadata["runtime_summary"] = _chat_runtime_summary(llm_response, metadata, runtime_evidence)
    llm_response.metadata = metadata
    return llm_response


def _agent_concurrency_evidence(decision: AgentConcurrencyDecision) -> dict[str, object]:
    return {
        "enabled": decision.enabled,
        "acquired": decision.acquired,
        "limits": {
            "tenant": decision.tenant_limit,
            "user": decision.user_limit,
            "agent": decision.agent_limit,
        },
        "active": dict(decision.active),
    }


def _chat_runtime_summary(
    llm_response: Any,
    metadata: dict[str, object],
    runtime_evidence: dict[str, object],
) -> dict[str, object]:
    knowledge = _dict_metadata_value(metadata.get("knowledge"))
    route_attempts = _runtime_route_attempts(runtime_evidence.get("route_attempts"))
    gateway_called = runtime_evidence.get("llm_gateway_called") is True
    mock_adapter = runtime_evidence.get("mock_adapter") is True
    execution = str(
        runtime_evidence.get("chat_execution")
        or runtime_evidence.get("execution")
        or metadata.get("chat_execution")
        or "-"
    )
    adapter_mode = _runtime_adapter_mode(
        execution=execution,
        gateway_called=gateway_called,
        mock_adapter=mock_adapter,
    )
    return {
        "status": _runtime_summary_status(adapter_mode),
        "adapter_mode": adapter_mode,
        "execution": execution,
        "gateway_called": gateway_called,
        "mock_adapter": mock_adapter,
        "provider_key": getattr(llm_response, "provider_key", None),
        "model_key": getattr(llm_response, "model_key", None),
        "request_id": getattr(llm_response, "request_id", None),
        "total_tokens": getattr(getattr(llm_response, "usage", None), "total_tokens", 0),
        "route_attempt_count": len(route_attempts),
        "fallback_attempt_count": runtime_evidence.get("fallback_attempt_count", 0),
        "selected_route_reason": runtime_evidence.get("selected_route_reason"),
        "knowledge_source_count": knowledge.get(
            "source_count", len(_sources_from_llm_metadata(metadata))
        ),
        "knowledge_confidence": knowledge.get("confidence_level"),
        "requires_human_review": knowledge.get("requires_human_review") is True,
    }


def _runtime_adapter_mode(*, execution: str, gateway_called: bool, mock_adapter: bool) -> str:
    if execution == "media_gateway":
        return "media_gateway"
    if gateway_called:
        return "mock_gateway" if mock_adapter else "live_gateway"
    return "local_runtime"


def _runtime_summary_status(adapter_mode: str) -> str:
    if adapter_mode == "live_gateway":
        return "real_model_call"
    if adapter_mode == "mock_gateway":
        return "mock_model_call"
    if adapter_mode == "media_gateway":
        return "media_generation_task"
    return "local_runtime"


def _runtime_route_attempts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _agent_concurrency_from_metadata(metadata: dict[str, object]) -> dict[str, object] | None:
    value = metadata.get("agent_concurrency")
    return value if isinstance(value, dict) else None


def _chat_message_audit_details(llm_response: Any) -> dict[str, object]:
    runtime_evidence = _dict_metadata_value(llm_response.metadata.get("runtime_evidence"))
    return {
        "model_key": llm_response.model_key,
        "provider_key": llm_response.provider_key,
        "total_tokens": llm_response.usage.total_tokens,
        "agent_concurrency": _agent_concurrency_from_metadata(llm_response.metadata),
        "runtime": _chat_runtime_audit_summary(runtime_evidence),
    }


def _chat_runtime_audit_summary(runtime_evidence: dict[str, object]) -> dict[str, object]:
    route_attempts = _audit_route_attempts(runtime_evidence.get("route_attempts"))
    selected_attempt = next(
        (attempt for attempt in route_attempts if attempt.get("status") == "success"), None
    )
    return {
        "execution": runtime_evidence.get("chat_execution") or runtime_evidence.get("execution"),
        "llm_gateway_called": runtime_evidence.get("llm_gateway_called"),
        "selected_route_reason": runtime_evidence.get("selected_route_reason"),
        "fallback_attempt_count": runtime_evidence.get("fallback_attempt_count"),
        "deployment_id": selected_attempt.get("deployment_id") if selected_attempt else None,
        "routing_key": selected_attempt.get("routing_key") if selected_attempt else None,
        "route_attempts": route_attempts,
    }


def _audit_route_attempts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    attempts: list[dict[str, object]] = []
    for item in value[:5]:
        if not isinstance(item, dict):
            continue
        attempts.append(
            {
                "attempt": item.get("attempt"),
                "deployment_id": item.get("deployment_id"),
                "model_key": item.get("model_key"),
                "provider_key": item.get("provider_key"),
                "routing_key": item.get("routing_key"),
                "status": item.get("status"),
                "error_code": item.get("error_code"),
            }
        )
    return attempts


def _provider_key_from_agent_metadata(metadata: dict[str, object]) -> object:
    provider_key = metadata.get("provider_key")
    if provider_key:
        return provider_key
    media_job = metadata.get("media_generation_job")
    if isinstance(media_job, dict):
        return media_job.get("provider_key")
    return None


def _chat_runtime_evidence_from_agent_response(
    agent_response: AgentRunResponse,
    provider_key: str,
) -> dict[str, object]:
    existing = agent_response.metadata.get("runtime_evidence")
    if isinstance(existing, dict):
        return {
            **existing,
            "chat_execution": "agent_runtime",
        }
    return {
        "execution": "agent_runtime",
        "chat_execution": "agent_runtime",
        "llm_gateway_called": provider_key != "agent_runtime",
        "provider_key": provider_key,
        "model_key": agent_response.model_key,
        "request_id": agent_response.request_id,
        "input_tokens": agent_response.usage.input_tokens,
        "output_tokens": agent_response.usage.output_tokens,
        "total_tokens": agent_response.usage.total_tokens,
        "cost_usd": str(agent_response.usage.cost_usd),
        "source_count": len(agent_response.sources),
    }


def _session_response(row: ConversationSession) -> ChatSessionResponse:
    return ChatSessionResponse(
        id=row.id,
        tenant_id=row.tenant_id,
        title=row.title,
        agent_id=row.agent_id,
        channel_id=row.channel_id,
        user_id=row.user_id,
        department_id=row.department_id,
        source=row.source,
        status=row.status,
        metadata=row.metadata_json,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _message_response(row: ConversationMessage) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=row.id,
        tenant_id=row.tenant_id,
        conversation_id=row.conversation_id,
        role=row.role,
        content=row.content,
        user_id=row.user_id,
        request_id=row.request_id,
        model_key=row.model_key,
        provider_key=row.provider_key,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        total_tokens=row.total_tokens,
        cost_usd=row.cost_usd,
        metadata=row.metadata_json,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _memory_session(
    principal: Principal,
    payload: ChatSessionCreateRequest,
    title: str,
) -> ChatSessionResponse:
    now = utc_now()
    response = ChatSessionResponse(
        id=uuid4(),
        tenant_id=principal.tenant_id,
        title=title,
        agent_id=payload.agent_id,
        channel_id=payload.channel_id,
        user_id=principal.user_id,
        department_id=payload.department_id,
        source=payload.source,
        status="active",
        metadata={"storage": "memory", **payload.metadata},
        created_at=now,
        updated_at=now,
    )
    _MEMORY_SESSIONS[response.id] = response
    _MEMORY_MESSAGES.setdefault(response.id, [])
    return response


def _memory_message_pair(
    principal: Principal,
    conversation_id: UUID,
    payload: ChatMessageCreateRequest,
    llm_response: Any,
) -> ChatMessageCreateResponse:
    now = utc_now()
    user_message = ChatMessageResponse(
        id=uuid4(),
        tenant_id=principal.tenant_id,
        conversation_id=conversation_id,
        role="user",
        content=payload.content,
        user_id=principal.user_id,
        request_id=llm_response.request_id,
        model_key=None,
        provider_key=None,
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        cost_usd=Decimal("0"),
        metadata=payload.metadata,
        created_at=now,
        updated_at=now,
    )
    assistant_message = ChatMessageResponse(
        id=uuid4(),
        tenant_id=principal.tenant_id,
        conversation_id=conversation_id,
        role="assistant",
        content=llm_response.content,
        user_id=None,
        request_id=llm_response.request_id,
        model_key=llm_response.model_key,
        provider_key=llm_response.provider_key,
        input_tokens=llm_response.usage.input_tokens,
        output_tokens=llm_response.usage.output_tokens,
        total_tokens=llm_response.usage.total_tokens,
        cost_usd=llm_response.usage.cost_usd,
        metadata={"storage": "memory", **llm_response.metadata},
        created_at=now,
        updated_at=now,
    )
    _MEMORY_MESSAGES.setdefault(conversation_id, []).extend([user_message, assistant_message])
    return ChatMessageCreateResponse(
        user_message=user_message,
        assistant_message=assistant_message,
        request_id=llm_response.request_id,
        provider_key=llm_response.provider_key,
        model_key=llm_response.model_key,
        usage=LLMUsageResponse(**llm_response.usage.model_dump()),
        sources=_sources_from_llm_metadata(llm_response.metadata),
        metadata=llm_response.metadata,
    )


def _sources_from_llm_metadata(metadata: dict[str, object]) -> list[dict[str, object]]:
    sources = metadata.get("agent_sources")
    if not isinstance(sources, list):
        return []
    return [source for source in sources if isinstance(source, dict)]


def _conversation_metadata_with_last_task(
    metadata: dict[str, object],
    *,
    payload: ChatMessageCreateRequest,
    llm_response: Any,
    completed_at: datetime,
) -> dict[str, object]:
    workflow_key = payload.metadata.get("workflow_key")
    if not isinstance(workflow_key, str):
        agent_context = payload.metadata.get("agent_context")
        if isinstance(agent_context, dict):
            workflow_key = agent_context.get("workflow_key")
    return {
        **metadata,
        "last_task": {
            "title": payload.content[:160],
            "status": "completed",
            "workflow_key": workflow_key if isinstance(workflow_key, str) else None,
            "request_id": llm_response.request_id,
            "model_key": llm_response.model_key,
            "provider_key": llm_response.provider_key,
            "total_tokens": llm_response.usage.total_tokens,
            "completed_at": completed_at.isoformat(),
        },
    }


def _title_from_first_message(current_title: str, content: str) -> str:
    if current_title != "New AgentHive conversation":
        return current_title
    return content[:80] or current_title


def _sse(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------------------
# Conversation history export (P1 feature)
# ---------------------------------------------------------------------------

EXPORT_FIELDNAMES = [
    "message_id",
    "conversation_id",
    "role",
    "content",
    "user_id",
    "request_id",
    "model_key",
    "provider_key",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cost_usd",
    "created_at",
]


async def export_chat_history(
    session: AsyncSession,
    principal: Principal,
    conversation_id: UUID,
    *,
    fmt: str = "csv",
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> str:
    """Export a single conversation's message history as CSV or JSON.

    Reuses the same access checks as ``list_chat_messages`` so the export
    respects tenant / admin / department / owner scoping. Records an audit
    event for the export action (consistent with audit log export).
    """
    conversation = await _get_accessible_conversation_session(session, principal, conversation_id)
    messages_response = await _list_chat_messages_for_conversation(
        session, principal, conversation_id
    )
    items = messages_response.messages

    await record_audit_event(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        action="chat.history.export",
        resource_type="conversation",
        resource_id=conversation_id,
        request_id=request_id,
        details={
            "format": fmt,
            "item_count": len(items),
            "conversation_title": conversation.title,
            "ip_address": ip_address,
            "user_agent": user_agent,
        },
    )
    await session.commit()

    if fmt == "json":
        return _chat_history_to_json(conversation, items)
    return _chat_history_to_csv(conversation, items)


def _chat_history_to_csv(
    conversation: ConversationSession,
    items: list[ChatMessageResponse],
) -> str:
    buffer = io.StringIO()
    # Prepend metadata header as comment-like rows for context.
    buffer.write(f"# conversation_id,{conversation.id}\n")
    buffer.write(f"# title,{_csv_escape(conversation.title)}\n")
    buffer.write(f"# agent_id,{conversation.agent_id or ''}\n")
    buffer.write(f"# source,{conversation.source}\n")
    buffer.write(f"# status,{conversation.status}\n")
    buffer.write(f"# created_at,{conversation.created_at.isoformat()}\n")
    buffer.write(f"# updated_at,{conversation.updated_at.isoformat()}\n")
    writer = csv.DictWriter(buffer, fieldnames=EXPORT_FIELDNAMES)
    writer.writeheader()
    for item in items:
        writer.writerow(
            {
                "message_id": item.id,
                "conversation_id": item.conversation_id,
                "role": item.role,
                "content": item.content,
                "user_id": item.user_id or "",
                "request_id": item.request_id or "",
                "model_key": item.model_key or "",
                "provider_key": item.provider_key or "",
                "input_tokens": item.input_tokens,
                "output_tokens": item.output_tokens,
                "total_tokens": item.total_tokens,
                "cost_usd": str(item.cost_usd),
                "created_at": item.created_at.isoformat(),
            }
        )
    return buffer.getvalue()


def _chat_history_to_json(
    conversation: ConversationSession,
    items: list[ChatMessageResponse],
) -> str:
    payload = {
        "conversation": _session_response(conversation).model_dump(mode="json"),
        "messages": [item.model_dump(mode="json") for item in items],
    }
    return json.dumps(payload, ensure_ascii=False, default=str)


def _csv_escape(value: str) -> str:
    if not value:
        return ""
    if "," in value or '"' in value or "\n" in value:
        return '"' + value.replace('"', '""') + '"'
    return value
