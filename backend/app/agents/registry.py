from app.agents.base import BaseAgent
from app.agents.custom_builder.agent import ConfigurableAgent
from app.agents.official.configured import build_configured_official_agents
from app.agents.official.customer_service.agent import CustomerServiceAgent


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.definition.agent_key] = agent

    def list_agents(self) -> list[BaseAgent]:
        return sorted(self._agents.values(), key=lambda item: item.definition.agent_key)

    def get(self, agent_key: str) -> BaseAgent | None:
        return self._agents.get(agent_key)


agent_registry = AgentRegistry()
agent_registry.register(CustomerServiceAgent())
agent_registry.register(ConfigurableAgent())
for official_agent in build_configured_official_agents():
    agent_registry.register(official_agent)
