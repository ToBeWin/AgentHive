import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import HTTPException

from app.llm.schemas import BudgetReservation
from app.media.schemas import MediaGenerationJobStatus, MediaGenerationProviderCallback
from app.models.audit_log import AuditLog
from app.models.media import MediaGenerationJob
from app.services.media_generation_budget_service import reservation_metadata
from app.services.media_generation_webhook_service import (
    assert_media_webhook_secret,
    handle_media_generation_provider_callback,
)
from app.services.media_output_archive_service import MediaOutputArchiveError


class MediaGenerationWebhookServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.settle_budget_patch = patch(
            "app.services.media_generation_webhook_service.settle_media_generation_budget",
            new_callable=AsyncMock,
        )
        self.settle_budget = self.settle_budget_patch.start()
        self.release_budget_patch = patch(
            "app.services.media_generation_webhook_service.release_media_generation_budget",
            new_callable=AsyncMock,
        )
        self.release_budget = self.release_budget_patch.start()

    async def asyncTearDown(self):
        self.settle_budget_patch.stop()
        self.release_budget_patch.stop()

    async def test_running_job_can_be_completed_by_provider_callback(self):
        job = _job(status="running", external_job_id="provider-task-1")
        job.metadata_json = {
            "budget_reservation": reservation_metadata(
                BudgetReservation(
                    approved=True,
                    reason="budget_approved",
                    estimated_cost_usd=Decimal("0.400000"),
                ),
                estimated_cost_usd=Decimal("0.400000"),
            )
        }
        session = FakeWebhookSession(rows=[job])
        object_key = f"generated/video/tenants/{job.tenant_id}/jobs/{job.id}/result.mp4"

        response = await handle_media_generation_provider_callback(
            session,
            MediaGenerationProviderCallback(
                external_job_id="provider-task-1",
                status=MediaGenerationJobStatus.SUCCEEDED,
                outputs=[
                    {
                        "bucket": "agenthive-media",
                        "object_key": object_key,
                        "mime_type": "video/mp4",
                    }
                ],
                provider_key="volcengine",
                provider_status="completed",
                metadata={"duration_ms": 2100},
            ),
            request_id="req-webhook",
            ip_address="127.0.0.1",
            user_agent="provider-webhook",
        )

        self.assertEqual(MediaGenerationJobStatus.SUCCEEDED, response.status)
        self.assertEqual(object_key, response.outputs[0]["object_key"])
        self.assertEqual("running", response.metadata["provider_webhook"]["previous_status"])
        self.assertEqual("completed", response.metadata["provider_webhook"]["provider_status"])
        self.assertEqual(0, response.metadata["output_archive"]["archived_count"])
        self.assertEqual(1, response.metadata["output_archive"]["skipped_count"])
        audits = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual("media.generation.provider_callback", audits[0].action)
        self.assertEqual("provider", audits[0].actor_type)
        self.assertEqual("settled", audits[0].details["budget_event"])
        self.assertEqual("0.400000", audits[0].details["budget_reservation"]["estimated_cost_usd"])
        self.assertEqual(1, audits[0].details["output_summary"]["output_count"])
        self.assertEqual(1, audits[0].details["output_summary"]["downloadable_output_count"])
        self.assertEqual(0, audits[0].details["output_summary"]["archived_output_count"])
        self.assertEqual(0, audits[0].details["output_archive"]["archived_count"])
        self.assertEqual(1, audits[0].details["output_archive"]["skipped_count"])
        self.assertTrue(session.committed)
        self.settle_budget.assert_awaited_once()

    async def test_duplicate_terminal_callback_is_idempotent(self):
        job = _job(status="succeeded", external_job_id="provider-task-1")
        session = FakeWebhookSession(rows=[job])

        response = await handle_media_generation_provider_callback(
            session,
            MediaGenerationProviderCallback(
                external_job_id="provider-task-1",
                status=MediaGenerationJobStatus.SUCCEEDED,
                provider_status="completed",
            ),
        )

        self.assertEqual(MediaGenerationJobStatus.SUCCEEDED, response.status)
        audits = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual("media.generation.provider_callback_ignored", audits[0].action)
        self.assertEqual("terminal_status_duplicate", audits[0].details["reason"])

    async def test_running_job_failure_callback_releases_budget_with_audit_evidence(self):
        job = _job(status="running", external_job_id="provider-task-1")
        job.metadata_json = {
            "budget_reservation": reservation_metadata(
                BudgetReservation(
                    approved=True,
                    reason="budget_approved",
                    estimated_cost_usd=Decimal("0.400000"),
                ),
                estimated_cost_usd=Decimal("0.400000"),
            )
        }
        session = FakeWebhookSession(rows=[job])

        response = await handle_media_generation_provider_callback(
            session,
            MediaGenerationProviderCallback(
                external_job_id="provider-task-1",
                status=MediaGenerationJobStatus.FAILED,
                error_message="provider quota exceeded",
                provider_key="volcengine",
                provider_status="failed",
            ),
            request_id="req-webhook-failed",
        )

        self.assertEqual(MediaGenerationJobStatus.FAILED, response.status)
        self.assertEqual("provider quota exceeded", response.error_message)
        audits = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual("media.generation.provider_callback", audits[0].action)
        self.assertEqual("released", audits[0].details["budget_event"])
        self.assertEqual("media_generation_failed", audits[0].details["budget_release_reason"])
        self.assertEqual("0.400000", audits[0].details["budget_reservation"]["estimated_cost_usd"])
        self.assertEqual(0, audits[0].details["output_summary"]["output_count"])
        self.release_budget.assert_awaited_once()
        self.settle_budget.assert_not_awaited()

    async def test_terminal_job_rejects_conflicting_callback(self):
        job = _job(status="succeeded", external_job_id="provider-task-1")
        session = FakeWebhookSession(rows=[job])

        with self.assertRaises(HTTPException) as error:
            await handle_media_generation_provider_callback(
                session,
                MediaGenerationProviderCallback(
                    external_job_id="provider-task-1",
                    status=MediaGenerationJobStatus.FAILED,
                ),
            )

        self.assertEqual(409, error.exception.status_code)
        audits = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual("media.generation.provider_callback_failed", audits[0].action)
        self.assertEqual("failure", audits[0].status)
        self.assertEqual("terminal_status_conflict", audits[0].details["reason"])
        self.assertTrue(session.committed)

    async def test_output_archive_failure_is_audited_without_settling_budget(self):
        job = _job(status="running", external_job_id="provider-task-1")
        session = FakeWebhookSession(rows=[job])

        with patch(
            "app.services.media_generation_webhook_service.archive_media_outputs",
            new_callable=AsyncMock,
        ) as archive_outputs:
            archive_outputs.side_effect = MediaOutputArchiveError(
                "Media output archival failed: minio down"
            )
            with self.assertRaises(HTTPException) as error:
                await handle_media_generation_provider_callback(
                    session,
                    MediaGenerationProviderCallback(
                        external_job_id="provider-task-1",
                        status=MediaGenerationJobStatus.SUCCEEDED,
                        outputs=[{"url": "https://cdn.example.com/result.mp4"}],
                        provider_key="volcengine",
                    ),
                    request_id="req-archive-failed",
                )

        self.assertEqual(503, error.exception.status_code)
        self.assertEqual("running", job.status)
        self.assertEqual([], job.outputs)
        audits = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual("media.generation.provider_callback_failed", audits[0].action)
        self.assertEqual("failure", audits[0].status)
        self.assertEqual("output_archive_failed", audits[0].details["reason"])
        self.assertEqual("MediaOutputArchiveError", audits[0].details["error_type"])
        self.assertNotIn("https://cdn.example.com/result.mp4", str(audits[0].details))
        self.assertTrue(session.committed)
        self.settle_budget.assert_not_awaited()

    async def test_callback_can_resolve_job_by_agenthive_job_id(self):
        job = _job(status="running", external_job_id=None)
        session = FakeWebhookSession(rows=[job])

        response = await handle_media_generation_provider_callback(
            session,
            MediaGenerationProviderCallback(
                job_id=job.id,
                external_job_id="late-provider-task-id",
                status=MediaGenerationJobStatus.RUNNING,
                provider_status="processing",
            ),
        )

        self.assertEqual(MediaGenerationJobStatus.RUNNING, response.status)
        self.assertEqual("late-provider-task-id", response.external_job_id)

    async def test_external_job_id_callback_rejects_ambiguous_matches(self):
        first = _job(status="running", external_job_id="shared-provider-task")
        second = _job(status="running", external_job_id="shared-provider-task")
        second.provider_key = "another-provider"
        session = FakeWebhookSession(rows=[first, second])

        with self.assertRaises(HTTPException) as error:
            await handle_media_generation_provider_callback(
                session,
                MediaGenerationProviderCallback(
                    external_job_id="shared-provider-task",
                    status=MediaGenerationJobStatus.SUCCEEDED,
                ),
            )

        self.assertEqual(409, error.exception.status_code)
        self.assertFalse(session.committed)
        self.settle_budget.assert_not_awaited()

    async def test_external_job_id_callback_uses_provider_key_to_disambiguate(self):
        first = _job(status="running", external_job_id="shared-provider-task")
        second = _job(status="running", external_job_id="shared-provider-task")
        second.provider_key = "another-provider"
        session = FakeWebhookSession(rows=[first, second])

        response = await handle_media_generation_provider_callback(
            session,
            MediaGenerationProviderCallback(
                external_job_id="shared-provider-task",
                status=MediaGenerationJobStatus.SUCCEEDED,
                provider_key="another-provider",
            ),
        )

        self.assertEqual(second.id, response.id)
        self.assertEqual("running", first.status)
        self.assertEqual("succeeded", second.status)

    async def test_job_id_callback_rejects_provider_key_mismatch(self):
        job = _job(status="running", external_job_id="provider-task-1")
        session = FakeWebhookSession(rows=[job])

        with self.assertRaises(HTTPException) as error:
            await handle_media_generation_provider_callback(
                session,
                MediaGenerationProviderCallback(
                    job_id=job.id,
                    external_job_id="provider-task-1",
                    status=MediaGenerationJobStatus.SUCCEEDED,
                    provider_key="another-provider",
                ),
            )

        self.assertEqual(409, error.exception.status_code)
        self.assertEqual("running", job.status)
        self.assertFalse(session.committed)

    async def test_job_id_callback_rejects_external_job_id_mismatch(self):
        job = _job(status="running", external_job_id="provider-task-1")
        session = FakeWebhookSession(rows=[job])

        with self.assertRaises(HTTPException) as error:
            await handle_media_generation_provider_callback(
                session,
                MediaGenerationProviderCallback(
                    job_id=job.id,
                    external_job_id="different-provider-task",
                    status=MediaGenerationJobStatus.SUCCEEDED,
                ),
            )

        self.assertEqual(409, error.exception.status_code)
        self.assertEqual("running", job.status)
        self.assertFalse(session.committed)


