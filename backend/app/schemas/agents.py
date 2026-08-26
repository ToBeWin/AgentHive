from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.llm import LLMUsageResponse


class AgentCatalogEntry(BaseModel):
    agent_key: str
    name: str
    category: str
    description: str
    status: str
    version: str
    capabilities: list[str]
    required_module: str
    orchestration_runtime: str = "langgraph"
    orchestration_features: list[str] = Field(default_factory=list)
    licensed: bool | None = None
    installed: bool | None = None
    enabled: bool | None = None
    license_gate: str = "unknown"


class AgentCatalogResponse(BaseModel):
    agents: list[AgentCatalogEntry]


class AgentInstanceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=80)
    agent_key: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    visibility: str = Field(default="tenant", pattern="^(tenant|department|private)$")
    department_id: UUID | None = None
    owner_user_id: UUID | None = None
    model_routing_key: str | None = Field(default=None, max_length=120)
    model_key: str | None = Field(default=None, max_length=120)
    system_prompt: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower().replace(" ", "-")
        return normalized or None


class AgentInstanceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, pattern="^(draft|active|disabled)$")
    visibility: str | None = Field(default=None, pattern="^(tenant|department|private)$")
    department_id: UUID | None = None
    owner_user_id: UUID | None = None
    model_routing_key: str | None = Field(default=None, max_length=120)
    model_key: str | None = Field(default=None, max_length=120)
    system_prompt: str | None = None
    config: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class AgentInstanceResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    slug: str
    agent_key: str
    module_key: str
    description: str | None
    status: str
    visibility: str
    department_id: UUID | None
    owner_user_id: UUID | None
    model_routing_key: str | None
    model_key: str | None
    system_prompt: str | None
    config: dict[str, Any]
    metadata: dict[str, Any]
    created_by: UUID | None
    created_at: Any
    updated_at: Any
    runnable: bool = True
    readiness: str = "ready"
    readiness_reasons: list[str] = Field(default_factory=list)
    model_available: bool = False
    knowledge_base_count: int = 0
    knowledge_enabled: bool = False


class AgentInstanceListResponse(BaseModel):
    agents: list[AgentInstanceResponse]


class WorkbenchAgentKnowledgeBaseSummary(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    visibility: str
    status: str
    document_count: int = 0
    tags: list[str] = Field(default_factory=list)
    updated_at: Any


class WorkbenchAgentInstanceResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    agent_key: str
    module_key: str
    description: str | None
    status: str
    visibility: str
    department_id: UUID | None
    category: str = "general"
    workflow_profile: str = "general"
    runnable: bool = True
    readiness: str = "ready"
    readiness_reasons: list[str] = Field(default_factory=list)
    model_profile: str | None = None
    model_policy: str
    model_available: bool = False
    knowledge_base_count: int = 0
    knowledge_enabled: bool = False
    knowledge_bases: list[WorkbenchAgentKnowledgeBaseSummary] = Field(default_factory=list)


class WorkbenchAgentInstanceListResponse(BaseModel):
    agents: list[WorkbenchAgentInstanceResponse]


class AgentGovernanceTargetItem(BaseModel):
    id: UUID
    label: str
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentGovernanceTargetsResponse(BaseModel):
    departments: list[AgentGovernanceTargetItem] = Field(default_factory=list)
    users: list[AgentGovernanceTargetItem] = Field(default_factory=list)
    knowledge_bases: list[AgentGovernanceTargetItem] = Field(default_factory=list)
    model_deployments: list[AgentGovernanceTargetItem] = Field(default_factory=list)


class AgentRunRequest(BaseModel):
    input: str = Field(min_length=1, max_length=12000)
    context: dict[str, Any] = Field(default_factory=dict)
    model_key: str | None = Field(default=None, max_length=120)
    routing_key: str | None = Field(default=None, max_length=120)
    max_tokens: int | None = Field(default=1024, ge=1, le=8192)
    mcp_server_keys: list[str] | None = Field(
        default=None,
        description="Optional MCP server_keys to mount for this run. None = use "
        "all active MCP servers in the tenant; empty list = disable MCP.",
    )


class AgentRunResponse(BaseModel):
    answer: str
    usage: LLMUsageResponse
    model_key: str
    request_id: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
