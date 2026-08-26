from __future__ import annotations

from time import perf_counter
from typing import Any, cast
from uuid import UUID

from sqlalchemy import ColumnElement, CursorResult, delete, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlmodel import select

from app.core.database import AsyncSessionLocal
from app.models.knowledge import KnowledgeChunk
from app.rag.base import BaseVectorStoreAdapter
from app.rag.cache import EMBEDDING_CACHE, RETRIEVAL_CACHE
from app.rag.embeddings import (
    EmbeddingService,
    embed_text_nonblocking,
    get_default_embedding_service,
    vector_literal,
)
from app.rag.schemas import (
    ComponentStatus,
    HealthStatus,
    RAGChunk,
    RAGEngineType,
    RetrieveResult,
    VectorSearchRequest,
    VectorUpsertRequest,
)


class PGVectorAdapter(BaseVectorStoreAdapter):
    """AgentHive-owned pgvector vector store boundary."""

    adapter_name = "pgvector"

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self.session_factory = session_factory or AsyncSessionLocal
        self.embedding_service = embedding_service or get_default_embedding_service()

    async def upsert_chunks(self, request: VectorUpsertRequest) -> int:
        async with self.session_factory() as session:
            await session.execute(
                delete(KnowledgeChunk).where(
                    cast(ColumnElement[bool], KnowledgeChunk.document_id == request.document_id)
                )
            )
            written = 0
            for index, chunk in enumerate(request.chunks):
                embedding = await embed_text_nonblocking(self.embedding_service, chunk.text)
                row = KnowledgeChunk(
                    tenant_id=request.tenant_id,
                    knowledge_base_id=request.knowledge_base_id,
                    document_id=request.document_id,
                    chunk_index=index,
                    text=chunk.text,
                    token_count=_int_metadata(chunk.metadata.get("token_count")),
                    source_name=chunk.source_name,
                    search_text=_normalize_search_text(chunk.text),
                    metadata_json={
                        **request.metadata,
                        **chunk.metadata,
                        "embedding_status": "ready",
                        "embedding_model_key": embedding.model_key,
                        "embedding_mode": embedding.mode,
                        "embedding_dimensions": embedding.dimensions,
                        "vector_store": self.adapter_name,
                    },
                )
                session.add(row)
                await session.flush()
                await session.execute(
                    text(
                        """
                        UPDATE knowledge_chunks
                        SET embedding_model_key = :embedding_model_key,
                            embedding_dimensions = :embedding_dimensions,
                            embedding = CAST(:embedding AS vector)
                        WHERE id = :chunk_id
                        """
                    ),
                    {
                        "chunk_id": row.id,
                        "embedding_model_key": embedding.model_key,
                        "embedding_dimensions": embedding.dimensions,
                        "embedding": vector_literal(embedding.vector),
                    },
                )
                written += 1
            await session.commit()
            return written

    async def search(self, request: VectorSearchRequest) -> RetrieveResult:
        cache_key = (
            request.tenant_id,
            request.knowledge_base_id,
            request.query.strip().lower(),
            request.top_k,
            request.filters.get("document_id") if request.filters else None,
        )
        cached = RETRIEVAL_CACHE.get(cache_key)
        if cached is not None:
            return cast(RetrieveResult, cached)
        started = perf_counter()
        async with self.session_factory() as session:
            if await _pgvector_schema_ready(session):
                result = await self._vector_search(session, request, started=started)
                if result.chunks:
                    RETRIEVAL_CACHE.set(cache_key, result)
                    return result
            result = await self._text_fallback_search(session, request, started=started)
            if result.chunks:
                RETRIEVAL_CACHE.set(cache_key, result)
            return result

    async def delete_document(self, knowledge_base_id: str, document_id: str) -> bool:
        async with self.session_factory() as session:
            result = await session.execute(
                delete(KnowledgeChunk).where(
                    cast(
                        ColumnElement[bool],
                        KnowledgeChunk.knowledge_base_id == UUID(str(knowledge_base_id)),
                    ),
                    cast(ColumnElement[bool], KnowledgeChunk.document_id == UUID(str(document_id))),
                )
            )
            await session.commit()
            return bool(cast(CursorResult[Any], result).rowcount)

    async def health_check(self) -> HealthStatus:
        try:
            async with self.session_factory() as session:
                schema_ready = await _pgvector_schema_ready(session)
                basic_result = await session.execute(text("SELECT 1"))
                reachable = basic_result.scalar_one() == 1
        except Exception as exc:
            return HealthStatus(
                component="pgvector",
                status=ComponentStatus.ERROR,
                message=f"pgvector health check failed: {exc.__class__.__name__}.",
                details={"adapter": self.adapter_name},
            )

        if reachable and schema_ready:
            return HealthStatus(
                component="pgvector",
                status=ComponentStatus.HEALTHY,
                message="PostgreSQL pgvector schema is ready.",
                details={
                    "adapter": self.adapter_name,
                    "embedding_model_key": self.embedding_service.model_key,
                },
            )
        return HealthStatus(
            component="pgvector",
            status=ComponentStatus.DEGRADED,
            message="PostgreSQL is reachable, but pgvector chunk schema is not ready.",
            details={"adapter": self.adapter_name, "schema_ready": schema_ready},
        )

    async def _vector_search(
        self,
        session: AsyncSession,
        request: VectorSearchRequest,
        *,
        started: float,
    ) -> RetrieveResult:
        embedding_cache_key = (self.embedding_service.model_key, request.query.strip().lower())
        cached_embedding = EMBEDDING_CACHE.get(embedding_cache_key)
        if cached_embedding is not None:
            query_embedding = cached_embedding
        else:
            query_embedding = await embed_text_nonblocking(self.embedding_service, request.query)
            EMBEDDING_CACHE.set(embedding_cache_key, query_embedding)
        result = await session.execute(
            text(
                """
                SELECT
                    id::text AS chunk_id,
                    document_id,
                    text,
                    source_name,
                    metadata_json,
                    chunk_index,
                    token_count,
                    GREATEST(0, 1 - (embedding <=> CAST(:query_embedding AS vector))) AS score
                FROM knowledge_chunks
                WHERE tenant_id = :tenant_id
                  AND knowledge_base_id = :knowledge_base_id
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:query_embedding AS vector)
                LIMIT :limit
                """
            ),
            {
                "tenant_id": request.tenant_id,
                "knowledge_base_id": request.knowledge_base_id,
                "query_embedding": vector_literal(query_embedding.vector),
                "limit": max(request.top_k * 5, request.top_k),
            },
        )
        chunks: list[RAGChunk] = []
        candidate_count = 0
        for row in result.mappings().all():
            candidate_count += 1
            metadata = dict(row["metadata_json"] or {})
            if not _matches_filters(
                document_id=row["document_id"],
                source_name=row["source_name"],
                metadata=metadata,
                filters=request.filters,
            ):
                continue
            chunks.append(
                RAGChunk(
                    chunk_id=str(row["chunk_id"]),
                    document_id=row["document_id"],
                    text=row["text"],
                    score=round(float(row["score"] or 0), 4),
                    source_name=row["source_name"],
                    metadata={
                        **metadata,
                        "chunk_index": row["chunk_index"],
                        "token_count": row["token_count"],
                    },
                )
            )
            if len(chunks) >= request.top_k:
                break
        return RetrieveResult(
            chunks=chunks,
            engine=RAGEngineType.PGVECTOR,
            elapsed_ms=int((perf_counter() - started) * 1000),
            diagnostics={
                "retrieval_mode": "vector_similarity",
                "embedding_status": "ready",
                "embedding_model_key": query_embedding.model_key,
                "embedding_mode": query_embedding.mode,
                "candidate_count": candidate_count,
                "vector_schema_ready": True,
                "adapter": self.adapter_name,
            },
        )

    async def _text_fallback_search(
        self,
        session: AsyncSession,
        request: VectorSearchRequest,
        *,
        started: float,
    ) -> RetrieveResult:
        result = await session.execute(
            select(KnowledgeChunk)
            .where(
                KnowledgeChunk.tenant_id == request.tenant_id,
                KnowledgeChunk.knowledge_base_id == request.knowledge_base_id,
            )
            .order_by(
                cast(Any, KnowledgeChunk.updated_at).desc(),
                cast(Any, KnowledgeChunk.chunk_index).asc(),
            )
            .limit(1000)
        )
        terms = _query_terms(request.query)
        scored: list[tuple[float, KnowledgeChunk]] = []
        for chunk in result.scalars().all():
            if not _matches_filters(
                document_id=chunk.document_id,
                source_name=chunk.source_name,
                metadata=chunk.metadata_json,
                filters=request.filters,
            ):
                continue
            score = _score_text(chunk.search_text, terms, request.query)
            if score > 0 or not terms:
                scored.append((score, chunk))
        scored.sort(key=lambda item: (item[0], item[1].updated_at), reverse=True)
        return RetrieveResult(
            chunks=[
                RAGChunk(
                    chunk_id=str(chunk.id),
                    document_id=chunk.document_id,
                    text=chunk.text,
                    score=score,
                    source_name=chunk.source_name,
                    metadata={
                        **chunk.metadata_json,
                        "chunk_index": chunk.chunk_index,
                        "token_count": chunk.token_count,
                    },
                )
                for score, chunk in scored[: request.top_k]
            ],
            engine=RAGEngineType.PGVECTOR,
            elapsed_ms=int((perf_counter() - started) * 1000),
            diagnostics={
                "retrieval_mode": "text_chunk_fallback",
                "embedding_status": "ready_no_vector_hits",
                "candidate_count": len(scored),
                "query_terms": terms,
                "adapter": self.adapter_name,
            },
        )


