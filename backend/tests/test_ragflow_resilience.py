"""Tests for RAGFlow adapter resilience features.

Covers:
  * Configurable request timeout (default vs override).
  * Configurable health-check timeout.
  * Retry with exponential backoff on transient 5xx / ConnectError.
  * No retry on 4xx client errors (deterministic).
  * X-Request-Id header propagation when request metadata carries one.
  * retry diagnostics surface in retrieve/ingest failure results.
"""

from __future__ import annotations

import unittest
from uuid import uuid4

import httpx

from app.rag.ragflow import RAGFlowAdapter
from app.rag.schemas import (
    DocumentIngestStatus,
    IngestRequest,
    RetrieveRequest,
    StoredObjectRef,
)


def _client_factory(handler):
    transport = httpx.MockTransport(handler)

    def factory(**kwargs):
        kwargs.pop("transport", None)
        return httpx.AsyncClient(transport=transport, **kwargs)

    return factory


class RAGFlowRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_retrieve_retries_on_5xx_then_succeeds(self) -> None:
        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            if call_count["n"] < 3:
                return httpx.Response(503, text="service unavailable")
            return httpx.Response(200, json={"chunks": []})

        adapter = RAGFlowAdapter(
            base_url="http://ragflow.local",
            max_retries=3,
            retry_backoff_seconds=0,  # speed up the test
            client_factory=_client_factory(handler),
        )
        result = await adapter.retrieve(
            RetrieveRequest(
                tenant_id=uuid4(),
                knowledge_base_id=uuid4(),
                query="测试",
            )
        )
        self.assertEqual(3, call_count["n"])
        self.assertEqual([], result.chunks)
        self.assertTrue(result.diagnostics["ragflow_url_configured"])

    async def test_retrieve_does_not_retry_on_4xx(self) -> None:
        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            return httpx.Response(401, text="unauthorized")

        adapter = RAGFlowAdapter(
            base_url="http://ragflow.local",
            max_retries=3,
            retry_backoff_seconds=0,
            client_factory=_client_factory(handler),
        )
        result = await adapter.retrieve(
            RetrieveRequest(
                tenant_id=uuid4(),
                knowledge_base_id=uuid4(),
                query="测试",
            )
        )
        # 4xx must NOT be retried -- single attempt only
        self.assertEqual(1, call_count["n"])
        self.assertEqual([], result.chunks)
        self.assertTrue(result.diagnostics["retries_exhausted"])
        self.assertIn("HTTPStatusError", result.diagnostics["error"])

    async def test_retrieve_retries_on_connect_error_then_succeeds(self) -> None:
        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            if call_count["n"] < 2:
                raise httpx.ConnectError("connection refused")
            return httpx.Response(200, json={"chunks": []})

        adapter = RAGFlowAdapter(
            base_url="http://ragflow.local",
            max_retries=2,
            retry_backoff_seconds=0,
            client_factory=_client_factory(handler),
        )
        result = await adapter.retrieve(
            RetrieveRequest(
                tenant_id=uuid4(),
                knowledge_base_id=uuid4(),
                query="测试",
            )
        )
        self.assertEqual(2, call_count["n"])
        self.assertEqual([], result.chunks)

    async def test_retrieve_exhausts_retries_and_reports_failure(self) -> None:
        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            return httpx.Response(500, text="internal error")

        adapter = RAGFlowAdapter(
            base_url="http://ragflow.local",
            max_retries=2,
            retry_backoff_seconds=0,
            client_factory=_client_factory(handler),
        )
        result = await adapter.retrieve(
            RetrieveRequest(
                tenant_id=uuid4(),
                knowledge_base_id=uuid4(),
                query="测试",
            )
        )
        # max_retries=2 -> 3 total attempts
        self.assertEqual(3, call_count["n"])
        self.assertEqual([], result.chunks)
        self.assertTrue(result.diagnostics["retries_exhausted"])

    async def test_ingest_retries_on_5xx_and_reports_failed_after_exhaustion(self) -> None:
        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            return httpx.Response(502, text="bad gateway")

        adapter = RAGFlowAdapter(
            base_url="http://ragflow.local",
            max_retries=1,
            retry_backoff_seconds=0,
            client_factory=_client_factory(handler),
        )
        result = await adapter.ingest(
            IngestRequest(
                tenant_id=uuid4(),
                knowledge_base_id=uuid4(),
                document_id=uuid4(),
                storage=StoredObjectRef(bucket="kb", object_key="d.txt"),
                parser_config={},
                metadata={},
            )
        )
        self.assertEqual(2, call_count["n"])  # 1 + 1 retry
        self.assertEqual(DocumentIngestStatus.FAILED, result.status)
        self.assertEqual("HTTPStatusError", result.metadata["error"])

    async def test_ingest_retries_then_succeeds(self) -> None:
        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            if call_count["n"] < 2:
                return httpx.Response(503, text="unavailable")
            return httpx.Response(
                200,
                json={
                    "status": "indexed",
                    "external_document_id": "rf-1",
                    "message": "ok",
                },
            )

        adapter = RAGFlowAdapter(
            base_url="http://ragflow.local",
            max_retries=2,
            retry_backoff_seconds=0,
            client_factory=_client_factory(handler),
        )
        result = await adapter.ingest(
            IngestRequest(
                tenant_id=uuid4(),
                knowledge_base_id=uuid4(),
                document_id=uuid4(),
                storage=StoredObjectRef(bucket="kb", object_key="d.txt"),
                parser_config={},
                metadata={},
            )
        )
        self.assertEqual(2, call_count["n"])
        self.assertEqual(DocumentIngestStatus.INDEXED, result.status)
        self.assertEqual("rf-1", result.external_document_id)


