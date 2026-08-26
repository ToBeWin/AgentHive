import unittest
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException

from app.api.deps import Principal
from app.media.schemas import (
    MediaGenerationKind,
    MediaGenerationMode,
    MediaGenerationPlan,
    MediaProviderType,
)
from app.models.audit_log import AuditLog
from app.models.llm import LLMPolicy
from app.services.media_generation_policy_service import enforce_media_generation_model_policy


class MediaGenerationPolicyServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_department_allow_policy_permits_media_generation_model(self):
        tenant_id = uuid4()
        department_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        policy = _policy(
            tenant_id=tenant_id,
            scope_type="department",
            scope_id=department_id,
            effect="allow",
            allowed_models=["google/nano-banana"],
            allowed_routing_keys=["image-generation"],
        )
        session = FakePolicySession([policy])

        await enforce_media_generation_model_policy(
            session,
            principal,
            _plan(model_key="google/nano-banana", routing_key="image-generation"),
            department_id=department_id,
            request_id="req-media-policy-allow",
        )

        self.assertEqual([], [row for row in session.added if isinstance(row, AuditLog)])
        self.assertEqual(0, session.commits)

    async def test_matched_policy_without_media_model_allow_denies_and_audits(self):
        tenant_id = uuid4()
        principal = Principal(tenant_id=tenant_id, user_id=uuid4(), permissions={"agents:write"})
        policy = _policy(
            tenant_id=tenant_id,
            scope_type="tenant",
            scope_id=None,
            effect="allow",
            allowed_models=["qwen-plus"],
            allowed_routing_keys=["qwen-chat"],
        )
        session = FakePolicySession([policy])

        with self.assertRaises(HTTPException) as raised:
            await enforce_media_generation_model_policy(
                session,
                principal,
                _plan(model_key="google/nano-banana", routing_key="image-generation"),
                request_id="req-media-policy-deny",
            )

        self.assertEqual(403, raised.exception.status_code)
        audits = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual(1, len(audits))
        self.assertEqual("media.generation.policy_denied", audits[0].action)
        self.assertEqual("failure", audits[0].status)
        self.assertEqual("google/nano-banana", audits[0].details["model_key"])
        self.assertEqual(1, session.commits)


def _policy(
    *,
    tenant_id,
    scope_type: str,
    scope_id,
    effect: str,
    allowed_models: list[str],
    allowed_routing_keys: list[str],
) -> LLMPolicy:
    return LLMPolicy(
        tenant_id=tenant_id,
        name="Media policy",
        scope_type=scope_type,
        scope_id=scope_id,
        effect=effect,
        allowed_models=allowed_models,
        allowed_routing_keys=allowed_routing_keys,
        priority=10,
        is_active=True,
    )


def _plan(*, model_key: str, routing_key: str) -> MediaGenerationPlan:
    return MediaGenerationPlan(
        kind=MediaGenerationKind.IMAGE,
        provider_key="google",
        provider_type=MediaProviderType.NANO_BANANA,
        model_key=model_key,
        routing_key=routing_key,
        mode=MediaGenerationMode.MANUAL_PROMPT,
        prompt="生成一张商品图",
        estimated_output_count=1,
        estimated_cost_usd=Decimal("0.030000"),
        pricing={"currency": "USD", "unit": "output"},
        normalized_parameters={"image_count": 1},
        reference_asset_count=0,
        output_storage={"driver": "minio"},
        execution={"mode": "sync_or_async"},
    )


class FakePolicySession:
    def __init__(self, policies):
        self.policies = policies
        self.added = []
        self.commits = 0
        self.rollback_called = False

    def add(self, row):
        self.added.append(row)

    async def execute(self, statement):
        statement_text = str(statement)
        if "llm_policies" in statement_text:
            return FakePoliciesResult(self.policies)
        return FakeScalarOneOrNoneResult(None)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollback_called = True


class FakePoliciesResult:
    def __init__(self, policies):
        self.policies = policies

    def scalars(self):
        return self

    def all(self):
        return self.policies


class FakeScalarOneOrNoneResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


if __name__ == "__main__":
    unittest.main()
