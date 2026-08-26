import unittest
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException

from app.api.deps import Principal
from app.models.audit_log import AuditLog
from app.models.llm import LLMPolicy
from app.schemas.llm import LLMPolicyEffect, LLMPolicyScope, LLMPolicyStatus, LLMPolicyUpsertRequest
from app.services.llm_service import upsert_model_policy


class LLMPolicyUpsertServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_cost_center_model_policy_persists_scope_and_audit(self) -> None:
        principal = Principal(
            tenant_id=uuid4(),
            user_id=uuid4(),
            permissions={"models:write"},
        )
        cost_center_id = uuid4()
        session = FakePolicyUpsertSession(scope_target_exists=True)

        response = await upsert_model_policy(
            session,
            LLMPolicyUpsertRequest(
                name="Operations cost center policy",
                scope_type=LLMPolicyScope.COST_CENTER,
                scope_id=cost_center_id,
                effect=LLMPolicyEffect.ALLOW,
                allowed_models=["qwen-plus", "qwen-plus"],
                allowed_routing_keys=["ops-qwen"],
                default_routing_key="ops-qwen",
                max_tokens=2048,
                priority=50,
                status=LLMPolicyStatus.ACTIVE,
            ),
            principal,
            request_id="req-policy-cost-center",
        )

        policy = next(row for row in session.added if isinstance(row, LLMPolicy))
        self.assertEqual(LLMPolicyScope.COST_CENTER, response.scope_type)
        self.assertEqual(cost_center_id, response.scope_id)
        self.assertEqual("cost_center", policy.scope_type)
        self.assertEqual(cost_center_id, policy.scope_id)
        self.assertEqual(["qwen-plus"], policy.allowed_models)
        audit_events = [row for row in session.added if isinstance(row, AuditLog)]
        self.assertEqual(1, len(audit_events))
        self.assertEqual("llm.policy.create", audit_events[0].action)
        self.assertEqual("cost_center", audit_events[0].details["scope_type"])
        self.assertEqual(str(cost_center_id), audit_events[0].details["scope_id"])
        self.assertEqual(1, session.commits)
        self.assertEqual(1, session.refreshes)

    async def test_create_scoped_model_policy_rejects_unknown_tenant_target_without_side_effects(
        self,
    ) -> None:
        principal = Principal(
            tenant_id=uuid4(),
            user_id=uuid4(),
            permissions={"models:write"},
        )

        for scope_type in (
            LLMPolicyScope.DEPARTMENT,
            LLMPolicyScope.COST_CENTER,
            LLMPolicyScope.USER,
            LLMPolicyScope.AGENT,
            LLMPolicyScope.CHANNEL,
        ):
            with self.subTest(scope_type=scope_type):
                session = FakePolicyUpsertSession(scope_target_exists=False)
                with self.assertRaises(HTTPException) as raised:
                    await upsert_model_policy(
                        session,
                        LLMPolicyUpsertRequest(
                            name=f"{scope_type.value} policy",
                            scope_type=scope_type,
                            scope_id=uuid4(),
                            effect=LLMPolicyEffect.ALLOW,
                            allowed_models=["qwen-plus"],
                            allowed_routing_keys=["ops-qwen"],
                            default_routing_key="ops-qwen",
                            status=LLMPolicyStatus.ACTIVE,
                        ),
                        principal,
                        request_id="req-policy-scope",
                    )

                self.assertEqual(404, raised.exception.status_code)
                self.assertIn(scope_type.value, str(raised.exception.detail))
                self.assertEqual([], session.added)
                self.assertEqual(0, session.commits)
                self.assertEqual(0, session.refreshes)

    async def test_create_model_policy_rejects_blank_name_without_side_effects(self) -> None:
        principal = Principal(
            tenant_id=uuid4(),
            user_id=uuid4(),
            permissions={"models:write"},
        )
        session = FakePolicyUpsertSession()

        with self.assertRaises(HTTPException) as raised:
            await upsert_model_policy(
                session,
                LLMPolicyUpsertRequest(
                    name="   ",
                    effect=LLMPolicyEffect.ALLOW,
                    allowed_models=["qwen-plus"],
                    default_model_key="qwen-plus",
                    status=LLMPolicyStatus.ACTIVE,
                ),
                principal,
            )

        self.assertEqual(422, raised.exception.status_code)
        self.assertIn("name", str(raised.exception.detail))
        self.assertEqual([], session.added)
        self.assertEqual(0, session.commits)

    async def test_create_allow_policy_rejects_empty_target_without_side_effects(self) -> None:
        principal = Principal(
            tenant_id=uuid4(),
            user_id=uuid4(),
            permissions={"models:write"},
        )
        session = FakePolicyUpsertSession()

        with self.assertRaises(HTTPException) as raised:
            await upsert_model_policy(
                session,
                LLMPolicyUpsertRequest(
                    name="Tenant allow policy",
                    effect=LLMPolicyEffect.ALLOW,
                    status=LLMPolicyStatus.ACTIVE,
                ),
                principal,
            )

        self.assertEqual(422, raised.exception.status_code)
        self.assertIn("at least one model", str(raised.exception.detail))
        self.assertEqual([], session.added)
        self.assertEqual(0, session.commits)

    async def test_create_model_policy_rejects_default_model_outside_allowed_list(self) -> None:
        principal = Principal(
            tenant_id=uuid4(),
            user_id=uuid4(),
            permissions={"models:write"},
        )
        session = FakePolicyUpsertSession()

        with self.assertRaises(HTTPException) as raised:
            await upsert_model_policy(
                session,
                LLMPolicyUpsertRequest(
                    name="Tenant model policy",
                    effect=LLMPolicyEffect.ALLOW,
                    allowed_models=["qwen-plus"],
                    default_model_key="deepseek-v4-flash",
                    status=LLMPolicyStatus.ACTIVE,
                ),
                principal,
            )

        self.assertEqual(422, raised.exception.status_code)
        self.assertIn("default_model_key", str(raised.exception.detail))
        self.assertEqual([], session.added)
        self.assertEqual(0, session.commits)

    async def test_create_model_policy_rejects_default_only_targets_without_side_effects(
        self,
    ) -> None:
        principal = Principal(
            tenant_id=uuid4(),
            user_id=uuid4(),
            permissions={"models:write"},
        )

        for payload, expected in (
            (
                LLMPolicyUpsertRequest(
                    name="Default-only model policy",
                    effect=LLMPolicyEffect.ALLOW,
                    default_model_key="qwen-plus",
                    status=LLMPolicyStatus.ACTIVE,
                ),
                "default_model_key",
            ),
            (
                LLMPolicyUpsertRequest(
                    name="Default-only route policy",
                    effect=LLMPolicyEffect.ALLOW,
                    default_routing_key="ops-qwen",
                    status=LLMPolicyStatus.ACTIVE,
                ),
                "default_routing_key",
            ),
        ):
            with self.subTest(expected=expected):
                session = FakePolicyUpsertSession()
                with self.assertRaises(HTTPException) as raised:
                    await upsert_model_policy(session, payload, principal)

                self.assertEqual(422, raised.exception.status_code)
                self.assertIn(expected, str(raised.exception.detail))
                self.assertEqual([], session.added)
                self.assertEqual(0, session.commits)

    async def test_create_model_policy_rejects_missing_active_model_or_route(self) -> None:
        principal = Principal(
            tenant_id=uuid4(),
            user_id=uuid4(),
            permissions={"models:write"},
        )

        for payload, expected in (
            (
                LLMPolicyUpsertRequest(
                    name="Missing model policy",
                    effect=LLMPolicyEffect.ALLOW,
                    allowed_models=["missing-model"],
                    default_model_key="missing-model",
                    status=LLMPolicyStatus.ACTIVE,
                ),
                "model_key",
            ),
            (
                LLMPolicyUpsertRequest(
                    name="Missing route policy",
                    effect=LLMPolicyEffect.ALLOW,
                    allowed_routing_keys=["missing-route"],
                    default_routing_key="missing-route",
                    status=LLMPolicyStatus.ACTIVE,
                ),
                "routing_key",
            ),
        ):
            with self.subTest(expected=expected):
                session = FakePolicyUpsertSession()
                with self.assertRaises(HTTPException) as raised:
                    await upsert_model_policy(session, payload, principal)

                self.assertEqual(422, raised.exception.status_code)
                self.assertIn(expected, str(raised.exception.detail))
                self.assertEqual([], session.added)
                self.assertEqual(0, session.commits)

    async def test_create_model_policy_rejects_max_tokens_above_model_context_window(self) -> None:
        principal = Principal(
            tenant_id=uuid4(),
            user_id=uuid4(),
            permissions={"models:write"},
        )
        session = FakePolicyUpsertSession(
            deployments=[make_deployment_row("qwen-plus", "ops-qwen", 4096)]
        )

        with self.assertRaises(HTTPException) as raised:
            await upsert_model_policy(
                session,
                LLMPolicyUpsertRequest(
                    name="Oversized token cap",
                    effect=LLMPolicyEffect.ALLOW,
                    allowed_models=["qwen-plus"],
                    default_model_key="qwen-plus",
                    max_tokens=8192,
                    status=LLMPolicyStatus.ACTIVE,
                ),
                principal,
            )

        self.assertEqual(422, raised.exception.status_code)
        self.assertIn("context window", str(raised.exception.detail))
        self.assertEqual([], session.added)
        self.assertEqual(0, session.commits)

    async def test_create_model_policy_normalizes_keys_before_persisting(self) -> None:
        principal = Principal(
            tenant_id=uuid4(),
            user_id=uuid4(),
            permissions={"models:write"},
        )
        session = FakePolicyUpsertSession()

        response = await upsert_model_policy(
            session,
            LLMPolicyUpsertRequest(
                name="  Tenant default policy  ",
                description="  trimmed  ",
                effect=LLMPolicyEffect.ALLOW,
                allowed_models=[" qwen-plus ", "qwen-plus", " "],
                allowed_routing_keys=[" ops-qwen ", "ops-qwen"],
                default_model_key=" qwen-plus ",
                default_routing_key=" ops-qwen ",
                max_tokens=2048,
                status=LLMPolicyStatus.ACTIVE,
            ),
            principal,
        )

        policy = next(row for row in session.added if isinstance(row, LLMPolicy))
        self.assertEqual("Tenant default policy", response.name)
        self.assertEqual("trimmed", response.description)
        self.assertEqual(["qwen-plus"], policy.allowed_models)
        self.assertEqual(["ops-qwen"], policy.allowed_routing_keys)
        self.assertEqual("qwen-plus", policy.default_model_key)
        self.assertEqual("ops-qwen", policy.default_routing_key)
        self.assertEqual(1, session.commits)


class FakePolicyUpsertSession:
    def __init__(self, *, scope_target_exists=None, deployments=None) -> None:
        self.added: list[object] = []
        self.commits = 0
        self.refreshes = 0
        self.scope_target_exists = scope_target_exists
        self.deployments = deployments or [make_deployment_row("qwen-plus", "ops-qwen", 8192)]
        self.scope_checked = False

    def add(self, row: object) -> None:
        self.added.append(row)

    async def execute(self, _statement):
        if self.scope_target_exists is not None and not self.scope_checked:
            self.scope_checked = True
            return FakeScalarOneOrNoneResult(uuid4() if self.scope_target_exists else None)
        return FakeRowsResult(self.deployments)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, _row: object) -> None:
        self.refreshes += 1


class FakeScalarOneOrNoneResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeRowsResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


def make_deployment_row(model_key: str, routing_key: str, context_window: int | None):
    deployment = SimpleNamespace(routing_key=routing_key)
    provider = SimpleNamespace()
    model = SimpleNamespace(model_key=model_key, context_window=context_window)
    return deployment, provider, model


if __name__ == "__main__":
    unittest.main()
