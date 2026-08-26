from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_permission
from app.core.database import get_session
from app.core.security import Permission
from app.schemas.chat import (
    ChatMessageCreateRequest,
    ChatMessageCreateResponse,
    ChatMessageListResponse,
    ChatSessionCreateRequest,
    ChatSessionListResponse,
    ChatSessionResponse,
)
from app.services.chat_service import (
    create_chat_session,
    export_chat_history,
    list_chat_messages,
    list_chat_sessions,
    send_chat_message,
    stream_chat_message,
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/sessions", response_model=ChatSessionListResponse)
async def read_chat_sessions(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.CHAT_READ))],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ChatSessionListResponse:
    return await list_chat_sessions(session, principal, limit=limit, offset=offset)


@router.post("/sessions", response_model=ChatSessionResponse)
async def create_session(
    request: Request,
    payload: ChatSessionCreateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.CHAT_WRITE))],
) -> ChatSessionResponse:
    return await create_chat_session(
        session,
        principal,
        payload,
        request_id=getattr(request.state, "request_id", None),
    )


@router.get("/sessions/{conversation_id}/messages", response_model=ChatMessageListResponse)
async def read_chat_messages(
    conversation_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.CHAT_READ))],
) -> ChatMessageListResponse:
    return await list_chat_messages(session, principal, conversation_id)


@router.post("/sessions/{conversation_id}/messages", response_model=ChatMessageCreateResponse)
async def create_message(
    request: Request,
    conversation_id: UUID,
    payload: ChatMessageCreateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.CHAT_WRITE))],
) -> ChatMessageCreateResponse:
    return await send_chat_message(
        session,
        principal,
        conversation_id,
        payload,
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/sessions/{conversation_id}/messages/stream")
async def stream_message(
    request: Request,
    conversation_id: UUID,
    payload: ChatMessageCreateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.CHAT_WRITE))],
) -> StreamingResponse:
    return StreamingResponse(
        stream_chat_message(
            session,
            principal,
            conversation_id,
            payload,
            request_id=getattr(request.state, "request_id", None),
        ),
        media_type="text/event-stream",
    )


@router.get("/sessions/{conversation_id}/export", response_class=Response)
async def export_session_history(
    request: Request,
    conversation_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(Permission.CHAT_READ))],
    format: str = Query(default="csv", pattern="^(csv|json)$"),
) -> Response:
    """Export a conversation's message history as CSV or JSON.

    Access is scoped by the same tenant/admin/department/owner rules as
    reading messages. An audit event (`chat.history.export`) is recorded.
    """
    body = await export_chat_history(
        session,
        principal,
        conversation_id,
        fmt=format,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    safe_id = str(conversation_id)
    if format == "json":
        return Response(
            content=body,
            media_type="application/json; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="agenthive-chat-{safe_id}.json"'
            },
        )
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="agenthive-chat-{safe_id}.csv"'},
    )
