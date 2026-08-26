from __future__ import annotations

import asyncio
from collections.abc import Callable
from time import perf_counter
from typing import Any
from uuid import UUID

import httpx

from app.core.config import settings
from app.rag.base import BaseRAGAdapter
from app.rag.schemas import (
    ComponentStatus,
    DocumentIngestStatus,
    HealthStatus,
    IngestRequest,
    IngestResult,
    RAGChunk,
    RAGEngineType,
    RetrieveRequest,
    RetrieveResult,
)

AsyncClientFactory = Callable[..., httpx.AsyncClient]


class RAGFlowAdapter(BaseRAGAdapter):
    """RAGFlow-compatible HTTP boundary.

    The exact external RAG service can be RAGFlow itself or a thin private
    bridge in front of RAGFlow. AgentHive sends stable payloads and keeps all
    tenant permissions, storage metadata, and audit ownership inside AgentHive.
    """

    adapter_name = "ragflow"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        health_path: str | None = None,
        ingest_path: str | None = None,
        retrieve_path: str | None = None,
        delete_path: str | None = None,
        request_timeout_seconds: float | None = None,
        health_timeout_seconds: float | None = None,
        max_retries: int | None = None,
        retry_backoff_seconds: float | None = None,
        client_factory: AsyncClientFactory | None = None,
    ) -> None:
        self.base_url = (base_url if base_url is not None else settings.ragflow_url) or ""
        self.api_key = api_key if api_key is not None else settings.ragflow_api_key
        self.health_path = health_path or settings.ragflow_health_path
        self.ingest_path = ingest_path or settings.ragflow_ingest_path
        self.retrieve_path = retrieve_path or settings.ragflow_retrieve_path
        self.delete_path = delete_path or settings.ragflow_delete_path
        self.request_timeout_seconds = (
            request_timeout_seconds
            if request_timeout_seconds is not None
            else settings.ragflow_request_timeout_seconds
        )
        self.health_timeout_seconds = (
            health_timeout_seconds
            if health_timeout_seconds is not None
            else settings.ragflow_health_timeout_seconds
        )
        self.max_retries = max_retries if max_retries is not None else settings.ragflow_max_retries
        self.retry_backoff_seconds = (
            retry_backoff_seconds
            if retry_backoff_seconds is not None
            else settings.ragflow_retry_backoff_seconds
        )
        self.client_factory = client_factory or httpx.AsyncClient

    async def ingest(self, request: IngestRequest) -> IngestResult:
        if not self._configured:
            return IngestResult(
                document_id=request.document_id,
                status=DocumentIngestStatus.FAILED,
                message="RAGFlow URL is not configured.",
                metadata={"ragflow_url_configured": False},
            )

        payload = {
            "tenant_id": str(request.tenant_id),
            "knowledge_base_id": str(request.knowledge_base_id),
            "document_id": str(request.document_id),
            "storage": request.storage.model_dump(mode="json"),
            "parser_config": request.parser_config,
            "metadata": request.metadata,
        }
        started = perf_counter()
        try:
            data = await self._post_json(
                self.ingest_path,
                payload,
                request_id=request.metadata.get("request_id"),
            )
        except httpx.HTTPError as exc:
            return IngestResult(
                document_id=request.document_id,
                status=DocumentIngestStatus.FAILED,
                message=f"RAGFlow ingest request failed: {exc.__class__.__name__}.",
                metadata={
                    "ragflow_url_configured": True,
                    "elapsed_ms": _elapsed_ms(started),
                    "error": exc.__class__.__name__,
                },
            )

        status_value = _string_path(data, "status") or _string_path(data, "data.status")
        ingest_status = _map_ingest_status(status_value)
        return IngestResult(
            document_id=request.document_id,
            status=ingest_status,
            external_document_id=(
                _string_path(data, "external_document_id")
                or _string_path(data, "document_id")
                or _string_path(data, "data.external_document_id")
                or _string_path(data, "data.document_id")
            ),
            message=(
                _string_path(data, "message")
                or _string_path(data, "data.message")
                or "RAGFlow ingest request accepted."
            ),
            metadata={
                "ragflow_url_configured": True,
                "elapsed_ms": _elapsed_ms(started),
                "response_status": status_value,
                "response_keys": sorted(data.keys()),
            },
        )

    async def retrieve(self, request: RetrieveRequest) -> RetrieveResult:
        started = perf_counter()
        if not self._configured:
            return RetrieveResult(
                chunks=[],
                engine=RAGEngineType.RAGFLOW,
                elapsed_ms=0,
                diagnostics={
                    "ragflow_url_configured": False,
                    "message": "RAGFlow URL is not configured.",
                },
            )

        payload = {
            "tenant_id": str(request.tenant_id),
            "knowledge_base_id": str(request.knowledge_base_id),
            "query": request.query,
            "top_k": request.top_k,
            "score_threshold": request.score_threshold,
            "filters": request.filters,
            "include_raw_chunks": request.include_raw_chunks,
        }
        try:
            data = await self._post_json(self.retrieve_path, payload)
        except httpx.HTTPError as exc:
            return RetrieveResult(
                chunks=[],
                engine=RAGEngineType.RAGFLOW,
                elapsed_ms=_elapsed_ms(started),
                diagnostics={
                    "ragflow_url_configured": True,
                    "error": f"{exc.__class__.__name__}: {exc}",
                    "retries_exhausted": True,
                },
            )

        raw_chunks = (
            _list_path(data, "chunks")
            or _list_path(data, "results")
            or _list_path(data, "data.chunks")
        )
        chunks = [_chunk_from_response(item) for item in raw_chunks if isinstance(item, dict)]
        return RetrieveResult(
            chunks=[chunk for chunk in chunks if chunk is not None][: request.top_k],
            engine=RAGEngineType.RAGFLOW,
            elapsed_ms=_elapsed_ms(started),
            diagnostics={
                "ragflow_url_configured": True,
                "candidate_count": len(raw_chunks),
                "response_keys": sorted(data.keys()),
            },
        )

    async def delete_document(self, knowledge_base_id: str, document_id: str) -> bool:
        if not self._configured:
            return False
        path = self.delete_path.format(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
        )
        try:
            async with self._client() as client:
                response = await client.request(
                    "DELETE",
                    path,
                    json={
                        "knowledge_base_id": knowledge_base_id,
                        "document_id": document_id,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError:
            return False
        return True

    async def health_check(self) -> HealthStatus:
        if not self._configured:
            return HealthStatus(
                component="ragflow",
                status=ComponentStatus.NOT_CONFIGURED,
                message="RAGFlow URL is not configured.",
                details={"base_url_configured": False},
            )
        try:
            async with self._client(timeout=self.health_timeout_seconds) as client:
                response = await client.get(self.health_path)
            healthy = 200 <= response.status_code < 300
            return HealthStatus(
                component="ragflow",
                status=ComponentStatus.HEALTHY if healthy else ComponentStatus.ERROR,
                message=f"RAGFlow health endpoint returned HTTP {response.status_code}.",
                details={
                    "base_url": self._safe_base_url,
                    "status_code": response.status_code,
                    "health_path": self.health_path,
                },
            )
        except httpx.HTTPError as exc:
            return HealthStatus(
                component="ragflow",
                status=ComponentStatus.ERROR,
                message=f"RAGFlow health check failed: {exc.__class__.__name__}.",
                details={"base_url": self._safe_base_url, "health_path": self.health_path},
            )

    def _client(self, **kwargs: Any) -> httpx.AsyncClient:
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request_id = kwargs.pop("request_id", None)
        if request_id:
            headers["X-Request-Id"] = str(request_id)
        return self.client_factory(
            base_url=self.base_url.rstrip("/"),
            headers=headers,
            timeout=kwargs.pop("timeout", self.request_timeout_seconds),
            # RAGFlow is an explicitly configured private infrastructure
            # endpoint. Do not let workstation-wide HTTP(S)_PROXY variables
            # silently reroute document and retrieval traffic.
            trust_env=False,
            **kwargs,
        )

    async def _post_json(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """POST JSON with configurable retry on transient network errors.

        Retries are triggered only for connection errors, read timeouts, and
        5xx responses -- never for 4xx client errors (those are deterministic
        and retrying would not help). Exponential backoff with jitter is applied
        between attempts.
        """

        last_exc: httpx.HTTPError | None = None
        for attempt in range(self.max_retries + 1):
            try:
                async with self._client(request_id=request_id) as client:
                    response = await client.post(path, json=payload)
                if response.status_code < 500:
                    response.raise_for_status()
                    data = response.json()
                    return data if isinstance(data, dict) else {"data": data}
                # 5xx: retryable; synthesize an HTTPStatusError for re-raise path
                response.raise_for_status()
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt >= self.max_retries or not _is_retryable(exc):
                    raise
                backoff = self.retry_backoff_seconds * (2**attempt)
                await asyncio.sleep(backoff)
        # Should be unreachable, but keep the type checker happy.
        assert last_exc is not None
        raise last_exc

    @property
    def _configured(self) -> bool:
        return bool(self.base_url)

    @property
    def _safe_base_url(self) -> str:
        return self.base_url.rstrip("/")


def _map_ingest_status(value: str | None) -> DocumentIngestStatus:
    normalized = (value or "").lower()
    aliases = {
        "ok": DocumentIngestStatus.INDEXED,
        "success": DocumentIngestStatus.INDEXED,
        "completed": DocumentIngestStatus.INDEXED,
        "indexed": DocumentIngestStatus.INDEXED,
        "accepted": DocumentIngestStatus.ACCEPTED,
        "pending": DocumentIngestStatus.PENDING,
        "ingesting": DocumentIngestStatus.INGESTING,
        "running": DocumentIngestStatus.INGESTING,
        "failed": DocumentIngestStatus.FAILED,
        "error": DocumentIngestStatus.FAILED,
    }
    return aliases.get(normalized, DocumentIngestStatus.ACCEPTED)


def _chunk_from_response(item: dict[str, Any]) -> RAGChunk | None:
    text = item.get("text") or item.get("content") or item.get("chunk") or item.get("answer")
    if text is None:
        return None
    raw_metadata = item.get("metadata")
    metadata: dict[str, Any] = dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
    return RAGChunk(
        chunk_id=str(item.get("chunk_id") or item.get("id") or item.get("chunkId") or ""),
        document_id=_uuid_or_none(
            item.get("document_id") or item.get("doc_id") or item.get("documentId")
        ),
        text=str(text),
        score=_float_or_none(item.get("score") or item.get("similarity")),
        source_name=_string_or_none(
            item.get("source_name") or item.get("source") or item.get("filename")
        ),
        metadata={**metadata, "ragflow_raw_keys": sorted(item.keys())},
    )


def _string_path(data: dict[str, Any], path: str) -> str | None:
    value: Any = data
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return str(value) if value is not None else None


def _list_path(data: dict[str, Any], path: str) -> list[Any]:
    value: Any = data
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return []
        value = value[part]
    return value if isinstance(value, list) else []


def _uuid_or_none(value: object) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _string_or_none(value: object) -> str | None:
    return str(value) if value is not None else None


def _elapsed_ms(started: float) -> int:
    return int((perf_counter() - started) * 1000)


def _is_retryable(exc: httpx.HTTPError) -> bool:
    """Classify whether an httpx error is worth retrying.

    Retryable:
      - ConnectError / ConnectTimeout: transient network issues.
      - ReadTimeout: server slow to respond.
      - RemoteProtocolError / PoolTimeout: connection-level hiccups.
      - HTTPStatusError with 5xx status_code.
    Not retryable:
      - 4xx HTTPStatusError (client errors).
      - LocalProtocolError (request malformed by us).
    """

    if isinstance(
        exc,
        (
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.PoolTimeout,
            httpx.RemoteProtocolError,
        ),
    ):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False
