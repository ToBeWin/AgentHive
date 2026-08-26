import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import HTTPException

from app.api.deps import Principal
from app.llm.schemas import BudgetReservation
from app.media.schemas import (
    MediaAssetKind,
    MediaAssetRef,
    MediaGenerationJobCreateRequest,
    MediaGenerationJobStatus,
    MediaGenerationJobStatusUpdate,
    MediaGenerationKind,
    MediaGenerationMode,
)
from app.models.audit_log import AuditLog
from app.models.base import utc_now
from app.models.media import MediaGenerationJob
from app.services.media_generation_service import (
    cancel_media_generation_job,
    create_media_generation_job,
    list_media_generation_job_events,
    list_media_generation_jobs,
    retry_media_generation_job,
    update_media_generation_job_status,
)
from app.services.media_generation_budget_service import reservation_metadata


class MediaGenerationServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.module_gate_patch = patch(
            "app.services.media_generation_service.ensure_media_generation_module_runnable",
            new_callable=AsyncMock,
        )
        self.module_gate = self.module_gate_patch.start()
        self.reserve_budget_patch = patch(
            "app.services.media_generation_service.reserve_media_generation_budget",
            new_callable=AsyncMock,
        )
        self.reserve_budget = self.reserve_budget_patch.start()
        self.reserve_budget.return_value = BudgetReservation(
            approved=True,
            reason="budget_approved",
            estimated_cost_usd=0,
        )
        self.release_budget_patch = patch(
            "app.services.media_generation_service.release_media_generation_budget",
            new_callable=AsyncMock,
        )
        self.release_budget = self.release_budget_patch.start()
        self.settle_budget_patch = patch(
            "app.services.media_generation_service.settle_media_generation_budget",
            new_callable=AsyncMock,
        )
        self.settle_budget = self.settle_budget_patch.start()
        self.policy_gate_patch = patch(
            "app.services.media_generation_service.enforce_media_generation_model_policy",
            new_callable=AsyncMock,
        )
        self.policy_gate = self.policy_gate_patch.start()
        self.provider_gate_patch = patch(
            "app.services.media_generation_service.ensure_media_provider_configured",
            new_callable=AsyncMock,
        )
        self.provider_gate = self.provider_gate_patch.start()

    async def asyncTearDown(self):
        self.module_gate_patch.stop()
        self.reserve_budget_patch.stop()
        self.release_budget_patch.stop()
        self.settle_budget_patch.stop()
        self.policy_gate_patch.stop()
        self.provider_gate_patch.stop()

    async def test_create_media_generation_job_persists_plan_and_audit(self):
        tenant_id = uuid4()
        user_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=user_id, permissions={"agents:write"})
        session = FakeMediaJobSession()
        payload = MediaGenerationJobCreateRequest(
            kind=MediaGenerationKind.IMAGE,
            mode=MediaGenerationMode.MANUAL_PROMPT,
            prompt="生成一张白底运动鞋商品图",
            model_key="google/nano-banana",
            reference_assets=[
                MediaAssetRef(
                    kind=MediaAssetKind.IMAGE, bucket="agenthive-assets", object_key="refs/shoe.png"
                )
            ],
            image_count=2,
            aspect_ratio="1:1",
            metadata={"campaign": "summer"},
        )

        response = await create_media_generation_job(
            session, principal, payload, request_id="req-media-1"
        )

        self.assertEqual(MediaGenerationJobStatus.QUEUED, response.status)
        self.assertEqual("google/nano-banana", response.model_key)
        self.assertEqual("minio", response.output_storage["driver"])
        self.assertEqual("summer", response.metadata["campaign"])
        self.assertEqual(2, response.metadata["estimated_output_count"])
        self.assertEqual("0.060000", response.metadata["estimated_cost_usd"])
        self.assertEqual("output", response.metadata["pricing"]["unit"])
        jobs = [row for row in session.added if isinstance(row, MediaGenerationJob)]
        audits = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual(1, len(jobs))
        self.assertEqual(1, len(audits))
        self.assertEqual("media.generation.create", audits[0].action)
        self.assertTrue(session.committed)
        self.module_gate.assert_awaited_once_with(session, principal, MediaGenerationKind.IMAGE)
        self.provider_gate.assert_awaited_once()
        self.reserve_budget.assert_awaited_once()

    async def test_create_media_generation_job_requires_configured_provider_before_budget(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        session = FakeMediaJobSession()
        payload = MediaGenerationJobCreateRequest(
            kind=MediaGenerationKind.IMAGE,
            mode=MediaGenerationMode.MANUAL_PROMPT,
            prompt="生成一张商品图",
            model_key="openai-compatible-image",
        )
        self.provider_gate.side_effect = HTTPException(
            status_code=409,
            detail="Media provider openai_compatible_media is not configured.",
        )

        with self.assertRaises(HTTPException) as error:
            await create_media_generation_job(
                session, principal, payload, request_id="req-media-no-provider"
            )

        self.assertEqual(409, error.exception.status_code)
        self.reserve_budget.assert_not_awaited()
        self.policy_gate.assert_not_awaited()
        self.assertFalse(session.committed)
        self.assertFalse(any(isinstance(row, MediaGenerationJob) for row in session.added))

    async def test_create_media_generation_job_requires_enabled_module(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        session = FakeMediaJobSession()
        payload = MediaGenerationJobCreateRequest(
            kind=MediaGenerationKind.VIDEO,
            mode=MediaGenerationMode.MANUAL_PROMPT,
            prompt="生成一条商品短视频",
        )
        self.module_gate.side_effect = HTTPException(
            status_code=403,
            detail="Enable agent.video_generation before using media generation.",
        )

        with self.assertRaises(HTTPException) as error:
            await create_media_generation_job(session, principal, payload)

        self.assertEqual(403, error.exception.status_code)
        self.assertFalse(session.committed)
        self.module_gate.assert_awaited_once_with(session, principal, MediaGenerationKind.VIDEO)
        self.reserve_budget.assert_not_awaited()

    async def test_list_media_generation_jobs_filters_by_tenant_kind_and_status(self):
        tenant_id = uuid4()
        other_tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:read"})
        image_job = _job(
            tenant_id=tenant_id, user_id=principal.user_id, kind="image", status="queued"
        )
        video_job = _job(
            tenant_id=tenant_id, user_id=principal.user_id, kind="video", status="running"
        )
        other_job = _job(tenant_id=other_tenant_id, kind="image", status="queued")
        session = FakeMediaJobSession(rows=[image_job, video_job, other_job])

        response = await list_media_generation_jobs(
            session,
            principal,
            kind=MediaGenerationKind.IMAGE,
            status_filter=MediaGenerationJobStatus.QUEUED,
        )

        self.assertEqual(1, response.total)
        self.assertEqual(image_job.id, response.jobs[0].id)

    async def test_list_media_generation_jobs_hides_other_user_private_jobs(self):
        tenant_id = uuid4()
        department_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:read"})
        own_job = _job(
            tenant_id=tenant_id, user_id=principal.user_id, kind="image", status="queued"
        )
        department_job = _job(
            tenant_id=tenant_id,
            user_id=uuid4(),
            department_id=department_id,
            kind="image",
            status="queued",
        )
        private_other_job = _job(
            tenant_id=tenant_id, user_id=uuid4(), kind="image", status="queued"
        )
        session = FakeMediaJobSession(
            rows=[own_job, department_job, private_other_job],
            department_ids={department_id},
        )

        response = await list_media_generation_jobs(
            session, principal, kind=MediaGenerationKind.IMAGE
        )

        self.assertEqual(2, response.total)
        self.assertEqual({own_job.id, department_job.id}, {job.id for job in response.jobs})

    async def test_get_media_generation_job_denies_other_user_private_job(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:read"})
        job = _job(tenant_id=tenant_id, user_id=uuid4(), kind="image", status="queued")
        session = FakeMediaJobSession(rows=[job])

        with self.assertRaises(HTTPException) as error:
            await list_media_generation_job_events(session, principal, job.id)

        self.assertEqual(403, error.exception.status_code)

    async def test_list_media_generation_job_events_returns_tenant_scoped_timeline(self):
        tenant_id = uuid4()
        other_tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:read"})
        job = _job(tenant_id=tenant_id, user_id=principal.user_id, kind="image", status="queued")
        other_job = _job(
            tenant_id=tenant_id, user_id=principal.user_id, kind="image", status="queued"
        )
        session = FakeMediaJobSession(
            rows=[
                job,
                other_job,
                _audit_event(
                    tenant_id=tenant_id,
                    job_id=job.id,
                    action="media.generation.create",
                    details={"status": "queued", "api_key": "sk-secret"},
                ),
                _audit_event(
                    tenant_id=tenant_id,
                    job_id=job.id,
                    action="media.generation.enqueue",
                    details={"task_id": "celery-task-1"},
                ),
                _audit_event(
                    tenant_id=tenant_id,
                    job_id=other_job.id,
                    action="media.generation.create",
                    details={"status": "queued"},
                ),
                _audit_event(
                    tenant_id=other_tenant_id,
                    job_id=job.id,
                    action="media.generation.create",
                    details={"status": "queued"},
                ),
            ]
        )

        response = await list_media_generation_job_events(session, principal, job.id)

        self.assertEqual(job.id, response.job_id)
        self.assertEqual(2, response.total)
        self.assertEqual(
            ["media.generation.create", "media.generation.enqueue"],
            [event.action for event in response.events],
        )
        self.assertEqual("[REDACTED]", response.events[0].details["api_key"])

    async def test_terminal_job_cannot_transition_back_to_running(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        job = _job(tenant_id=tenant_id, user_id=principal.user_id, kind="video", status="succeeded")
        session = FakeMediaJobSession(rows=[job])

        with self.assertRaises(HTTPException) as error:
            await update_media_generation_job_status(
                session,
                principal,
                job.id,
                MediaGenerationJobStatusUpdate(status=MediaGenerationJobStatus.RUNNING),
            )

        self.assertEqual(409, error.exception.status_code)

    async def test_running_job_can_succeed_with_outputs(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        job = _job(tenant_id=tenant_id, user_id=principal.user_id, kind="video", status="running")
        session = FakeMediaJobSession(rows=[job])
        object_key = f"generated/video/tenants/{tenant_id}/jobs/{job.id}/result.mp4"

        response = await update_media_generation_job_status(
            session,
            principal,
            job.id,
            MediaGenerationJobStatusUpdate(
                status=MediaGenerationJobStatus.SUCCEEDED,
                outputs=[
                    {
                        "bucket": "agenthive-demo",
                        "object_key": object_key,
                        "mime_type": "video/mp4",
                        "size_bytes": 2048,
                        "archived": True,
                        "archive_source": "provider_url",
                    }
                ],
                external_job_id="seedance-job-1",
                metadata={
                    "output_archive": {
                        "archived_count": 1,
                        "skipped_count": 0,
                        "bucket": "agenthive-demo",
                    }
                },
            ),
            request_id="req-media-status",
        )

        self.assertEqual(MediaGenerationJobStatus.SUCCEEDED, response.status)
        self.assertEqual("seedance-job-1", response.external_job_id)
        self.assertEqual(object_key, response.outputs[0]["object_key"])
        self.assertIsNotNone(response.completed_at)
        audits = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual("media.generation.status_update", audits[0].action)
        self.assertEqual("openai_compatible_media", audits[0].details["provider_type"])
        self.assertEqual("private-video-generation", audits[0].details["routing_key"])
        self.assertEqual("settled", audits[0].details["budget_event"])
        self.assertEqual(1, audits[0].details["output_summary"]["output_count"])
        self.assertEqual(1, audits[0].details["output_summary"]["downloadable_output_count"])
        self.assertEqual(1, audits[0].details["output_summary"]["archived_output_count"])
        self.assertEqual(2048, audits[0].details["output_summary"]["total_size_bytes"])
        self.assertEqual(["video/mp4"], audits[0].details["output_summary"]["mime_types"])
        self.assertEqual("agenthive-demo", audits[0].details["output_archive"]["bucket"])
        self.settle_budget.assert_awaited_once()

    async def test_status_update_rejects_untrusted_private_object_references(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})

        invalid_references = [
            {
                "bucket": "another-tenant-bucket",
                "object_key": "placeholder",
            },
            {
                "bucket": "agenthive-demo",
                "object_key": (f"generated/video/tenants/{uuid4()}/jobs/{uuid4()}/result.mp4"),
            },
            {
                "bucket": "agenthive-demo",
                "object_key": (f"generated/video/tenants/{tenant_id}/jobs/{uuid4()}/result.mp4"),
            },
        ]

        for output in invalid_references:
            with self.subTest(output=output):
                job = _job(
                    tenant_id=tenant_id,
                    user_id=principal.user_id,
                    kind="video",
                    status="running",
                )
                session = FakeMediaJobSession(rows=[job])

                with self.assertRaises(HTTPException) as error:
                    await update_media_generation_job_status(
                        session,
                        principal,
                        job.id,
                        MediaGenerationJobStatusUpdate(
                            status=MediaGenerationJobStatus.SUCCEEDED,
                            outputs=[output],
                        ),
                    )

                self.assertEqual(422, error.exception.status_code)
                self.assertEqual("running", job.status)
                self.assertEqual([], job.outputs)
                self.assertFalse(session.committed)
        self.settle_budget.assert_not_awaited()

    async def test_failed_job_can_be_retried_to_queued_with_audit(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        now = utc_now()
        job = _job(tenant_id=tenant_id, user_id=principal.user_id, kind="image", status="failed")
        job.outputs = [{"bucket": "agenthive-demo", "object_key": "failed.png"}]
        job.external_job_id = "external-job-1"
        job.error_message = "provider failed"
        job.started_at = now
        job.completed_at = now
        job.metadata_json = {"queue": {"task_id": "old-task"}, "retry_count": 1}
        session = FakeMediaJobSession(rows=[job])

        response = await retry_media_generation_job(
            session, principal, job.id, request_id="req-retry"
        )

        self.assertEqual(MediaGenerationJobStatus.QUEUED, response.status)
        self.assertEqual([], response.outputs)
        self.assertIsNone(response.external_job_id)
        self.assertIsNone(response.error_message)
        self.assertIsNone(response.started_at)
        self.assertIsNone(response.completed_at)
        self.assertEqual(2, response.metadata["retry_count"])
        self.assertEqual("failed", response.metadata["last_retry"]["previous_status"])
        self.assertEqual("old-task", response.metadata["previous_queue"]["task_id"])
        audits = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual("media.generation.retry", audits[0].action)
        self.assertTrue(session.committed)
        self.module_gate.assert_awaited_once_with(session, principal, "image")
        self.reserve_budget.assert_awaited_once()

    async def test_queued_job_cannot_be_retried(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        job = _job(tenant_id=tenant_id, user_id=principal.user_id, kind="image", status="queued")
        session = FakeMediaJobSession(rows=[job])

        with self.assertRaises(HTTPException) as error:
            await retry_media_generation_job(session, principal, job.id)

        self.assertEqual(409, error.exception.status_code)

    async def test_running_job_can_be_canceled_with_audit(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        job = _job(tenant_id=tenant_id, user_id=principal.user_id, kind="video", status="running")
        job.external_job_id = "seedance-job-1"
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
        session = FakeMediaJobSession(rows=[job])

        response = await cancel_media_generation_job(
            session, principal, job.id, request_id="req-cancel"
        )

        self.assertEqual(MediaGenerationJobStatus.CANCELED, response.status)
        self.assertIsNotNone(response.completed_at)
        self.assertEqual("running", response.metadata["last_cancel"]["previous_status"])
        self.assertEqual("not_configured", response.metadata["last_cancel"]["provider_cancel"])
        audits = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual("media.generation.cancel", audits[0].action)
        self.assertEqual("media_generation_canceled", audits[0].details["budget_release_reason"])
        self.assertEqual("0.400000", audits[0].details["budget_reservation"]["estimated_cost_usd"])
        self.assertTrue(session.committed)
        self.release_budget.assert_awaited_once()

    async def test_status_update_to_failed_audits_budget_release_reason(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        job = _job(tenant_id=tenant_id, user_id=principal.user_id, kind="video", status="running")
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
        session = FakeMediaJobSession(rows=[job])

        response = await update_media_generation_job_status(
            session,
            principal,
            job.id,
            MediaGenerationJobStatusUpdate(
                status=MediaGenerationJobStatus.FAILED, error_message="provider failed"
            ),
            request_id="req-media-failed",
        )

        self.assertEqual(MediaGenerationJobStatus.FAILED, response.status)
        audits = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual("media.generation.status_update", audits[0].action)
        self.assertEqual("released", audits[0].details["budget_event"])
        self.assertEqual("media_generation_failed", audits[0].details["budget_release_reason"])
        self.assertEqual("0.400000", audits[0].details["budget_reservation"]["estimated_cost_usd"])
        self.assertEqual(0, audits[0].details["output_summary"]["output_count"])
        self.release_budget.assert_awaited_once()

    async def test_failed_job_cannot_be_canceled(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        job = _job(tenant_id=tenant_id, user_id=principal.user_id, kind="video", status="failed")
        session = FakeMediaJobSession(rows=[job])

        with self.assertRaises(HTTPException) as error:
            await cancel_media_generation_job(session, principal, job.id)

        self.assertEqual(409, error.exception.status_code)


def _job(
    *,
    tenant_id,
    kind: str,
    status: str,
    user_id=None,
    department_id=None,
) -> MediaGenerationJob:
    return MediaGenerationJob(
        tenant_id=tenant_id,
        user_id=user_id or uuid4(),
        department_id=department_id,
        kind=kind,
        mode="manual_prompt",
        status=status,
        provider_key="test",
        provider_type="openai_compatible_media",
        model_key="openai-compatible-video" if kind == "video" else "openai-compatible-image",
        routing_key="private-video-generation" if kind == "video" else "private-image-generation",
        prompt="test prompt",
        normalized_parameters={},
        output_storage={
            "driver": "minio",
            "bucket": "agenthive-demo",
            "prefix": f"generated/{kind}",
            "tenant_id": str(tenant_id),
        },
    )


def _audit_event(*, tenant_id, job_id, action: str, details: dict) -> AuditLog:
    return AuditLog(
        tenant_id=tenant_id,
        actor_id=uuid4(),
        action=action,
        resource_type="media_generation_job",
        resource_id=job_id,
        request_id=f"req-{action}",
        details=details,
        created_at=utc_now(),
        updated_at=utc_now(),
    )


class FakeMediaJobSession:
    def __init__(self, rows=None, department_ids=None):
        self.rows = list(rows or [])
        self.department_ids = set(department_ids or set())
        self.added = []
        self.committed = False
        self.rollback_called = False

    def add(self, row):
        self.added.append(row)
        if isinstance(row, MediaGenerationJob):
            self.rows.append(row)

    async def flush(self):
        return None

    async def commit(self):
        self.committed = True

    async def refresh(self, _row):
        return None

    async def rollback(self):
        self.rollback_called = True

    async def get(self, model, row_id):
        if model is not MediaGenerationJob:
            return None
        return next((row for row in self.rows if row.id == row_id), None)

    async def execute(self, statement):
        statement_text = str(statement)
        if "user_departments" in statement_text:
            return FakeRowsResult(list(self.department_ids))
        if "audit_logs" in statement_text:
            rows = [row for row in self.rows if isinstance(row, AuditLog)]
            if "audit_logs.tenant_id = :tenant_id_1" in statement_text:
                rows = [
                    row
                    for row in rows
                    if row.tenant_id == _first_statement_param(statement, "tenant_id")
                ]
            if "audit_logs.resource_type = :resource_type_1" in statement_text:
                rows = [
                    row
                    for row in rows
                    if row.resource_type == _first_statement_param(statement, "resource_type")
                ]
            if "audit_logs.resource_id = :resource_id_1" in statement_text:
                rows = [
                    row
                    for row in rows
                    if row.resource_id == _first_statement_param(statement, "resource_id")
                ]
            return FakeRowsResult(rows)
        rows = [row for row in self.rows if isinstance(row, MediaGenerationJob)]
        params = statement.compile().params
        if "WHERE media_generation_jobs.tenant_id = :tenant_id_1" in statement_text:
            rows = [
                row
                for row in rows
                if row.tenant_id == _first_statement_param(statement, "tenant_id")
            ]
        if "media_generation_jobs.user_id = :user_id_1" in statement_text:
            user_id = _first_statement_param(statement, "user_id")
            department_ids = _statement_param_values(params, "department_id")
            rows = [
                row
                for row in rows
                if row.user_id == user_id
                or (row.department_id is not None and row.department_id in department_ids)
            ]
        if "media_generation_jobs.kind = :kind_1" in statement_text:
            rows = [row for row in rows if row.kind == _first_statement_param(statement, "kind")]
        if "media_generation_jobs.status = :status_1" in statement_text:
            rows = [
                row for row in rows if row.status == _first_statement_param(statement, "status")
            ]
        return FakeRowsResult(rows)


class FakeRowsResult:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return self.rows


def _first_statement_param(statement, prefix: str):
    for key, value in statement.compile().params.items():
        if key.startswith(prefix):
            return value
    return None


def _statement_param_values(params: dict, prefix: str) -> set:
    values = set()
    for key, value in params.items():
        if not key.startswith(prefix):
            continue
        if isinstance(value, (list, tuple, set)):
            values.update(value)
        else:
            values.add(value)
    return values


if __name__ == "__main__":
    unittest.main()
