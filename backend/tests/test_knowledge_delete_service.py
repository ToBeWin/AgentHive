from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4
import unittest

from fastapi import HTTPException

from app.api.deps import Principal
from app.rag.schemas import DocumentIngestStatus, IngestResult, RAGEngineType
from app.schemas.knowledge import (
    KnowledgeBaseResponse,
    KnowledgeBaseStatus,
    KnowledgeBaseVisibility,
    KnowledgeDocumentResponse,
    KnowledgeDocumentSource,
    KnowledgeDocumentStatus,
    RetrievalConfig,
)
from app.services.knowledge_service import (
    _bases,
    _count_documents_for_base,
    _documents,
    _memory_delete_knowledge_base,
    _memory_delete_knowledge_document,
    _memory_reingest_knowledge_document,
)


class KnowledgeDeleteServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        _bases.clear()
        _documents.clear()

    async def test_memory_delete_document_hides_document_and_updates_base_count(self) -> None:
        principal = _principal()
        base = _base(principal)
        document = _document(principal, base.id)
        _bases[base.id] = base.model_copy(update={"document_count": 1})
        _documents[base.id] = [document]

        response = await _memory_delete_knowledge_document(base.id, document.id, principal)

        self.assertTrue(response.deleted)
        self.assertEqual(document.id, response.id)
        self.assertEqual([], _documents[base.id])
        self.assertEqual(0, _bases[base.id].document_count)
        self.assertEqual("development_memory_fallback", response.diagnostics["persistence"])

    async def test_memory_delete_base_removes_base_and_documents(self) -> None:
        principal = _principal()
        base = _base(principal)
        document = _document(principal, base.id)
        _bases[base.id] = base.model_copy(update={"document_count": 1})
        _documents[base.id] = [document]

        response = await _memory_delete_knowledge_base(base.id, principal)

        self.assertTrue(response.deleted)
        self.assertEqual(base.id, response.id)
        self.assertNotIn(base.id, _bases)
        self.assertNotIn(base.id, _documents)
        self.assertEqual(1, response.diagnostics["document_count"])

    async def test_memory_reingest_document_reindexes_existing_document(self) -> None:
        principal = _principal()
        base = _base(principal)
        document = _document(principal, base.id)
        _bases[base.id] = base.model_copy(update={"document_count": 1})
        _documents[base.id] = [document]

        ingest_result = IngestResult(
            document_id=document.id,
            status=DocumentIngestStatus.INDEXED,
            external_document_id="rag-doc-new",
            message="Indexed again.",
            metadata={"chunk_count": 3},
        )
        with patch(
            "app.services.knowledge_service._rag_router.ingest",
            new=AsyncMock(return_value=ingest_result),
        ):
            response = await _memory_reingest_knowledge_document(base.id, document.id, principal)

        self.assertEqual(KnowledgeDocumentStatus.INDEXED, response.document.status)
        self.assertEqual("rag-doc-new", response.document.rag_document_id)
        self.assertEqual(3, response.document.chunk_count)
        self.assertTrue(response.document.metadata["reingest"])
        self.assertIn("reingest_cleanup", response.document.metadata)
        self.assertEqual(DocumentIngestStatus.INDEXED.value, response.diagnostics["adapter_status"])

    async def test_memory_reingest_rejects_pending_upload_document(self) -> None:
        principal = _principal()
        base = _base(principal)
        document = _document(principal, base.id).model_copy(
            update={"status": KnowledgeDocumentStatus.PENDING_UPLOAD}
        )
        _bases[base.id] = base.model_copy(update={"document_count": 1})
        _documents[base.id] = [document]

        with self.assertRaises(HTTPException) as context:
            await _memory_reingest_knowledge_document(base.id, document.id, principal)

        self.assertEqual(409, context.exception.status_code)

    async def test_document_count_query_is_tenant_scoped(self) -> None:
        tenant_id = uuid4()
        knowledge_base_id = uuid4()
        session = FakeCountSession(value=2)

        count = await _count_documents_for_base(
            session,
            knowledge_base_id,
            tenant_id=tenant_id,
        )

        self.assertEqual(2, count)
        statement_text = str(session.statement)
        self.assertIn("knowledge_documents.tenant_id", statement_text)
        self.assertIn("knowledge_documents.knowledge_base_id", statement_text)
        self.assertIn("knowledge_documents.deleted_at IS NULL", statement_text)


def _principal() -> Principal:
    return Principal(
        tenant_id=uuid4(),
        user_id=uuid4(),
        permissions={"knowledge:read", "knowledge:write"},
    )


def _base(principal: Principal) -> KnowledgeBaseResponse:
    now = datetime.now(timezone.utc)
    return KnowledgeBaseResponse(
        id=uuid4(),
        tenant_id=principal.tenant_id,
        name="Support KB",
        description=None,
        visibility=KnowledgeBaseVisibility.PRIVATE,
        department_ids=[],
        rag_engine=RAGEngineType.PGVECTOR,
        embedding_model_key=None,
        retrieval_config=RetrievalConfig(),
        status=KnowledgeBaseStatus.ACTIVE,
        document_count=0,
        tags=[],
        metadata={"owner_user_id": str(principal.user_id)},
        created_at=now,
        updated_at=now,
    )


def _document(principal: Principal, base_id: UUID) -> KnowledgeDocumentResponse:
    now = datetime.now(timezone.utc)
    return KnowledgeDocumentResponse(
        id=uuid4(),
        knowledge_base_id=base_id,
        tenant_id=principal.tenant_id,
        filename="policy.md",
        content_type="text/markdown",
        size_bytes=128,
        checksum_sha256=None,
        source=KnowledgeDocumentSource.API_UPLOAD,
        status=KnowledgeDocumentStatus.INDEXED,
        storage_bucket="agenthive-knowledge",
        storage_object_key="tenants/test/policy.md",
        rag_document_id=None,
        chunk_count=2,
        error_message=None,
        metadata={},
        created_at=now,
        updated_at=now,
    )


class FakeCountSession:
    def __init__(self, value: int) -> None:
        self.value = value
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return FakeScalarOneResult(self.value)


class FakeScalarOneResult:
    def __init__(self, value: int) -> None:
        self.value = value

    def scalar_one(self) -> int:
        return self.value


if __name__ == "__main__":
    unittest.main()
