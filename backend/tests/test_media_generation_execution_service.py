import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import HTTPException

from app.api.deps import Principal
from app.media.providers import (
    BaseMediaProviderAdapter,
    MediaProviderError,
    MediaProviderSubmitResult,
)
from app.media.schemas import MediaGenerationJobStatus, MediaProviderType
from app.models.audit_log import AuditLog
from app.models.media import MediaGenerationJob
from app.services.media_generation_execution_service import (
    execute_media_generation_job,
    poll_media_generation_job,
)


class MediaGenerationExecutionServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.module_gate_patch = patch(
            "app.services.media_generation_execution_service.ensure_media_generation_module_runnable",
            new_callable=AsyncMock,
        )
        self.module_gate = self.module_gate_patch.start()
        self.settle_budget_patch = patch(
            "app.services.media_generation_service.settle_media_generation_budget",
            new_callable=AsyncMock,
        )
        self.settle_budget = self.settle_budget_patch.start()
        self.release_budget_patch = patch(
            "app.services.media_generation_service.release_media_generation_budget",
            new_callable=AsyncMock,
        )
        self.release_budget = self.release_budget_patch.start()
        self.policy_gate_patch = patch(
            "app.services.media_generation_execution_service.enforce_media_generation_model_policy",
            new_callable=AsyncMock,
        )
        self.policy_gate = self.policy_gate_patch.start()
        self.provider_gate_patch = patch(
            "app.services.media_generation_execution_service.ensure_media_provider_configured",
            new_callable=AsyncMock,
        )
        self.provider_gate = self.provider_gate_patch.start()

    async def asyncTearDown(self):
        self.module_gate_patch.stop()
        self.settle_budget_patch.stop()
        self.release_budget_patch.stop()
        self.policy_gate_patch.stop()
        self.provider_gate_patch.stop()

    async def test_execute_queued_image_job_can_succeed_with_outputs(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        job = _job(tenant_id=tenant_id, user_id=principal.user_id, kind="image", status="queued")
        session = FakeExecutionSession(rows=[job])

        response = await execute_media_generation_job(
            session,
            principal,
            job.id,
            adapter=SuccessfulImageAdapter(),
            request_id="req-exec-image",
        )

        self.assertEqual(MediaGenerationJobStatus.SUCCEEDED, response.status)
        self.assertEqual(
            f"generated/image/tenants/{tenant_id}/jobs/{job.id}/result.png",
            response.outputs[0]["object_key"],
        )
        self.assertIsNotNone(response.started_at)
        self.assertIsNotNone(response.completed_at)
        audit_actions = [row.action for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual(
            ["media.generation.status_update", "media.generation.status_update"],
            audit_actions,
        )
        self.module_gate.assert_awaited_once_with(session, principal, "image")
        self.settle_budget.assert_awaited_once()

    async def test_execute_video_job_can_submit_async_and_stay_running(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        job = _job(tenant_id=tenant_id, user_id=principal.user_id, kind="video", status="queued")
        session = FakeExecutionSession(rows=[job])

        response = await execute_media_generation_job(
            session,
            principal,
            job.id,
            adapter=AsyncVideoSubmitAdapter(),
        )

        self.assertEqual(MediaGenerationJobStatus.RUNNING, response.status)
        self.assertEqual("seedance-task-42", response.external_job_id)
        self.assertIsNotNone(response.started_at)
        self.assertIsNone(response.completed_at)
        self.assertEqual("submitted", response.metadata["provider_status"])

    async def test_unconfigured_provider_marks_job_failed_without_mock_success(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        job = _job(tenant_id=tenant_id, user_id=principal.user_id, kind="image", status="queued")
        session = FakeExecutionSession(rows=[job])

        response = await execute_media_generation_job(session, principal, job.id)

        self.assertEqual(MediaGenerationJobStatus.FAILED, response.status)
        self.assertIn("not configured", response.error_message or "")
        self.assertFalse(response.metadata["live_network_call"])
        self.assertEqual("MediaProviderNotConfiguredError", response.metadata["error_type"])

    async def test_unconfigured_provider_guard_blocks_before_running(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        job = _job(tenant_id=tenant_id, user_id=principal.user_id, kind="image", status="queued")
        session = FakeExecutionSession(rows=[job])
        self.provider_gate.side_effect = HTTPException(
            status_code=409,
            detail="Media provider openai_compatible_media is not configured.",
        )

        with self.assertRaises(HTTPException) as error:
            await execute_media_generation_job(
                session,
                principal,
                job.id,
                adapter=SuccessfulImageAdapter(),
                request_id="req-provider-guard",
            )

        self.assertEqual(409, error.exception.status_code)
        self.assertEqual("queued", job.status)
        self.policy_gate.assert_not_awaited()
        self.settle_budget.assert_not_awaited()
        self.assertFalse(any(isinstance(row, AuditLog) for row in session.added))

    async def test_terminal_job_cannot_be_executed_again(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        job = _job(tenant_id=tenant_id, user_id=principal.user_id, kind="image", status="succeeded")
        session = FakeExecutionSession(rows=[job])

        with self.assertRaises(HTTPException) as error:
            await execute_media_generation_job(
                session, principal, job.id, adapter=SuccessfulImageAdapter()
            )

        self.assertEqual(409, error.exception.status_code)

    async def test_execute_job_requires_enabled_module(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        job = _job(tenant_id=tenant_id, user_id=principal.user_id, kind="video", status="queued")
        session = FakeExecutionSession(rows=[job])
        self.module_gate.side_effect = HTTPException(
            status_code=403,
            detail="Enable agent.video_generation before using media generation.",
        )

        with self.assertRaises(HTTPException) as error:
            await execute_media_generation_job(
                session, principal, job.id, adapter=AsyncVideoSubmitAdapter()
            )

        self.assertEqual(403, error.exception.status_code)
        self.module_gate.assert_awaited_once_with(session, principal, "video")

    async def test_execute_job_denies_other_user_private_job_before_provider_call(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        job = _job(tenant_id=tenant_id, user_id=uuid4(), kind="image", status="queued")
        session = FakeExecutionSession(rows=[job])
        adapter = SuccessfulImageAdapter()

        with self.assertRaises(HTTPException) as error:
            await execute_media_generation_job(session, principal, job.id, adapter=adapter)

        self.assertEqual(403, error.exception.status_code)
        self.module_gate.assert_not_awaited()
        self.settle_budget.assert_not_awaited()
        self.assertFalse(any(isinstance(row, AuditLog) for row in session.added))

    async def test_poll_running_video_job_can_complete_when_webhook_is_missing(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        job = _job(tenant_id=tenant_id, user_id=principal.user_id, kind="video", status="running")
        job.external_job_id = "seedance-task-42"
        session = FakeExecutionSession(rows=[job])

        response = await poll_media_generation_job(
            session,
            principal,
            job.id,
            adapter=CompletedVideoPollAdapter(),
            request_id="req-poll-video",
        )

        self.assertEqual(MediaGenerationJobStatus.SUCCEEDED, response.status)
        self.assertEqual(
            f"generated/video/tenants/{tenant_id}/jobs/{job.id}/result.mp4",
            response.outputs[0]["object_key"],
        )
        self.assertEqual("seedance-task-42", response.external_job_id)
        self.assertEqual("agenthive_media_generation_poller", response.metadata["executor"])
        self.settle_budget.assert_awaited_once()

    async def test_poll_provider_error_keeps_job_running_for_later_webhook(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        job = _job(tenant_id=tenant_id, user_id=principal.user_id, kind="video", status="running")
        job.external_job_id = "seedance-task-42"
        session = FakeExecutionSession(rows=[job])

        response = await poll_media_generation_job(
            session,
            principal,
            job.id,
            adapter=FailingPollAdapter(),
            request_id="req-poll-fail",
        )

        self.assertEqual(MediaGenerationJobStatus.RUNNING, response.status)
        self.assertEqual("temporary provider outage", response.error_message)
        self.assertTrue(response.metadata["poll_failed"])
        self.settle_budget.assert_not_awaited()
        self.release_budget.assert_not_awaited()

    async def test_poll_requires_running_job_with_external_id(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        queued_job = _job(
            tenant_id=tenant_id, user_id=principal.user_id, kind="video", status="queued"
        )
        running_without_external = _job(
            tenant_id=tenant_id,
            user_id=principal.user_id,
            kind="video",
            status="running",
        )
        session = FakeExecutionSession(rows=[queued_job, running_without_external])

        with self.assertRaises(HTTPException) as queued_error:
            await poll_media_generation_job(
                session, principal, queued_job.id, adapter=CompletedVideoPollAdapter()
            )
        with self.assertRaises(HTTPException) as missing_external_error:
            await poll_media_generation_job(
                session,
                principal,
                running_without_external.id,
                adapter=CompletedVideoPollAdapter(),
            )

        self.assertEqual(409, queued_error.exception.status_code)
        self.assertEqual(409, missing_external_error.exception.status_code)


class SuccessfulImageAdapter(BaseMediaProviderAdapter):
    provider_type = MediaProviderType.OPENAI_COMPATIBLE_MEDIA

    async def submit(self, job: MediaGenerationJob) -> MediaProviderSubmitResult:
        return MediaProviderSubmitResult(
            status=MediaGenerationJobStatus.SUCCEEDED,
            outputs=[
                {
                    "bucket": job.output_storage.get("bucket", "agenthive-demo"),
                    "object_key": (
                        f"generated/image/tenants/{job.tenant_id}/jobs/{job.id}/result.png"
                    ),
                    "mime_type": "image/png",
                }
            ],
            external_job_id="image-job-1",
            metadata={"provider_status": "completed"},
        )


class AsyncVideoSubmitAdapter(BaseMediaProviderAdapter):
    provider_type = MediaProviderType.VOLCENGINE_SEEDANCE

    async def submit(self, _job: MediaGenerationJob) -> MediaProviderSubmitResult:
        return MediaProviderSubmitResult(
            status=MediaGenerationJobStatus.RUNNING,
            external_job_id="seedance-task-42",
            metadata={"provider_status": "submitted"},
        )


class CompletedVideoPollAdapter(BaseMediaProviderAdapter):
    provider_type = MediaProviderType.VOLCENGINE_SEEDANCE

    async def submit(self, _job: MediaGenerationJob) -> MediaProviderSubmitResult:
        raise AssertionError("poll test should not submit a new media job")

    async def poll(self, job: MediaGenerationJob) -> MediaProviderSubmitResult:
        return MediaProviderSubmitResult(
            status=MediaGenerationJobStatus.SUCCEEDED,
            outputs=[
                {
                    "bucket": job.output_storage.get("bucket", "agenthive-demo"),
                    "object_key": (
                        f"generated/video/tenants/{job.tenant_id}/jobs/{job.id}/result.mp4"
                    ),
                    "mime_type": "video/mp4",
                }
            ],
            external_job_id=job.external_job_id,
            metadata={"provider_status": "completed"},
        )


class FailingPollAdapter(BaseMediaProviderAdapter):
    provider_type = MediaProviderType.VOLCENGINE_SEEDANCE

    async def submit(self, _job: MediaGenerationJob) -> MediaProviderSubmitResult:
        raise AssertionError("poll test should not submit a new media job")

    async def poll(self, _job: MediaGenerationJob) -> MediaProviderSubmitResult:
        raise MediaProviderError(
            "temporary provider outage",
            metadata={"provider_status": "timeout", "live_network_call": True},
        )


def _job(
    *, tenant_id, kind: str, status: str, user_id=None, department_id=None
) -> MediaGenerationJob:
    return MediaGenerationJob(
        tenant_id=tenant_id,
        user_id=user_id or uuid4(),
        department_id=department_id,
        kind=kind,
        mode="manual_prompt",
        status=status,
        provider_key="openai_compatible_media" if kind == "image" else "volcengine",
        provider_type="openai_compatible_media" if kind == "image" else "volcengine_seedance",
        model_key="openai-compatible-image" if kind == "image" else "volcengine/seedance-2.0",
        routing_key="private-image-generation" if kind == "image" else "video-generation",
        prompt="test prompt",
        normalized_parameters={},
        output_storage={
            "driver": "minio",
            "bucket": "agenthive-demo",
            "prefix": f"generated/{kind}",
            "tenant_id": str(tenant_id),
        },
        metadata_json={},
    )


class FakeExecutionSession:
    def __init__(self, rows=None, department_ids=None):
        self.rows = list(rows or [])
        self.department_ids = set(department_ids or set())
        self.added = []
        self.committed = False

    def add(self, row):
        self.added.append(row)

    async def get(self, model, row_id):
        if model is not MediaGenerationJob:
            return None
        return next((row for row in self.rows if row.id == row_id), None)

    async def execute(self, _statement):
        return FakeRowsResult(list(self.department_ids))

    async def commit(self):
        self.committed = True

    async def flush(self):
        return None

    async def refresh(self, _row):
        return None


class FakeRowsResult:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return self.rows


if __name__ == "__main__":
    unittest.main()
