from abc import ABC, abstractmethod

from app.rag.schemas import (
    HealthStatus,
    IngestRequest,
    IngestResult,
    ObjectUploadPlan,
    RetrieveRequest,
    RetrieveResult,
    StoredObjectRef,
    VectorSearchRequest,
    VectorUpsertRequest,
)


class BaseObjectStorageAdapter(ABC):
    """Boundary for MinIO/S3-compatible object storage.

    The service layer owns document metadata. The storage adapter only prepares
    upload targets and manages object bytes; it must not parse documents or own
    knowledge-base state.
    """

    adapter_name: str

    @abstractmethod
    async def prepare_upload(self, storage: StoredObjectRef) -> ObjectUploadPlan:
        """Prepare an upload target for the caller."""

    @abstractmethod
    async def put_object(self, storage: StoredObjectRef, data: bytes) -> StoredObjectRef:
        """Persist object bytes and return the final storage reference."""

    @abstractmethod
    async def get_object(self, storage: StoredObjectRef) -> bytes:
        """Read object bytes by storage reference."""

    @abstractmethod
    async def delete_object(self, storage: StoredObjectRef) -> bool:
        """Delete an object by storage reference."""

    @abstractmethod
    async def health_check(self) -> HealthStatus:
        """Validate object-storage reachability and configuration."""


class BaseRAGAdapter(ABC):
    """Boundary for external RAG engines such as RAGFlow."""

    adapter_name: str

    @abstractmethod
    async def ingest(self, request: IngestRequest) -> IngestResult:
        """Submit a stored document for parsing, chunking, and indexing."""

    @abstractmethod
    async def retrieve(self, request: RetrieveRequest) -> RetrieveResult:
        """Retrieve semantically relevant chunks from the RAG engine."""

    @abstractmethod
    async def delete_document(self, knowledge_base_id: str, document_id: str) -> bool:
        """Remove a document and its indexed chunks from the RAG engine."""

    @abstractmethod
    async def health_check(self) -> HealthStatus:
        """Validate RAG engine reachability and configuration."""


class BaseVectorStoreAdapter(ABC):
    """Boundary for AgentHive-owned pgvector fallback storage."""

    adapter_name: str

    @abstractmethod
    async def upsert_chunks(self, request: VectorUpsertRequest) -> int:
        """Persist embedded chunks into the vector store."""

    @abstractmethod
    async def search(self, request: VectorSearchRequest) -> RetrieveResult:
        """Search embedded chunks from the vector store."""

    @abstractmethod
    async def delete_document(self, knowledge_base_id: str, document_id: str) -> bool:
        """Remove vector rows for a document."""

    @abstractmethod
    async def health_check(self) -> HealthStatus:
        """Validate vector-store reachability and configuration."""
