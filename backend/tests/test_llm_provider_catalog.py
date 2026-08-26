import unittest

from app.services.llm_service import (
    _DEPLOYMENTS,
    _PROVIDERS,
    _default_model_key,
    _default_routing_key,
)


EXPECTED_PROVIDER_KEYS = {
    "ai302",
    "anthropic",
    "anthropic_compatible",
    "azure_openai",
    "baidu_qianfan",
    "bedrock",
    "cohere",
    "deepseek",
    "doubao",
    "fireworks",
    "gemini",
    "glm",
    "groq",
    "hunyuan",
    "kimi",
    "litellm",
    "lmstudio",
    "localai",
    "mimo",
    "minimax",
    "mistral",
    "novita",
    "ollama",
    "openai",
    "openai_compatible",
    "openrouter",
    "qwen",
    "sglang",
    "siliconflow",
    "spark",
    "together",
    "vertex_ai",
    "vllm",
    "xai",
    "xinference",
}

EXPECTED_MEDIA_PROVIDER_KEYS = {
    "nano_banana",
    "openai_compatible_media",
    "openai_images",
    "volcengine_seedance",
}


class LLMProviderCatalogTests(unittest.TestCase):
    def test_provider_catalog_covers_required_frontend_groups(self):
        provider_keys = {provider.provider_key for provider in _PROVIDERS}

        self.assertTrue(EXPECTED_PROVIDER_KEYS.issubset(provider_keys))
        self.assertTrue(EXPECTED_MEDIA_PROVIDER_KEYS.issubset(provider_keys))
        self.assertEqual(len(provider_keys), len(_PROVIDERS))

    def test_each_provider_has_default_deployment_or_runtime_placeholder(self):
        deployment_keys = {deployment.provider_key for deployment in _DEPLOYMENTS}

        self.assertTrue(EXPECTED_PROVIDER_KEYS.issubset(deployment_keys))
        self.assertTrue(EXPECTED_MEDIA_PROVIDER_KEYS.issubset(deployment_keys))
        self.assertEqual(len({deployment.id for deployment in _DEPLOYMENTS}), len(_DEPLOYMENTS))

    def test_default_model_and_routing_key_are_defined_for_required_providers(self):
        for provider_key in EXPECTED_PROVIDER_KEYS:
            self.assertNotEqual("chat-model", _default_model_key(provider_key), provider_key)
            self.assertTrue(_default_routing_key(provider_key).endswith("-chat"))

        self.assertEqual("default-chat", _default_routing_key("litellm"))
        self.assertEqual("private-chat", _default_routing_key("openai_compatible"))
        self.assertEqual("anthropic-private-chat", _default_routing_key("anthropic_compatible"))
        self.assertEqual("vllm-chat", _default_routing_key("vllm"))

    def test_sales_critical_defaults_are_pinned(self):
        self.assertEqual("deepseek-v4-flash", _default_model_key("deepseek"))
        self.assertEqual("mimo-chat", _default_model_key("mimo"))
        self.assertEqual("abab6.5s-chat", _default_model_key("minimax"))
        self.assertEqual("google/nano-banana", _default_model_key("nano_banana"))
        self.assertEqual("volcengine/seedance-2.0", _default_model_key("volcengine_seedance"))
        self.assertEqual("openai/gpt-image-2", _default_model_key("openai_images"))


if __name__ == "__main__":
    unittest.main()
