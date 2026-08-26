"""In-process metrics collector for observability.

Thread-safe counters and histograms exported in Prometheus text exposition format.
Keeps cardinality bounded by normalising paths and limiting label values.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Iterable

from app.llm.schemas import LLMCallStatus

_HTTP_BUCKETS_SECONDS: tuple[float, ...] = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)
_LLM_BUCKETS_SECONDS: tuple[float, ...] = (
    0.1,
    0.25,
    0.5,
    1.0,
    2.0,
    5.0,
    10.0,
    30.0,
    60.0,
    120.0,
)

_LLM_STATUS_LABEL: dict[LLMCallStatus, str] = {
    LLMCallStatus.SUCCESS: "success",
    LLMCallStatus.ERROR: "error",
    LLMCallStatus.DENIED: "denied",
    LLMCallStatus.BUDGET_EXCEEDED: "budget_exceeded",
}


def _normalise_path(path: str) -> str:
    """Collapse dynamic path segments to keep cardinality bounded.

    Examples:
      /api/v1/channels/550e8400.../push  ->  /api/v1/channels/:param/push
      /api/v1/health                     ->  /api/v1/health
    """
    if not path:
        return "/"
    parts = path.split("/")
    rebuilt: list[str] = []
    for part in parts:
        if not part:
            rebuilt.append(part)
            continue
        if _looks_dynamic(part):
            rebuilt.append(":param")
        else:
            rebuilt.append(part)
    return "/".join(rebuilt)


def _looks_dynamic(part: str) -> bool:
    if part.isdigit():
        return True
    if len(part) == 36 and part.count("-") == 4:  # UUID
        return True
    if len(part) >= 16 and all(c in "0123456789abcdefABCDEF" for c in part):
        return True
    return False


class _Histogram:
    """Incremental bucket counter with cumulative export."""

    __slots__ = ("buckets", "bucket_counts", "count", "sum_seconds")

    def __init__(self, buckets: Iterable[float]) -> None:
        self.buckets: tuple[float, ...] = tuple(sorted(buckets))
        self.bucket_counts: list[int] = [0 for _ in self.buckets]
        self.count = 0
        self.sum_seconds = 0.0

    def observe(self, seconds: float) -> None:
        self.count += 1
        self.sum_seconds += seconds
        for index, threshold in enumerate(self.buckets):
            if seconds <= threshold:
                self.bucket_counts[index] += 1

    def cumulative(self) -> list[tuple[float, int]]:
        result: list[tuple[float, int]] = []
        running = 0
        for threshold, count in zip(self.buckets, self.bucket_counts):
            running = count
            result.append((threshold, running))
        return result


class MetricsCollector:
    """Thread-safe in-process metrics collector (single instance per process)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._http_requests: dict[tuple[str, str, int], int] = defaultdict(int)
        self._http_duration: dict[tuple[str, str], _Histogram] = defaultdict(
            lambda: _Histogram(_HTTP_BUCKETS_SECONDS)
        )
        self._llm_calls: dict[tuple[str, str, str], int] = defaultdict(int)
        self._llm_duration: dict[tuple[str, str], _Histogram] = defaultdict(
            lambda: _Histogram(_LLM_BUCKETS_SECONDS)
        )
        self._llm_errors: dict[tuple[str, str, str], int] = defaultdict(int)
        self._started_at = time.time()

    # ---- HTTP ---------------------------------------------------------------

    def observe_http_request(
        self, *, method: str, path: str, status: int, duration_ms: float
    ) -> None:
        path_template = _normalise_path(path)
        seconds = duration_ms / 1000.0
        with self._lock:
            self._http_requests[(method.upper(), path_template, status)] += 1
            self._http_duration[(method.upper(), path_template)].observe(seconds)

    # ---- LLM ----------------------------------------------------------------

    def observe_llm_call(
        self,
        *,
        provider_key: str | None,
        model_key: str | None,
        status: LLMCallStatus,
        duration_ms: float,
        error_code: str | None = None,
    ) -> None:
        provider = provider_key or "unknown"
        model = model_key or "unknown"
        status_label = _LLM_STATUS_LABEL.get(status, status.value)
        seconds = duration_ms / 1000.0
        with self._lock:
            self._llm_calls[(provider, model, status_label)] += 1
            self._llm_duration[(provider, model)].observe(seconds)
            if status != LLMCallStatus.SUCCESS and error_code:
                self._llm_errors[(provider, model, error_code)] += 1

    # ---- Export -------------------------------------------------------------

    def render_prometheus(self) -> str:
        lines: list[str] = []
        with self._lock:
            self._render_http(lines)
            self._render_llm(lines)
            lines.append("")
            lines.append(
                "# HELP agenthive_metrics_process_uptime_seconds Time since the collector started."
            )
            lines.append("# TYPE agenthive_metrics_process_uptime_seconds gauge")
            lines.append(
                f"agenthive_metrics_process_uptime_seconds {time.time() - self._started_at:.3f}"
            )
        return "\n".join(lines)

    def reset(self) -> None:
        with self._lock:
            self._http_requests.clear()
            self._http_duration.clear()
            self._llm_calls.clear()
            self._llm_duration.clear()
            self._llm_errors.clear()
            self._started_at = time.time()

    # ---- internal render helpers -------------------------------------------

    def _render_http(self, lines: list[str]) -> None:
        lines.append(
            "# HELP agenthive_http_requests_total Total HTTP requests by method/path/status."
        )
        lines.append("# TYPE agenthive_http_requests_total counter")
        for (method, path, status), count in sorted(self._http_requests.items()):
            lines.append(
                f'agenthive_http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}'
            )
        lines.append(
            "# HELP agenthive_http_request_duration_seconds HTTP request latency histogram."
        )
        lines.append("# TYPE agenthive_http_request_duration_seconds histogram")
        for (method, path), histogram in sorted(self._http_duration.items()):
            self._render_histogram(
                lines,
                metric="agenthive_http_request_duration_seconds",
                labels=f'method="{method}",path="{path}"',
                histogram=histogram,
            )

    def _render_llm(self, lines: list[str]) -> None:
        lines.append(
            "# HELP agenthive_llm_calls_total Total LLM gateway calls by provider/model/status."
        )
        lines.append("# TYPE agenthive_llm_calls_total counter")
        for (provider, model, status_label), count in sorted(self._llm_calls.items()):
            lines.append(
                f'agenthive_llm_calls_total{{provider="{provider}",model="{model}",status="{status_label}"}} {count}'
            )
        lines.append("# HELP agenthive_llm_call_duration_seconds LLM call latency histogram.")
        lines.append("# TYPE agenthive_llm_call_duration_seconds histogram")
        for (provider, model), histogram in sorted(self._llm_duration.items()):
            self._render_histogram(
                lines,
                metric="agenthive_llm_call_duration_seconds",
                labels=f'provider="{provider}",model="{model}"',
                histogram=histogram,
            )
        if self._llm_errors:
            lines.append(
                "# HELP agenthive_llm_errors_total Total LLM errors by provider/model/error_code."
            )
            lines.append("# TYPE agenthive_llm_errors_total counter")
            for (provider, model, error_code), count in sorted(self._llm_errors.items()):
                lines.append(
                    f'agenthive_llm_errors_total{{provider="{provider}",model="{model}",error_code="{error_code}"}} {count}'
                )

    def _render_histogram(
        self,
        lines: list[str],
        *,
        metric: str,
        labels: str,
        histogram: _Histogram,
    ) -> None:
        for bucket, count in histogram.cumulative():
            lines.append(f'{metric}_bucket{{{labels},le="{bucket}"}} {count}')
        lines.append(f'{metric}_bucket{{{labels},le="+Inf"}} {histogram.count}')
        lines.append(f"{metric}_sum{{{labels}}} {histogram.sum_seconds:.6f}")
        lines.append(f"{metric}_count{{{labels}}} {histogram.count}")


metrics_collector = MetricsCollector()
