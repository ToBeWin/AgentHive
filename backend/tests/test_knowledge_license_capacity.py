from datetime import datetime, timezone
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.api.deps import Principal
from app.models.knowledge import KnowledgeBase
from app.rag.schemas import ObjectUploadPlan, RAGEngineType, StoredObjectRef
from app.schemas.knowledge import (
    DocumentUploadPrepareRequest,
    KnowledgeBaseVisibility,
)
from app.services.knowledge_service import prepare_document_upload


class KnowledgeLicenseCapacityTests(unittest.IsolatedAsyncioTestCase):
    async def test_prepare_document_upload_checks_license_storage_capacity(self) -> None:
        tenant_id = uuid4()
        base = KnowledgeBase(
            id=uuid4(),
            tenant_id=tenant_id,
            name="Support KB",
            visibility=KnowledgeBaseVisibility.TENANT.value,
            department_ids=[],
            rag_engine=RAGEngineType.PGVECTOR.value,
            retrieval_config={},
            status="active",
            document_count=0,
            tags=[],
            metadata_json={"owner_user_id": str(uuid4())},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session = FakeKnowledgeUploadSession(base)
        principal = Principal(
            tenant_id=tenant_id,
            user_id=uuid4(),
            permissions={"tenant.admin", "knowledge:write"},
        )
        upload_plan = ObjectUploadPlan(
            storage=StoredObjectRef(
                bucket="agenthive-knowledge",
                object_key="tenants/test/documents/policy.md",
                content_type="text/markdown",
                size_bytes=4096,
            ),
            placeholder=True,
        )

        with (
            patch(
                "app.services.knowledge_service.ensure_license_capacity",
                new=AsyncMock(),
            ) as capacity_guard,
            patch(
                "app.services.knowledge_service._storage.prepare_upload",
                new=AsyncMock(return_value=upload_plan),
            ),
        ):
            response = await prepare_document_upload(
                session,
                base.id,
                DocumentUploadPrepareRequest(
                    filename="policy.md",
                    content_type="text/markdown",
                    size_bytes=4096,
                ),
                principal,
            )

        capacity_guard.assert_awaited_once_with(
            session,
            tenant_id=tenant_id,
            resource="knowledge_storage_bytes",
            increment=4096,
        )
        self.assertEqual(4096, response.document.size_bytes)
        self.assertEqual(1, session.commits)


class FakeKnowledgeUploadSession:
    def __init__(self, base: KnowledgeBase) -> None:
        self.base = base
        self.added: list[object] = []
        self.commits = 0
        self.refreshes = 0

    async def get(self, model, row_id):
        if model is KnowledgeBase and row_id == self.base.id:
            return self.base
        return None

    async def execute(self, _statement):
        return FakeScalarOneResult(0)

    def add(self, row: object) -> None:
        self.added.append(row)

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, _row: object) -> None:
        self.refreshes += 1


class FakeScalarOneResult:
    def __init__(self, value: int) -> None:
        self.value = value

    def scalar_one(self) -> int:
        return self.value


if __name__ == "__main__":
    unittest.main()
