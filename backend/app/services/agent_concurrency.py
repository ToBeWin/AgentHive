from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from math import ceil
from time import monotonic
from uuid import UUID

from fastapi import HTTPException, status

from app.core.config import settings


@dataclass(frozen=True)
class AgentConcurrencySlot:
    scope: str
    key: str
    limit: int


@dataclass(frozen=True)
class AgentConcurrencyDecision:
    enabled: bool
    acquired: bool
    tenant_limit: int
    user_limit: int
    agent_limit: int
    active: dict[str, int]


class InMemoryAgentConcurrencyLimiter:
    """Single-process Agent execution slot limiter.

    Docker Compose delivery runs one backend process by default. For multi-replica
    deployments this service is intentionally isolated so it can be swapped for a
    Redis-backed distributed limiter without changing Agent execution code.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._active: dict[tuple[str, str], int] = {}

    @asynccontextmanager
    async def acquire(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        agent_id: UUID | None,
        request_id: str | None = None,
    ) -> AsyncIterator[AgentConcurrencyDecision]:
        decision = await self._acquire(
            tenant_id=tenant_id,
            user_id=user_id,
            agent_id=agent_id,
            request_id=request_id,
        )
        try:
            yield decision
        finally:
            if decision.enabled and decision.acquired:
                await self._release(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    agent_id=agent_id,
                )

    async def _acquire(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        agent_id: UUID | None,
        request_id: str | None,
    ) -> AgentConcurrencyDecision:
        limits = self._limits()
        if not settings.agent_concurrency_enabled:
            return AgentConcurrencyDecision(
                enabled=False,
                acquired=False,
                tenant_limit=limits["tenant"],
                user_limit=limits["user"],
                agent_limit=limits["agent"],
                active={},
            )

        slots = self._slots(tenant_id=tenant_id, user_id=user_id, agent_id=agent_id, limits=limits)
        deadline = monotonic() + max(settings.agent_concurrency_wait_timeout_seconds, 0)
        blocked_slot: AgentConcurrencySlot | None = None
        while True:
            async with self._lock:
                blocked_slot = self._blocked_slot(slots)
                if blocked_slot is None:
                    active: dict[str, int] = {}
                    for slot in slots:
                        key = (slot.scope, slot.key)
                        self._active[key] = self._active.get(key, 0) + 1
                        active[slot.scope] = self._active[key]
                    return AgentConcurrencyDecision(
                        enabled=True,
                        acquired=True,
                        tenant_limit=limits["tenant"],
                        user_limit=limits["user"],
                        agent_limit=limits["agent"],
                        active=active,
                    )

            if monotonic() >= deadline:
                self._raise_limit_exceeded(blocked_slot, limits, request_id)
            await asyncio.sleep(min(0.05, max(deadline - monotonic(), 0.01)))

    async def _release(self, *, tenant_id: UUID, user_id: UUID, agent_id: UUID | None) -> None:
        limits = self._limits()
        slots = self._slots(tenant_id=tenant_id, user_id=user_id, agent_id=agent_id, limits=limits)
        async with self._lock:
            for slot in slots:
                key = (slot.scope, slot.key)
                count = self._active.get(key, 0)
                if count <= 1:
                    self._active.pop(key, None)
                else:
                    self._active[key] = count - 1

    async def snapshot(self) -> AgentConcurrencyDecision:
        limits = self._limits()
        async with self._lock:
            active = {
                f"{scope}:{key}": count
                for (scope, key), count in sorted(self._active.items(), key=lambda item: item[0])
            }
        return AgentConcurrencyDecision(
            enabled=settings.agent_concurrency_enabled,
            acquired=False,
            tenant_limit=limits["tenant"],
            user_limit=limits["user"],
            agent_limit=limits["agent"],
            active=active,
        )

    async def reset(self) -> None:
        async with self._lock:
            self._active.clear()

    def _limits(self) -> dict[str, int]:
        return {
            "tenant": max(settings.agent_concurrency_tenant_limit, 0),
            "user": max(settings.agent_concurrency_user_limit, 0),
            "agent": max(settings.agent_concurrency_agent_limit, 0),
        }

    def _slots(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        agent_id: UUID | None,
        limits: dict[str, int],
    ) -> list[AgentConcurrencySlot]:
        tenant_key = str(tenant_id)
        agent_key = str(agent_id) if agent_id is not None else "direct-chat"
        candidates = [
            AgentConcurrencySlot("tenant", tenant_key, limits["tenant"]),
            AgentConcurrencySlot("user", f"{tenant_key}:{user_id}", limits["user"]),
            AgentConcurrencySlot("agent", f"{tenant_key}:{agent_key}", limits["agent"]),
        ]
        return [slot for slot in candidates if slot.limit > 0]

    def _blocked_slot(self, slots: list[AgentConcurrencySlot]) -> AgentConcurrencySlot | None:
        for slot in slots:
            if self._active.get((slot.scope, slot.key), 0) >= slot.limit:
                return slot
        return None

    def _raise_limit_exceeded(
        self,
        blocked_slot: AgentConcurrencySlot | None,
        limits: dict[str, int],
        request_id: str | None,
    ) -> None:
        scope = blocked_slot.scope if blocked_slot else "unknown"
        retry_after_seconds = max(1, ceil(settings.agent_concurrency_wait_timeout_seconds))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "agent_concurrency_limited",
                "message": "Agent execution concurrency limit exceeded. Please retry shortly.",
                "scope": scope,
                "limits": limits,
                "request_id": request_id,
                "retry_after_seconds": retry_after_seconds,
            },
            headers={"Retry-After": str(retry_after_seconds)},
        )


agent_concurrency_limiter = InMemoryAgentConcurrencyLimiter()
