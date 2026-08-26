from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from dataclasses import dataclass
from hashlib import blake2b
from math import sqrt
import re
from threading import Lock
from typing import Protocol

import httpx

from app.core.config import settings
from app.llm.mock_policy import llm_mock_allowed, llm_mock_disabled_message

logger = logging.getLogger(__name__)

TOKEN_PATTERN = re.compile(r"[\w]+|[\u4e00-\u9fff]")


@dataclass(frozen=True)
class EmbeddingResult:
    model_key: str
    dimensions: int
    vector: list[float]
    mode: str


class EmbeddingService(Protocol):
    """Contract every embedding implementation must satisfy.

    LocalHashEmbeddingService and LLMGatewayEmbeddingAdapter both conform to
    this protocol so callers can swap them without touching retrieval code.
    """

    model_key: str
    dimensions: int
    mode: str

    def embed_text(self, text: str) -> EmbeddingResult: ...


async def embed_text_nonblocking(
    service: EmbeddingService,
    text: str,
) -> EmbeddingResult:
    """Run the synchronous embedding boundary without blocking the event loop.

    The live adapter performs synchronous HTTP and retry sleeps, while the
    offline adapter performs CPU work. Async RAG flows must therefore execute
    either implementation in the default worker pool.
    """

    return await asyncio.to_thread(service.embed_text, text)


class LocalHashEmbeddingService:
    """Deterministic offline embedding boundary.

    This is intentionally simple and replaceable. It lets private deployments
    validate pgvector write/search mechanics without requiring an external
    embedding provider. Production semantic embeddings should route through
    AgentHive LLM Gateway using the same return contract.
    """

    def __init__(
        self,
        *,
        model_key: str | None = None,
        dimensions: int | None = None,
        mode: str | None = None,
    ) -> None:
        self.model_key = model_key or settings.rag_embedding_model_key
        self.dimensions = min(max(dimensions or settings.rag_embedding_dimensions, 64), 1536)
        self.mode = mode or settings.rag_embedding_mode

    def embed_text(self, text: str) -> EmbeddingResult:
        tokens = _tokens(text)
        vector = [0.0] * self.dimensions
        if not tokens:
            return EmbeddingResult(
                model_key=self.model_key,
                dimensions=self.dimensions,
                vector=vector,
                mode=self.mode,
            )

        counts = Counter(tokens)
        for token, count in counts.items():
            digest = blake2b(token.encode("utf-8"), digest_size=16).digest()
            index = int.from_bytes(digest[:8], "big") % self.dimensions
            sign = 1.0 if digest[8] % 2 == 0 else -1.0
            vector[index] += sign * float(count)

        norm = sqrt(sum(value * value for value in vector))
        if norm > 0:
            vector = [round(value / norm, 8) for value in vector]
        return EmbeddingResult(
            model_key=self.model_key,
            dimensions=self.dimensions,
            vector=vector,
            mode=self.mode,
        )


class _CircuitBreaker:
    """Minimal circuit breaker for the embedding endpoint.

    Tracks consecutive failures. After ``failure_threshold`` failures the
    breaker opens for ``reset_timeout_seconds``; calls during the open window
    short-circuit with ``CircuitBreakerOpenError`` instead of hitting the
    network. A successful call resets the failure count.
    """

    def __init__(self, *, failure_threshold: int, reset_timeout_seconds: float) -> None:
        self._failure_threshold = max(1, failure_threshold)
        self._reset_timeout_seconds = max(0.0, reset_timeout_seconds)
        self._failures = 0
        self._opened_at: float | None = None
        self._lock = Lock()

    @property
    def state(self) -> str:
        with self._lock:
            if self._opened_at is None:
                return "closed"
            if time.monotonic() - self._opened_at >= self._reset_timeout_seconds:
                return "half_open"
            return "open"

    def allow(self) -> bool:
        with self._lock:
            if self._opened_at is None:
                return True
            if time.monotonic() - self._opened_at >= self._reset_timeout_seconds:
                # Half-open: let one probe through.
                return True
            return False

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self._failure_threshold:
                self._opened_at = time.monotonic()