class MediaWebhookSecretTests(unittest.TestCase):
    def test_missing_expected_secret_blocks_webhook(self):
        with self.assertRaises(HTTPException) as error:
            assert_media_webhook_secret("provided", "")

        self.assertEqual(503, error.exception.status_code)

    def test_invalid_secret_blocks_webhook(self):
        with self.assertRaises(HTTPException) as error:
            assert_media_webhook_secret("wrong", "expected")

        self.assertEqual(401, error.exception.status_code)

    def test_valid_secret_is_accepted(self):
        assert_media_webhook_secret("expected", "expected")


def _job(*, status: str, external_job_id: str | None) -> MediaGenerationJob:
    tenant_id = uuid4()
    return MediaGenerationJob(
        id=uuid4(),
        tenant_id=tenant_id,
        user_id=uuid4(),
        kind="video",
        mode="manual_prompt",
        status=status,
        provider_key="volcengine",
        provider_type="volcengine_seedance",
        model_key="volcengine/seedance-2.0",
        routing_key="video-generation",
        prompt="test prompt",
        normalized_parameters={"duration_seconds": 5, "fps": 24},
        output_storage={
            "driver": "minio",
            "bucket": "agenthive-media",
            "prefix": "generated/video",
            "tenant_id": str(tenant_id),
        },
        external_job_id=external_job_id,
        metadata_json={},
    )


class FakeWebhookSession:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.added = []
        self.committed = False

    def add(self, row):
        self.added.append(row)

    async def get(self, model, row_id):
        if model is not MediaGenerationJob:
            return None
        return next((row for row in self.rows if row.id == row_id), None)

    async def execute(self, statement):
        provider_key = None
        external_job_id = None
        for key, value in statement.compile().params.items():
            if key.startswith("provider_key"):
                provider_key = value
            if key.startswith("external_job_id"):
                external_job_id = value
        rows = [row for row in self.rows if row.external_job_id == external_job_id]
        if provider_key is not None:
            rows = [row for row in rows if row.provider_key == provider_key]
        return FakeRowsResult(rows)

    async def commit(self):
        self.committed = True

    async def refresh(self, _row):
        return None


class FakeRowsResult:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return self.rows


if __name__ == "__main__":
    unittest.main()
