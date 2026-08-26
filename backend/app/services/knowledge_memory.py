"""In-memory knowledge metadata fallback used by development environments."""

from datetime import datetime, timezone
from re import sub
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.api.deps import Principal
from app.rag.minio import MinIOObjectStorageAdapter
from app.rag.router import RAGRouter
from app.rag.schemas import DocumentIngestStatus, IngestRequest, StoredObjectRef
from app.schemas.knowledge import (
    DocumentIngestPlanResponse,
    DocumentUploadCompleteRequest,
    DocumentUploadCompleteResponse,
    DocumentUploadPrepareRequest,
    DocumentUploadPrepareResponse,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    KnowledgeBaseStatus,
    KnowledgeBaseVisibility,
    KnowledgeDeleteResponse,
    KnowledgeDocumentListResponse,
    KnowledgeDocumentResponse,
    KnowledgeDocumentStatus,
    StorageTargetResponse,
)


_DEFAULT_BUCKET = "agenthive-knowledge"
_bases: dict[UUID, KnowledgeBaseResponse] = {}
_documents: dict[UUID, list[KnowledgeDocumentResponse]] = {}
_storage = MinIOObjectStorageAdapter()
_rag_router = RAGRouter()


def _prepare_response(
    *,
    base: KnowledgeBaseResponse,
    document: KnowledgeDocumentResponse,
    upload_plan: Any,
    parser_config: dict[str, Any],
) -> DocumentUploadPrepareResponse:
    return DocumentUploadPrepareResponse(
        document=document,
        upload_session_id=uuid4().hex,
        storage=StorageTargetResponse(
            bucket=upload_plan.storage.bucket,
            object_key=upload_plan.storage.object_key,
            content_type=upload_plan.storage.content_type,
            size_bytes=upload_plan.storage.size_bytes,
            checksum_sha256=upload_plan.storage.checksum_sha256,
            upload_url=upload_plan.upload_url,
            expires_in_seconds=upload_plan.expires_in_seconds,
            headers=upload_plan.headers,
            placeholder=upload_plan.placeholder,
        ),
        ingest_plan=DocumentIngestPlanResponse(
            rag_engine=base.rag_engine,
            parser_config=parser_config,
            auto_ingest=False,
            message="Upload target prepared. Complete upload to trigger optional ingestion.",
        ),
    )


def _storage_ref_for_document(
    *,
    tenant_id: UUID,
    knowledge_base_id: UUID,
    document_id: UUID,
    filename: str,
    content_type: str | None,
    size_bytes: int | None,
    checksum_sha256: str | None,
) -> StoredObjectRef:
    return StoredObjectRef(
        bucket=_DEFAULT_BUCKET,
        object_key=_build_object_key(
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            filename=filename,
        ),
        content_type=content_type,
        size_bytes=size_bytes,
        checksum_sha256=checksum_sha256,
        metadata={
            "tenant_id": str(tenant_id),
            "knowledge_base_id": str(knowledge_base_id),
            "document_id": str(document_id),
        },
    )


def _memory_list_knowledge_bases(principal: Principal) -> KnowledgeBaseListResponse:
    return KnowledgeBaseListResponse(
        bases=[
            base
            for base in _bases.values()
            if base.tenant_id == principal.tenant_id
            and base.status != KnowledgeBaseStatus.ARCHIVED
            and _memory_can_access_base(base, principal)
        ]
    )


