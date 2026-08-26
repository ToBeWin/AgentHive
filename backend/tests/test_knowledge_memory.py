from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4
import unittest

from app.api.deps import Principal
from app.rag.schemas import ObjectUploadPlan, RAGEngineType, StoredObjectRef
from app.schemas.knowledge import (
    DocumentUploadCompleteRequest,
    DocumentUploadPrepareRequest,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseResponse,
    KnowledgeBaseStatus,
    KnowledgeBaseVisibility,
    KnowledgeDocumentStatus,
    RetrievalConfig,
)
from app.services import knowledge_memory, knowledge_service


class KnowledgeMemoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        knowledge_memory._bases.clear()
        knowledge_memory._documents.clear()

    async def test_service_reexports_memory_state_and_operations(self) -> None:
        self.assertIs(knowledge_service._bases, knowledge_memory._bases)
        self.assertIs(knowledge_service._documents, knowledge_memory._documents)
        self.assertIs(
            knowledge_service._memory_prepare_document_upload,
            knowledge_memory._memory_prepare_document_upload,
        )
        self.assertIs(
            knowledge_service._memory_complete_document_upload,
            knowledge_memory._memory_complete_document_upload,
        )

    async def test_list_bases_scopes_memory_state_by_tenant_and_visibility(self) -> None:
        owner = _principal()
        same_tenant_user = _principal(tenant_id=owner.tenant_id)
        other_tenant_user = _principal()
        private_base = _create_base(owner, KnowledgeBaseVisibility.PRIVATE)
        tenant_base = _create_base(owner, KnowledgeBaseVisibility.TENANT)
        knowledge_memory._bases[private_base.id] = private_base
        knowledge_memory._bases[tenant_base.id] = tenant_base

        self.assertEqual(
            {private_base.id, tenant_base.id},
            {base.id for base in knowledge_memory._memory_list_knowledge_bases(owner).bases},
        )
        self.assertEqual(
            {tenant_base.id},
            {
                base.id
                for base in knowledge_memory._memory_list_knowledge_bases(same_tenant_user).bases
            },
        )
        self.assertEqual([], knowledge_memory._memory_list_knowledge_bases(other_tenant_user).bases)

    async def test_prepare_and_complete_upload_update_memory_state(self) -> None:
        principal = _principal()
        payload = KnowledgeBaseCreateRequest(name="Support KB")
        base = knowledge_memory._memory_create_knowledge_base(payload, principal)
        storage_ref = StoredObjectRef(
            bucket="agenthive-knowledge",
            object_key="tenants/example/document.txt",
            content_type="text/plain",
            size_bytes=4,
        )
        upload_plan = ObjectUploadPlan(storage=storage_ref)
        with patch.object(
            knowledge_memory._storage,
            "prepare_upload",
            new=AsyncMock(return_value=upload_plan),
        ):
            prepared = await knowledge_memory._memory_prepare_document_upload(
                base.id,
                DocumentUploadPrepareRequest(filename="document.txt", size_bytes=4),
                principal,
            )

        self.assertEqual(KnowledgeDocumentStatus.PENDING_UPLOAD, prepared.document.status)
        self.assertEqual(1, knowledge_memory._bases[base.id].document_count)
        completed = await knowledge_memory._memory_complete_document_upload(
            base.id,
            prepared.document.id,
            DocumentUploadCompleteRequest(auto_ingest=False, size_bytes=4),
            principal,
        )

        self.assertEqual(KnowledgeDocumentStatus.UPLOADED, completed.document.status)
        self.assertFalse(completed.auto_ingest)
        self.assertEqual(
            KnowledgeDocumentStatus.UPLOADED,
            knowledge_memory._documents[base.id][0].status,
        )


def _principal(*, tenant_id=None) -> Principal:
    return Principal(
        tenant_id=tenant_id or uuid4(),
        user_id=uuid4(),
        permissions={"knowledge:read", "knowledge:write"},
    )


def _create_base(
    principal: Principal, visibility: KnowledgeBaseVisibility
) -> KnowledgeBaseResponse:
    now = datetime.now(timezone.utc)
    return KnowledgeBaseResponse(
        id=uuid4(),
        tenant_id=principal.tenant_id,
        name="Support KB",
        description=None,
        visibility=visibility,
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


if __name__ == "__main__":
    unittest.main()
