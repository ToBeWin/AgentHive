from decimal import Decimal
from datetime import datetime, timedelta, timezone
from typing import Any, cast
from uuid import UUID

from sqlalchemy import ColumnElement, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.base import utc_now
from app.models.llm import LLMBudget, LLMBudgetLedger, LLMUsage
from app.llm.cost_center import resolve_cost_center
from app.llm.pricing import ModelPricingCatalog
from app.llm.schemas import (
    BudgetReservation,
    BudgetReservationScope,
    LLMChatRequest,
    LLMRequestContext,
    LLMUsageMetrics,
)


class BudgetGuard:
    """Pre-call budget reservation and post-call settlement boundary."""

    def __init__(
        self,
        pricing: ModelPricingCatalog | None = None,
        session: AsyncSession | None = None,
    ):
        self.pricing = pricing or ModelPricingCatalog()
        self.session = session

    async def reserve(
        self,
        request: LLMChatRequest,
        context: LLMRequestContext,
    ) -> BudgetReservation:
        estimate = self.pricing.estimate(request)
        return await self.reserve_usage(estimate, context)

    async def reserve_usage(
        self,
        estimate: LLMUsageMetrics,
        context: LLMRequestContext,
        *,
        metadata: dict[str, object] | None = None,
    ) -> BudgetReservation:
        if self.session is not None:
            try:
                policies = await self._matching_policies(context)
                denial = await self._first_hard_limit_denial(context, estimate, policies)
            except (OSError, SQLAlchemyError):
                await self.session.rollback()
                return BudgetReservation(
                    approved=False,
                    reason="budget_storage_unavailable",
                    estimated_tokens=estimate.total_tokens,
                    estimated_cost_usd=estimate.cost_usd,
                )
            if denial is not None:
                policy, reason = denial
                reservation = BudgetReservation(
                    approved=False,
                    reason=reason,
                    estimated_tokens=estimate.total_tokens,
                    estimated_cost_usd=estimate.cost_usd,
                    budget_scopes=[_reservation_scope(policy)],
                )
                await self._record_budget_event(
                    reservation=reservation,
                    context=context,
                    event_type="deny",
                    scope=reservation.budget_scopes[0],
                    estimated_usage=estimate,
                    reason=reason,
                    metadata=metadata,
                )
                return reservation

            reservation = BudgetReservation(
                approved=True,
                reason="budget_approved",
                estimated_tokens=estimate.total_tokens,
                estimated_cost_usd=estimate.cost_usd,
                budget_scopes=[_reservation_scope(policy) for policy in policies],
            )
            for scope in reservation.budget_scopes:
                await self._record_budget_event(
                    reservation=reservation,
                    context=context,
                    event_type="reserve",
                    scope=scope,
                    estimated_usage=estimate,
                    reason="budget_reserved",
                    metadata=metadata,
                )
            return reservation
        return BudgetReservation(
            approved=True,
            reason="budget_approved",
            estimated_tokens=estimate.total_tokens,
            estimated_cost_usd=estimate.cost_usd,
        )

    async def settle(
        self,
        reservation: BudgetReservation,
        actual_usage: LLMUsageMetrics,
        context: LLMRequestContext,
    ) -> None:
        if self.session is None or not reservation.approved:
            return
        for scope in reservation.budget_scopes:
            await self._record_budget_event(
                reservation=reservation,
                context=context,
                event_type="settle",
                scope=scope,
                actual_usage=actual_usage,
                reason="budget_settled",
            )
            policy = await self._policy_by_id(scope.budget_id)
            if policy is not None and not policy.hard_limit:
                await self._record_soft_limit_alert_if_needed(
                    policy,
                    reservation=reservation,
                    context=context,
                    scope=scope,
                    actual_usage=actual_usage,
                )

    async def release(
        self,
        reservation: BudgetReservation,
        context: LLMRequestContext,
        reason: str,
    ) -> None:
        if self.session is None or not reservation.approved:
            return
        for scope in reservation.budget_scopes:
            await self._record_budget_event(
                reservation=reservation,
                context=context,
                event_type="release",
                scope=scope,
                reason=reason,
            )

    async def preview(
        self,
        request: LLMChatRequest,
    ) -> Decimal:
        return self.pricing.estimate(request).cost_usd

    async def _matching_policies(
        self,
        context: LLMRequestContext,
    ) -> list[LLMBudget]:
        if self.session is None:
            return []
        cost_center_id, _source = await resolve_cost_center(self.session, context)
        result = await self.session.execute(
            select(LLMBudget).where(
                cast(ColumnElement[bool], LLMBudget.tenant_id == context.tenant_id),
                cast(Any, LLMBudget.is_active).is_(True),
            )
        )
        return [
            policy
            for policy in result.scalars().all()
            if _policy_matches_context(policy, context, cost_center_id=cost_center_id)
        ]

    async def _first_hard_limit_denial(
        self,
        context: LLMRequestContext,
        estimate: LLMUsageMetrics,
        policies: list[LLMBudget],
    ) -> tuple[LLMBudget, str] | None:
        for policy in policies:
            if not policy.hard_limit:
                continue
            start, end = _period_window(policy)
            spent_cost, spent_tokens = await self._usage_for_policy(policy, context, start, end)
            amount_limit = Decimal(policy.amount_usd or 0)
            if amount_limit > 0 and spent_cost + estimate.cost_usd > amount_limit:
                return (
                    policy,
                    f"{policy.scope_type} budget amount limit exceeded "
                    f"({spent_cost + estimate.cost_usd} > {amount_limit} USD).",
                )
            if (
                policy.token_limit is not None
                and spent_tokens + estimate.total_tokens > policy.token_limit
            ):
                return (
                    policy,
                    f"{policy.scope_type} budget token limit exceeded "
                    f"({spent_tokens + estimate.total_tokens} > {policy.token_limit}).",
                )
        return None

    async def _usage_for_policy(
        self,
        policy: LLMBudget,
        context: LLMRequestContext,
        start: datetime,
        end: datetime,
    ) -> tuple[Decimal, int]:
        if self.session is None:
            return Decimal("0"), 0
        filters = [
            LLMUsage.tenant_id == context.tenant_id,
            LLMUsage.status == "success",
            LLMUsage.created_at >= start,
            LLMUsage.created_at < end,
        ]
        if policy.scope_type == "department" and context.department_id is not None:
            filters.append(LLMUsage.department_id == context.department_id)
        elif policy.scope_type == "cost_center":
            cost_center_id, _source = await resolve_cost_center(self.session, context)
            if cost_center_id is not None:
                filters.append(LLMUsage.cost_center_id == cost_center_id)
        elif policy.scope_type == "user" and context.user_id is not None:
            filters.append(LLMUsage.user_id == context.user_id)
        elif policy.scope_type == "agent" and context.agent_id is not None:
            filters.append(LLMUsage.agent_id == context.agent_id)
        elif policy.scope_type == "channel" and context.channel_id is not None:
            filters.append(LLMUsage.channel_id == context.channel_id)

        result = await self.session.execute(
            select(
                func.coalesce(func.sum(LLMUsage.cost_usd), Decimal("0")),
                func.coalesce(func.sum(LLMUsage.total_tokens), 0),
            ).where(*filters)
        )
        cost, tokens = result.one()
        return Decimal(cost or 0), int(tokens or 0)

    async def _policy_by_id(self, budget_id: UUID) -> LLMBudget | None:
        if self.session is None:
            return None
        try:
            return await self.session.get(LLMBudget, budget_id)
        except (OSError, SQLAlchemyError, AttributeError):
            return None

    async def _record_soft_limit_alert_if_needed(
        self,
        policy: LLMBudget,
        *,
        reservation: BudgetReservation,
        context: LLMRequestContext,
        scope: BudgetReservationScope,
        actual_usage: LLMUsageMetrics,
    ) -> None:
        start, end = _period_window(policy)
        spent_cost, spent_tokens = await self._usage_for_policy(policy, context, start, end)
        amount_limit = Decimal(policy.amount_usd or 0)
        amount_after = spent_cost + actual_usage.cost_usd
        tokens_after = spent_tokens + actual_usage.total_tokens
        threshold = Decimal(policy.alert_threshold_pct) / Decimal("100")
        amount_alert = (
            amount_limit > 0
            and _ratio(spent_cost, amount_limit) < threshold
            and _ratio(amount_after, amount_limit) >= threshold
        )
        token_alert = (
            policy.token_limit is not None
            and _ratio(Decimal(spent_tokens), Decimal(policy.token_limit)) < threshold
            and _ratio(Decimal(tokens_after), Decimal(policy.token_limit)) >= threshold
        )
        if not amount_alert and not token_alert:
            return

        await self._record_budget_event(
            reservation=reservation,
            context=context,
            event_type="alert",
            scope=scope,
            actual_usage=actual_usage,
            reason="soft_budget_threshold_reached",
            metadata={
                "alert_threshold_pct": policy.alert_threshold_pct,
                "amount_limit_usd": str(amount_limit),
                "amount_after_usd": str(amount_after),
                "token_limit": policy.token_limit,
                "tokens_after": tokens_after,
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
            },
        )

    async def _record_budget_event(
        self,
        *,
        reservation: BudgetReservation,
        context: LLMRequestContext,
        event_type: str,
        scope: BudgetReservationScope,
        estimated_usage: LLMUsageMetrics | None = None,
        actual_usage: LLMUsageMetrics | None = None,
        reason: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        if self.session is None:
            return
        estimated = estimated_usage or LLMUsageMetrics(
            total_tokens=reservation.estimated_tokens,
            cost_usd=reservation.estimated_cost_usd,
        )
        actual = actual_usage or LLMUsageMetrics()
        try:
            cost_center_id, cost_center_source = await resolve_cost_center(self.session, context)
            self.session.add(
                LLMBudgetLedger(
                    tenant_id=context.tenant_id,
                    budget_id=scope.budget_id,
                    reservation_id=reservation.reservation_id,
                    request_id=context.request_id,
                    event_type=event_type,
                    scope_type=scope.scope_type,
                    scope_id=scope.scope_id,
                    user_id=context.user_id,
                    department_id=context.department_id,
                    cost_center_id=cost_center_id,
                    agent_id=context.agent_id,
                    channel_id=context.channel_id,
                    conversation_id=context.conversation_id,
                    estimated_tokens=estimated.total_tokens,
                    actual_tokens=actual.total_tokens,
                    estimated_cost_usd=estimated.cost_usd,
                    actual_cost_usd=actual.cost_usd,
                    reason=reason[:240],
                    metadata_json={
                        "source": context.source,
                        "approved": reservation.approved,
                        "estimated_input_tokens": estimated.input_tokens,
                        "estimated_output_tokens": estimated.output_tokens,
                        "actual_input_tokens": actual.input_tokens,
                        "actual_output_tokens": actual.output_tokens,
                        "cost_center_source": cost_center_source,
                        **(metadata or {}),
                    },
                )
            )
            await self.session.commit()
        except (OSError, SQLAlchemyError, AttributeError):
            rollback = getattr(self.session, "rollback", None)
            if rollback is not None:
                await rollback()


def _policy_matches_context(
    policy: LLMBudget,
    context: LLMRequestContext,
    *,
    cost_center_id: UUID | None = None,
) -> bool:
    scope_id: UUID | None = policy.scope_id
    if policy.scope_type == "tenant":
        return scope_id is None
    if policy.scope_type == "department":
        return scope_id is not None and scope_id == context.department_id
    if policy.scope_type == "cost_center":
        return scope_id is not None and scope_id == cost_center_id
    if policy.scope_type == "user":
        return scope_id is not None and scope_id == context.user_id
    if policy.scope_type == "agent":
        return scope_id is not None and scope_id == context.agent_id
    if policy.scope_type == "channel":
        return scope_id is not None and scope_id == context.channel_id
    return False


def _reservation_scope(policy: LLMBudget) -> BudgetReservationScope:
    return BudgetReservationScope(
        budget_id=policy.id,
        scope_type=policy.scope_type,
        scope_id=policy.scope_id,
    )


def _period_window(policy: LLMBudget) -> tuple[datetime, datetime]:
    if (
        policy.period == "custom"
        and policy.custom_period_start is not None
        and policy.custom_period_end is not None
    ):
        return policy.custom_period_start, policy.custom_period_end
    now = utc_now()
    if policy.period == "daily":
        start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        return start, start + timedelta(days=1)
    if policy.period == "quarterly":
        # Calendar quarters: Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec.
        quarter_start_month = ((now.month - 1) // 3) * 3 + 1
        start = datetime(now.year, quarter_start_month, 1, tzinfo=timezone.utc)
        end_month = quarter_start_month + 3
        if end_month > 12:
            end = datetime(now.year + 1, end_month - 12, 1, tzinfo=timezone.utc)
        else:
            end = datetime(now.year, end_month, 1, tzinfo=timezone.utc)
        return start, end
    # Default to monthly window.
    start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    if now.month == 12:
        return start, datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    return start, datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)


def _ratio(value: Decimal, limit: Decimal) -> Decimal:
    if limit <= 0:
        return Decimal("0")
    return value / limit