def _memory_create_knowledge_base(
    payload: KnowledgeBaseCreateRequest,
    principal: Principal,
) -> KnowledgeBaseResponse:
    now = _utcnow()
    base = KnowledgeBaseResponse(
        id=uuid4(),
        tenant_id=principal.tenant_id,
        name=payload.name,
        description=payload.description,
        visibility=payload.visibility,
        department_ids=payload.department_ids,
        rag_engine=payload.rag_engine,
        embedding_model_key=payload.embedding_model_key,
        retrieval_config=payload.retrieval_config,
        status=KnowledgeBaseStatus.ACTIVE,
        document_count=0,
        tags=payload.tags,
        metadata={
            **payload.metadata,
            "owner_user_id": str(principal.user_id),
            "access_control": {
                "visibility": payload.visibility.value,
                "department_ids": [str(department_id) for department_id in payload.department_ids],
            },
            "storage_boundary": "minio",
            "rag_boundary": payload.rag_engine.value,
            "vector_boundary": "pgvector",
            "persistence": "development_memory_fallback",
        },
        created_at=now,
        updated_at=now,
    )
    _bases[base.id] = base
    _documents.setdefault(base.id, [])
    return base


def _memory_list_knowledge_documents(
    knowledge_base_id: UUID,
    principal: Principal,
) -> KnowledgeDocumentListResponse:
    _memory_get_accessible_base(knowledge_base_id, principal, require_write=False)
    return KnowledgeDocumentListResponse(documents=list(_documents.get(knowledge_base_id, [])))


async def _memory_prepare_document_upload(
    knowledge_base_id: UUID,
    payload: DocumentUploadPrepareRequest,
    principal: Principal,
) -> DocumentUploadPrepareResponse:
    base = _memory_get_accessible_base(knowledge_base_id, principal, require_write=True)
    now = _utcnow()
    document_id = uuid4()
    storage_ref = _storage_ref_for_document(
        tenant_id=principal.tenant_id,
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
        filename=payload.filename,
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
        checksum_sha256=payload.checksum_sha256,
    )
    upload_plan = await _storage.prepare_upload(storage_ref)
    document = KnowledgeDocumentResponse(
        id=document_id,
        knowledge_base_id=knowledge_base_id,
        tenant_id=principal.tenant_id,
        filename=payload.filename,
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
        checksum_sha256=payload.checksum_sha256,
        source=payload.source,
        status=KnowledgeDocumentStatus.PENDING_UPLOAD,
        storage_bucket=storage_ref.bucket,
        storage_object_key=storage_ref.object_key,
        rag_document_id=None,
        chunk_count=0,
        metadata={
            **payload.metadata,
            "parser_config": payload.parser_config,
            "persistence": "development_memory_fallback",
        },
        created_at=now,
        updated_at=now,
    )
    _documents.setdefault(knowledge_base_id, []).append(document)
    _bases[knowledge_base_id] = base.model_copy(
        update={"document_count": len(_documents[knowledge_base_id]), "updated_at": now}
    )
    return _prepare_response(
        base=_bases[knowledge_base_id],
        document=document,
        upload_plan=upload_plan,
        parser_config=payload.parser_config,
    )


