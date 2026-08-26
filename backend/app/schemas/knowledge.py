from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.rag.schemas import RAGEngineType


class KnowledgeBaseStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class KnowledgeBaseVisibility(StrEnum):
    PRIVATE = "private"
    DEPARTMENT = "department"
    TENANT = "tenant"


class KnowledgeDocumentStatus(StrEnum):
    PENDING_UPLOAD = "pending_upload"
    UPLOADED = "uploaded"
    INGESTING = "ingesting"
    INDEXED = "indexed"
    FAILED = "failed"
    DELETED = "deleted"


class KnowledgeDocumentSource(StrEnum):
    API_UPLOAD = "api_upload"
    CHANNEL_ATTACHMENT = "channel_attachment"
    INTERNAL_IMPORT = "internal_import"


class RetrievalConfig(BaseModel):
    top_k: int = Field(default=5, ge=1, le=50)
    score_threshold: float | None = Field(default=None, ge=0, le=1)
    rerank_enabled: bool = False
    citation_required: bool = True
    metadata_filters: dict[str, Any] = Field(default_factory=dict)


class KnowledgeBaseCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    visibility: KnowledgeBaseVisibility = KnowledgeBaseVisibility.TENANT
    department_ids: list[UUID] = Field(default_factory=list)
    rag_engine: RAGEngineType = RAGEngineType.RAGFLOW
    embedding_model_key: str | None = Field(default=None, max_length=120)
    retrieval_config: RetrievalConfig = Field(default_factory=RetrievalConfig)
    tags: list[str] = Field(default_factory=list, max_length=20)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_visibility_scope(self) -> "KnowledgeBaseCreateRequest":
        if self.visibility == KnowledgeBaseVisibility.DEPARTMENT and not self.department_ids:
            raise ValueError("department_ids is required when visibility is department.")
        if self.visibility != KnowledgeBaseVisibility.DEPARTMENT:
            self.department_ids = []
        return self


class KnowledgeBaseResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    visibility: KnowledgeBaseVisibility
    department_ids: list[UUID]
    rag_engine: RAGEngineType
    embedding_model_key: str | None
    retrieval_config: RetrievalConfig
    status: KnowledgeBaseStatus
    document_count: int = Field(ge=0)
    tags: list[str]
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseListResponse(BaseModel):
    bases: list[KnowledgeBaseResponse]


class WorkbenchKnowledgeBaseResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    visibility: KnowledgeBaseVisibility
    department_ids: list[UUID]
    status: KnowledgeBaseStatus
    document_count: int = Field(ge=0)
    tags: list[str]
    updated_at: datetime


class WorkbenchKnowledgeBaseListResponse(BaseModel):
    bases: list[WorkbenchKnowledgeBaseResponse]


class KnowledgeGovernanceTargetItem(BaseModel):
    id: UUID
    label: str
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeGovernanceTargetsResponse(BaseModel):
    departments: list[KnowledgeGovernanceTargetItem] = Field(default_factory=list)


class DocumentUploadPrepareRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str | None = Field(default=None, max_length=160)
    size_bytes: int | None = Field(default=None, ge=0, le=1024 * 1024 * 1024)
    checksum_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    source: KnowledgeDocumentSource = KnowledgeDocumentSource.API_UPLOAD
    parser_config: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("filename")
    @classmethod
    def filename_must_not_be_path(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or "/" in normalized or "\\" in normalized:
            raise ValueError("filename must be a plain file name, not a path")
        return normalized


class KnowledgeDocumentResponse(BaseModel):
    id: UUID
    knowledge_base_id: UUID
    tenant_id: UUID
    filename: str
    content_type: str | None
    size_bytes: int | None
    checksum_sha256: str | None
    source: KnowledgeDocumentSource
    status: KnowledgeDocumentStatus
    storage_bucket: str
    storage_object_key: str
    rag_document_id: str | None
    chunk_count: int = Field(ge=0)
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentListResponse(BaseModel):
    documents: list[KnowledgeDocumentResponse]


class WorkbenchKnowledgeDocumentResponse(BaseModel):
    id: UUID
    knowledge_base_id: UUID
    filename: str
    content_type: str | None
    size_bytes: int | None
    source: KnowledgeDocumentSource
    status: KnowledgeDocumentStatus
    chunk_count: int = Field(ge=0)
    updated_at: datetime


class WorkbenchKnowledgeDocumentListResponse(BaseModel):
    documents: list[WorkbenchKnowledgeDocumentResponse]


class KnowledgeDeleteResponse(BaseModel):
    id: UUID
    deleted: bool
    message: str
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class StorageTargetResponse(BaseModel):
    bucket: str
    object_key: str
    content_type: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    checksum_sha256: str | None = None
    upload_url: str | None = None
    expires_in_seconds: int | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    placeholder: bool = True


class DocumentIngestPlanResponse(BaseModel):
    rag_engine: RAGEngineType
    vector_store: str = "pgvector"
    parser_config: dict[str, Any] = Field(default_factory=dict)
    auto_ingest: bool = False
    message: str


class DocumentUploadPrepareResponse(BaseModel):
    document: KnowledgeDocumentResponse
    upload_session_id: str
    storage: StorageTargetResponse
    ingest_plan: DocumentIngestPlanResponse


class DocumentUploadCompleteRequest(BaseModel):
    etag: str | None = Field(default=None, max_length=256)
    size_bytes: int | None = Field(default=None, ge=0, le=1024 * 1024 * 1024)
    checksum_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    auto_ingest: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentUploadCompleteResponse(BaseModel):
    document: KnowledgeDocumentResponse
    auto_ingest: bool
    ingest_status: KnowledgeDocumentStatus | None = None
    message: str
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class RetrievalTestRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=50)
    score_threshold: float | None = Field(default=None, ge=0, le=1)
    filters: dict[str, Any] = Field(default_factory=dict)
    include_raw_chunks: bool = False
    rerank: bool = False


class RetrievalSourceResponse(BaseModel):
    chunk_id: str
    document_id: UUID | None = None
    source_name: str | None = None
    score: float | None = None
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalTestResponse(BaseModel):
    knowledge_base_id: UUID
    query: str
    engine: RAGEngineType
    elapsed_ms: int = Field(ge=0)
    results: list[RetrievalSourceResponse]
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
