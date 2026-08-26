from datetime import datetime, timezone
import json
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal
from app.llm import connection_diagnostics_service
from app.llm.schemas import ConnectionTestResult, LLMAdapterType, ProviderConfig
from app.models.audit_log import AuditLog
from app.schemas.llm import LLMConnectionTestRequest


pytestmark = pytest.mark.asyncio


class FakeAuditSession:
    def __init__(self) -> None:
        self.added: list[AuditLog] = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, row: AuditLog) -> None:
        self.added.append(row)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class HistoryResult:
    def __init__(self, rows: list[AuditLog]) -> None:
        self.rows = rows

    def scalars(self) -> "HistoryResult":
        return self

    def all(self) -> list[AuditLog]:
        return self.rows


class HistorySession:
    def __init__(self, rows: list[AuditLog]) -> None:
        self.rows = rows
        self.statement: object | None = None

    async def execute(self, statement: object) -> HistoryResult:
        self.statement = statement
        return HistoryResult(self.rows)


def make_principal() -> Principal:
    return Principal(tenant_id=uuid4(), user_id=uuid4(), permissions={"models:write"})


async def test_connection_orchestration_redacts_temporary_secrets_from_audit() -> None:
    session = FakeAuditSession()
    principal = make_principal()
    payload = LLMConnectionTestRequest(
        provider_key="openai_compatible",
        model_key="private-chat",
        base_url="https://private-llm.example/v1",
        api_key="sk-temporary-secret",
    )
    gateway = AsyncMock()
    gateway.test_connection.return_value = ConnectionTestResult(
        ok=False,
        provider_key="openai_compatible",
        adapter_type=LLMAdapterType.OPENAI_COMPATIBLE,
        model_key="private-chat",
        latency_ms=12,
        checked_at=datetime.now(timezone.utc),
        message="failed at https://private-llm.example/v1 with sk-temporary-secret",
        diagnostics={
            "route_attempts": [{"status": "error", "error_message": "sk-temporary-secret"}]
        },
    )

    response = await connection_diagnostics_service.run_connection_test(
        payload,
        principal,
        cast(AsyncSession, session),
        request_id="req-diagnostics-redaction",
        build_gateway=AsyncMock(return_value=gateway),
        provider_config=lambda _provider_key: ProviderConfig(
            provider_key="openai_compatible",
            name="OpenAI-compatible Endpoint",
            adapter_type=LLMAdapterType.OPENAI_COMPATIBLE,
        ),
        default_model_key=lambda _provider_key: "private-chat",
        default_routing_key=lambda _provider_key: "private-chat",
    )

    assert response.ok is False
    assert len(session.added) == 1
    serialized = json.dumps(session.added[0].details)
    assert "[REDACTED_BASE_URL]" in serialized
    assert "[REDACTED_API_KEY]" in serialized
    assert "private-llm.example" not in serialized
    assert "sk-temporary-secret" not in serialized


async def test_history_query_contains_principal_tenant_scope() -> None:
    principal = make_principal()
    event = AuditLog(
        tenant_id=principal.tenant_id,
        action="llm.connection_test",
        status="success",
        created_at=datetime.now(timezone.utc),
        details={"ok": True},
    )
    session = HistorySession([event])

    response = await connection_diagnostics_service.list_connection_test_history(
        cast(AsyncSession, session),
        principal,
        limit=10,
    )

    assert len(response.tests) == 1
    assert session.statement is not None
    statement_text = str(session.statement)
    assert "audit_logs.tenant_id" in statement_text
