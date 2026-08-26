from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.llm import LLMUsageResponse


class ChatSessionCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=160)
    agent_id: UUID | None = None
    agent_instance_id: UUID | None = None
    channel_id: UUID | None = None
    department_id: UUID | None = None
    source: str = Field(default="chat_console", max_length=40)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_agent_instance_alias(self) -> "ChatSessionCreateRequest":
        if (
            self.agent_id is not None
            and self.agent_instance_id is not None
            and self.agent_id != self.agent_instance_id
        ):
            raise ValueError("agent_id and agent_instance_id must match when both are provided.")
        if self.agent_id is None:
            self.agent_id = self.agent_instance_id
        return self


class ChatSessionResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    title: str
    agent_id: UUID | None
    channel_id: UUID | None
    user_id: UUID | None
    department_id: UUID | None
    source: str
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ChatSessionListResponse(BaseModel):
    sessions: list[ChatSessionResponse]
    total: int
    limit: int
    offset: int


class ChatMessageResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    conversation_id: UUID
    role: str
    content: str
    user_id: UUID | None
    request_id: str | None
    model_key: str | None
    provider_key: str | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: Decimal
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ChatMessageListResponse(BaseModel):
    messages: list[ChatMessageResponse]


class ChatMessageCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=12000)
    model_key: str | None = Field(default=None, max_length=120)
    routing_key: str | None = Field(default=None, max_length=120)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=1024, ge=1, le=8192)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatMessageCreateResponse(BaseModel):
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse
    request_id: str
    provider_key: str
    model_key: str
    usage: LLMUsageResponse
    sources: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
