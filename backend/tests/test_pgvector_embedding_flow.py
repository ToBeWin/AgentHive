from uuid import uuid4
import unittest

from app.rag.embeddings import LocalHashEmbeddingService, vector_literal
from app.rag.schemas import RetrieveRequest
from app.services.knowledge_service import _retrieve_pgvector_embedding_chunks


class FakeMappingResult:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return self.rows


class FakeVectorSearchSession:
    def __init__(self, rows):
        self.rows = rows
        self.executed = []

    async def execute(self, statement, params=None):
        self.executed.append((statement, params or {}))
        return FakeMappingResult(self.rows)


class PGVectorEmbeddingFlowTest(unittest.IsolatedAsyncioTestCase):
    def test_local_hash_embedding_is_stable_and_normalized(self) -> None:
        service = LocalHashEmbeddingService(model_key="test-hash", dimensions=128)

        first = service.embed_text("七天无理由退货 policy")
        second = service.embed_text("七天无理由退货 policy")

        self.assertEqual(first.vector, second.vector)
        self.assertEqual(128, first.dimensions)
        self.assertEqual("test-hash", first.model_key)
        self.assertAlmostEqual(sum(value * value for value in first.vector), 1.0, places=5)

    def test_vector_literal_uses_pgvector_format(self) -> None:
        self.assertEqual("[0.10000000,-0.25000000]", vector_literal([0.1, -0.25]))

    async def test_vector_search_maps_rows_and_applies_filters(self) -> None:
        tenant_id = uuid4()
        knowledge_base_id = uuid4()
        matching_document_id = uuid4()
        skipped_document_id = uuid4()
        session = FakeVectorSearchSession(
            rows=[
                {
                    "chunk_id": str(uuid4()),
                    "document_id": matching_document_id,
                    "text": "七天内可以申请退货。",
                    "source_name": "售后.md",
                    "metadata_json": {"embedding_status": "ready"},
                    "chunk_index": 0,
                    "token_count": 12,
                    "score": 0.91,
                },
                {
                    "chunk_id": str(uuid4()),
                    "document_id": skipped_document_id,
                    "text": "不相关内容。",
                    "source_name": "其他.md",
                    "metadata_json": {},
                    "chunk_index": 1,
                    "token_count": 8,
                    "score": 0.88,
                },
            ]
        )

        result = await _retrieve_pgvector_embedding_chunks(
            session,
            RetrieveRequest(
                tenant_id=tenant_id,
                knowledge_base_id=knowledge_base_id,
                query="退货",
                top_k=3,
                filters={"document_id": str(matching_document_id)},
            ),
            started=0,
        )

        self.assertEqual("vector_similarity", result.diagnostics["retrieval_mode"])
        self.assertEqual("ready", result.diagnostics["embedding_status"])
        self.assertEqual(2, result.diagnostics["candidate_count"])
        self.assertEqual(1, len(result.chunks))
        self.assertEqual(matching_document_id, result.chunks[0].document_id)
        self.assertEqual(0.91, result.chunks[0].score)
        self.assertEqual("vector_lexical_max", result.chunks[0].metadata["score_strategy"])
        self.assertIn("query_embedding", session.executed[0][1])

    async def test_vector_search_blends_chinese_lexical_score_when_embedding_score_is_low(
        self,
    ) -> None:
        tenant_id = uuid4()
        knowledge_base_id = uuid4()
        document_id = uuid4()
        session = FakeVectorSearchSession(
            rows=[
                {
                    "chunk_id": str(uuid4()),
                    "document_id": document_id,
                    "text": "鞋子尺码偏小需要换大一码时，若客户签收后7天内、商品未穿着、吊牌和包装完整，可以引导客户发起换货。",
                    "source_name": "客服SOP.md",
                    "metadata_json": {},
                    "chunk_index": 0,
                    "token_count": 36,
                    "score": 0.0,
                }
            ]
        )

        result = await _retrieve_pgvector_embedding_chunks(
            session,
            RetrieveRequest(
                tenant_id=tenant_id,
                knowledge_base_id=knowledge_base_id,
                query="客户问鞋子尺码偏小，想换大一码，店铺规则怎么回复？",
                top_k=3,
            ),
            started=0,
        )

        self.assertEqual(1, len(result.chunks))
        self.assertGreater(result.chunks[0].score, 0.35)
        self.assertEqual(0.0, result.chunks[0].metadata["vector_score"])
        self.assertEqual(result.chunks[0].score, result.chunks[0].metadata["lexical_score"])
        self.assertEqual("vector_lexical_max", result.diagnostics["score_strategy"])

    async def test_vector_search_orders_by_blended_score_not_raw_vector_order(self) -> None:
        tenant_id = uuid4()
        knowledge_base_id = uuid4()
        session = FakeVectorSearchSession(
            rows=[
                {
                    "chunk_id": str(uuid4()),
                    "document_id": uuid4(),
                    "text": "客户咨询物流延迟时，先表达歉意并确认订单号。",
                    "source_name": "物流SOP.md",
                    "metadata_json": {},
                    "chunk_index": 0,
                    "token_count": 18,
                    "score": 0.01,
                },
                {
                    "chunk_id": str(uuid4()),
                    "document_id": uuid4(),
                    "text": "鞋子尺码偏小需要换大一码时，若客户签收后7天内且商品未穿着，可以引导客户发起换货。",
                    "source_name": "换货SOP.md",
                    "metadata_json": {},
                    "chunk_index": 1,
                    "token_count": 34,
                    "score": 0.0,
                },
            ]
        )

        result = await _retrieve_pgvector_embedding_chunks(
            session,
            RetrieveRequest(
                tenant_id=tenant_id,
                knowledge_base_id=knowledge_base_id,
                query="鞋子尺码偏小想换大一码",
                top_k=2,
            ),
            started=0,
        )

        self.assertEqual("换货SOP.md", result.chunks[0].source_name)
        self.assertGreater(result.chunks[0].score, result.chunks[1].score)


if __name__ == "__main__":
    unittest.main()
