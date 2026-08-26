import unittest
from decimal import Decimal
from uuid import uuid4

from app.api.deps import Principal
from app.llm.schemas import BudgetReservation
from app.models.llm import LLMUsage
from app.models.media import MediaGenerationJob
from app.services.media_generation_budget_service import (
    release_media_generation_budget,
    reservation_metadata,
    settle_media_generation_budget,
)


class MediaGenerationBudgetServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_settle_media_generation_budget_writes_model_usage_cost(self):
        tenant_id = uuid4()
        user_id = uuid4()
        job = _job(tenant_id=tenant_id, user_id=user_id)
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
        session = FakeMediaBudgetSession()
        principal = Principal(tenant_id=tenant_id, user_id=user_id, permissions={"agents:write"})

        await settle_media_generation_budget(session, principal, job, request_id="req-media-settle")

        usage_rows = [row for row in session.added if isinstance(row, LLMUsage)]
        self.assertEqual(1, len(usage_rows))
        self.assertEqual("volcengine/seedance-2.0", usage_rows[0].model_key)
        self.assertEqual(Decimal("0.400000"), usage_rows[0].cost_usd)
        self.assertEqual(0, usage_rows[0].total_tokens)
        self.assertEqual("media_generation", usage_rows[0].metadata_json["usage_family"])
        self.assertEqual(str(job.id), usage_rows[0].metadata_json["media_generation_job_id"])
        self.assertEqual("success", usage_rows[0].metadata_json["status"])
        self.assertEqual("0.400000", usage_rows[0].metadata_json["estimated_cost_usd"])
        self.assertEqual(5, usage_rows[0].metadata_json["duration_seconds"])
        self.assertEqual(24, usage_rows[0].metadata_json["fps"])
        self.assertEqual("1080p", usage_rows[0].metadata_json["resolution"])
        self.assertEqual(1, usage_rows[0].metadata_json["reference_asset_count"])
        self.assertEqual(2, usage_rows[0].metadata_json["output_count"])
        self.assertEqual("minio", usage_rows[0].metadata_json["output_storage"]["driver"])
        self.assertEqual(
            "generated/video_generation", usage_rows[0].metadata_json["output_storage"]["prefix"]
        )
        self.assertEqual(
            {"count": 1, "by_kind": {"video": 1}, "locations": {"minio": 1}},
            usage_rows[0].metadata_json["normalized_parameters"]["reference_assets"],
        )
        self.assertGreaterEqual(session.commit_count, 1)

    async def test_release_without_reservation_is_noop(self):
        tenant_id = uuid4()
        user_id = uuid4()
        job = _job(tenant_id=tenant_id, user_id=user_id)
        session = FakeMediaBudgetSession()
        principal = Principal(tenant_id=tenant_id, user_id=user_id, permissions={"agents:write"})

        await release_media_generation_budget(
            session,
            principal,
            job,
            request_id="req-media-release",
            reason="media_generation_failed",
        )

        self.assertEqual([], session.added)
        self.assertEqual(0, session.commit_count)


def _job(*, tenant_id, user_id) -> MediaGenerationJob:
    return MediaGenerationJob(
        id=uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        kind="video",
        mode="manual_prompt",
        status="succeeded",
        provider_key="volcengine",
        provider_type="volcengine_seedance",
        model_key="volcengine/seedance-2.0",
        routing_key="video-generation",
        prompt="test prompt",
        reference_assets=[
            {"kind": "video", "bucket": "agenthive-assets", "object_key": "refs/source.mp4"}
        ],
        normalized_parameters={
            "duration_seconds": 5,
            "fps": 24,
            "resolution": "1080p",
            "reference_assets": {"count": 1, "by_kind": {"video": 1}, "locations": {"minio": 1}},
        },
        output_storage={
            "driver": "minio",
            "bucket_scope": "tenant",
            "tenant_id": str(tenant_id),
            "prefix": "generated/video_generation",
            "temporary_callback_payload": {"ignored": True},
        },
        outputs=[
            {"object_key": "generated/video_generation/a.mp4"},
            {"object_key": "generated/video_generation/b.mp4"},
        ],
        metadata_json={},
    )


class FakeCostCenterResult:
    def scalar_one_or_none(self):
        return None


class FakeMediaBudgetSession:
    def __init__(self):
        self.added = []
        self.commit_count = 0
        self.rollback_called = False

    def add(self, row):
        self.added.append(row)

    async def execute(self, _statement):
        return FakeCostCenterResult()

    async def get(self, _model, _row_id):
        return None

    async def commit(self):
        self.commit_count += 1

    async def rollback(self):
        self.rollback_called = True


if __name__ == "__main__":
    unittest.main()
