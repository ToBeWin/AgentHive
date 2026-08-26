import json
from uuid import uuid4
import unittest

import httpx

from app.rag.ragflow import RAGFlowAdapter
from app.rag.schemas import (
    ComponentStatus,
    DocumentIngestStatus,
    IngestRequest,
    RetrieveRequest,
    StoredObjectRef,
)


class RAGFlowAdapterTest(unittest.IsolatedAsyncioTestCase):
    async def test_unconfigured_adapter_reports_not_configured(self) -> None:
        adapter = RAGFlowAdapter(base_url="")

        health = await adapter.health_check()
        result = await adapter.retrieve(
            RetrieveRequest(
                tenant_id=uuid4(),
                knowledge_base_id=uuid4(),
                query="退货",
            )
        )

        self.assertEqual(ComponentStatus.NOT_CONFIGURED, health.status)
        self.assertEqual([], result.chunks)
        self.assertFalse(result.diagnostics["ragflow_url_configured"])

    async def test_ingest_posts_agenthive_payload_and_maps_status(self) -> None:
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            captured["authorization"] = request.headers.get("authorization")
            captured["payload"] = json.loads(request.content.decode("utf-8"))
            body = {
                "status": "indexed",
                "external_document_id": "ragflow-doc-1",
                "message": "Indexed by RAGFlow.",
            }
            return httpx.Response(200, json=body)

        adapter = RAGFlowAdapter(
            base_url="http://ragflow.local",
            api_key="rag-key",
            client_factory=_client_factory(handler),
        )
        tenant_id = uuid4()
        knowledge_base_id = uuid4()
        document_id = uuid4()

        result = await adapter.ingest(
            IngestRequest(
                tenant_id=tenant_id,
                knowledge_base_id=knowledge_base_id,
                document_id=document_id,
                storage=StoredObjectRef(bucket="kb", object_key="doc.txt"),
                parser_config={"chunk_size": 500},
                metadata={"source": "test"},
            )
        )

        self.assertEqual("/api/v1/agenthive/ingest", captured["path"])
        self.assertEqual("Bearer rag-key", captured["authorization"])
        self.assertEqual(str(tenant_id), captured["payload"]["tenant_id"])
        self.assertEqual(str(knowledge_base_id), captured["payload"]["knowledge_base_id"])
        self.assertEqual(DocumentIngestStatus.INDEXED, result.status)
        self.assertEqual("ragflow-doc-1", result.external_document_id)
        self.assertEqual("Indexed by RAGFlow.", result.message)

    async def test_retrieve_maps_chunks_from_response(self) -> None:
        document_id = uuid4()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "chunks": [
                        {
                            "id": "chunk-1",
                            "document_id": str(document_id),
                            "content": "七天内可申请退货。",
                            "score": 0.88,
                            "source": "售后.md",
                            "metadata": {"page": 1},
                        }
                    ]
                },
            )

        adapter = RAGFlowAdapter(
            base_url="http://ragflow.local", client_factory=_client_factory(handler)
        )

        result = await adapter.retrieve(
            RetrieveRequest(
                tenant_id=uuid4(),
                knowledge_base_id=uuid4(),
                query="退货",
                top_k=3,
            )
        )

        self.assertEqual(1, len(result.chunks))
        self.assertEqual("chunk-1", result.chunks[0].chunk_id)
        self.assertEqual(document_id, result.chunks[0].document_id)
        self.assertEqual("售后.md", result.chunks[0].source_name)
        self.assertEqual(0.88, result.chunks[0].score)

    async def test_delete_uses_configured_path_placeholders(self) -> None:
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["path"] = request.url.path
            return httpx.Response(204)

        adapter = RAGFlowAdapter(
            base_url="http://ragflow.local", client_factory=_client_factory(handler)
        )
        knowledge_base_id = uuid4()
        document_id = uuid4()

        deleted = await adapter.delete_document(str(knowledge_base_id), str(document_id))

        self.assertTrue(deleted)
        self.assertEqual("DELETE", captured["method"])
        self.assertEqual(
            f"/api/v1/agenthive/documents/{knowledge_base_id}/{document_id}",
            captured["path"],
        )

    async def test_health_reports_error_for_auth_failure(self) -> None:
        adapter = RAGFlowAdapter(
            base_url="http://ragflow.local",
            api_key="bad-key",
            client_factory=_client_factory(lambda _request: httpx.Response(401)),
        )

        health = await adapter.health_check()

        self.assertEqual(ComponentStatus.ERROR, health.status)
        self.assertEqual(401, health.details["status_code"])


def _client_factory(handler):
    transport = httpx.MockTransport(handler)

    def factory(**kwargs):
        return httpx.AsyncClient(transport=transport, **kwargs)

    return factory


if __name__ == "__main__":
    unittest.main()
