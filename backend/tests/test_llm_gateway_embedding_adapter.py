from __future__ import annotations

import threading
import unittest

import httpx

from app.core.config import settings
from app.rag.embeddings import (
    EmbeddingResult,
    EmbeddingService,
    LLMGatewayEmbeddingAdapter,
    LocalHashEmbeddingService,
    _extract_embedding_vector,
    embed_text_nonblocking,
    get_default_embedding_service,
)


class GetDefaultEmbeddingServiceTests(unittest.TestCase):
    """Factory must select the right embedding backend based on settings."""

    def setUp(self) -> None:
        self._provider = settings.rag_embedding_provider

    def tearDown(self) -> None:
        settings.rag_embedding_provider = self._provider

    def test_local_hash_is_default(self) -> None:
        settings.rag_embedding_provider = "local_hash"
        service = get_default_embedding_service()
        self.assertIsInstance(service, LocalHashEmbeddingService)

    def test_llm_gateway_provider_returns_gateway_adapter(self) -> None:
        settings.rag_embedding_provider = "llm_gateway"
        service = get_default_embedding_service()
        self.assertIsInstance(service, LLMGatewayEmbeddingAdapter)

    def test_openai_compatible_alias_returns_gateway_adapter(self) -> None:
        settings.rag_embedding_provider = "openai_compatible"
        service = get_default_embedding_service()
        self.assertIsInstance(service, LLMGatewayEmbeddingAdapter)

    def test_litellm_alias_returns_gateway_adapter(self) -> None:
        settings.rag_embedding_provider = "litellm"
        service = get_default_embedding_service()
        self.assertIsInstance(service, LLMGatewayEmbeddingAdapter)

    def test_unknown_provider_falls_back_to_local_hash(self) -> None:
        settings.rag_embedding_provider = "unknown_future_provider"
        service = get_default_embedding_service()
        self.assertIsInstance(service, LocalHashEmbeddingService)


class LLMGatewayEmbeddingAdapterFallbackTests(unittest.TestCase):
    """In development with missing credentials, gateway adapter must fall back."""

    def setUp(self) -> None:
        self._environment = settings.environment
        self._base_url = settings.rag_embedding_api_base_url
        self._api_key = settings.rag_embedding_api_key
        self._model_key = settings.rag_embedding_model_key
        self._dimensions = settings.rag_embedding_dimensions

        settings.environment = "development"
        settings.rag_embedding_api_base_url = None
        settings.rag_embedding_api_key = ""

    def tearDown(self) -> None:
        settings.environment = self._environment
        settings.rag_embedding_api_base_url = self._base_url
        settings.rag_embedding_api_key = self._api_key
        settings.rag_embedding_model_key = self._model_key
        settings.rag_embedding_dimensions = self._dimensions

    def test_development_falls_back_to_local_hash_when_unconfigured(self) -> None:
        adapter = LLMGatewayEmbeddingAdapter()
        result = adapter.embed_text("七天无理由退货")

        self.assertEqual("llm_gateway_openai_compatible+local_hash_fallback", result.mode)
        self.assertEqual(settings.rag_embedding_dimensions, result.dimensions)
        self.assertEqual(settings.rag_embedding_model_key, result.model_key)
        self.assertEqual(len(result.vector), result.dimensions)

    def test_development_fallback_is_deterministic(self) -> None:
        adapter = LLMGatewayEmbeddingAdapter()
        first = adapter.embed_text("尺码偏小")
        second = adapter.embed_text("尺码偏小")
        self.assertEqual(first.vector, second.vector)

    def test_production_fails_closed_when_unconfigured(self) -> None:
        settings.environment = "production"
        adapter = LLMGatewayEmbeddingAdapter()
        with self.assertRaises(RuntimeError) as ctx:
            adapter.embed_text("any text")
        self.assertIn("RAG_EMBEDDING_API_BASE_URL", str(ctx.exception))
        self.assertIn("RAG_EMBEDDING_API_KEY", str(ctx.exception))


