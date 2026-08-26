"""Pure post-processing for hybrid knowledge retrieval results."""

from typing import Any
from uuid import UUID

from app.rag.schemas import RAGChunk


def rrf_fuse(
    vector_chunks: list[RAGChunk],
    fts_rows: list[dict[str, Any]],
    *,
    k: int = 60,
    top_k: int,
) -> list[RAGChunk]:
    """Merge vector and FTS rankings with Reciprocal Rank Fusion in place."""
    scores: dict[str, float] = {}
    chunks_by_id: dict[str, RAGChunk] = {}
    for rank, chunk in enumerate(vector_chunks):
        chunk_id = chunk.chunk_id
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
        chunks_by_id[chunk_id] = chunk
    for rank, row in enumerate(fts_rows):
        chunk_id = str(row["chunk_id"])
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
        if chunk_id not in chunks_by_id:
            metadata = dict(row.get("metadata_json") or {})
            metadata.update(
                {
                    "chunk_index": row["chunk_index"],
                    "token_count": row["token_count"],
                    "fts_score": round(float(row["score"] or 0), 4),
                }
            )
            chunks_by_id[chunk_id] = RAGChunk(
                chunk_id=chunk_id,
                document_id=row["document_id"],
                text=row["text"],
                score=0.0,
                source_name=row["source_name"],
                metadata=metadata,
            )
    sorted_ids = sorted(scores, key=lambda chunk_id: scores[chunk_id], reverse=True)
    result: list[RAGChunk] = []
    for chunk_id in sorted_ids[:top_k]:
        chunk = chunks_by_id[chunk_id]
        chunk.metadata["rrf_score"] = round(scores[chunk_id], 4)
        result.append(chunk)
    return result


def chunk_matches_filters(
    *,
    document_id: UUID,
    source_name: str | None,
    filters: dict[str, Any],
) -> bool:
    """Apply optional document and source filters to a retrieval candidate."""
    if not filters:
        return True
    requested_document_id = filters.get("document_id")
    if requested_document_id and str(document_id) != str(requested_document_id):
        return False
    requested_source_name = filters.get("source_name")
    return not requested_source_name or source_name == requested_source_name
