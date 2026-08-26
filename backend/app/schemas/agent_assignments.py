"""Schemas for agent-user assignment API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AgentAssignmentCreateRequest(BaseModel):
    user_id: UUID
    role: str = Field(default="user", pattern=r"^(owner|operator|viewer)$")


class AgentAssignmentBulkRequest(BaseModel):
    users: list[AgentAssignmentCreateRequest] = Field(min_length=1, max_length=50)


class AgentAssignmentResponse(BaseModel):
    id: UUID
    agent_id: UUID
    user_id: UUID
    user_email: str
    user_full_name: str | None
    role: str
    assigned_by: UUID | None
    created_at: datetime


class AgentAssignmentListResponse(BaseModel):
    assignments: list[AgentAssignmentResponse]


class UserAgentItem(BaseModel):
    agent_id: UUID
    agent_name: str
    agent_key: str
    description: str | None
    role: str
    status: str


class UserAgentsResponse(BaseModel):
    agents: list[UserAgentItem]