class CircuitBreakerOpenError(RuntimeError):
    """Raised when the embedding endpoint circuit breaker is open."""


class LLMGatewayEmbeddingAdapter:
    """Semantic embedding adapter backed by an OpenAI-compatible /embeddings endpoint.

    Routes through the AgentHive LLM Gateway contract: when credentials are
    configured, calls the live endpoint and returns the provider's vector.
    When credentials are absent and the runtime is development, falls back to
    LocalHashEmbeddingService so demos still work. Outside development with
    missing credentials, raises to fail-closed (mirrors LLM chat adapter
    policy).

    Resilience:
      * Timeout per request (``rag_embedding_request_timeout_seconds``).
      * Retry on 5xx / network errors only (``rag_embedding_max_retries``),
        with exponential backoff (``rag_embedding_retry_backoff_seconds``).
        4xx is treated as permanent (bad request / bad credentials) and not
        retried.
      * Circuit breaker (``rag_embedding_circuit_breaker_*``): after N
        consecutive failures the breaker opens for a cooldown window. In
        development, opens fall back to local hash so retrieval still works;
        outside development, opens raise.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model_key: str | None = None,
        dimensions: int | None = None,
        timeout_seconds: float | None = None,
        http_client: httpx.Client | None = None,
        max_retries: int | None = None,
        retry_backoff_seconds: float | None = None,
        circuit_breaker: _CircuitBreaker | None = None,
    ) -> None:
        self._base_url = (base_url or settings.rag_embedding_api_base_url or "").strip()
        self._api_key = (api_key or settings.rag_embedding_api_key or "").strip()
        self.model_key = model_key or settings.rag_embedding_model_key
        requested_dimensions = dimensions or settings.rag_embedding_dimensions
        self.dimensions = min(max(requested_dimensions, 64), 4096)
        self.timeout_seconds = timeout_seconds or settings.rag_embedding_request_timeout_seconds
        self._max_retries = (
            max_retries if max_retries is not None else settings.rag_embedding_max_retries
        )
        self._retry_backoff_seconds = (
            retry_backoff_seconds
            if retry_backoff_seconds is not None
            else settings.rag_embedding_retry_backoff_seconds
        )
        self.mode = "llm_gateway_openai_compatible"
        # When http_client is supplied (typically in tests via httpx.MockTransport),
        # we use it directly and skip constructing a fresh client per call. The
        # caller is responsible for closing it.
        self._injected_client = http_client
        self._fallback = LocalHashEmbeddingService(
            model_key=self.model_key,
            dimensions=min(self.dimensions, 1536),
            mode=f"{self.mode}+local_hash_fallback",
        )
        self._circuit_breaker: _CircuitBreaker | None
        if circuit_breaker is not None:
            self._circuit_breaker = circuit_breaker
        elif settings.rag_embedding_circuit_breaker_enabled:
            self._circuit_breaker = _CircuitBreaker(
                failure_threshold=settings.rag_embedding_circuit_breaker_failure_threshold,
                reset_timeout_seconds=settings.rag_embedding_circuit_breaker_reset_timeout_seconds,
            )
        else:
            self._circuit_breaker = None

    def embed_text(self, text: str) -> EmbeddingResult:
        if not self._is_live_configured():
            if not llm_mock_allowed():
                raise RuntimeError(
                    llm_mock_disabled_message("LLM Gateway embedding adapter")
                    + " Configure RAG_EMBEDDING_API_BASE_URL and RAG_EMBEDDING_API_KEY."
                )
            fallback_result = self._fallback.embed_text(text)
            return EmbeddingResult(
                model_key=fallback_result.model_key,
                dimensions=fallback_result.dimensions,
                vector=fallback_result.vector,
                mode=fallback_result.mode,
            )

        try:
            vector = self._post_embeddings_with_resilience(text)
        except CircuitBreakerOpenError:
            # Breaker open: in development, fall back to local hash so
            # retrieval still works. Outside development, fail closed.
            if llm_mock_allowed():
                logger.warning("Embedding circuit breaker open; falling back to local hash.")
                fallback_result = self._fallback.embed_text(text)
                return EmbeddingResult(
                    model_key=fallback_result.model_key,
                    dimensions=fallback_result.dimensions,
                    vector=fallback_result.vector,
                    mode=fallback_result.mode,
                )
            raise
        actual_dimensions = len(vector)
        return EmbeddingResult(
            model_key=self.model_key,
            dimensions=actual_dimensions,
            vector=vector,
            mode=self.mode,
        )

    def _is_live_configured(self) -> bool:
        return bool(self._base_url and self._api_key)

    def _post_embeddings_with_resilience(self, text: str) -> list[float]:
        if self._circuit_breaker is not None and not self._circuit_breaker.allow():
            raise CircuitBreakerOpenError("Embedding endpoint circuit breaker is open.")

        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                vector = self._post_embeddings(text)
                if self._circuit_breaker is not None:
                    self._circuit_breaker.record_success()
                return vector
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                status_code = exc.response.status_code
                # 4xx is a permanent error (bad request / bad credentials);
                # do not retry, but count it as a breaker failure.
                if 400 <= status_code < 500:
                    if self._circuit_breaker is not None:
                        self._circuit_breaker.record_failure()
                    raise
                # 5xx is transient — fall through to retry.
            except (httpx.HTTPError, ValueError) as exc:
                last_exc = exc

            if attempt < self._max_retries:
                backoff = self._retry_backoff_seconds * (2**attempt)
                time.sleep(backoff)

        # Exhausted retries.
        if self._circuit_breaker is not None:
            self._circuit_breaker.record_failure()
        raise (
            last_exc
            if last_exc is not None
            else RuntimeError("Embedding endpoint call failed after retries.")
        )

    def _post_embeddings(self, text: str) -> list[float]:
        payload = {
            "model": self.model_key,
            "input": text,
        }
        headers = {"content-type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        # Async RAG callers enter this synchronous boundary through
        # ``embed_text_nonblocking``, which offloads HTTP and retry sleeps to a
        # worker thread. Keeping this method synchronous preserves compatibility
        # with offline callers and injected test clients.
        if self._injected_client is not None:
            response = self._injected_client.post(
                f"{self._base_url.rstrip('/')}/embeddings",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
        else:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self._base_url.rstrip('/')}/embeddings",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Embedding endpoint returned a non-object response.")
        return _extract_embedding_vector(data)


def get_default_embedding_service() -> EmbeddingService:
    """Factory that picks the embedding implementation based on settings.

    Provider selection (RAG_EMBEDDING_PROVIDER):
      - "local_hash" (default): deterministic offline hash embedding; safe
        for development and air-gapped demos.
      - "llm_gateway": route through an OpenAI-compatible /embeddings
        endpoint configured via RAG_EMBEDDING_API_BASE_URL and
        RAG_EMBEDDING_API_KEY. Falls back to local hash in development when
        credentials are missing; fails closed outside development.
    """

    provider = (settings.rag_embedding_provider or "local_hash").strip().lower()
    if provider in {"llm_gateway", "openai_compatible", "litellm"}:
        return LLMGatewayEmbeddingAdapter()
    return LocalHashEmbeddingService()


def vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in vector) + "]"


def _tokens(text: str) -> list[str]:
    normalized = text.lower()
    return [match.group(0) for match in TOKEN_PATTERN.finditer(normalized)]


def _extract_embedding_vector(payload: dict[str, object]) -> list[float]:
    data_field = payload.get("data")
    if not isinstance(data_field, list) or not data_field:
        raise ValueError("Embedding response is missing the `data` array.")
    first_item = data_field[0]
    if not isinstance(first_item, dict):
        raise ValueError("Embedding response `data[0]` is not an object.")
    embedding_field = first_item.get("embedding")
    if not isinstance(embedding_field, list):
        raise ValueError("Embedding response `data[0].embedding` is not a list.")
    vector: list[float] = []
    for value in embedding_field:
        try:
            vector.append(float(value))
        except (TypeError, ValueError) as exc:
            raise ValueError("Embedding response contains a non-numeric value.") from exc
    if not vector:
        raise ValueError("Embedding response returned an empty vector.")
    return vector