async def _memory_complete_document_upload(
    knowledge_base_id: UUID,
    document_id: UUID,
    payload: DocumentUploadCompleteRequest,
    principal: Principal,
) -> DocumentUploadCompleteResponse:
    base = _memory_get_accessible_base(knowledge_base_id, principal, require_write=True)
    document, document_index = _memory_get_document_for_tenant(
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
        tenant_id=principal.tenant_id,
    )
    if document.status not in {
        KnowledgeDocumentStatus.PENDING_UPLOAD,
        KnowledgeDocumentStatus.UPLOADED,
        KnowledgeDocumentStatus.FAILED,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document upload cannot be completed from status {document.status.value}.",
        )

    now = _utcnow()
    document = document.model_copy(
        update={
            "size_bytes": payload.size_bytes
            if payload.size_bytes is not None
            else document.size_bytes,
            "checksum_sha256": payload.checksum_sha256
            if payload.checksum_sha256 is not None
            else document.checksum_sha256,
            "status": KnowledgeDocumentStatus.UPLOADED,
            "error_message": None,
            "metadata": {
                **document.metadata,
                **payload.metadata,
                "upload_completed_at": now.isoformat(),
            },
            "updated_at": now,
        }
    )
    _memory_replace_document(knowledge_base_id, document_index, document)

    if not payload.auto_ingest:
        return DocumentUploadCompleteResponse(
            document=document,
            auto_ingest=False,
            ingest_status=None,
            message="Upload completed. Ingestion was not requested.",
            diagnostics={
                "rag_engine": base.rag_engine.value,
                "persistence": "development_memory_fallback",
            },
        )

    document = document.model_copy(
        update={"status": KnowledgeDocumentStatus.INGESTING, "updated_at": _utcnow()}
    )
    _memory_replace_document(knowledge_base_id, document_index, document)
    try:
        ingest_result = await _rag_router.ingest(
            IngestRequest(
                tenant_id=principal.tenant_id,
                knowledge_base_id=knowledge_base_id,
                document_id=document_id,
                storage=StoredObjectRef(
                    bucket=document.storage_bucket,
                    object_key=document.storage_object_key,
                    content_type=document.content_type,
                    size_bytes=document.size_bytes,
                    checksum_sha256=document.checksum_sha256,
                    metadata={
                        "tenant_id": str(principal.tenant_id),
                        "knowledge_base_id": str(knowledge_base_id),
                        "document_id": str(document_id),
                    },
                ),
                parser_config=document.metadata.get("parser_config", {}),
                metadata=document.metadata,
            ),
            engine=base.rag_engine,
        )
        mapped_status = _map_ingest_status(ingest_result.status)
        result_metadata = {
            **document.metadata,
            **ingest_result.metadata,
            "ingest_status": ingest_result.status.value,
            "ingest_message": ingest_result.message,
            "ingest_updated_at": _utcnow().isoformat(),
        }
        if ingest_result.metadata.get("placeholder_adapter"):
            result_metadata["placeholder_ingest"] = True

        document = document.model_copy(
            update={
                "status": mapped_status,
                "rag_document_id": ingest_result.external_document_id,
                "chunk_count": _extract_chunk_count(ingest_result.metadata),
                "error_message": ingest_result.message
                if mapped_status == KnowledgeDocumentStatus.FAILED
                else None,
                "metadata": result_metadata,
                "updated_at": _utcnow(),
            }
        )
        _memory_replace_document(knowledge_base_id, document_index, document)
        return DocumentUploadCompleteResponse(
            document=document,
            auto_ingest=True,
            ingest_status=mapped_status,
            message=ingest_result.message,
            diagnostics={
                "rag_engine": base.rag_engine.value,
                "adapter_status": ingest_result.status.value,
                "placeholder_ingest": result_metadata.get("placeholder_ingest", False),
                "persistence": "development_memory_fallback",
            },
        )
    except Exception as exc:
        document = document.model_copy(
            update={
                "status": KnowledgeDocumentStatus.FAILED,
                "error_message": str(exc),
                "metadata": {
                    **document.metadata,
                    "ingest_status": DocumentIngestStatus.FAILED.value,
                    "ingest_updated_at": _utcnow().isoformat(),
                },
                "updated_at": _utcnow(),
            }
        )
        _memory_replace_document(knowledge_base_id, document_index, document)
        return DocumentUploadCompleteResponse(
            document=document,
            auto_ingest=True,
            ingest_status=KnowledgeDocumentStatus.FAILED,
            message="Upload completed, but ingestion failed.",
            diagnostics={"rag_engine": base.rag_engine.value, "error": str(exc)},
        )


