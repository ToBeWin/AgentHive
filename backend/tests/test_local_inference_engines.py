"""Tests for local / on-prem inference engines (Ollama, vLLM, ...).

These engines expose OpenAI-compatible endpoints on localhost and typically
require no API key. The catalog must mark them ``auth_required=False`` so the
OpenAI-compatible adapter makes live calls when only a ``base_url`` is set.
"""

import unittest

from app.core.config import settings
from app.llm.openai_compatible import OpenAICompatibleAdapter
from app.llm.schemas import (
    ConnectionTestRequest,
    DeploymentConfig,
    LLMAdapterType,
    ProviderConfig,
)
from app.services.llm_service import (
    _LOCAL_INFERENCE_ENGINES,
    _catalog_provider_base_url,
    _catalog_provider_configured,
    _is_local_inference_engine,
    _local_inference_api_key,
    _PROVIDERS,
)

LOCAL_ENGINE_KEYS = set(_LOCAL_INFERENCE_ENGINES.keys())


class LocalInferenceCatalogTests(unittest.TestCase):
    """Catalog wiring: base_url + auth_required metadata."""

    def setUp(self):
        self._saved = {
            key: getattr(settings, attrs[0]) for key, attrs in _LOCAL_INFERENCE_ENGINES.items()
        }
        for attrs in _LOCAL_INFERENCE_ENGINES.values():
            setattr(settings, attrs[0], None)

    def tearDown(self):
        for key, attrs in _LOCAL_INFERENCE_ENGINES.items():
            setattr(settings, attrs[0], self._saved[key])

    def test_all_local_engines_are_recognised(self):
        for key in LOCAL_ENGINE_KEYS:
            self.assertTrue(_is_local_inference_engine(key), key)
        self.assertFalse(_is_local_inference_engine("openai"))
        self.assertFalse(_is_local_inference_engine("openai_compatible"))

    def test_local_engines_not_configured_without_base_url(self):
        for key in LOCAL_ENGINE_KEYS:
            self.assertFalse(_catalog_provider_configured(key), key)
            self.assertIsNone(_catalog_provider_base_url(key), key)

    def test_local_engine_activated_by_base_url_only(self):
        settings.ollama_base_url = "http://localhost:11434/v1"
        self.assertTrue(_catalog_provider_configured("ollama"))
        self.assertEqual("http://localhost:11434/v1", _catalog_provider_base_url("ollama"))
        # No api_key set; still configured.
        self.assertEqual("", _local_inference_api_key("ollama"))

    def test_local_engine_api_key_passthrough(self):
        settings.vllm_base_url = "http://localhost:8001/v1"
        settings.vllm_api_key = "sk-vllm-secret"
        self.assertEqual("sk-vllm-secret", _local_inference_api_key("vllm"))

    def test_catalog_provider_metadata_marks_auth_required_false(self):
        # _PROVIDERS is built at import time; metadata flags are set based on
        # _is_local_inference_engine (provider_key), not on activation state.
        for key in LOCAL_ENGINE_KEYS:
            provider = next(p for p in _PROVIDERS if p.provider_key == key)
            self.assertIs(False, provider.metadata.get("auth_required"), key)
            self.assertIs(True, provider.metadata.get("local_inference_engine"), key)

    def test_remote_provider_keeps_auth_required_true(self):
        provider = next(p for p in _PROVIDERS if p.provider_key == "openai_compatible")
        self.assertNotIn(provider.provider_key, LOCAL_ENGINE_KEYS)
        # auth_required defaults to True for non-local OpenAI-compatible providers.
        self.assertIs(True, provider.metadata.get("auth_required", True))
        self.assertIs(False, provider.metadata.get("local_inference_engine", False))


