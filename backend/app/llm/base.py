from abc import ABC, abstractmethod

from app.llm.schemas import (
    ConnectionTestRequest,
    ConnectionTestResult,
    DeploymentConfig,
    LLMChatRequest,
    LLMRequestContext,
    LLMResponse,
    ProviderConfig,
    StreamChunks,
)


class BaseLLMAdapter(ABC):
    """Adapter contract for every model provider behind AgentHive LLM Gateway."""

    adapter_name: str

    def __init__(self, provider: ProviderConfig, deployment: DeploymentConfig | None = None):
        self.provider = provider
        self.deployment = deployment

    @abstractmethod
    async def chat(
        self,
        request: LLMChatRequest,
        context: LLMRequestContext,
    ) -> LLMResponse:
        """Run a non-streaming chat completion."""

    @abstractmethod
    def stream_chat(
        self,
        request: LLMChatRequest,
        context: LLMRequestContext,
    ) -> StreamChunks:
        """Run a streaming chat completion."""

    @abstractmethod
    async def test_connection(
        self,
        request: ConnectionTestRequest,
    ) -> ConnectionTestResult:
        """Validate provider reachability and credentials without exposing secrets."""
