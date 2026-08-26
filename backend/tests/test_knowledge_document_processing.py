from __future__ import annotations

import pytest

from app.knowledge.document_processing import (
    build_fts_query,
    build_fts_text,
    chunk_text,
    decode_document_text,
    normalize_search_text,
    query_terms,
    score_chunk,
    sha256_hex,
)


def test_plain_text_decode_and_checksum_are_deterministic() -> None:
    raw = b"AgentHive knowledge document"

    assert decode_document_text(raw, "text/plain", "guide.txt") == raw.decode()
    assert sha256_hex(raw) == "4b4330942b8800b7cc9db24fb3fece7cda189db71e6cbcd8afd0b336d2602c84"


def test_document_decode_rejects_empty_and_unsupported_uploads() -> None:
    with pytest.raises(ValueError, match="empty after text decoding"):
        decode_document_text(b"   ", "text/plain", "empty.txt")

    with pytest.raises(ValueError, match="Unsupported file type"):
        decode_document_text(b"binary", "application/octet-stream", "archive.bin")


def test_chunk_text_enforces_bounds_and_preserves_overlap() -> None:
    text = "a" * 260 + "b" * 260

    chunks = chunk_text(text, chunk_size=200, overlap=40)

    assert len(chunks) == 3
    assert all(len(chunk) <= 200 for chunk in chunks)
    assert chunks[0][-40:] == chunks[1][:40]
    assert chunks[1][-40:] == chunks[2][:40]


def test_cjk_search_terms_produce_fts_text_and_query() -> None:
    terms = query_terms("退货政策, Return policy!")

    assert normalize_search_text("退货政策, Return policy!") == "退货政策 return policy"
    assert {"退货", "货政", "政策", "return", "policy"}.issubset(terms)
    assert build_fts_text("退货政策") == "退货政策 退货 货政 政策"
    assert build_fts_query("退货政策") == "退货政策 | 退货 | 货政 | 政策"


def test_chunk_scoring_rewards_exact_and_repeated_matches() -> None:
    terms = query_terms("预算 policy")
    matching = score_chunk("预算 policy policy", terms, "预算 policy")
    unrelated = score_chunk("inventory status", terms, "预算 policy")

    assert matching > unrelated
    assert unrelated == 0.0
