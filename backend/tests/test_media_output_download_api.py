import unittest
from uuid import UUID
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.media import router as media_router
from app.core.database import get_session
from app.core.security import Permission, create_access_token
from app.models.audit_log import AuditLog
from app.models.media import MediaGenerationJob
from app.models.tenant import Tenant
from app.models.user import User
from app.rag.schemas import StoredObjectRef


class MediaOutputDownloadApiTests(unittest.TestCase):
    def test_download_output_returns_attachment_and_records_audit(self):
        session = FakeMediaDownloadApiSession()
        client = _client(session)
        storage = FakeStorage(data=b"api-output")

        with patch(
            "app.services.media_output_download_service.MinIOObjectStorageAdapter",
            new=lambda: storage,
        ):
            response = client.get(
                f"/api/v1/media/generations/{session.job_id}/outputs/0/download",
                headers={"Authorization": f"Bearer {_token(Permission.AGENTS_READ)}"},
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual(b"api-output", response.content)
        self.assertEqual("video/mp4", response.headers["content-type"])
        self.assertIn("attachment;", response.headers["content-disposition"])
        audit_events = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual(1, len(audit_events))
        self.assertEqual("media.output.download", audit_events[0].action)
        self.assertEqual(session.job_id, audit_events[0].resource_id)
        self.assertEqual(1, session.commits)

    def test_download_output_rejects_missing_agent_read_permission(self):
        session = FakeMediaDownloadApiSession()
        client = _client(session)

        response = client.get(
            f"/api/v1/media/generations/{session.job_id}/outputs/0/download",
            headers={"Authorization": f"Bearer {_token(Permission.ANALYTICS_READ)}"},
        )

        self.assertEqual(403, response.status_code)


class FakeMediaDownloadApiSession:
    def __init__(self):
        self.user_id = UUID("00000000-0000-4000-8000-000000000301")
        self.tenant_id = UUID("00000000-0000-4000-8000-000000000401")
        self.job_id = UUID("00000000-0000-4000-8000-000000000501")
        self.added: list[object] = []
        self.commits = 0

    def add(self, row):
        self.added.append(row)

    async def get(self, model, row_id):
        if model is User and row_id == self.user_id:
            return User(
                id=self.user_id,
                tenant_id=self.tenant_id,
                email="operator@example.com",
                hashed_password="bcrypt-sha256$placeholder",
                is_active=True,
            )
        if model is Tenant and row_id == self.tenant_id:
            return Tenant(id=self.tenant_id, name="Demo", slug="demo", is_active=True)
        if model is MediaGenerationJob and row_id == self.job_id:
            return MediaGenerationJob(
                id=self.job_id,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                kind="video",
                mode="manual_prompt",
                status="succeeded",
                provider_key="volcengine",
                provider_type="volcengine_seedance",
                model_key="volcengine/seedance-2.0",
                routing_key="video-generation",
                prompt="test prompt",
                normalized_parameters={},
                output_storage={
                    "driver": "minio",
                    "bucket": "agenthive-media",
                    "prefix": "generated/video",
                    "tenant_id": str(self.tenant_id),
                },
                outputs=[
                    {
                        "bucket": "agenthive-media",
                        "object_key": (
                            "generated/video/tenants/"
                            f"{self.tenant_id}/jobs/{self.job_id}/result.mp4"
                        ),
                        "mime_type": "video/mp4",
                        "size_bytes": 10,
                        "storage_metadata": {"storage_backend": "minio"},
                    }
                ],
                metadata_json={},
            )
        return None

    async def commit(self):
        self.commits += 1


class FakeStorage:
    def __init__(self, *, data: bytes):
        self.data = data
        self.read_ref: StoredObjectRef | None = None

    async def get_object(self, storage: StoredObjectRef) -> bytes:
        self.read_ref = storage
        return self.data


def _client(session: FakeMediaDownloadApiSession) -> TestClient:
    app = FastAPI()
    app.include_router(media_router, prefix="/api/v1")

    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app)


def _token(*permissions: Permission) -> str:
    return create_access_token(
        subject=UUID("00000000-0000-4000-8000-000000000301"),
        tenant_id=UUID("00000000-0000-4000-8000-000000000401"),
        permissions=[permission.value for permission in permissions],
    )


if __name__ == "__main__":
    unittest.main()