async def _memory_delete_knowledge_document(
    knowledge_base_id: UUID,
    document_id: UUID,
    principal: Principal,
) -> KnowledgeDeleteResponse:
    _memory_get_accessible_base(knowledge_base_id, principal, require_write=True)
    document, document_index = _memory_get_document_for_tenant(
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
        tenant_id=principal.tenant_id,
    )
    now = _utcnow()
    deleted_document = document.model_copy(
        update={
            "status": KnowledgeDocumentStatus.DELETED,
            "metadata": {
                **document.metadata,
                "deleted_at": now.isoformat(),
                "deleted_by": str(principal.user_id),
                "cleanup": {
                    "object_deleted": False,
                    "rag_deleted": False,
                    "chunk_rows_deleted": False,
                    "errors": ["development_memory_fallback_cleanup_not_available"],
                },
            },
            "updated_at": now,
        }
    )
    _memory_replace_document(knowledge_base_id, document_index, deleted_document)
    _documents[knowledge_base_id] = [
        item
        for item in _documents.get(knowledge_base_id, [])
        if item.status != KnowledgeDocumentStatus.DELETED
    ]
    if knowledge_base_id in _bases:
        _bases[knowledge_base_id] = _bases[knowledge_base_id].model_copy(
            update={"document_count": len(_documents.get(knowledge_base_id, [])), "updated_at": now}
        )
    return KnowledgeDeleteResponse(
        id=document_id,
        deleted=True,
        message="Knowledge document deleted.",
        diagnostics={
            "persistence": "development_memory_fallback",
            "object_deleted": False,
            "rag_deleted": False,
            "chunk_rows_deleted": False,
            "errors": ["development_memory_fallback_cleanup_not_available"],
        },
    )


async def _memory_reingest_knowledge_document(
    knowledge_base_id: UUID,
    document_id: UUID,
    principal: Principal,
) -> DocumentUploadCompleteResponse:
    _memory_get_accessible_base(knowledge_base_id, principal, require_write=True)
    document, document_index = _memory_get_document_for_tenant(
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
        tenant_id=principal.tenant_id,
    )
    if document.status in {
        KnowledgeDocumentStatus.DELETED,
        KnowledgeDocumentStatus.PENDING_UPLOAD,
        KnowledgeDocumentStatus.INGESTING,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document cannot be reingested from status {document.status.value}.",
        )

    now = _utcnow()
    document = document.model_copy(
        update={
            "status": KnowledgeDocumentStatus.UPLOADED,
            "rag_document_id": None,
            "chunk_count": 0,
            "error_message": None,
            "metadata": {
                **document.metadata,
                "reingest_requested_at": now.isoformat(),
                "reingest_requested_by": str(principal.user_id),
                "reingest_cleanup": {
                    "object_deleted": False,
                    "rag_deleted": False,
                    "chunk_rows_deleted": False,
                    "errors": ["development_memory_fallback_cleanup_not_available"],
                },
            },
            "updated_at": now,
        }
    )
    _memory_replace_document(knowledge_base_id, document_index, document)
    return await _memory_complete_document_upload(
        knowledge_base_id,
        document_id,
        DocumentUploadCompleteRequest(
            auto_ingest=True,
            metadata={
                "reingest": True,
                "reingest_cleanup": document.metadata.get("reingest_cleanup", {}),
            },
        ),
        principal,
    )


async def _memory_delete_knowledge_base(
    knowledge_base_id: UUID,
    principal: Principal,
) -> KnowledgeDeleteResponse:
    base = _memory_get_accessible_base(knowledge_base_id, principal, require_write=True)
    document_count = len(_documents.get(knowledge_base_id, []))
    _documents.pop(knowledge_base_id, None)
    _bases.pop(knowledge_base_id, None)
    return KnowledgeDeleteResponse(
        id=base.id,
        deleted=True,
        message="Knowledge base archived and documents deleted.",
        diagnostics={
            "persistence": "development_memory_fallback",
            "document_count": document_count,
            "documents_checked": document_count,
            "objects_deleted": 0,
            "rag_deleted": 0,
            "chunk_rows_deleted": 0,
            "errors": ["development_memory_fallback_cleanup_not_available"],
        },
    )