async def _pgvector_schema_ready(session: AsyncSession) -> bool:
    try:
        result = await session.execute(
            text(
                """
                SELECT
                    EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')
                    AND (
                        SELECT COUNT(*)
                        FROM information_schema.columns
                        WHERE table_name = 'knowledge_chunks'
                          AND column_name IN ('embedding', 'embedding_dimensions', 'embedding_model_key')
                    ) = 3
                    AND EXISTS (
                        SELECT 1
                        FROM pg_indexes
                        WHERE tablename = 'knowledge_chunks'
                          AND indexname = 'ix_knowledge_chunks_embedding_cosine'
                    )
                """
            )
        )
        return bool(result.scalar_one())
    except (OSError, SQLAlchemyError):
        return False


def _matches_filters(
    *,
    document_id: UUID,
    source_name: str | None,
    metadata: dict[str, object],
    filters: dict[str, object],
) -> bool:
    if not filters:
        return True
    if filters.get("document_id") and str(document_id) != str(filters["document_id"]):
        return False
    if filters.get("source_name") and source_name != str(filters["source_name"]):
        return False
    for key, value in filters.items():
        if key in {"document_id", "source_name"}:
            continue
        if str(metadata.get(key)) != str(value):
            return False
    return True


def _normalize_search_text(value: str) -> str:
    return " ".join(value.lower().split())


def _query_terms(query: str) -> list[str]:
    return [term for term in _normalize_search_text(query).split(" ") if term]


def _score_text(search_text: str, terms: list[str], raw_query: str) -> float:
    if not terms:
        return 0.1
    matches = sum(1 for term in terms if term in search_text)
    exact_bonus = 1 if _normalize_search_text(raw_query) in search_text else 0
    return round((matches / len(terms)) + exact_bonus, 4)


def _int_metadata(value: object) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0
