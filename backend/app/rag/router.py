from app.rag.base import BaseRAGAdapter, BaseVectorStoreAdapter
from app.rag.cache import clear_rag_caches
from app.rag.pgvector import PGVectorAdapter
from app.rag.ragflow import RAGFlowAdapter
from app.rag.schemas import (
    DocumentIngestStatus,
    IngestRequest,
    IngestResult,
    RAGEngineType,
    RetrieveRequest,
    RetrieveResult,
    VectorSearchRequest,
)


class RAGRouter:
    """Route retrieval to the configured engine while keeping pgvector as fallback.

    When ``fallback_to_pgvector`` is enabled and a RAGFlow retrieve call fails
    (empty chunks + error diagnostic), the router transparently retries the
    query against the pgvector vector store so the agent's RAG context is not
    silently empty during RAGFlow outages. The fallback result preserves the
    original RAGFlow error in ``diagnostics`` for observability.
    """

    def __init__(
        self,
        *,
        ragflow: BaseRAGAdapter | None = None,
        vector_store: BaseVectorStoreAdapter | None = None,
        fallback_to_pgvector: bool | None = None,
    ) -> None:
        self.ragflow = ragflow or RAGFlowAdapter()
        self.vector_store = vector_store or PGVectorAdapter()
        from app.core.config import settings

        self.fallback_to_pgvector = (
            fallback_to_pgvector
            if fallback_to_pgvector is not None
            else settings.ragflow_fallback_to_pgvector
        )

    async def retrieve(
        self,
        request: RetrieveRequest,
        *,
        engine: RAGEngineType,
    ) -> RetrieveResult:
        if engine == RAGEngineType.RAGFLOW:
            result = await self.ragflow.retrieve(request)
            if self.fallback_to_pgvector and _is_ragflow_failure(result):
                return await self._fallback_to_pgvector(request, ragflow_result=result)
            return result
        return await self.vector_store.search(
            VectorSearchRequest(
                tenant_id=request.tenant_id,
                knowledge_base_id=request.knowledge_base_id,
                query=request.query,
                top_k=request.top_k,
                filters=request.filters,
            )
        )

    async def _fallback_to_pgvector(
        self,
        request: RetrieveRequest,
        *,
        ragflow_result: RetrieveResult,
    ) -> RetrieveResult:
        try:
            fallback = await self.vector_store.search(
                VectorSearchRequest(
                    tenant_id=request.tenant_id,
                    knowledge_base_id=request.knowledge_base_id,
                    query=request.query,
                    top_k=request.top_k,
                    filters=request.filters,
                )
            )
        except Exception as exc:
            # If pgvector itself fails, return the original RAGFlow failure
            # but annotate that the fallback also failed.
            return RetrieveResult(
                chunks=[],
                engine=RAGEngineType.RAGFLOW,
                elapsed_ms=ragflow_result.elapsed_ms,
                diagnostics={
                    **ragflow_result.diagnostics,
                    "pgvector_fallback_attempted": True,
                    "pgvector_fallback_error": exc.__class__.__name__,
                },
            )
        # Merge diagnostics so callers can see both the RAGFlow failure reason
        # and the fact that pgvector served the fallback.
        return RetrieveResult(
            chunks=fallback.chunks,
            engine=fallback.engine,
            elapsed_ms=fallback.elapsed_ms,
            diagnostics={
                **fallback.diagnostics,
                "ragflow_failure": ragflow_result.diagnostics,
                "pgvector_fallback_used": True,
            },
        )

    async def ingest(
        self,
        request: IngestRequest,
        *,
        engine: RAGEngineType,
    ) -> IngestResult:
        if engine == RAGEngineType.RAGFLOW:
            result = await self.ragflow.ingest(request)
            clear_rag_caches()
            return result
        return IngestResult(
            document_id=request.document_id,
            status=DocumentIngestStatus.PENDING,
            message=(
                "pgvector ingest is handled by the AgentHive knowledge service so it can "
                "read MinIO objects, parse text, write chunks, and persist embeddings in "
                "one database transaction."
            ),
            metadata={
                "delegated_to": "knowledge_service",
                "vector_store": self.vector_store.adapter_name,
            },
        )

    async def delete_document(
        self,
        *,
        engine: RAGEngineType,
        knowledge_base_id: str,
        document_id: str,
    ) -> bool:
        if engine == RAGEngineType.RAGFLOW:
            result = await self.ragflow.delete_document(knowledge_base_id, document_id)
        else:
            result = await self.vector_store.delete_document(knowledge_base_id, document_id)
        clear_rag_caches()
        return result


def _is_ragflow_failure(result: RetrieveResult) -> bool:
    """A RAGFlow retrieve is considered failed when it returns no chunks AND
    surfaces an error diagnostic (network error, retries exhausted, etc.).

    A successful retrieve that simply finds no matching chunks will have empty
    chunks but no ``error`` key in diagnostics, so it will NOT trigger fallback
    (we don't want to mask legitimate "no results" responses).
    """

    if result.chunks:
        return False
    diagnostics = result.diagnostics or {}
    return bool(
        diagnostics.get("error")
        or diagnostics.get("retries_exhausted")
        or diagnostics.get("ragflow_url_configured") is False
    )
