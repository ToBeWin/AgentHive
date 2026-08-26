from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.cost_center import resolve_cost_center
from app.llm.schemas import (
    ConnectionTestResult,
    LLMCallStatus,
    LLMRequestContext,
    LLMResponse,
    LLMUsageMetrics,
    RouteSelection,
    UsageRecord,
)
from app.models.llm import LLMUsage


class UsageCollector:
    """Collects usage ledger rows and audit-ready events."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session
        self.records: list[UsageRecord] = []
        self.audit_events: list[dict[str, object]] = []

    async def record_success(
        self,
        *,
        context: LLMRequestContext,
        route: RouteSelection,
        response: LLMResponse,
    ) -> UsageRecord:
        record = UsageRecord(
            request_id=context.request_id,
            tenant_id=context.tenant_id,
            status=LLMCallStatus.SUCCESS,
            provider_key=route.provider.provider_key,
            model_key=response.model_key,
            deployment_id=route.deployment.id,
            usage=response.usage,
            metadata={"route_reason": route.reason, **response.metadata},
        )
        await self._append(record, context=context)
        return record

    async def record_failure(
        self,
        *,
        context: LLMRequestContext,
        status: LLMCallStatus,
        error_code: str,
        error_message: str,
        route: RouteSelection | None = None,
        metadata: dict[str, object] | None = None,
    ) -> UsageRecord:
        record = UsageRecord(
            request_id=context.request_id,
            tenant_id=context.tenant_id,
            status=status,
            provider_key=route.provider.provider_key if route else None,
            model_key=route.deployment.model_key if route else None,
            deployment_id=route.deployment.id if route else None,
            usage=LLMUsageMetrics(),
            error_code=error_code,
            error_message=error_message,
            metadata=metadata or {},
        )
        await self._append(record, context=context)
        return record

    async def record_connection_test(
        self,
        *,
        context: LLMRequestContext,
        route: RouteSelection,
        result: ConnectionTestResult,
    ) -> UsageRecord:
        record = UsageRecord(
            request_id=context.request_id,
            tenant_id=context.tenant_id,
            status=LLMCallStatus.SUCCESS if result.ok else LLMCallStatus.ERROR,
            provider_key=route.provider.provider_key,
            model_key=result.model_key or route.deployment.model_key,
            deployment_id=route.deployment.id,
            usage=LLMUsageMetrics(),
            error_code=None if result.ok else "connection_test_failed",
            error_message=None if result.ok else result.message,
            metadata={
                "operation": "test_connection",
                "latency_ms": result.latency_ms,
                "diagnostics": result.diagnostics,
            },
        )
        await self._append(record, context=context)
        return record

    async def _append(self, record: UsageRecord, *, context: LLMRequestContext) -> None:
        self.records.append(record)
        cost_center_id, cost_center_source = await resolve_cost_center(self.session, context)
        self.audit_events.append(
            {
                "event_type": "llm.call",
                "request_id": record.request_id,
                "tenant_id": str(record.tenant_id),
                "status": record.status.value,
                "provider_key": record.provider_key,
                "model_key": record.model_key,
                "cost_usd": str(record.usage.cost_usd),
                "cost_center_id": str(cost_center_id) if cost_center_id else None,
            }
        )
        if self.session is None:
            return
        self.session.add(
            LLMUsage(
                tenant_id=context.tenant_id,
                deployment_id=record.deployment_id,
                user_id=context.user_id,
                department_id=context.department_id,
                cost_center_id=cost_center_id,
                agent_id=context.agent_id,
                channel_id=context.channel_id,
                conversation_id=context.conversation_id,
                request_id=record.request_id,
                model_key=record.model_key or "unknown",
                input_tokens=record.usage.input_tokens,
                output_tokens=record.usage.output_tokens,
                total_tokens=record.usage.total_tokens,
                cost_usd=record.usage.cost_usd,
                status=record.status.value,
                error_code=record.error_code,
                metadata_json={
                    "provider_key": record.provider_key,
                    "source": context.source,
                    "cost_center_source": cost_center_source,
                    "error_message": record.error_message,
                    **record.metadata,
                },
            )
        )
        await self.session.commit()
