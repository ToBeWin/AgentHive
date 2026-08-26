from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ComponentStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    NOT_CONFIGURED = "not_configured"
    ERROR = "error"


class RAGEngineType(StrEnum):
    RAGFLOW = "ragflow"
    PGVECTOR = "pgvector"


class DocumentIngestStatus(StrEnum):
    ACCEPTED = "accepted"
    PENDING = "pending"
    INGESTING = "ingesting"
    INDEXED = "indexed"
    FAILED = "failed"


class HealthStatus(BaseModel):
    component: str
    status: ComponentStatus
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class StoredObjectRef(BaseModel):
    bucket: str
    object_key: str
    content_type: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    checksum_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ObjectUploadPlan(BaseModel):
    storage: StoredObjectRef
    upload_url: str | None = None
    expires_in_seconds: int | None = Field(default=None, ge=1)
    headers: dict[str, str] = Field(default_factory=dict)
    placeholder: bool = True


class IngestRequest(BaseModel):
    tenant_id: UUID
    knowledge_base_id: UUID
    document_id: UUID
    storage: StoredObjectRef
    parser_config: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestResult(BaseModel):
    document_id: UUID
    status: DocumentIngestStatus
    external_document_id: str | None = None
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RAGChunk(BaseModel):
    chunk_id: str
    document_id: UUID | None = None
    text: str
    score: float | None = Field(default=None, ge=0)
    source_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrieveRequest(BaseModel):
    tenant_id: UUID
    knowledge_base_id: UUID
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)
    score_threshold: float | None = Field(default=None, ge=0, le=1)
    filters: dict[str, Any] = Field(default_factory=dict)
    include_raw_chunks: bool = False


class RetrieveResult(BaseModel):
    chunks: list[RAGChunk]
    engine: RAGEngineType
    elapsed_ms: int
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class VectorUpsertRequest(BaseModel):
    tenant_id: UUID
    knowledge_base_id: UUID
    document_id: UUID
    chunks: list[RAGChunk]
    embedding_model_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class VectorSearchRequest(BaseModel):
    tenant_id: UUID
    knowledge_base_id: UUID
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)
    filters: dict[str, Any] = Field(default_factory=dict)