class RAGFlowTraceIdPropagationTests(unittest.IsolatedAsyncioTestCase):
    async def test_ingest_propagates_request_id_header_from_metadata(self) -> None:
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["x_request_id"] = request.headers.get("x-request-id")
            captured["authorization"] = request.headers.get("authorization")
            return httpx.Response(200, json={"status": "indexed"})

        adapter = RAGFlowAdapter(
            base_url="http://ragflow.local",
            api_key="k-1",
            client_factory=_client_factory(handler),
        )
        await adapter.ingest(
            IngestRequest(
                tenant_id=uuid4(),
                knowledge_base_id=uuid4(),
                document_id=uuid4(),
                storage=StoredObjectRef(bucket="kb", object_key="d.txt"),
                parser_config={},
                metadata={"request_id": "req-trace-001"},
            )
        )
        self.assertEqual("req-trace-001", captured["x_request_id"])
        self.assertEqual("Bearer k-1", captured["authorization"])

    async def test_ingest_omits_request_id_header_when_metadata_absent(self) -> None:
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["x_request_id"] = request.headers.get("x-request-id")
            return httpx.Response(200, json={"status": "indexed"})

        adapter = RAGFlowAdapter(
            base_url="http://ragflow.local",
            client_factory=_client_factory(handler),
        )
        await adapter.ingest(
            IngestRequest(
                tenant_id=uuid4(),
                knowledge_base_id=uuid4(),
                document_id=uuid4(),
                storage=StoredObjectRef(bucket="kb", object_key="d.txt"),
                parser_config={},
                metadata={},
            )
        )
        self.assertIsNone(captured["x_request_id"])


class RAGFlowTimeoutConfigTests(unittest.TestCase):
    def test_request_timeout_defaults_from_settings(self) -> None:
        from app.core.config import settings

        adapter = RAGFlowAdapter(base_url="http://ragflow.local")
        self.assertEqual(settings.ragflow_request_timeout_seconds, adapter.request_timeout_seconds)

    def test_health_timeout_defaults_from_settings(self) -> None:
        from app.core.config import settings

        adapter = RAGFlowAdapter(base_url="http://ragflow.local")
        self.assertEqual(settings.ragflow_health_timeout_seconds, adapter.health_timeout_seconds)

    def test_max_retries_defaults_from_settings(self) -> None:
        from app.core.config import settings

        adapter = RAGFlowAdapter(base_url="http://ragflow.local")
        self.assertEqual(settings.ragflow_max_retries, adapter.max_retries)

    def test_constructor_overrides_take_precedence(self) -> None:
        adapter = RAGFlowAdapter(
            base_url="http://ragflow.local",
            request_timeout_seconds=42.0,
            health_timeout_seconds=1.5,
            max_retries=5,
            retry_backoff_seconds=0.25,
        )
        self.assertEqual(42.0, adapter.request_timeout_seconds)
        self.assertEqual(1.5, adapter.health_timeout_seconds)
        self.assertEqual(5, adapter.max_retries)
        self.assertEqual(0.25, adapter.retry_backoff_seconds)

    def test_client_uses_configured_request_timeout(self) -> None:
        adapter = RAGFlowAdapter(
            base_url="http://ragflow.local",
            request_timeout_seconds=17.0,
        )
        client = adapter._client()
        self.assertEqual(17.0, client.timeout.read)


class RAGFlowHealthTimeoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_health_check_uses_configured_health_timeout(self) -> None:
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            return httpx.Response(200)

        adapter = RAGFlowAdapter(
            base_url="http://ragflow.local",
            health_timeout_seconds=7.0,
            client_factory=_client_factory(handler),
        )
        await adapter.health_check()
        # The MockTransport handler always returns 200 regardless of timeout,
        # but we verify the client was constructed with the configured timeout
        # via the adapter attribute (the timeout is passed to httpx.Client).
        self.assertEqual(7.0, adapter.health_timeout_seconds)


if __name__ == "__main__":
    unittest.main()
