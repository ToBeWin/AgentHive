from __future__ import annotations

from uuid import uuid4

from app.knowledge.retrieval_postprocessing import chunk_matches_filters, rrf_fuse
from app.rag.schemas import RAGChunk


def test_rrf_fuse_prefers_candidates_present_in_both_rankings_and_preserves_metadata() -> None:
    document_id = uuid4()
    vector_chunk = RAGChunk(
        chunk_id="shared",
        document_id=document_id,
        text="Vector source",
        score=0.9,
        source_name="guide.md",
        metadata={"vector_score": 0.9},
    )

    fused = rrf_fuse(
        [vector_chunk],
        [
            {
                "chunk_id": "shared",
                "document_id": document_id,
                "text": "FTS duplicate",
                "source_name": "guide.md",
                "metadata_json": {},
                "chunk_index": 1,
                "token_count": 10,
                "score": 0.7,
            },
            {
                "chunk_id": "fts-only",
                "document_id": document_id,
                "text": "FTS source",
                "source_name": "policy.md",
                "metadata_json": {"origin": "fts"},
                "chunk_index": 2,
                "token_count": 20,
                "score": 0.4,
            },
        ],
        top_k=2,
    )

    assert [chunk.chunk_id for chunk in fused] == ["shared", "fts-only"]
    assert fused[0] is vector_chunk
    assert fused[0].metadata["rrf_score"] == 0.0328
    assert fused[1].metadata == {
        "origin": "fts",
        "chunk_index": 2,
        "token_count": 20,
        "fts_score": 0.4,
        "rrf_score": 0.0161,
    }


def test_chunk_filters_keep_document_and_source_matching_semantics() -> None:
    document_id = uuid4()

    assert chunk_matches_filters(
        document_id=document_id,
        source_name="policy.md",
        filters={"document_id": str(document_id), "source_name": "policy.md"},
    )
    assert not chunk_matches_filters(
        document_id=document_id,
        source_name="policy.md",
        filters={"source_name": "other.md"},
    )
    assert not chunk_matches_filters(
        document_id=document_id,
        source_name="policy.md",
        filters={"document_id": str(uuid4())},
    )