class LocalInferenceLiveCallGuardTests(unittest.TestCase):
    """The OpenAI-compatible adapter must allow live calls without api_key."""

    def setUp(self):
        self._saved_base_url = settings.openai_compatible_base_url
        self._saved_api_key = settings.openai_compatible_api_key
        self._saved_ollama_base_url = settings.ollama_base_url
        self._saved_ollama_api_key = settings.ollama_api_key
        settings.openai_compatible_base_url = None
        settings.openai_compatible_api_key = ""
        settings.ollama_base_url = None
        settings.ollama_api_key = ""

    def tearDown(self):
        settings.openai_compatible_base_url = self._saved_base_url
        settings.openai_compatible_api_key = self._saved_api_key
        settings.ollama_base_url = self._saved_ollama_base_url
        settings.ollama_api_key = self._saved_ollama_api_key

    def test_local_engine_live_without_api_key(self):
        settings.ollama_base_url = "http://localhost:11434/v1"
        adapter = OpenAICompatibleAdapter(
            provider=_provider("ollama", auth_required=False),
            deployment=_deployment(),
        )
        # base_url set, no api_key: live call should be allowed for local engine.
        self.assertTrue(adapter._should_call_live())

    def test_remote_engine_still_requires_api_key(self):
        settings.openai_compatible_base_url = "http://localhost:8000/v1"
        adapter = OpenAICompatibleAdapter(
            provider=_provider("openai_compatible", auth_required=True),
            deployment=_deployment(),
        )
        # base_url set but no api_key: remote engine must NOT go live.
        self.assertFalse(adapter._should_call_live())

    def test_local_engine_with_explicit_request_credentials(self):
        adapter = OpenAICompatibleAdapter(
            provider=_provider("ollama", auth_required=False),
            deployment=_deployment(),
        )
        request = ConnectionTestRequest(
            model_key="llama3.1",
            base_url="http://localhost:11434/v1",
        )
        self.assertTrue(adapter._should_call_live(request))

    def test_local_engine_skipped_when_marked_mock(self):
        settings.ollama_base_url = "http://localhost:11434/v1"
        adapter = OpenAICompatibleAdapter(
            provider=_provider("ollama", auth_required=False),
            deployment=_deployment(mock=True),
        )
        self.assertFalse(adapter._should_call_live())

    def test_api_key_falls_back_to_engine_setting(self):
        settings.ollama_api_key = "ollama-token"
        adapter = OpenAICompatibleAdapter(
            provider=_provider("ollama", auth_required=False),
            deployment=_deployment(),
        )
        self.assertEqual("ollama-token", adapter._api_key())

    def test_api_key_falls_back_to_provider_metadata_secret(self):
        adapter = OpenAICompatibleAdapter(
            provider=_provider("ollama", auth_required=False, api_key="meta-secret"),
            deployment=_deployment(),
        )
        self.assertEqual("meta-secret", adapter._api_key())

    def test_api_key_empty_when_nothing_configured(self):
        adapter = OpenAICompatibleAdapter(
            provider=_provider("ollama", auth_required=False),
            deployment=_deployment(),
        )
        self.assertEqual("", adapter._api_key())


def _provider(
    provider_key: str,
    *,
    auth_required: bool,
    api_key: str | None = None,
) -> ProviderConfig:
    metadata: dict[str, object] = {
        "auth_required": auth_required,
        "local_inference_engine": not auth_required,
    }
    if api_key is not None:
        metadata["api_key"] = api_key
    return ProviderConfig(
        provider_key=provider_key,
        name=provider_key,
        adapter_type=LLMAdapterType.OPENAI_COMPATIBLE,
        base_url=None,
        metadata=metadata,
    )


def _deployment(*, mock: bool = False) -> DeploymentConfig:
    return DeploymentConfig(
        provider_key="ollama",
        provider_name="ollama",
        adapter_type=LLMAdapterType.OPENAI_COMPATIBLE,
        model_key="llama3.1",
        display_name="Ollama Llama",
        deployment_name="Ollama Llama",
        routing_key="ollama-chat",
        config={"mock": mock},
    )


if __name__ == "__main__":
    unittest.main()
