"""Per-deployment circuit breaker for the LLM Gateway.

Tracks recent call outcomes (success / failure) for each LLM deployment and
short-circuits routing away from deployments that are failing repeatedly.

States (per deployment_id):
    CLOSED      -> requests flow normally; failures increment the counter.
    OPEN        -> after ``failure_threshold`` consecutive failures the circuit
                   opens; routing skips this deployment for
                   ``cooldown_seconds``.
    HALF_OPEN   -> after the cooldown elapses the next request is allowed
                   through as a probe. On success the circuit closes (after
                   ``success_threshold`` consecutive probe successes); on
                   failure it re-opens immediately.

The breaker is a process-wide singleton (``circuit_breaker``) so that state
persists across gateway instances, which are constructed per-request.
Thread-safe via a single lock — contention is negligible because operations
are O(1) dict lookups.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import StrEnum


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class _DeploymentCircuit:
    state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    opened_at: float | None = None
    last_failure_at: float | None = None
    last_failure_code: str | None = None
    total_opened: int = 0


@dataclass
class CircuitBreakerSnapshot:
    """Immutable view of a single deployment's circuit state."""

    deployment_id: str
    state: CircuitState
    consecutive_failures: int
    consecutive_successes: int
    opened_at: float | None
    last_failure_at: float | None
    last_failure_code: str | None
    total_opened: int
    seconds_until_half_open: float | None


