from typing import Any
from uuid import UUID

from sqlalchemy import Column, JSON
from sqlmodel import Field

from app.models.base import SoftDeleteMixin, TenantScopedMixin, TimestampMixin, UUIDMixin


class KnowledgeBase(UUIDMixin, TenantScopedMixin, TimestampMixin, SoftDeleteMixin, table=True):
    __tablename__ = "knowledge_bases"

    name: str = Field(max_length=120, nullable=False)
    description: str | None = Field(default=None)
    visibility: str = Field(default="tenant", max_length=30, index=True)
    department_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    rag_engine: str = Field(default="ragflow", max_length=40, index=True)
    embedding_model_key: str | None = Field(default=None, max_length=120)
    retrieval_config: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    status: str = Field(default="active", max_length=30, index=True)
    document_count: int = Field(default=0, ge=0)
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    metadata_json: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )


class KnowledgeDocument(UUIDMixin, TenantScopedMixin, TimestampMixin, SoftDeleteMixin, table=True):
    __tablename__ = "knowledge_documents"

    knowledge_base_id: UUID = Field(foreign_key="knowledge_bases.id", index=True, nullable=False)
    filename: str = Field(max_length=255, nullable=False)
    content_type: str | None = Field(default=None, max_length=160)
    size_bytes: int | None = Field(default=None, ge=0)
    checksum_sha256: str | None = Field(default=None, max_length=64, index=True)
    source: str = Field(default="api_upload", max_length=40, index=True)
    status: str = Field(default="pending_upload", max_length=40, index=True)
    storage_bucket: str = Field(max_length=120, nullable=False)
    storage_object_key: str = Field(max_length=1024, nullable=False)
    rag_document_id: str | None = Field(default=None, max_length=255, index=True)
    chunk_count: int = Field(default=0, ge=0)
    error_message: str | None = Field(default=None)
    metadata_json: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )


class KnowledgeChunk(UUIDMixin, TenantScopedMixin, TimestampMixin, table=True):
    __tablename__ = "knowledge_chunks"

    knowledge_base_id: UUID = Field(foreign_key="knowledge_bases.id", index=True, nullable=False)
    document_id: UUID = Field(foreign_key="knowledge_documents.id", index=True, nullable=False)
    chunk_index: int = Field(ge=0, nullable=False)
    text: str = Field(nullable=False)
    token_count: int = Field(default=0, ge=0)
    source_name: str | None = Field(default=None, max_length=255)
    search_text: str = Field(nullable=False)
    metadata_json: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
