from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestration import AgentOrchestrationRuntime
from app.api.deps import Principal
from app.schemas.agents import AgentRunRequest, AgentRunResponse


@dataclass(frozen=True)
class AgentDefinition:
    agent_key: str
    name: str
    category: str
    description: str
    status: str
    version: str
    capabilities: list[str]
    required_module: str
    orchestration_runtime: AgentOrchestrationRuntime = AgentOrchestrationRuntime.LANGGRAPH
    orchestration_features: list[str] | None = None


class BaseAgent(ABC):
    definition: AgentDefinition

    @abstractmethod
    async def run(
        self,
        payload: AgentRunRequest,
        principal: Principal,
        *,
        request_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> AgentRunResponse:
        raise NotImplementedError

    def catalog_entry(self) -> dict[str, Any]:
        return {
            "agent_key": self.definition.agent_key,
            "name": self.definition.name,
            "category": self.definition.category,
            "description": self.definition.description,
            "status": self.definition.status,
            "version": self.definition.version,
            "capabilities": list(self.definition.capabilities),
            "required_module": self.definition.required_module,
            "orchestration_runtime": self.definition.orchestration_runtime.value,
            "orchestration_features": list(self.definition.orchestration_features or []),
        }