class CircuitBreaker:
    """Thread-safe circuit breaker keyed by deployment_id (string)."""

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        cooldown_seconds: float = 30.0,
        success_threshold: int = 2,
        enabled: bool = True,
    ) -> None:
        self._failure_threshold = max(1, failure_threshold)
        self._cooldown_seconds = max(0.01, cooldown_seconds)
        self._success_threshold = max(1, success_threshold)
        self._enabled = enabled
        # RLock so internal helpers (e.g. snapshot_all -> snapshot) can re-enter.
        self._lock = threading.RLock()
        self._circuits: dict[str, _DeploymentCircuit] = {}

    # ---- Configuration ---------------------------------------------------

    def configure(
        self,
        *,
        failure_threshold: int | None = None,
        cooldown_seconds: float | None = None,
        success_threshold: int | None = None,
        enabled: bool | None = None,
    ) -> None:
        with self._lock:
            if failure_threshold is not None:
                self._failure_threshold = max(1, failure_threshold)
            if cooldown_seconds is not None:
                self._cooldown_seconds = max(0.01, cooldown_seconds)
            if success_threshold is not None:
                self._success_threshold = max(1, success_threshold)
            if enabled is not None:
                self._enabled = enabled

    # ---- State queries ---------------------------------------------------

    def is_open(self, deployment_id: str) -> bool:
        """Return True if the circuit is OPEN and still in its cooldown window.

        A circuit whose cooldown has elapsed is transitioned to HALF_OPEN and
        returns False (the caller may attempt a probe). Returns False when the
        breaker is disabled.
        """
        if not self._enabled:
            return False
        with self._lock:
            circuit = self._circuits.get(deployment_id)
            if circuit is None or circuit.state != CircuitState.OPEN:
                return False
            if circuit.opened_at is None:
                return True
            if (time.time() - circuit.opened_at) >= self._cooldown_seconds:
                circuit.state = CircuitState.HALF_OPEN
                circuit.consecutive_successes = 0
                return False
            return True

    def get_state(self, deployment_id: str) -> CircuitState:
        with self._lock:
            circuit = self._circuits.get(deployment_id)
            if circuit is None:
                return CircuitState.CLOSED
            # Lazily transition OPEN -> HALF_OPEN if cooldown elapsed.
            if (
                circuit.state == CircuitState.OPEN
                and circuit.opened_at is not None
                and (time.time() - circuit.opened_at) >= self._cooldown_seconds
            ):
                circuit.state = CircuitState.HALF_OPEN
                circuit.consecutive_successes = 0
            return circuit.state

    def snapshot(self, deployment_id: str) -> CircuitBreakerSnapshot | None:
        with self._lock:
            circuit = self._circuits.get(deployment_id)
            if circuit is None:
                return None
            # Lazy transition for snapshot accuracy.
            if (
                circuit.state == CircuitState.OPEN
                and circuit.opened_at is not None
                and (time.time() - circuit.opened_at) >= self._cooldown_seconds
            ):
                circuit.state = CircuitState.HALF_OPEN
                circuit.consecutive_successes = 0
            seconds_until_half_open: float | None = None
            if circuit.state == CircuitState.OPEN and circuit.opened_at is not None:
                seconds_until_half_open = max(
                    0.0,
                    self._cooldown_seconds - (time.time() - circuit.opened_at),
                )
            return CircuitBreakerSnapshot(
                deployment_id=deployment_id,
                state=circuit.state,
                consecutive_failures=circuit.consecutive_failures,
                consecutive_successes=circuit.consecutive_successes,
                opened_at=circuit.opened_at,
                last_failure_at=circuit.last_failure_at,
                last_failure_code=circuit.last_failure_code,
                total_opened=circuit.total_opened,
                seconds_until_half_open=seconds_until_half_open,
            )

    def snapshot_all(self) -> list[CircuitBreakerSnapshot]:
        with self._lock:
            return [
                snap
                for snap in (self.snapshot(deployment_id) for deployment_id in list(self._circuits))
                if snap is not None
            ]

    # ---- Outcome recording ------------------------------------------------

    def record_success(self, deployment_id: str) -> None:
        with self._lock:
            circuit = self._circuits.setdefault(deployment_id, _DeploymentCircuit())
            circuit.consecutive_failures = 0
            if circuit.state == CircuitState.HALF_OPEN:
                circuit.consecutive_successes += 1
                if circuit.consecutive_successes >= self._success_threshold:
                    circuit.state = CircuitState.CLOSED
                    circuit.consecutive_successes = 0
                    circuit.opened_at = None
            elif circuit.state == CircuitState.OPEN:
                # Defensive: a success while OPEN shouldn't happen (routing
                # skips OPEN circuits), but if it does, close immediately.
                circuit.state = CircuitState.CLOSED
                circuit.opened_at = None
                circuit.consecutive_successes = 0
            # CLOSED stays CLOSED.

    def record_failure(
        self,
        deployment_id: str,
        *,
        error_code: str | None = None,
    ) -> None:
        with self._lock:
            circuit = self._circuits.setdefault(deployment_id, _DeploymentCircuit())
            circuit.consecutive_failures += 1
            circuit.last_failure_at = time.time()
            circuit.last_failure_code = error_code
            if circuit.state == CircuitState.HALF_OPEN:
                # Probe failed: re-open immediately and reset cooldown clock.
                circuit.state = CircuitState.OPEN
                circuit.opened_at = time.time()
                circuit.total_opened += 1
                circuit.consecutive_successes = 0
            elif circuit.state == CircuitState.CLOSED:
                if circuit.consecutive_failures >= self._failure_threshold:
                    circuit.state = CircuitState.OPEN
                    circuit.opened_at = time.time()
                    circuit.total_opened += 1
                    circuit.consecutive_successes = 0
            # OPEN stays OPEN (failure counter keeps climbing).

    # ---- Maintenance -----------------------------------------------------

    def reset(self, deployment_id: str | None = None) -> None:
        with self._lock:
            if deployment_id is None:
                self._circuits.clear()
            else:
                self._circuits.pop(deployment_id, None)

    def force_state(
        self,
        deployment_id: str,
        state: CircuitState,
    ) -> None:
        """Manually override a circuit's state (operator escape hatch)."""
        with self._lock:
            circuit = self._circuits.setdefault(deployment_id, _DeploymentCircuit())
            circuit.state = state
            if state == CircuitState.OPEN:
                circuit.opened_at = time.time()
                circuit.total_opened += 1
            else:
                circuit.opened_at = None
                circuit.consecutive_failures = 0
                circuit.consecutive_successes = 0


# Process-wide singleton. Configuration is applied from settings at app startup
# (see ``app.main`` / ``app.services.llm_service``). Tests reset it between
# cases to avoid cross-test contamination.
circuit_breaker = CircuitBreaker()
