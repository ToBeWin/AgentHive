from datetime import datetime, timezone
import unittest
from uuid import uuid4

from app.schemas.knowledge import (
    KnowledgeBaseResponse,
    KnowledgeBaseStatus,
    KnowledgeBaseVisibility,
    KnowledgeDocumentResponse,
    KnowledgeDocumentSource,
    KnowledgeDocumentStatus,
    RetrievalConfig,
)
from app.services.knowledge_service import _workbench_base_response, _workbench_document_response


class WorkbenchKnowledgeSafeResponseTest(unittest.TestCase):
    def test_workbench_base_response_hides_management_fields(self) -> None:
        now = datetime.now(timezone.utc)
        base = KnowledgeBaseResponse(
            id=uuid4(),
            tenant_id=uuid4(),
            name="客服 SOP",
            description="售后知识库",
            visibility=KnowledgeBaseVisibility.TENANT,
            department_ids=[uuid4()],
            rag_engine="pgvector",
            embedding_model_key="embedding-private",
            retrieval_config=RetrievalConfig(top_k=10, metadata_filters={"secret": "internal"}),
            status=KnowledgeBaseStatus.ACTIVE,
            document_count=3,
            tags=["customer-service"],
            metadata={
                "owner_user_id": str(uuid4()),
                "storage_boundary": "minio",
                "rag_boundary": "ragflow",
                "internal_note": "do not expose",
            },
            created_at=now,
            updated_at=now,
        )

        safe = _workbench_base_response(base).model_dump()

        self.assertEqual("客服 SOP", safe["name"])
        self.assertEqual(3, safe["document_count"])
        self.assertNotIn("tenant_id", safe)
        self.assertNotIn("rag_engine", safe)
        self.assertNotIn("embedding_model_key", safe)
        self.assertNotIn("retrieval_config", safe)
        self.assertNotIn("metadata", safe)

    def test_workbench_document_response_hides_storage_fields(self) -> None:
        now = datetime.now(timezone.utc)
        document = KnowledgeDocumentResponse(
            id=uuid4(),
            knowledge_base_id=uuid4(),
            tenant_id=uuid4(),
            filename="policy.md",
            content_type="text/markdown",
            size_bytes=1024,
            checksum_sha256="a" * 64,
            source=KnowledgeDocumentSource.API_UPLOAD,
            status=KnowledgeDocumentStatus.INDEXED,
            storage_bucket="agenthive-knowledge",
            storage_object_key="tenant/kb/doc/private.md",
            rag_document_id="rag-private-doc",
            chunk_count=12,
            error_message=None,
            metadata={
                "parser_config": {"ocr": True},
                "storage_metadata": {"etag": "secret"},
                "diagnostics": {"adapter": "internal"},
            },
            created_at=now,
            updated_at=now,
        )

        safe = _workbench_document_response(document).model_dump()

        self.assertEqual("policy.md", safe["filename"])
        self.assertEqual(1024, safe["size_bytes"])
        self.assertEqual(12, safe["chunk_count"])
        self.assertNotIn("tenant_id", safe)
        self.assertNotIn("checksum_sha256", safe)
        self.assertNotIn("storage_bucket", safe)
        self.assertNotIn("storage_object_key", safe)
        self.assertNotIn("rag_document_id", safe)
        self.assertNotIn("error_message", safe)
        self.assertNotIn("metadata", safe)


if __name__ == "__main__":
    unittest.main()
