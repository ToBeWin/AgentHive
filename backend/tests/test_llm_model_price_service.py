from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
import unittest

from fastapi import HTTPException

from app.api.deps import Principal
from app.models.llm import LLMModel, LLMModelPrice
from app.models.user import User
from app.schemas.llm import LLMModelPriceUpsertRequest
from app.services.llm_service import list_model_prices, upsert_model_price


class FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeRowsResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeListPriceSession:
    def __init__(self, rows):
        self.rows = rows

    async def execute(self, _statement):
        return FakeRowsResult(self.rows)


class FakePriceSession:
    def __init__(self, *, actor=None, existing_model=None, existing_price=None):
        self.actor = actor
        self.existing_model = existing_model
        self.existing_price = existing_price
        self.added = []
        self.commits = 0
        self.flushes = 0
        self.refreshes = []
        self.execute_count = 0

    async def get(self, model, row_id):
        if model is User and self.actor is not None and self.actor.id == row_id:
            return self.actor
        return None

    def add(self, row):
        self.added.append(row)
        if isinstance(row, LLMModel):
            self.existing_model = row
        elif row.__class__.__name__ == "LLMModelPrice":
            self.existing_price = row

    async def execute(self, _statement):
        self.execute_count += 1
        if self.execute_count == 1:
            return FakeScalarResult(self.existing_model)
        return FakeScalarResult(self.existing_price)

    async def flush(self):
        self.flushes += 1

    async def commit(self):
        self.commits += 1

    async def refresh(self, row):
        self.refreshes.append(row)


def make_principal(*, tenant_id=None, user_id=None, tenant_admin: bool = False) -> Principal:
    permissions = {"models:write"}
    if tenant_admin:
        permissions.add("tenant.admin")
    return Principal(
        tenant_id=tenant_id or uuid4(),
        user_id=user_id or uuid4(),
        permissions=permissions,
    )


def make_super_admin_session() -> tuple[FakePriceSession, Principal]:
    principal = make_principal()
    actor = User(
        id=principal.user_id,
        tenant_id=principal.tenant_id,
        email="platform-admin@example.com",
        hashed_password="unused-test-hash",
        is_super_admin=True,
        is_active=True,
    )
    return FakePriceSession(actor=actor), principal


class LLMModelPriceServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_model_prices_maps_model_and_price_rows(self):
        model = LLMModel(
            provider_key="deepseek",
            model_key="deepseek-chat",
            display_name="DeepSeek Contract",
        )
        price = LLMModelPrice(
            model_id=model.id,
            currency="USD",
            input_per_1k_tokens=Decimal("0.01"),
            output_per_1k_tokens=Decimal("0.02"),
            effective_from=datetime(2026, 6, 12, tzinfo=timezone.utc),
        )
        response = await list_model_prices(FakeListPriceSession(rows=[(price, model)]))

        self.assertEqual(1, len(response.prices))
        self.assertEqual("deepseek", response.prices[0].provider_key)
        self.assertEqual("deepseek-chat", response.prices[0].model_key)
        self.assertEqual(Decimal("0.01"), response.prices[0].input_per_1k_tokens)

    async def test_upsert_model_price_creates_model_price_and_audit_event(self):
        session, principal = make_super_admin_session()
        effective_from = datetime(2026, 6, 12, tzinfo=timezone.utc)

        response = await upsert_model_price(
            session,
            LLMModelPriceUpsertRequest(
                provider_key="qwen",
                model_key="qwen-plus",
                display_name="Qwen Contract",
                input_per_1k_tokens=Decimal("0.12"),
                output_per_1k_tokens=Decimal("0.34"),
                effective_from=effective_from,
            ),
            principal,
            request_id="req-price",
        )

        self.assertEqual("qwen", response.provider_key)
        self.assertEqual("qwen-plus", response.model_key)
        self.assertEqual("Qwen Contract", response.display_name)
        self.assertEqual(Decimal("0.12"), response.input_per_1k_tokens)
        self.assertEqual(Decimal("0.34"), response.output_per_1k_tokens)
        self.assertEqual(1, session.commits)
        self.assertGreaterEqual(len(session.added), 3)
        self.assertTrue(any(row.__class__.__name__ == "AuditLog" for row in session.added))

    async def test_tenant_model_admin_cannot_modify_global_model_price(self):
        tenant_id = uuid4()
        principal = make_principal(tenant_id=tenant_id, tenant_admin=True)
        actor = User(
            id=principal.user_id,
            tenant_id=tenant_id,
            email="tenant-admin@example.com",
            hashed_password="unused-test-hash",
            is_tenant_admin=True,
            is_active=True,
        )
        model = LLMModel(
            provider_key="qwen",
            model_key="qwen-plus",
            display_name="Global Qwen",
        )
        price = LLMModelPrice(
            model_id=model.id,
            input_per_1k_tokens=Decimal("0.10"),
            output_per_1k_tokens=Decimal("0.20"),
            effective_from=datetime(2026, 6, 12, tzinfo=timezone.utc),
        )
        session = FakePriceSession(actor=actor, existing_model=model, existing_price=price)

        with self.assertRaises(HTTPException) as raised:
            await upsert_model_price(
                session,
                LLMModelPriceUpsertRequest(
                    provider_key="qwen",
                    model_key="qwen-plus",
                    input_per_1k_tokens=Decimal("999"),
                    output_per_1k_tokens=Decimal("999"),
                    effective_from=price.effective_from,
                ),
                principal,
            )

        self.assertEqual(403, raised.exception.status_code)
        self.assertIn("platform super administrator", str(raised.exception.detail))
        self.assertEqual(Decimal("0.10"), price.input_per_1k_tokens)
        self.assertEqual(Decimal("0.20"), price.output_per_1k_tokens)
        self.assertEqual(0, session.execute_count)
        self.assertEqual(0, session.commits)

    async def test_super_admin_identity_must_match_principal_tenant(self):
        principal = make_principal()
        actor = User(
            id=principal.user_id,
            tenant_id=uuid4(),
            email="foreign-super-admin@example.com",
            hashed_password="unused-test-hash",
            is_super_admin=True,
            is_active=True,
        )
        session = FakePriceSession(actor=actor)

        with self.assertRaises(HTTPException) as raised:
            await upsert_model_price(
                session,
                LLMModelPriceUpsertRequest(
                    provider_key="qwen",
                    model_key="qwen-plus",
                    input_per_1k_tokens=Decimal("1"),
                    output_per_1k_tokens=Decimal("1"),
                ),
                principal,
            )

        self.assertEqual(403, raised.exception.status_code)
        self.assertEqual(0, session.execute_count)
        self.assertEqual(0, session.commits)

    async def test_upsert_model_price_rejects_non_usd_currency(self):
        session, principal = make_super_admin_session()
        with self.assertRaises(HTTPException) as raised:
            await upsert_model_price(
                session,
                LLMModelPriceUpsertRequest(
                    provider_key="qwen",
                    model_key="qwen-plus",
                    currency="CNY",
                    input_per_1k_tokens=Decimal("1"),
                    output_per_1k_tokens=Decimal("1"),
                ),
                principal,
            )

        self.assertEqual(422, raised.exception.status_code)

    async def test_upsert_model_price_rejects_effective_to_before_default_start(self):
        session, principal = make_super_admin_session()
        with self.assertRaises(HTTPException) as raised:
            await upsert_model_price(
                session,
                LLMModelPriceUpsertRequest(
                    provider_key="qwen",
                    model_key="qwen-plus",
                    input_per_1k_tokens=Decimal("1"),
                    output_per_1k_tokens=Decimal("1"),
                    effective_to=datetime.now(timezone.utc) - timedelta(days=1),
                ),
                principal,
            )

        self.assertEqual(422, raised.exception.status_code)


if __name__ == "__main__":
    unittest.main()
