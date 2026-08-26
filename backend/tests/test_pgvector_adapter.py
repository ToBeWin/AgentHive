from datetime import datetime, timezone
from uuid import uuid4
import unittest

from app.models.knowledge import KnowledgeChunk
from app.rag.pgvector import PGVectorAdapter
from app.rag.schemas import ComponentStatus, VectorSearchRequest


class FakeScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class FakeMappingResult:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return self.rows


class FakeScalars:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeSelectResult:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return FakeScalars(self.rows)


class FakeRowcountResult:
    def __init__(self, rowcount):
        self.rowcount = rowcount


class FakePGVectorSession:
    def __init__(self, *, schema_ready=True, vector_rows=None, text_rows=None, health_ok=True):
        self.schema_ready = schema_ready
        self.vector_rows = vector_rows or []
        self.text_rows = text_rows or []
        self.health_ok = health_ok
        self.executed_params = []
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def execute(self, statement, params=None):
        statement_text = str(statement)
        self.executed_params.append(params or {})
        if "pg_extension" in statement_text:
            return FakeScalarResult(self.schema_ready)
        if "SELECT 1" in statement_text:
            return FakeScalarResult(1 if self.health_ok else 0)
        if "embedding <=>" in statement_text:
            return FakeMappingResult(self.vector_rows)
        if statement_text.startswith("DELETE FROM knowledge_chunks"):
            return FakeRowcountResult(1)
        return FakeSelectResult(self.text_rows)

    async def commit(self):
        self.committed = True


class FakeSessionFactory:
    def __init__(self, session):
        self.session = session

    def __call__(self):
        return self.session


class PGVectorAdapterTest(unittest.IsolatedAsyncioTestCase):
    async def test_vector_search_maps_rows_and_uses_embedding_query(self) -> None:
        tenant_id = uuid4()
        knowledge_base_id = uuid4()
        document_id = uuid4()
        session = FakePGVectorSession(
            schema_ready=True,
            vector_rows=[
                {
                    "chunk_id": str(uuid4()),
                    "document_id": document_id,
                    "text": "七天内支持退货。",
                    "source_name": "售后.md",
                    "metadata_json": {"department": "support"},
                    "chunk_index": 0,
                    "token_count": 10,
                    "score": 0.92,
                }
            ],
        )
        adapter = PGVectorAdapter(session_factory=FakeSessionFactory(session))

        result = await adapter.search(
            VectorSearchRequest(
                tenant_id=tenant_id,
                knowledge_base_id=knowledge_base_id,
                query="退货",
                top_k=3,
                filters={"department": "support"},
            )
        )

        self.assertEqual("vector_similarity", result.diagnostics["retrieval_mode"])
        self.assertEqual(1, len(result.chunks))
        self.assertEqual(document_id, result.chunks[0].document_id)
        self.assertEqual(0.92, result.chunks[0].score)
        self.assertIn("query_embedding", session.executed_params[1])

    async def test_search_falls_back_to_text_chunks_when_schema_is_not_ready(self) -> None:
        tenant_id = uuid4()
        knowledge_base_id = uuid4()
        document_id = uuid4()
        chunk = KnowledgeChunk(
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            chunk_index=0,
            text="客户可以在七天内申请退货。",
            token_count=12,
            source_name="售后.md",
            search_text="客户 可以 在 七天 内 申请 退货",
            metadata_json={"department": "support"},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session = FakePGVectorSession(schema_ready=False, text_rows=[chunk])
        adapter = PGVectorAdapter(session_factory=FakeSessionFactory(session))

        result = await adapter.search(
            VectorSearchRequest(
                tenant_id=tenant_id,
                knowledge_base_id=knowledge_base_id,
                query="退货",
                top_k=3,
                filters={"source_name": "售后.md"},
            )
        )

        self.assertEqual("text_chunk_fallback", result.diagnostics["retrieval_mode"])
        self.assertEqual(1, len(result.chunks))
        self.assertEqual("售后.md", result.chunks[0].source_name)

    async def test_health_reports_degraded_when_schema_is_missing(self) -> None:
        session = FakePGVectorSession(schema_ready=False)
        adapter = PGVectorAdapter(session_factory=FakeSessionFactory(session))

        health = await adapter.health_check()

        self.assertEqual(ComponentStatus.DEGRADED, health.status)
        self.assertFalse(health.details["schema_ready"])

    async def test_delete_document_removes_chunk_rows(self) -> None:
        session = FakePGVectorSession()
        adapter = PGVectorAdapter(session_factory=FakeSessionFactory(session))

        deleted = await adapter.delete_document(str(uuid4()), str(uuid4()))

        self.assertTrue(deleted)
        self.assertTrue(session.committed)


if __name__ == "__main__":
    unittest.main()
