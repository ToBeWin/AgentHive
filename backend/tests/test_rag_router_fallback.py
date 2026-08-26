"""Tests for RAGRouter fallback behavior.

Covers:
  * When fallback is disabled (default), RAGFlow failures pass through unchanged.
  * When fallback is enabled and RAGFlow retrieve fails, pgvector serves results.
  * A successful RAGFlow retrieve with zero chunks does NOT trigger fallback
    (legitimate "no results" must not be masked).
  * When pgvector fallback itself raises, the original RAGFlow failure is
    returned with an annotation.
  * Fallback diagnostics preserve the original RAGFlow error for observability.
"""

from __future__ import annotations

import unittest
from uuid import uuid4

from app.rag.base import BaseRAGAdapter, BaseVectorStoreAdapter
from app.rag.router import RAGRouter, _is_ragflow_failure
from app.rag.schemas import (
    ComponentStatus,
    DocumentIngestStatus,
    HealthStatus,
    IngestRequest,
    IngestResult,
    RAGEngineType,
    RetrieveRequest,
    RetrieveResult,
    VectorSearchRequest,
)
from app.rag.schemas import RAGChunk


class _FakeRAGFlow(BaseRAGAdapter):
    adapter_name = "fake_ragflow"

    def __init__(self, retrieve_result: RetrieveResult) -> None:
        self.retrieve_result = retrieve_result
        self.retrieve_called = 0

    async def ingest(self, request: IngestRequest) -> IngestResult:
        return IngestResult(
            document_id=request.document_id,
            status=DocumentIngestStatus.ACCEPTED,
            message="ok",
            metadata={},
        )

    async def retrieve(self, request: RetrieveRequest) -> RetrieveResult:
        self.retrieve_called += 1
        return self.retrieve_result

    async def delete_document(self, knowledge_base_id: str, document_id: str) -> bool:
        return True

    async def health_check(self) -> HealthStatus:
        return HealthStatus(
            component="ragflow",
            status=ComponentStatus.HEALTHY,
            message="ok",
            details={},
        )


class _FakeVectorStore(BaseVectorStoreAdapter):
    adapter_name = "fake_pgvector"

    def __init__(
        self,
        search_result: RetrieveResult | None = None,
        search_exc: Exception | None = None,
    ) -> None:
        self.search_result = search_result
        self.search_exc = search_exc
        self.search_called = 0

    async def upsert_chunks(self, request):
        return 0

    async def search(self, request: VectorSearchRequest) -> RetrieveResult:
        self.search_called += 1
        if self.search_exc is not None:
            raise self.search_exc
        assert self.search_result is not None
        return self.search_result

    async def delete_document(self, knowledge_base_id: str, document_id: str) -> bool:
        return True

    async def health_check(self) -> HealthStatus:
        return HealthStatus(
            component="pgvector",
            status=ComponentStatus.HEALTHY,
            message="ok",
            details={},
        )


def _retrieve_request() -> RetrieveRequest:
    return RetrieveRequest(
        tenant_id=uuid4(),
        knowledge_base_id=uuid4(),
        query="退货",
        top_k=5,
    )


class IsRagFlowFailureTests(unittest.TestCase):
    def test_empty_chunks_with_error_is_failure(self) -> None:
        result = RetrieveResult(
            chunks=[],
            engine=RAGEngineType.RAGFLOW,
            elapsed_ms=10,
            diagnostics={"error": "HTTPStatusError: 503"},
        )
        self.assertTrue(_is_ragflow_failure(result))

    def test_empty_chunks_with_retries_exhausted_is_failure(self) -> None:
        result = RetrieveResult(
            chunks=[],
            engine=RAGEngineType.RAGFLOW,
            elapsed_ms=10,
            diagnostics={"retries_exhausted": True},
        )
        self.assertTrue(_is_ragflow_failure(result))

    def test_empty_chunks_without_error_is_not_failure(self) -> None:
        """Legitimate 'no results' must NOT trigger fallback."""
        result = RetrieveResult(
            chunks=[],
            engine=RAGEngineType.RAGFLOW,
            elapsed_ms=10,
            diagnostics={"ragflow_url_configured": True, "candidate_count": 0},
        )
        self.assertFalse(_is_ragflow_failure(result))

    def test_non_empty_chunks_is_not_failure(self) -> None:
        result = RetrieveResult(
            chunks=[
                RAGChunk(
                    chunk_id="c1",
                    document_id=None,
                    text="x",
                    score=0.5,
                    source_name=None,
                    metadata={},
                )
            ],
            engine=RAGEngineType.RAGFLOW,
            elapsed_ms=10,
            diagnostics={"error": "ignored"},
        )
        self.assertFalse(_is_ragflow_failure(result))

    def test_unconfigured_ragflow_is_failure(self) -> None:
        result = RetrieveResult(
            chunks=[],
            engine=RAGEngineType.RAGFLOW,
            elapsed_ms=0,
            diagnostics={"ragflow_url_configured": False},
        )
        self.assertTrue(_is_ragflow_failure(result))


class RAGRouterFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_fallback_disabled_passes_through_ragflow_failure(self) -> None:
        ragflow_failure = RetrieveResult(
            chunks=[],
            engine=RAGEngineType.RAGFLOW,
            elapsed_ms=10,
            diagnostics={"error": "ConnectError"},
        )
        ragflow = _FakeRAGFlow(ragflow_failure)
        vector_store = _FakeVectorStore(
            search_result=RetrieveResult(
                chunks=[
                    RAGChunk(
                        chunk_id="pgv-1",
                        document_id=None,
                        text="fallback",
                        score=0.5,
                        source_name=None,
                        metadata={},
                    )
                ],
                engine=RAGEngineType.PGVECTOR,
                elapsed_ms=5,
                diagnostics={},
            )
        )
        router = RAGRouter(
            ragflow=ragflow,
            vector_store=vector_store,
            fallback_to_pgvector=False,
        )
        result = await router.retrieve(_retrieve_request(), engine=RAGEngineType.RAGFLOW)

        self.assertEqual(RAGEngineType.RAGFLOW, result.engine)
        self.assertEqual([], result.chunks)
        self.assertEqual(0, vector_store.search_called)

    async def test_fallback_enabled_serves_pgvector_when_ragflow_fails(self) -> None:
        ragflow_failure = RetrieveResult(
            chunks=[],
            engine=RAGEngineType.RAGFLOW,
            elapsed_ms=10,
            diagnostics={"error": "ConnectError", "retries_exhausted": True},
        )
        ragflow = _FakeRAGFlow(ragflow_failure)
        fallback_chunk = RAGChunk(
            chunk_id="pgv-1",
            document_id=None,
            text="fallback content",
            score=0.7,
            source_name="doc.md",
            metadata={},
        )
        vector_store = _FakeVectorStore(
            search_result=RetrieveResult(
                chunks=[fallback_chunk],
                engine=RAGEngineType.PGVECTOR,
                elapsed_ms=5,
                diagnostics={"source": "pgvector"},
            )
        )
        router = RAGRouter(
            ragflow=ragflow,
            vector_store=vector_store,
            fallback_to_pgvector=True,
        )
        result = await router.retrieve(_retrieve_request(), engine=RAGEngineType.RAGFLOW)

        self.assertEqual(RAGEngineType.PGVECTOR, result.engine)
        self.assertEqual(1, len(result.chunks))
        self.assertEqual("pgv-1", result.chunks[0].chunk_id)
        self.assertEqual(1, ragflow.retrieve_called)
        self.assertEqual(1, vector_store.search_called)
        # Diagnostics preserve both the RAGFlow failure and the fallback flag
        self.assertTrue(result.diagnostics["pgvector_fallback_used"])
        self.assertEqual("ConnectError", result.diagnostics["ragflow_failure"]["error"])
        self.assertEqual("pgvector", result.diagnostics["source"])

    async def test_fallback_not_triggered_when_ragflow_succeeds_with_zero_chunks(self) -> None:
        """Legitimate zero-chunk RAGFlow response must not fall back."""
        ragflow_success_empty = RetrieveResult(
            chunks=[],
            engine=RAGEngineType.RAGFLOW,
            elapsed_ms=10,
            diagnostics={"ragflow_url_configured": True, "candidate_count": 0},
        )
        ragflow = _FakeRAGFlow(ragflow_success_empty)
        vector_store = _FakeVectorStore(
            search_result=RetrieveResult(
                chunks=[
                    RAGChunk(
                        chunk_id="pgv-1",
                        document_id=None,
                        text="x",
                        score=0.5,
                        source_name=None,
                        metadata={},
                    )
                ],
                engine=RAGEngineType.PGVECTOR,
                elapsed_ms=5,
                diagnostics={},
            )
        )
        router = RAGRouter(
            ragflow=ragflow,
            vector_store=vector_store,
            fallback_to_pgvector=True,
        )
        result = await router.retrieve(_retrieve_request(), engine=RAGEngineType.RAGFLOW)

        self.assertEqual(RAGEngineType.RAGFLOW, result.engine)
        self.assertEqual([], result.chunks)
        self.assertEqual(0, vector_store.search_called)

    async def test_fallback_when_pgvector_itself_raises_returns_ragflow_failure(self) -> None:
        ragflow_failure = RetrieveResult(
            chunks=[],
            engine=RAGEngineType.RAGFLOW,
            elapsed_ms=10,
            diagnostics={"error": "ConnectError"},
        )
        ragflow = _FakeRAGFlow(ragflow_failure)
        vector_store = _FakeVectorStore(search_exc=RuntimeError("pgvector down"))
        router = RAGRouter(
            ragflow=ragflow,
            vector_store=vector_store,
            fallback_to_pgvector=True,
        )
        result = await router.retrieve(_retrieve_request(), engine=RAGEngineType.RAGFLOW)

        # Fallback failed too -> return original RAGFlow failure shape
        self.assertEqual(RAGEngineType.RAGFLOW, result.engine)
        self.assertEqual([], result.chunks)
        self.assertTrue(result.diagnostics["pgvector_fallback_attempted"])
        self.assertEqual("RuntimeError", result.diagnostics["pgvector_fallback_error"])
        self.assertEqual("ConnectError", result.diagnostics["error"])

    async def test_fallback_with_successful_ragflow_chunks_does_not_call_pgvector(self) -> None:
        ragflow_success = RetrieveResult(
            chunks=[
                RAGChunk(
                    chunk_id="rf-1",
                    document_id=None,
                    text="x",
                    score=0.9,
                    source_name=None,
                    metadata={},
                )
            ],
            engine=RAGEngineType.RAGFLOW,
            elapsed_ms=10,
            diagnostics={},
        )
        ragflow = _FakeRAGFlow(ragflow_success)
        vector_store = _FakeVectorStore()
        router = RAGRouter(
            ragflow=ragflow,
            vector_store=vector_store,
            fallback_to_pgvector=True,
        )
        result = await router.retrieve(_retrieve_request(), engine=RAGEngineType.RAGFLOW)

        self.assertEqual(RAGEngineType.RAGFLOW, result.engine)
        self.assertEqual(1, len(result.chunks))
        self.assertEqual(0, vector_store.search_called)


if __name__ == "__main__":
    unittest.main()
