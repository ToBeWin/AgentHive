import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import HTTPException
from kombu.exceptions import OperationalError

from app.api.deps import Principal
from app.models.audit_log import AuditLog
from app.models.media import MediaGenerationJob
from app.services.media_generation_queue_service import (
    enqueue_media_generation_job_for_worker,
    enqueue_media_generation_poll_for_worker,
    enqueue_running_media_generation_polls_for_worker,
)


class MediaGenerationQueueServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.module_gate_patch = patch(
            "app.services.media_generation_queue_service.ensure_media_generation_module_runnable",
            new_callable=AsyncMock,
        )
        self.module_gate = self.module_gate_patch.start()
        self.policy_gate_patch = patch(
            "app.services.media_generation_queue_service.enforce_media_generation_model_policy",
            new_callable=AsyncMock,
        )
        self.policy_gate = self.policy_gate_patch.start()
        self.provider_gate_patch = patch(
            "app.services.media_generation_queue_service.ensure_media_provider_configured",
            new_callable=AsyncMock,
        )
        self.provider_gate = self.provider_gate_patch.start()

    async def asyncTearDown(self):
        self.module_gate_patch.stop()
        self.policy_gate_patch.stop()
        self.provider_gate_patch.stop()

    async def test_enqueue_media_generation_job_returns_task_id_and_audits(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        job = _job(tenant_id=tenant_id, user_id=principal.user_id, status="queued")
        session = FakeQueueSession(rows=[job])

        with patch(
            "app.services.media_generation_queue_service.enqueue_worker_job",
            return_value=FakeAsyncResult("celery-task-1"),
        ) as enqueue:
            response = await enqueue_media_generation_job_for_worker(
                session,
                principal,
                job.id,
                request_id="req-enqueue",
            )

        self.assertTrue(response.queued)
        self.assertEqual(job.id, response.job_id)
        self.assertEqual("celery-task-1", response.task_id)
        self.assertEqual("celery-task-1", job.metadata_json["queue"]["task_id"])
        self.assertEqual("req-enqueue", job.metadata_json["queue"]["request_id"])
        self.assertEqual("queued", job.metadata_json["queue"]["status_at_enqueue"])
        enqueue.assert_called_once()
        audits = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual(1, len(audits))
        self.assertEqual("media.generation.enqueue", audits[0].action)
        self.assertEqual("celery-task-1", audits[0].details["task_id"])
        self.assertTrue(session.committed)
        self.module_gate.assert_awaited_once_with(session, principal, "image")
        self.provider_gate.assert_awaited_once()

    async def test_enqueue_media_generation_job_is_idempotent_while_status_unchanged(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        job = _job(tenant_id=tenant_id, user_id=principal.user_id, status="queued")
        job.metadata_json = {
            "queue": {"task_id": "celery-task-existing", "status_at_enqueue": "queued"}
        }
        session = FakeQueueSession(rows=[job])

        with patch("app.services.media_generation_queue_service.enqueue_worker_job") as enqueue:
            response = await enqueue_media_generation_job_for_worker(
                session,
                principal,
                job.id,
                request_id="req-enqueue-duplicate",
            )

        self.assertFalse(response.queued)
        self.assertEqual("celery-task-existing", response.task_id)
        enqueue.assert_not_called()
        audits = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual("media.generation.enqueue_skipped", audits[0].action)
        self.assertEqual("duplicate_active_queue", audits[0].details["reason"])
        self.assertTrue(session.committed)

    async def test_enqueue_media_generation_job_requires_configured_provider(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        job = _job(tenant_id=tenant_id, user_id=principal.user_id, status="queued")
        session = FakeQueueSession(rows=[job])
        self.provider_gate.side_effect = HTTPException(
            status_code=409,
            detail="Media provider openai_compatible_media is not configured.",
        )

        with patch("app.services.media_generation_queue_service.enqueue_worker_job") as enqueue:
            with self.assertRaises(HTTPException) as error:
                await enqueue_media_generation_job_for_worker(session, principal, job.id)

        self.assertEqual(409, error.exception.status_code)
        enqueue.assert_not_called()
        self.policy_gate.assert_not_awaited()
        self.assertFalse(session.committed)

    async def test_enqueue_media_generation_job_requires_enabled_module(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        job = _job(tenant_id=tenant_id, user_id=principal.user_id, status="queued")
        session = FakeQueueSession(rows=[job])
        self.module_gate.side_effect = HTTPException(
            status_code=403,
            detail="Enable agent.image_generation before using media generation.",
        )

        with self.assertRaises(HTTPException) as error:
            await enqueue_media_generation_job_for_worker(session, principal, job.id)

        self.assertEqual(403, error.exception.status_code)
        self.module_gate.assert_awaited_once_with(session, principal, "image")

    async def test_enqueue_media_generation_job_denies_other_user_private_job(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        job = _job(tenant_id=tenant_id, user_id=uuid4(), status="queued")
        session = FakeQueueSession(rows=[job])

        with patch("app.services.media_generation_queue_service.enqueue_worker_job") as enqueue:
            with self.assertRaises(HTTPException) as error:
                await enqueue_media_generation_job_for_worker(session, principal, job.id)

        self.assertEqual(403, error.exception.status_code)
        enqueue.assert_not_called()
        self.module_gate.assert_not_awaited()

    async def test_terminal_job_cannot_be_enqueued(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        job = _job(tenant_id=tenant_id, user_id=principal.user_id, status="failed")
        session = FakeQueueSession(rows=[job])

        with self.assertRaises(HTTPException) as error:
            await enqueue_media_generation_job_for_worker(session, principal, job.id)

        self.assertEqual(409, error.exception.status_code)

    async def test_queue_unavailable_returns_service_unavailable(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        job = _job(tenant_id=tenant_id, user_id=principal.user_id, status="queued")
        session = FakeQueueSession(rows=[job])

        with patch(
            "app.services.media_generation_queue_service.enqueue_worker_job",
            side_effect=OperationalError("redis unavailable"),
        ):
            with self.assertRaises(HTTPException) as error:
                await enqueue_media_generation_job_for_worker(session, principal, job.id)

        self.assertEqual(503, error.exception.status_code)
        self.assertTrue(session.rollback_called)

    async def test_enqueue_media_generation_poll_returns_task_id_and_audits(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        job = _job(
            tenant_id=tenant_id,
            user_id=principal.user_id,
            status="running",
            external_job_id="provider-task-1",
        )
        session = FakeQueueSession(rows=[job])

        with patch(
            "app.services.media_generation_queue_service.enqueue_worker_poll",
            return_value=FakeAsyncResult("celery-poll-1"),
        ) as enqueue:
            response = await enqueue_media_generation_poll_for_worker(
                session,
                principal,
                job.id,
                request_id="req-poll-enqueue",
            )

        self.assertTrue(response.queued)
        self.assertEqual(job.id, response.job_id)
        self.assertEqual("celery-poll-1", response.task_id)
        self.assertEqual("celery-poll-1", job.metadata_json["poll_queue"]["task_id"])
        self.assertEqual("provider-task-1", job.metadata_json["poll_queue"]["external_job_id"])
        enqueue.assert_called_once()
        audits = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual("media.generation.poll_enqueue", audits[0].action)
        self.assertEqual("provider-task-1", audits[0].details["external_job_id"])
        self.assertTrue(session.committed)

    async def test_enqueue_media_generation_poll_is_idempotent_for_same_external_job(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        job = _job(
            tenant_id=tenant_id,
            user_id=principal.user_id,
            status="running",
            external_job_id="provider-task-1",
        )
        job.metadata_json = {
            "poll_queue": {
                "task_id": "celery-poll-existing",
                "status_at_enqueue": "running",
                "external_job_id": "provider-task-1",
            }
        }
        session = FakeQueueSession(rows=[job])

        with patch("app.services.media_generation_queue_service.enqueue_worker_poll") as enqueue:
            response = await enqueue_media_generation_poll_for_worker(
                session,
                principal,
                job.id,
                request_id="req-poll-duplicate",
            )

        self.assertFalse(response.queued)
        self.assertEqual("celery-poll-existing", response.task_id)
        enqueue.assert_not_called()
        audits = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual("media.generation.poll_enqueue_skipped", audits[0].action)
        self.assertEqual("duplicate_active_queue", audits[0].details["reason"])
        self.assertTrue(session.committed)

    async def test_enqueue_media_generation_poll_requires_running_external_job(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        queued_job = _job(
            tenant_id=tenant_id,
            user_id=principal.user_id,
            status="queued",
            external_job_id="provider-task-1",
        )
        missing_external = _job(tenant_id=tenant_id, user_id=principal.user_id, status="running")
        session = FakeQueueSession(rows=[queued_job, missing_external])

        with self.assertRaises(HTTPException) as queued_error:
            await enqueue_media_generation_poll_for_worker(session, principal, queued_job.id)
        with self.assertRaises(HTTPException) as missing_external_error:
            await enqueue_media_generation_poll_for_worker(session, principal, missing_external.id)

        self.assertEqual(409, queued_error.exception.status_code)
        self.assertEqual(409, missing_external_error.exception.status_code)

    async def test_poll_queue_unavailable_returns_service_unavailable(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        job = _job(
            tenant_id=tenant_id,
            user_id=principal.user_id,
            status="running",
            external_job_id="provider-task-1",
        )
        session = FakeQueueSession(rows=[job])

        with patch(
            "app.services.media_generation_queue_service.enqueue_worker_poll",
            side_effect=OperationalError("redis unavailable"),
        ):
            with self.assertRaises(HTTPException) as error:
                await enqueue_media_generation_poll_for_worker(session, principal, job.id)

        self.assertEqual(503, error.exception.status_code)
        self.assertTrue(session.rollback_called)

    async def test_enqueue_running_media_generation_polls_batches_candidates(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        first = _job(
            tenant_id=tenant_id,
            user_id=principal.user_id,
            status="running",
            external_job_id="provider-task-1",
        )
        second = _job(
            tenant_id=tenant_id,
            user_id=principal.user_id,
            status="running",
            external_job_id="provider-task-2",
        )
        queued = _job(
            tenant_id=tenant_id,
            user_id=principal.user_id,
            status="queued",
            external_job_id="provider-task-3",
        )
        missing_external = _job(tenant_id=tenant_id, user_id=principal.user_id, status="running")
        session = FakeQueueSession(rows=[first, second, queued, missing_external])

        with patch(
            "app.services.media_generation_queue_service.enqueue_worker_poll",
            side_effect=[FakeAsyncResult("celery-poll-1"), FakeAsyncResult("celery-poll-2")],
        ):
            response = await enqueue_running_media_generation_polls_for_worker(
                session,
                principal,
                limit=20,
                request_id="req-batch-poll",
            )

        self.assertEqual(2, response.requested)
        self.assertEqual(2, response.queued)
        self.assertEqual(0, response.failed)
        self.assertEqual(
            ["celery-poll-1", "celery-poll-2"], [item.task_id for item in response.items]
        )
        self.assertEqual("provider-task-1", response.items[0].external_job_id)
        audits = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual(
            ["media.generation.poll_enqueue", "media.generation.poll_enqueue"],
            [row.action for row in audits],
        )

    async def test_enqueue_running_media_generation_polls_filters_inaccessible_candidates_before_limit(
        self,
    ):
        tenant_id = uuid4()
        department_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        own_job = _job(
            tenant_id=tenant_id,
            user_id=principal.user_id,
            status="running",
            external_job_id="own-task",
        )
        department_job = _job(
            tenant_id=tenant_id,
            user_id=uuid4(),
            department_id=department_id,
            status="running",
            external_job_id="department-task",
        )
        private_other_job = _job(
            tenant_id=tenant_id, user_id=uuid4(), status="running", external_job_id="other-task"
        )
        session = FakeQueueSession(
            rows=[private_other_job, own_job, department_job],
            department_ids={department_id},
        )

        with patch(
            "app.services.media_generation_queue_service.enqueue_worker_poll",
            side_effect=[FakeAsyncResult("celery-own"), FakeAsyncResult("celery-department")],
        ):
            response = await enqueue_running_media_generation_polls_for_worker(
                session, principal, limit=20
            )

        self.assertEqual(2, response.requested)
        self.assertEqual(2, response.queued)
        self.assertEqual({own_job.id, department_job.id}, {item.job_id for item in response.items})

    async def test_enqueue_running_media_generation_polls_reports_partial_failures(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        first = _job(
            tenant_id=tenant_id,
            user_id=principal.user_id,
            status="running",
            external_job_id="provider-task-1",
        )
        second = _job(
            tenant_id=tenant_id,
            user_id=principal.user_id,
            status="running",
            external_job_id="provider-task-2",
        )
        session = FakeQueueSession(rows=[first, second])

        with patch(
            "app.services.media_generation_queue_service.enqueue_worker_poll",
            side_effect=[FakeAsyncResult("celery-poll-1"), OperationalError("redis unavailable")],
        ):
            response = await enqueue_running_media_generation_polls_for_worker(
                session,
                principal,
                limit=20,
                request_id="req-batch-partial",
            )

        self.assertEqual(2, response.requested)
        self.assertEqual(1, response.queued)
        self.assertEqual(1, response.failed)
        self.assertEqual("celery-poll-1", response.items[0].task_id)
        self.assertIn("unavailable", response.items[1].reason or "")

    async def test_enqueue_running_media_generation_polls_counts_duplicate_as_skipped(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        duplicate = _job(
            tenant_id=tenant_id,
            user_id=principal.user_id,
            status="running",
            external_job_id="provider-task-existing",
        )
        duplicate.metadata_json = {
            "poll_queue": {
                "task_id": "celery-poll-existing",
                "status_at_enqueue": "running",
                "external_job_id": "provider-task-existing",
            }
        }
        fresh = _job(
            tenant_id=tenant_id,
            user_id=principal.user_id,
            status="running",
            external_job_id="provider-task-new",
        )
        session = FakeQueueSession(rows=[duplicate, fresh])

        with patch(
            "app.services.media_generation_queue_service.enqueue_worker_poll",
            return_value=FakeAsyncResult("celery-poll-new"),
        ):
            response = await enqueue_running_media_generation_polls_for_worker(
                session,
                principal,
                limit=20,
                request_id="req-batch-skipped",
            )

        self.assertEqual(2, response.requested)
        self.assertEqual(1, response.queued)
        self.assertEqual(1, response.skipped)
        self.assertEqual(0, response.failed)
        self.assertEqual("celery-poll-existing", response.items[0].task_id)
        self.assertFalse(response.items[0].queued)
        self.assertEqual("duplicate_active_queue", response.items[0].reason)


def _job(
    *,
    tenant_id,
    status: str,
    user_id=None,
    department_id=None,
    external_job_id: str | None = None,
) -> MediaGenerationJob:
    return MediaGenerationJob(
        tenant_id=tenant_id,
        user_id=user_id or uuid4(),
        department_id=department_id,
        kind="image",
        mode="manual_prompt",
        status=status,
        provider_key="openai_compatible_media",
        provider_type="openai_compatible_media",
        model_key="openai-compatible-image",
        routing_key="private-image-generation",
        prompt="test prompt",
        normalized_parameters={},
        output_storage={"driver": "minio"},
        external_job_id=external_job_id,
        metadata_json={},
    )


class FakeAsyncResult:
    def __init__(self, task_id: str):
        self.id = task_id


class FakeQueueSession:
    def __init__(self, rows=None, department_ids=None):
        self.rows = list(rows or [])
        self.department_ids = set(department_ids or set())
        self.added = []
        self.committed = False
        self.rollback_called = False

    def add(self, row):
        self.added.append(row)

    async def get(self, model, row_id):
        if model is not MediaGenerationJob:
            return None
        return next((row for row in self.rows if row.id == row_id), None)

    async def execute(self, statement):
        statement_text = str(statement)
        if "user_departments" in statement_text:
            return FakeRowsResult(list(self.department_ids))
        params = statement.compile().params
        tenant_id = next(
            (value for key, value in params.items() if key.startswith("tenant_id")), None
        )
        status = next((value for key, value in params.items() if key.startswith("status")), None)
        user_id = next((value for key, value in params.items() if key.startswith("user_id")), None)
        department_ids = _statement_param_values(params, "department_id")
        rows = [
            row
            for row in self.rows
            if row.tenant_id == tenant_id
            and row.status == status
            and row.external_job_id is not None
        ]
        if "media_generation_jobs.user_id = :user_id_1" in statement_text:
            rows = [
                row
                for row in rows
                if row.user_id == user_id
                or (row.department_id is not None and row.department_id in department_ids)
            ]
        return FakeRowsResult(rows)

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rollback_called = True


class FakeRowsResult:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return self.rows


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