def _memory_get_base_for_tenant(knowledge_base_id: UUID, tenant_id: UUID) -> KnowledgeBaseResponse:
    base = _bases.get(knowledge_base_id)
    if base is None or base.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found."
        )
    return base


def _memory_get_accessible_base(
    knowledge_base_id: UUID,
    principal: Principal,
    *,
    require_write: bool,
) -> KnowledgeBaseResponse:
    base = _memory_get_base_for_tenant(knowledge_base_id, principal.tenant_id)
    allowed = (
        _memory_can_write_base(base, principal)
        if require_write
        else _memory_can_access_base(base, principal)
    )
    if allowed:
        return base
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Knowledge base access denied by visibility policy.",
    )


def _memory_can_access_base(base: KnowledgeBaseResponse, principal: Principal) -> bool:
    if _is_tenant_admin(principal):
        return True
    if base.visibility == KnowledgeBaseVisibility.TENANT:
        return True
    if base.visibility == KnowledgeBaseVisibility.PRIVATE:
        return str(base.metadata.get("owner_user_id")) == str(principal.user_id)
    return False


def _memory_can_write_base(base: KnowledgeBaseResponse, principal: Principal) -> bool:
    if _is_tenant_admin(principal):
        return True
    if str(base.metadata.get("owner_user_id")) == str(principal.user_id):
        return True
    if str(principal.user_id) in _metadata_uuid_strings(base.metadata, "write_user_ids"):
        return True
    return False


def _memory_get_document_for_tenant(
    *,
    knowledge_base_id: UUID,
    document_id: UUID,
    tenant_id: UUID,
) -> tuple[KnowledgeDocumentResponse, int]:
    for index, document in enumerate(_documents.get(knowledge_base_id, [])):
        if document.id == document_id and document.tenant_id == tenant_id:
            return document, index
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge document not found."
    )


def _memory_replace_document(
    knowledge_base_id: UUID,
    document_index: int,
    document: KnowledgeDocumentResponse,
) -> None:
    _documents.setdefault(knowledge_base_id, [])[document_index] = document


def _memory_mark_document_failed(
    knowledge_base_id: UUID,
    document_id: UUID,
    tenant_id: UUID,
    message: str,
    metadata: dict[str, Any],
) -> None:
    try:
        document, index = _memory_get_document_for_tenant(
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            tenant_id=tenant_id,
        )
    except HTTPException:
        return
    _memory_replace_document(
        knowledge_base_id,
        index,
        document.model_copy(
            update={
                "status": KnowledgeDocumentStatus.FAILED,
                "error_message": message,
                "metadata": {**document.metadata, **metadata},
                "updated_at": _utcnow(),
            }
        ),
    )


def _map_ingest_status(status_value: DocumentIngestStatus) -> KnowledgeDocumentStatus:
    if status_value == DocumentIngestStatus.INDEXED:
        return KnowledgeDocumentStatus.INDEXED
    if status_value == DocumentIngestStatus.FAILED:
        return KnowledgeDocumentStatus.FAILED
    return KnowledgeDocumentStatus.INGESTING


def _extract_chunk_count(metadata: dict[str, Any]) -> int:
    chunk_count = metadata.get("chunk_count", 0)
    if isinstance(chunk_count, int) and chunk_count >= 0:
        return chunk_count
    return 0


def _build_object_key(
    *,
    tenant_id: UUID,
    knowledge_base_id: UUID,
    document_id: UUID,
    filename: str,
) -> str:
    safe_name = sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._") or "document"
    return f"tenants/{tenant_id}/knowledge/{knowledge_base_id}/documents/{document_id}/{safe_name}"


def _dict_metadata_value(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    return {}


def _metadata_uuid_strings(metadata: dict[str, Any], key: str) -> set[str]:
    value = metadata.get(key)
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value if isinstance(item, (str, UUID))}


def _is_tenant_admin(principal: Principal) -> bool:
    return "tenant:admin" in principal.permissions or "*" in principal.permissions


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
