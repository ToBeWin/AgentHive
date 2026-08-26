from pydantic import BaseModel, Field

from app.schemas.license import AgentModuleState


class AgentModuleCatalogEntry(BaseModel):
    id: str
    name: str
    scenario: str
    priority: str
    description: str
    version: str
    state: AgentModuleState
    licensed: bool
    installed: bool
    enabled: bool
    required_features: list[str]
    missing_features: list[str] = Field(default_factory=list)
    dependencies: list[str]
    missing_dependencies: list[str] = Field(default_factory=list)


class AgentModuleDetailResponse(AgentModuleCatalogEntry):
    category: str
    capabilities: list[str]
    default_agent_slug: str
    recommended_model_capabilities: list[str] = Field(default_factory=list)
    recommended_orchestration_runtimes: list[str] = Field(default_factory=list)
    default_config: dict[str, object] = Field(default_factory=dict)


class AgentModuleListResponse(BaseModel):
    modules: list[AgentModuleCatalogEntry]


class AgentModuleActionResponse(BaseModel):
    module_id: str
    state: AgentModuleState
    message: str