class LLMGatewayEmbeddingAdapterLiveCallTests(unittest.TestCase):
    """When credentials are configured, the adapter must call the live endpoint."""

    def setUp(self) -> None:
        self._environment = settings.environment
        self._base_url = settings.rag_embedding_api_base_url
        self._api_key = settings.rag_embedding_api_key
        self._model_key = settings.rag_embedding_model_key

        settings.environment = "production"
        settings.rag_embedding_api_base_url = "https://embeddings.example.com/v1"
        settings.rag_embedding_api_key = "test-key"
        settings.rag_embedding_model_key = "text-embedding-3-small"

    def tearDown(self) -> None:
        settings.environment = self._environment
        settings.rag_embedding_api_base_url = self._base_url
        settings.rag_embedding_api_key = self._api_key
        settings.rag_embedding_model_key = self._model_key

    def test_live_call_returns_provider_vector(self) -> None:
        fake_vector = [0.1] * 1536
        captured_requests: list[dict[str, object]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_requests.append(
                {
                    "url": str(request.url),
                    "method": request.method,
                    "authorization": request.headers.get("authorization"),
                    "body": request.read().decode("utf-8"),
                }
            )
            return httpx.Response(
                status_code=200,
                json={
                    "object": "list",
                    "data": [{"object": "embedding", "index": 0, "embedding": fake_vector}],
                    "model": "text-embedding-3-small",
                    "usage": {"prompt_tokens": 4, "total_tokens": 4},
                },
            )

        transport = httpx.MockTransport(handler)
        with httpx.Client(transport=transport) as http_client:
            adapter = LLMGatewayEmbeddingAdapter(http_client=http_client)
            result = adapter.embed_text("七天无理由退货")

        self.assertEqual(1, len(captured_requests))
        request = captured_requests[0]
        self.assertEqual("https://embeddings.example.com/v1/embeddings", request["url"])
        self.assertEqual("POST", request["method"])
        self.assertEqual("Bearer test-key", request["authorization"])
        self.assertIn('"model":"text-embedding-3-small"', request["body"])
        self.assertIn('"input":"七天无理由退货"', request["body"])

        self.assertEqual("llm_gateway_openai_compatible", result.mode)
        self.assertEqual(1536, result.dimensions)
        self.assertEqual(fake_vector, result.vector)
        self.assertEqual("text-embedding-3-small", result.model_key)

    def test_live_call_adapts_to_provider_returned_dimensions(self) -> None:
        fake_vector = [0.2] * 768

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                status_code=200,
                json={"data": [{"embedding": fake_vector}]},
            )

        transport = httpx.MockTransport(handler)
        with httpx.Client(transport=transport) as http_client:
            adapter = LLMGatewayEmbeddingAdapter(http_client=http_client)
            result = adapter.embed_text("尺码偏小")

        self.assertEqual(768, result.dimensions)
        self.assertEqual(fake_vector, result.vector)

    def test_live_call_raises_on_http_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status_code=401, json={"error": "invalid api key"})

        transport = httpx.MockTransport(handler)
        with httpx.Client(transport=transport) as http_client:
            adapter = LLMGatewayEmbeddingAdapter(http_client=http_client)
            with self.assertRaises(httpx.HTTPStatusError):
                adapter.embed_text("any text")

    def test_live_call_raises_on_malformed_response(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status_code=200, json={"unexpected": "shape"})

        transport = httpx.MockTransport(handler)
        with httpx.Client(transport=transport) as http_client:
            adapter = LLMGatewayEmbeddingAdapter(http_client=http_client)
            with self.assertRaises(ValueError) as ctx:
                adapter.embed_text("any text")
            self.assertIn("data", str(ctx.exception))


