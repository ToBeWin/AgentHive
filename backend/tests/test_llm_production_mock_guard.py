from uuid import uuid4
import unittest

from app.core.config import settings
from app.llm.anthropic_compatible import AnthropicCompatibleAdapter
from app.llm.litellm_adapter import LiteLLMAdapter
from app.llm.openai_compatible import OpenAICompatibleAdapter
from app.llm.openai_compatible import _effective_max_tokens, _empty_content_reason
from app.llm.schemas import (
    ConnectionTestRequest,
    DeploymentConfig,
    LLMAdapterType,
    LLMChatRequest,
    LLMRequestContext,
    ProviderConfig,
)


class LLMProductionMockGuardTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._environment = settings.environment
        self._litellm_master_key = settings.litellm_master_key
        self._openai_compatible_base_url = settings.openai_compatible_base_url
        self._openai_compatible_api_key = settings.openai_compatible_api_key
        settings.litellm_master_key = ""
        settings.openai_compatible_base_url = None
        settings.openai_compatible_api_key = ""

    def tearDown(self):
        settings.environment = self._environment
        settings.litellm_master_key = self._litellm_master_key
        settings.openai_compatible_base_url = self._openai_compatible_base_url
        settings.openai_compatible_api_key = self._openai_compatible_api_key

    async def test_litellm_chat_rejects_mock_mode_outside_development(self):
        settings.environment = "production"
        adapter = LiteLLMAdapter(
            provider=_provider("litellm", LLMAdapterType.LITELLM),
            deployment=_deployment("litellm", LLMAdapterType.LITELLM),
        )

        with self.assertRaisesRegex(RuntimeError, "mock mode is disabled"):
            await adapter.chat(_chat_request(), _context())

    async def test_openai_compatible_chat_rejects_mock_mode_outside_development(self):
        settings.environment = "production"
        adapter = OpenAICompatibleAdapter(
            provider=_provider("openai_compatible", LLMAdapterType.OPENAI_COMPATIBLE),
            deployment=_deployment("openai_compatible", LLMAdapterType.OPENAI_COMPATIBLE),
        )

        with self.assertRaisesRegex(RuntimeError, "mock mode is disabled"):
            await adapter.chat(_chat_request(), _context())

    async def test_anthropic_compatible_chat_rejects_mock_mode_outside_development(self):
        settings.environment = "production"
        adapter = AnthropicCompatibleAdapter(
            provider=_provider("anthropic_compatible", LLMAdapterType.ANTHROPIC_COMPATIBLE),
            deployment=_deployment("anthropic_compatible", LLMAdapterType.ANTHROPIC_COMPATIBLE),
        )

        with self.assertRaisesRegex(RuntimeError, "mock mode is disabled"):
            await adapter.chat(_chat_request(), _context())

    async def test_connection_test_fails_in_production_when_only_mock_is_available(self):
        settings.environment = "production"
        litellm = LiteLLMAdapter(
            provider=_provider("litellm", LLMAdapterType.LITELLM),
            deployment=_deployment("litellm", LLMAdapterType.LITELLM),
        )
        openai_compatible = OpenAICompatibleAdapter(
            provider=_provider("openai_compatible", LLMAdapterType.OPENAI_COMPATIBLE),
            deployment=_deployment("openai_compatible", LLMAdapterType.OPENAI_COMPATIBLE),
        )
        anthropic_compatible = AnthropicCompatibleAdapter(
            provider=_provider("anthropic_compatible", LLMAdapterType.ANTHROPIC_COMPATIBLE),
            deployment=_deployment("anthropic_compatible", LLMAdapterType.ANTHROPIC_COMPATIBLE),
        )

        litellm_result = await litellm.test_connection(
            ConnectionTestRequest(model_key="agenthive-chat")
        )
        openai_result = await openai_compatible.test_connection(
            ConnectionTestRequest(model_key="agenthive-chat")
        )
        anthropic_result = await anthropic_compatible.test_connection(
            ConnectionTestRequest(model_key="agenthive-chat")
        )

        self.assertFalse(litellm_result.ok)
        self.assertFalse(openai_result.ok)
        self.assertFalse(anthropic_result.ok)
        self.assertFalse(litellm_result.diagnostics["mock_allowed"])
        self.assertFalse(openai_result.diagnostics["mock_allowed"])
        self.assertFalse(anthropic_result.diagnostics["mock_allowed"])
        self.assertFalse(litellm_result.diagnostics["live_network_call"])
        self.assertFalse(openai_result.diagnostics["live_network_call"])
        self.assertFalse(anthropic_result.diagnostics["live_network_call"])

    async def test_development_still_allows_adapter_mock_responses(self):
        settings.environment = "development"
        adapter = OpenAICompatibleAdapter(
            provider=_provider("openai_compatible", LLMAdapterType.OPENAI_COMPATIBLE),
            deployment=_deployment("openai_compatible", LLMAdapterType.OPENAI_COMPATIBLE),
        )

        response = await adapter.chat(_chat_request(), _context())
        result = await adapter.test_connection(ConnectionTestRequest(model_key="agenthive-chat"))

        self.assertTrue(response.metadata["mock"])
        self.assertTrue(result.ok)
        self.assertTrue(result.diagnostics["mock_allowed"])

    async def test_openai_compatible_raises_mimo_output_token_floor(self):
        self.assertEqual(
            512,
            _effective_max_tokens(
                model_key="mimo-v2.5-pro",
                provider_key="mimo",
                requested_max_tokens=128,
            ),
        )
        self.assertEqual(
            768,
            _effective_max_tokens(
                model_key="mimo-v2.5-pro",
                provider_key="mimo",
                requested_max_tokens=768,
            ),
        )
        self.assertEqual(
            128,
            _effective_max_tokens(
                model_key="qwen-plus",
                provider_key="qwen",
                requested_max_tokens=128,
            ),
        )

    async def test_openai_compatible_reports_empty_reasoning_content_reason(self):
        self.assertEqual(
            "reasoning_tokens_exhausted_output_budget",
            _empty_content_reason(content="", finish_reason="length", reasoning_tokens=63),
        )
        self.assertIsNone(
            _empty_content_reason(content="hello", finish_reason="stop", reasoning_tokens=63)
        )


def _provider(provider_key: str, adapter_type: LLMAdapterType) -> ProviderConfig:
    return ProviderConfig(
        provider_key=provider_key,
        name=provider_key,
        adapter_type=adapter_type,
        base_url=None,
        metadata={},
    )


def _deployment(provider_key: str, adapter_type: LLMAdapterType) -> DeploymentConfig:
    return DeploymentConfig(
        provider_key=provider_key,
        provider_name=provider_key,
        adapter_type=adapter_type,
        model_key="agenthive-chat",
        display_name="AgentHive Chat",
        deployment_name="AgentHive Chat",
        routing_key="agenthive-chat",
        config={"mock": True},
    )


def _chat_request() -> LLMChatRequest:
    return LLMChatRequest(
        model_key="agenthive-chat",
        messages=[{"role": "user", "content": "hello"}],
        max_tokens=32,
    )


def _context() -> LLMRequestContext:
    return LLMRequestContext(tenant_id=uuid4())


if __name__ == "__main__":
    unittest.main()
