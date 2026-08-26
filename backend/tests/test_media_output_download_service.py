import unittest
from uuid import uuid4

from fastapi import HTTPException

from app.api.deps import Principal
from app.models.audit_log import AuditLog
from app.models.media import MediaGenerationJob
from app.rag.schemas import StoredObjectRef
from app.services.media_output_download_service import download_media_generation_output


class MediaOutputDownloadServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_archived_output_can_be_downloaded_by_same_tenant(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:read"})
        job = _job(tenant_id=tenant_id, user_id=principal.user_id)
        storage = FakeStorage(data=b"private-output")
        session = FakeDownloadSession(rows=[job])

        response = await download_media_generation_output(
            session,
            principal,
            job.id,
            0,
            request_id="req-download",
            ip_address="127.0.0.1",
            user_agent="pytest",
            storage=storage,
        )

        self.assertEqual(b"private-output", response.data)
        self.assertEqual("video/mp4", response.content_type)
        self.assertIn(str(job.id), response.filename)
        self.assertEqual("agenthive-media", storage.read_ref.bucket)
        self.assertEqual(job.outputs[0]["object_key"], storage.read_ref.object_key)
        audits = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual(1, len(audits))
        self.assertEqual("media.output.download", audits[0].action)
        self.assertEqual(job.id, audits[0].resource_id)
        self.assertEqual("req-download", audits[0].request_id)
        self.assertEqual(job.outputs[0]["object_key"], audits[0].details["object_key"])
        self.assertNotIn("private-output", str(audits[0].details))
        self.assertEqual(1, session.commits)

    async def test_cross_tenant_download_is_not_found(self):
        job = _job(tenant_id=uuid4())
        principal = Principal(tenant_id=uuid4(), user_id=uuid4(), permissions={"agents:read"})
        session = FakeDownloadSession(rows=[job])

        with self.assertRaises(HTTPException) as error:
            await download_media_generation_output(
                session, principal, job.id, 0, storage=FakeStorage()
            )

        self.assertEqual(404, error.exception.status_code)

    async def test_other_user_private_output_download_is_forbidden(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:read"})
        job = _job(tenant_id=tenant_id, user_id=uuid4())
        storage = FakeStorage()
        session = FakeDownloadSession(rows=[job])

        with self.assertRaises(HTTPException) as error:
            await download_media_generation_output(session, principal, job.id, 0, storage=storage)

        self.assertEqual(403, error.exception.status_code)
        self.assertIsNone(storage.read_ref)

    async def test_department_member_can_download_department_output(self):
        tenant_id = uuid4()
        department_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:read"})
        job = _job(tenant_id=tenant_id, user_id=uuid4(), department_id=department_id)
        storage = FakeStorage(data=b"department-output")
        session = FakeDownloadSession(rows=[job], department_ids={department_id})

        response = await download_media_generation_output(
            session, principal, job.id, 0, storage=storage
        )

        self.assertEqual(b"department-output", response.data)
        self.assertEqual(job.outputs[0]["object_key"], storage.read_ref.object_key)

    async def test_tampered_private_object_reference_is_rejected_before_storage_read(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:read"})
        invalid_references = [
            {
                "bucket": "another-tenant-bucket",
                "object_key": (f"generated/video/tenants/{tenant_id}/jobs/{uuid4()}/result.mp4"),
            },
            {
                "bucket": "agenthive-media",
                "object_key": (f"generated/video/tenants/{uuid4()}/jobs/{uuid4()}/result.mp4"),
            },
            {
                "bucket": "agenthive-media",
                "object_key": (f"generated/video/tenants/{tenant_id}/jobs/{uuid4()}/result.mp4"),
            },
        ]

        for output in invalid_references:
            with self.subTest(output=output):
                job = _job(tenant_id=tenant_id, user_id=principal.user_id)
                job.outputs = [output]
                storage = FakeStorage()
                session = FakeDownloadSession(rows=[job])

                with self.assertRaises(HTTPException) as error:
                    await download_media_generation_output(
                        session, principal, job.id, 0, storage=storage
                    )

                self.assertEqual(409, error.exception.status_code)
                self.assertIsNone(storage.read_ref)

    async def test_non_archived_output_cannot_be_downloaded(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:read"})
        job = _job(tenant_id=tenant_id, user_id=principal.user_id)
        job.outputs = [{"url": "https://cdn.example.com/result.mp4"}]
        session = FakeDownloadSession(rows=[job])

        with self.assertRaises(HTTPException) as error:
            await download_media_generation_output(
                session, principal, job.id, 0, storage=FakeStorage()
            )

        self.assertEqual(409, error.exception.status_code)

    async def test_storage_read_failure_returns_service_unavailable(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:read"})
        job = _job(tenant_id=tenant_id, user_id=principal.user_id)
        session = FakeDownloadSession(rows=[job])

        with self.assertRaises(HTTPException) as error:
            await download_media_generation_output(
                session, principal, job.id, 0, storage=FakeStorage(error=True)
            )

        self.assertEqual(503, error.exception.status_code)
        audits = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual(1, len(audits))
        self.assertEqual("failure", audits[0].status)
        self.assertEqual("media.output.download", audits[0].action)
        self.assertEqual("RuntimeError", audits[0].details["error_type"])
        self.assertEqual(1, session.commits)

    async def test_missing_output_index_returns_not_found(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:read"})
        job = _job(tenant_id=tenant_id, user_id=principal.user_id)
        session = FakeDownloadSession(rows=[job])

        with self.assertRaises(HTTPException) as error:
            await download_media_generation_output(
                session, principal, job.id, 5, storage=FakeStorage()
            )

        self.assertEqual(404, error.exception.status_code)


def _job(*, tenant_id, user_id=None, department_id=None) -> MediaGenerationJob:
    job_id = uuid4()
    return MediaGenerationJob(
        id=job_id,
        tenant_id=tenant_id,
        user_id=user_id or uuid4(),
        department_id=department_id,
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
            "tenant_id": str(tenant_id),
        },
        outputs=[
            {
                "bucket": "agenthive-media",
                "object_key": (f"generated/video/tenants/{tenant_id}/jobs/{job_id}/result.mp4"),
                "mime_type": "video/mp4",
                "size_bytes": 14,
                "storage_metadata": {"storage_backend": "minio"},
            }
        ],
        metadata_json={},
    )


class FakeStorage:
    def __init__(self, *, data: bytes = b"data", error: bool = False):
        self.data = data
        self.error = error
        self.read_ref: StoredObjectRef | None = None

    async def get_object(self, storage: StoredObjectRef) -> bytes:
        self.read_ref = storage
        if self.error:
            raise RuntimeError("minio down")
        return self.data


class FakeDownloadSession:
    def __init__(self, rows=None, department_ids=None):
        self.rows = list(rows or [])
        self.department_ids = set(department_ids or set())
        self.added = []
        self.commits = 0

    def add(self, row):
        self.added.append(row)

    async def get(self, model, row_id):
        if model is not MediaGenerationJob:
            return None
        return next((row for row in self.rows if row.id == row_id), None)

    async def execute(self, _statement):
        return FakeRowsResult(list(self.department_ids))

    async def commit(self):
        self.commits += 1


class FakeRowsResult:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return self.rows


if __name__ == "__main__":
    unittest.main()