class ExtractEmbeddingVectorTests(unittest.TestCase):
    """Response parser must validate OpenAI-compatible embedding payloads."""

    def test_parses_well_formed_payload(self) -> None:
        payload = {
            "object": "list",
            "data": [{"object": "embedding", "index": 0, "embedding": [0.1, -0.2, 0.3]}],
            "model": "text-embedding-3-small",
        }
        vector = _extract_embedding_vector(payload)
        self.assertEqual([0.1, -0.2, 0.3], vector)

    def test_rejects_missing_data_array(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _extract_embedding_vector({"model": "x"})
        self.assertIn("data", str(ctx.exception))

    def test_rejects_empty_data_array(self) -> None:
        with self.assertRaises(ValueError):
            _extract_embedding_vector({"data": []})

    def test_rejects_non_list_embedding_field(self) -> None:
        with self.assertRaises(ValueError):
            _extract_embedding_vector({"data": [{"embedding": "not a list"}]})

    def test_rejects_empty_vector(self) -> None:
        with self.assertRaises(ValueError):
            _extract_embedding_vector({"data": [{"embedding": []}]})

    def test_rejects_non_numeric_values(self) -> None:
        with self.assertRaises(ValueError):
            _extract_embedding_vector({"data": [{"embedding": [0.1, "not a number"]}]})

    def test_coerces_integer_values_to_floats(self) -> None:
        vector = _extract_embedding_vector({"data": [{"embedding": [0, 1, 2]}]})
        self.assertEqual([0.0, 1.0, 2.0], vector)


class EmbeddingServiceProtocolConformanceTests(unittest.TestCase):
    """Both implementations must satisfy the EmbeddingService protocol contract."""

    def test_local_hash_exposes_protocol_attributes(self) -> None:
        service: EmbeddingService = LocalHashEmbeddingService()
        self.assertTrue(hasattr(service, "model_key"))
        self.assertTrue(hasattr(service, "dimensions"))
        self.assertTrue(hasattr(service, "mode"))
        result = service.embed_text("test")
        self.assertEqual(service.model_key, result.model_key)
        self.assertEqual(service.dimensions, result.dimensions)
        self.assertEqual(service.mode, result.mode)

    def test_llm_gateway_adapter_exposes_protocol_attributes(self) -> None:
        settings.environment = "development"
        settings.rag_embedding_api_base_url = None
        settings.rag_embedding_api_key = ""
        try:
            service: EmbeddingService = LLMGatewayEmbeddingAdapter()
            self.assertTrue(hasattr(service, "model_key"))
            self.assertTrue(hasattr(service, "dimensions"))
            self.assertTrue(hasattr(service, "mode"))
            result = service.embed_text("test")
            # In dev fallback mode, model_key matches but mode reflects fallback.
            self.assertEqual(service.model_key, result.model_key)
        finally:
            settings.environment = "development"


class NonblockingEmbeddingBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_embedding_runs_outside_the_event_loop_thread(self) -> None:
        caller_thread = threading.get_ident()

        class ThreadRecordingService:
            model_key = "thread-test"
            dimensions = 1
            mode = "test"
            worker_thread: int | None = None

            def embed_text(self, _text: str) -> EmbeddingResult:
                self.worker_thread = threading.get_ident()
                return EmbeddingResult(
                    model_key=self.model_key,
                    dimensions=self.dimensions,
                    vector=[1.0],
                    mode=self.mode,
                )

        service = ThreadRecordingService()

        result = await embed_text_nonblocking(service, "hello")

        self.assertEqual([1.0], result.vector)
        self.assertIsNotNone(service.worker_thread)
        self.assertNotEqual(caller_thread, service.worker_thread)


class LLMGatewayEmbeddingAdapterResilienceTests(unittest.TestCase):
    """Retry, circuit-breaker, and fallback behavior."""

    def setUp(self) -> None:
        self._environment = settings.environment
        self._base_url = settings.rag_embedding_api_base_url
        self._api_key = settings.rag_embedding_api_key
        self._model_key = settings.rag_embedding_model_key

        settings.environment = "production"
        settings.rag_embedding_api_base_url = "https://embeddings.example.com/v1"
        settings.rag_embedding_api_key = "test-key"
        settings.rag_embedding_model_key = "text-embedding-3-small"

    def tearDown(self) -> None:
        settings.environment = self._environment
        settings.rag_embedding_api_base_url = self._base_url
        settings.rag_embedding_api_key = self._api_key
        settings.rag_embedding_model_key = self._model_key

    def _adapter(
        self,
        *,
        transport: httpx.MockTransport,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.0,
        circuit_breaker=None,
    ) -> LLMGatewayEmbeddingAdapter:
        http_client = httpx.Client(transport=transport)
        adapter = LLMGatewayEmbeddingAdapter(
            http_client=http_client,
            max_retries=max_retries,
            retry_backoff_seconds=retry_backoff_seconds,
            circuit_breaker=circuit_breaker,
        )
        # Hold a ref so the client isn't GC'd mid-test.
        self._http_client = http_client
        return adapter

    def test_5xx_retries_then_succeeds(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] < 3:
                return httpx.Response(503, text="unavailable")
            return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2, 0.3]}]})

        adapter = self._adapter(transport=httpx.MockTransport(handler))
        result = adapter.embed_text("hello")
        self.assertEqual([0.1, 0.2, 0.3], result.vector)
        self.assertEqual(3, calls["n"])

    def test_4xx_does_not_retry(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(401, json={"error": "invalid api key"})

        adapter = self._adapter(transport=httpx.MockTransport(handler))
        with self.assertRaises(httpx.HTTPStatusError):
            adapter.embed_text("hello")
        self.assertEqual(1, calls["n"])

    def test_5xx_exhausts_retries_then_raises(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(500, text="down")

        adapter = self._adapter(transport=httpx.MockTransport(handler), max_retries=2)
        with self.assertRaises(httpx.HTTPStatusError):
            adapter.embed_text("hello")
        self.assertEqual(3, calls["n"])

    def test_network_error_retries_then_raises(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            raise httpx.ConnectError("connection refused")

        adapter = self._adapter(transport=httpx.MockTransport(handler), max_retries=1)
        with self.assertRaises(httpx.ConnectError):
            adapter.embed_text("hello")
        self.assertEqual(2, calls["n"])

    def test_circuit_breaker_opens_after_threshold_failures(self) -> None:
        from app.rag.embeddings import CircuitBreakerOpenError, _CircuitBreaker

        breaker = _CircuitBreaker(failure_threshold=2, reset_timeout_seconds=60.0)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="down")

        adapter = self._adapter(
            transport=httpx.MockTransport(handler),
            max_retries=0,
            circuit_breaker=breaker,
        )
        # First two calls fail and trip the breaker.
        with self.assertRaises(httpx.HTTPStatusError):
            adapter.embed_text("a")
        with self.assertRaises(httpx.HTTPStatusError):
            adapter.embed_text("b")
        self.assertEqual("open", breaker.state)
        # Third call short-circuits without hitting the network.
        with self.assertRaises(CircuitBreakerOpenError):
            adapter.embed_text("c")

    def test_circuit_breaker_resets_on_success_in_half_open(self) -> None:
        from app.rag.embeddings import _CircuitBreaker

        breaker = _CircuitBreaker(failure_threshold=1, reset_timeout_seconds=0.05)

        def failing_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="down")

        adapter = self._adapter(
            transport=httpx.MockTransport(failing_handler),
            max_retries=0,
            circuit_breaker=breaker,
        )
        with self.assertRaises(httpx.HTTPStatusError):
            adapter.embed_text("a")
        self.assertEqual("open", breaker.state)

        # Wait for reset window → half-open. Use a generous margin to avoid
        # flakiness on slow CI runners.
        import time

        time.sleep(0.2)
        self.assertEqual("half_open", breaker.state)

        # Now swap to a succeeding handler.
        def ok_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"data": [{"embedding": [0.5]}]})

        ok_adapter = self._adapter(
            transport=httpx.MockTransport(ok_handler),
            max_retries=0,
            circuit_breaker=breaker,
        )
        result = ok_adapter.embed_text("b")
        self.assertEqual([0.5], result.vector)
        self.assertEqual("closed", breaker.state)

    def test_circuit_breaker_open_falls_back_to_local_hash_in_dev(self) -> None:
        from app.rag.embeddings import _CircuitBreaker

        settings.environment = "development"

        breaker = _CircuitBreaker(failure_threshold=1, reset_timeout_seconds=60.0)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="down")

        adapter = self._adapter(
            transport=httpx.MockTransport(handler),
            max_retries=0,
            circuit_breaker=breaker,
        )
        # First call trips the breaker.
        with self.assertRaises(httpx.HTTPStatusError):
            adapter.embed_text("a")
        # Second call: breaker open → dev fallback to local hash.
        result = adapter.embed_text("b")
        self.assertEqual("llm_gateway_openai_compatible+local_hash_fallback", result.mode)

    def test_circuit_breaker_open_raises_in_production(self) -> None:
        from app.rag.embeddings import CircuitBreakerOpenError, _CircuitBreaker

        breaker = _CircuitBreaker(failure_threshold=1, reset_timeout_seconds=60.0)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="down")

        adapter = self._adapter(
            transport=httpx.MockTransport(handler),
            max_retries=0,
            circuit_breaker=breaker,
        )
        with self.assertRaises(httpx.HTTPStatusError):
            adapter.embed_text("a")
        with self.assertRaises(CircuitBreakerOpenError):
            adapter.embed_text("b")

    def test_circuit_breaker_disabled_does_not_short_circuit(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(500, text="down")

        adapter = self._adapter(
            transport=httpx.MockTransport(handler),
            max_retries=0,
            circuit_breaker=None,
        )
        # No breaker → every call hits the network.
        with self.assertRaises(httpx.HTTPStatusError):
            adapter.embed_text("a")
        with self.assertRaises(httpx.HTTPStatusError):
            adapter.embed_text("b")
        self.assertEqual(2, calls["n"])

    def test_success_resets_failure_count(self) -> None:
        from app.rag.embeddings import _CircuitBreaker

        breaker = _CircuitBreaker(failure_threshold=3, reset_timeout_seconds=60.0)

        def fail_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="down")

        fail_adapter = self._adapter(
            transport=httpx.MockTransport(fail_handler),
            max_retries=0,
            circuit_breaker=breaker,
        )
        with self.assertRaises(httpx.HTTPStatusError):
            fail_adapter.embed_text("a")
        # 1 failure, breaker still closed.

        def ok_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"data": [{"embedding": [0.1]}]})

        ok_adapter = self._adapter(
            transport=httpx.MockTransport(ok_handler),
            max_retries=0,
            circuit_breaker=breaker,
        )
        ok_adapter.embed_text("b")
        self.assertEqual("closed", breaker.state)

        # 2 more failures needed to trip (success reset the count).
        with self.assertRaises(httpx.HTTPStatusError):
            fail_adapter.embed_text("c")
        self.assertEqual("closed", breaker.state)


if __name__ == "__main__":
    unittest.main()
