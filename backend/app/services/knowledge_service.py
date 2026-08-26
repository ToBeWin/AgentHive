import asyncio
import json
from time import perf_counter
from typing import Any, cast
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, delete, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from app.api.deps import Principal
from app.core.config import is_development_environment, settings
from app.knowledge import document_processing
from app.knowledge import retrieval_postprocessing
from app.models.knowledge import KnowledgeBase, KnowledgeChunk, KnowledgeDocument
from app.models.org import Department
from app.models.user import UserDepartment
from app.rag.cache import clear_rag_caches
from app.rag.embeddings import embed_text_nonblocking, get_default_embedding_service, vector_literal
from app.rag.schemas import (
    DocumentIngestStatus,
    IngestRequest,
    IngestResult,
    RAGChunk,
    RAGEngineType,
    RetrieveRequest,
    RetrieveResult,
    StoredObjectRef,
)
from app.schemas.knowledge import (
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
    KnowledgeDocumentSource,
    KnowledgeDocumentStatus,
    KnowledgeGovernanceTargetItem,
    KnowledgeGovernanceTargetsResponse,
    RetrievalSourceResponse,
    RetrievalTestRequest,
    RetrievalTestResponse,
    WorkbenchKnowledgeBaseListResponse,
    WorkbenchKnowledgeBaseResponse,
    WorkbenchKnowledgeDocumentListResponse,
    WorkbenchKnowledgeDocumentResponse,
)
from app.services.audit_service import record_audit_event
from app.services.knowledge_memory import (
    _bases,  # noqa: F401
    _dict_metadata_value,
    _documents,  # noqa: F401
    _extract_chunk_count,
    _map_ingest_status,
    _memory_complete_document_upload,
    _memory_create_knowledge_base,
    _memory_delete_knowledge_base,
    _memory_delete_knowledge_document,
    _memory_get_accessible_base,
    _memory_list_knowledge_bases,
    _memory_list_knowledge_documents,
    _memory_mark_document_failed,
    _memory_prepare_document_upload,
    _memory_reingest_knowledge_document,
    _storage,
    _storage_ref_for_document,
    _rag_router,
    _prepare_response,
    _utcnow,
)
from app.services.license_service import ensure_license_capacity


_embedding_service = get_default_embedding_service()


async def list_knowledge_bases(
    session: AsyncSession,
    principal: Principal,
) -> KnowledgeBaseListResponse:
    _require_knowledge_permission(principal, "knowledge:read")
    try:
        result = await session.execute(
            select(KnowledgeBase)
            .where(
                cast(ColumnElement[bool], KnowledgeBase.tenant_id == principal.tenant_id),
                cast(Any, KnowledgeBase.deleted_at).is_(None),
                cast(
                    ColumnElement[bool], KnowledgeBase.status != KnowledgeBaseStatus.ARCHIVED.value
                ),
            )
            .order_by(cast(Any, KnowledgeBase.updated_at).desc())
        )
        department_ids = await _principal_department_ids(session, principal)
        bases = [
            _base_to_response(row)
            for row in result.scalars()
            if _can_access_base(row, principal, department_ids)
        ]
        return KnowledgeBaseListResponse(bases=bases)
    except (OSError, SQLAlchemyError):
        if _can_use_memory_fallback(principal):
            return _memory_list_knowledge_bases(principal)
        raise _storage_unavailable()


async def list_knowledge_governance_targets(
    session: AsyncSession,
    principal: Principal,
) -> KnowledgeGovernanceTargetsResponse:
    _require_knowledge_permission(principal, "knowledge:read")
    try:
        departments_result = await session.execute(
            select(Department)
            .where(cast(ColumnElement[bool], Department.tenant_id == principal.tenant_id))
            .order_by(cast(Any, Department.sort_order).asc(), cast(Any, Department.name).asc())
        )
    except (OSError, SQLAlchemyError):
        if _can_use_memory_fallback(principal):
            return KnowledgeGovernanceTargetsResponse()
        raise _storage_unavailable()

    departments = [
        KnowledgeGovernanceTargetItem(
            id=row.id,
            label=row.name,
            description=row.description,
            metadata={
                "parent_id": str(row.parent_id) if row.parent_id else None,
                "sort_order": row.sort_order,
            },
        )
        for row in departments_result.scalars().all()
    ]
    return KnowledgeGovernanceTargetsResponse(departments=departments)


async def list_workbench_knowledge_bases(
    session: AsyncSession,
    principal: Principal,
) -> WorkbenchKnowledgeBaseListResponse:
    response = await list_knowledge_bases(session, principal)
    return WorkbenchKnowledgeBaseListResponse(
        bases=[_workbench_base_response(base) for base in response.bases]
    )


async def create_knowledge_base(
    session: AsyncSession,
    payload: KnowledgeBaseCreateRequest,
    principal: Principal,
) -> KnowledgeBaseResponse:
    _require_knowledge_permission(principal, "knowledge:write")
    department_ids = await _validate_knowledge_department_ids(
        session, payload.department_ids, principal
    )
    now = _utcnow()
    row = KnowledgeBase(
        tenant_id=principal.tenant_id,
        name=payload.name,
        description=payload.description,
        visibility=payload.visibility.value,
        department_ids=[str(department_id) for department_id in department_ids],
        rag_engine=payload.rag_engine.value,
        embedding_model_key=payload.embedding_model_key,
        retrieval_config=payload.retrieval_config.model_dump(mode="json"),
        status=KnowledgeBaseStatus.ACTIVE.value,
        document_count=0,
        tags=payload.tags,
        metadata_json={
            **payload.metadata,
            "owner_user_id": str(principal.user_id),
            "access_control": {
                "visibility": payload.visibility.value,
                "department_ids": [str(department_id) for department_id in department_ids],
            },
            "storage_boundary": "minio",
            "rag_boundary": payload.rag_engine.value,
            "vector_boundary": "pgvector",
            "persistence": "postgresql",
        },
        created_at=now,
        updated_at=now,
    )
    try:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return _base_to_response(row)
    except (OSError, SQLAlchemyError):
        await _rollback_quietly(session)
        if _can_use_memory_fallback(principal):
            return _memory_create_knowledge_base(payload, principal)
        raise _storage_unavailable()


async def list_knowledge_documents(
    session: AsyncSession,
    knowledge_base_id: UUID,
    principal: Principal,
) -> KnowledgeDocumentListResponse:
    _require_knowledge_permission(principal, "knowledge:read")
    try:
        await _get_accessible_base_db(session, knowledge_base_id, principal, require_write=False)
        result = await session.execute(
            select(KnowledgeDocument)
            .where(
                cast(ColumnElement[bool], KnowledgeDocument.tenant_id == principal.tenant_id),
                cast(ColumnElement[bool], KnowledgeDocument.knowledge_base_id == knowledge_base_id),
                cast(Any, KnowledgeDocument.deleted_at).is_(None),
                cast(
                    ColumnElement[bool],
                    KnowledgeDocument.status != KnowledgeDocumentStatus.DELETED.value,
                ),
            )
            .order_by(cast(Any, KnowledgeDocument.created_at).desc())
        )
        return KnowledgeDocumentListResponse(
            documents=[_document_to_response(row) for row in result.scalars()]
        )
    except HTTPException:
        raise
    except (OSError, SQLAlchemyError):
        if _can_use_memory_fallback(principal):
            return _memory_list_knowledge_documents(knowledge_base_id, principal)
        raise _storage_unavailable()


async def list_workbench_knowledge_documents(
    session: AsyncSession,
    knowledge_base_id: UUID,
    principal: Principal,
) -> WorkbenchKnowledgeDocumentListResponse:
    response = await list_knowledge_documents(session, knowledge_base_id, principal)
    return WorkbenchKnowledgeDocumentListResponse(
        documents=[_workbench_document_response(document) for document in response.documents]
    )


async def prepare_document_upload(
    session: AsyncSession,
    knowledge_base_id: UUID,
    payload: DocumentUploadPrepareRequest,
    principal: Principal,
) -> DocumentUploadPrepareResponse:
    _require_knowledge_permission(principal, "knowledge:write")
    if payload.size_bytes is not None and payload.size_bytes > settings.knowledge_upload_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Knowledge document upload exceeds the configured size limit.",
        )
    try:
        base = await _get_accessible_base_db(
            session, knowledge_base_id, principal, require_write=True
        )
        await ensure_license_capacity(
            session,
            tenant_id=principal.tenant_id,
            resource="knowledge_storage_bytes",
            increment=payload.size_bytes or 0,
        )
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
        now = _utcnow()
        row = KnowledgeDocument(
            id=document_id,
            tenant_id=principal.tenant_id,
            knowledge_base_id=knowledge_base_id,
            filename=payload.filename,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
            checksum_sha256=payload.checksum_sha256,
            source=payload.source.value,
            status=KnowledgeDocumentStatus.PENDING_UPLOAD.value,
            storage_bucket=storage_ref.bucket,
            storage_object_key=storage_ref.object_key,
            rag_document_id=None,
            chunk_count=0,
            metadata_json={
                **payload.metadata,
                "parser_config": payload.parser_config,
                "upload_mode": payload.metadata.get("upload_mode", "prepared_object_storage"),
            },
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        base.document_count = await _count_documents_for_base(
            session,
            knowledge_base_id,
            tenant_id=principal.tenant_id,
        )
        base.updated_at = now
        await session.commit()
        await session.refresh(row)
        await session.refresh(base)
        return _prepare_response(
            base=_base_to_response(base),
            document=_document_to_response(row),
            upload_plan=upload_plan,
            parser_config=payload.parser_config,
        )
    except HTTPException:
        raise
    except (OSError, SQLAlchemyError):
        await _rollback_quietly(session)
        if _can_use_memory_fallback(principal):
            return await _memory_prepare_document_upload(knowledge_base_id, payload, principal)
        raise _storage_unavailable()


async def upload_document_file(
    session: AsyncSession,
    knowledge_base_id: UUID,
    *,
    filename: str,
    content_type: str | None,
    data: bytes,
    auto_ingest: bool,
    parser_config: dict[str, Any] | None,
    metadata: dict[str, Any] | None,
    principal: Principal,
) -> DocumentUploadCompleteResponse:
    checksum = await _sha256_hex_nonblocking(data)
    prepare_response = await prepare_document_upload(
        session,
        knowledge_base_id,
        DocumentUploadPrepareRequest(
            filename=filename,
            content_type=content_type,
            size_bytes=len(data),
            checksum_sha256=checksum,
            parser_config=parser_config or {},
            metadata={
                **(metadata or {}),
                "upload_mode": "multipart_backend",
            },
        ),
        principal,
    )
    document = prepare_response.document
    storage = StoredObjectRef(
        bucket=document.storage_bucket,
        object_key=document.storage_object_key,
        content_type=document.content_type,
        size_bytes=len(data),
        checksum_sha256=checksum,
        metadata={
            "tenant_id": str(principal.tenant_id),
            "knowledge_base_id": str(knowledge_base_id),
            "document_id": str(document.id),
            "filename": filename,
        },
    )
    try:
        stored_object = await _storage.put_object(storage, data)
    except Exception as exc:
        await _mark_document_failed(
            session,
            knowledge_base_id=knowledge_base_id,
            document_id=document.id,
            tenant_id=principal.tenant_id,
            message=str(exc),
            metadata={"storage_error": str(exc), "upload_failed_at": _utcnow().isoformat()},
            principal=principal,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Object storage upload failed: {exc}",
        ) from exc

    return await complete_document_upload(
        session,
        knowledge_base_id,
        document.id,
        DocumentUploadCompleteRequest(
            etag=stored_object.metadata.get("etag")
            if isinstance(stored_object.metadata.get("etag"), str)
            else None,
            size_bytes=stored_object.size_bytes,
            checksum_sha256=stored_object.checksum_sha256,
            auto_ingest=auto_ingest,
            metadata={
                "storage_backend": stored_object.metadata.get("storage_backend"),
                "storage_metadata": stored_object.metadata,
                "uploaded_via": "backend_multipart",
            },
        ),
        principal,
    )


async def complete_document_upload(
    session: AsyncSession,
    knowledge_base_id: UUID,
    document_id: UUID,
    payload: DocumentUploadCompleteRequest,
    principal: Principal,
) -> DocumentUploadCompleteResponse:
    _require_knowledge_permission(principal, "knowledge:write")
    try:
        base = await _get_accessible_base_db(
            session, knowledge_base_id, principal, require_write=True
        )
        row = await _get_document_for_tenant_db(
            session,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            tenant_id=principal.tenant_id,
        )
        response = await _complete_document_row(session, base, row, payload, principal)
        return response
    except HTTPException:
        raise
    except (OSError, SQLAlchemyError):
        await _rollback_quietly(session)
        if _can_use_memory_fallback(principal):
            return await _memory_complete_document_upload(
                knowledge_base_id,
                document_id,
                payload,
                principal,
            )
        raise _storage_unavailable()


async def run_retrieval_test(
    session: AsyncSession,
    knowledge_base_id: UUID,
    payload: RetrievalTestRequest,
    principal: Principal,
) -> RetrievalTestResponse:
    _require_knowledge_permission(principal, "knowledge:read")
    try:
        base_row = await _get_accessible_base_db(
            session, knowledge_base_id, principal, require_write=False
        )
        base = _base_to_response(base_row)
    except HTTPException:
        raise
    except (OSError, SQLAlchemyError):
        if not _can_use_memory_fallback(principal):
            raise _storage_unavailable()
        base = _memory_get_accessible_base(knowledge_base_id, principal, require_write=False)

    retrieve_request = RetrieveRequest(
        tenant_id=principal.tenant_id,
        knowledge_base_id=knowledge_base_id,
        query=payload.query,
        top_k=payload.top_k,
        score_threshold=payload.score_threshold,
        filters=payload.filters,
        include_raw_chunks=payload.include_raw_chunks,
    )
    if base.rag_engine == RAGEngineType.PGVECTOR:
        try:
            result = await _retrieve_pgvector_chunks(session, retrieve_request)
        except (OSError, SQLAlchemyError):
            if not _can_use_memory_fallback(principal):
                raise _storage_unavailable()
            result = RetrieveResult(
                chunks=[],
                engine=RAGEngineType.PGVECTOR,
                elapsed_ms=0,
                diagnostics={
                    "persistence": "development_memory_fallback",
                    "message": "Database is unavailable; memory fallback retrieval has no chunk index.",
                },
            )
    else:
        result = await _rag_router.retrieve(retrieve_request, engine=base.rag_engine)
    return RetrievalTestResponse(
        knowledge_base_id=knowledge_base_id,
        query=payload.query,
        engine=result.engine,
        elapsed_ms=result.elapsed_ms,
        results=[
            RetrievalSourceResponse(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                source_name=chunk.source_name,
                score=chunk.score,
                text=chunk.text,
                metadata=chunk.metadata if payload.include_raw_chunks else {},
            )
            for chunk in result.chunks
        ],
        diagnostics={
            **result.diagnostics,
            "knowledge_base_name": base.name,
            "knowledge_base_visibility": base.visibility.value,
            "rerank_requested": payload.rerank,
            "score_threshold": payload.score_threshold,
            "document_count": base.document_count,
        },
    )


async def delete_knowledge_document(
    session: AsyncSession,
    knowledge_base_id: UUID,
    document_id: UUID,
    principal: Principal,
    *,
    request_id: str | None = None,
) -> KnowledgeDeleteResponse:
    _require_knowledge_permission(principal, "knowledge:write")
    try:
        base = await _get_accessible_base_db(
            session, knowledge_base_id, principal, require_write=True
        )
        row = await _get_document_for_tenant_db(
            session,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            tenant_id=principal.tenant_id,
        )
        return await _delete_document_row(
            session,
            base=base,
            row=row,
            principal=principal,
            request_id=request_id,
            audit_action="knowledge.document.delete",
        )
    except HTTPException:
        raise
    except (OSError, SQLAlchemyError):
        await _rollback_quietly(session)
        if _can_use_memory_fallback(principal):
            return await _memory_delete_knowledge_document(
                knowledge_base_id, document_id, principal
            )
        raise _storage_unavailable()


async def delete_knowledge_base(
    session: AsyncSession,
    knowledge_base_id: UUID,
    principal: Principal,
    *,
    request_id: str | None = None,
) -> KnowledgeDeleteResponse:
    _require_knowledge_permission(principal, "knowledge:write")
    try:
        base = await _get_accessible_base_db(
            session, knowledge_base_id, principal, require_write=True
        )
        result = await session.execute(
            select(KnowledgeDocument).where(
                cast(ColumnElement[bool], KnowledgeDocument.tenant_id == principal.tenant_id),
                cast(ColumnElement[bool], KnowledgeDocument.knowledge_base_id == knowledge_base_id),
                cast(Any, KnowledgeDocument.deleted_at).is_(None),
                cast(
                    ColumnElement[bool],
                    KnowledgeDocument.status != KnowledgeDocumentStatus.DELETED.value,
                ),
            )
        )
        documents = list(result.scalars().all())
        cleanup_results = [
            await _cleanup_document_indexes_and_object(session, base=base, row=document)
            for document in documents
        ]
        now = _utcnow()
        await session.execute(
            delete(KnowledgeChunk).where(
                cast(ColumnElement[bool], KnowledgeChunk.tenant_id == principal.tenant_id),
                cast(ColumnElement[bool], KnowledgeChunk.knowledge_base_id == knowledge_base_id),
            )
        )
        for document, cleanup in zip(documents, cleanup_results):
            document.status = KnowledgeDocumentStatus.DELETED.value
            document.deleted_at = now
            document.updated_at = now
            document.error_message = None
            document.metadata_json = {
                **document.metadata_json,
                "deleted_at": now.isoformat(),
                "deleted_by": str(principal.user_id),
                "cleanup": cleanup,
            }
        base.status = KnowledgeBaseStatus.ARCHIVED.value
        base.deleted_at = now
        base.updated_at = now
        base.document_count = 0
        base.metadata_json = {
            **base.metadata_json,
            "deleted_at": now.isoformat(),
            "deleted_by": str(principal.user_id),
        }
        diagnostics = _summarize_delete_cleanup(cleanup_results)
        await record_audit_event(
            session,
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            request_id=request_id,
            action="knowledge.base.delete",
            resource_type="knowledge_base",
            resource_id=knowledge_base_id,
            details={
                "name": base.name,
                "document_count": len(documents),
                "rag_engine": base.rag_engine,
                "cleanup": diagnostics,
            },
        )
        await session.commit()
        return KnowledgeDeleteResponse(
            id=knowledge_base_id,
            deleted=True,
            message="Knowledge base archived and documents deleted.",
            diagnostics={
                **diagnostics,
                "document_count": len(documents),
                "persistence": "postgresql",
            },
        )
    except HTTPException:
        raise
    except (OSError, SQLAlchemyError):
        await _rollback_quietly(session)
        if _can_use_memory_fallback(principal):
            return await _memory_delete_knowledge_base(knowledge_base_id, principal)
        raise _storage_unavailable()


async def reingest_knowledge_document(
    session: AsyncSession,
    knowledge_base_id: UUID,
    document_id: UUID,
    principal: Principal,
    *,
    request_id: str | None = None,
) -> DocumentUploadCompleteResponse:
    _require_knowledge_permission(principal, "knowledge:write")
    try:
        base = await _get_accessible_base_db(
            session, knowledge_base_id, principal, require_write=True
        )
        row = await _get_document_for_tenant_db(
            session,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            tenant_id=principal.tenant_id,
        )
        return await _reingest_document_row(
            session,
            base=base,
            row=row,
            principal=principal,
            request_id=request_id,
        )
    except HTTPException:
        raise
    except (OSError, SQLAlchemyError):
        await _rollback_quietly(session)
        if _can_use_memory_fallback(principal):
            return await _memory_reingest_knowledge_document(
                knowledge_base_id, document_id, principal
            )
        raise _storage_unavailable()


async def _delete_document_row(
    session: AsyncSession,
    *,
    base: KnowledgeBase,
    row: KnowledgeDocument,
    principal: Principal,
    request_id: str | None,
    audit_action: str,
) -> KnowledgeDeleteResponse:
    cleanup = await _cleanup_document_indexes_and_object(session, base=base, row=row)
    now = _utcnow()
    await session.execute(
        delete(KnowledgeChunk).where(
            cast(ColumnElement[bool], KnowledgeChunk.tenant_id == principal.tenant_id),
            cast(ColumnElement[bool], KnowledgeChunk.knowledge_base_id == base.id),
            cast(ColumnElement[bool], KnowledgeChunk.document_id == row.id),
        )
    )
    row.status = KnowledgeDocumentStatus.DELETED.value
    row.deleted_at = now
    row.updated_at = now
    row.error_message = None
    row.metadata_json = {
        **row.metadata_json,
        "deleted_at": now.isoformat(),
        "deleted_by": str(principal.user_id),
        "cleanup": cleanup,
    }
    base.document_count = await _count_documents_for_base(
        session,
        base.id,
        tenant_id=principal.tenant_id,
    )
    base.updated_at = now
    await record_audit_event(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        request_id=request_id,
        action=audit_action,
        resource_type="knowledge_document",
        resource_id=row.id,
        details={
            "knowledge_base_id": str(base.id),
            "filename": row.filename,
            "rag_engine": base.rag_engine,
            "cleanup": cleanup,
        },
    )
    await session.commit()
    return KnowledgeDeleteResponse(
        id=row.id,
        deleted=True,
        message="Knowledge document deleted.",
        diagnostics={**cleanup, "persistence": "postgresql"},
    )


async def _reingest_document_row(
    session: AsyncSession,
    *,
    base: KnowledgeBase,
    row: KnowledgeDocument,
    principal: Principal,
    request_id: str | None,
) -> DocumentUploadCompleteResponse:
    if row.status in {
        KnowledgeDocumentStatus.DELETED.value,
        KnowledgeDocumentStatus.PENDING_UPLOAD.value,
        KnowledgeDocumentStatus.INGESTING.value,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document cannot be reingested from status {row.status}.",
        )

    cleanup = await _cleanup_document_indexes(session, base=base, row=row)
    cleanup_errors = [error for error in cleanup.get("errors", []) if isinstance(error, str)]
    if cleanup_errors:
        await _rollback_quietly(session)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Document reingestion cleanup failed.",
                "errors": cleanup_errors,
            },
        )

    now = _utcnow()
    row.status = KnowledgeDocumentStatus.UPLOADED.value
    row.rag_document_id = None
    row.chunk_count = 0
    row.error_message = None
    row.metadata_json = {
        **row.metadata_json,
        "reingest_requested_at": now.isoformat(),
        "reingest_requested_by": str(principal.user_id),
        "reingest_cleanup": cleanup,
    }
    row.updated_at = now
    base.updated_at = now
    await session.commit()
    await session.refresh(row)
    await session.refresh(base)

    response = await _complete_document_row(
        session,
        base,
        row,
        DocumentUploadCompleteRequest(
            auto_ingest=True,
            metadata={
                "reingest": True,
                "reingest_cleanup": cleanup,
            },
        ),
        principal,
    )
    await record_audit_event(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        request_id=request_id,
        action="knowledge.document.reingest",
        resource_type="knowledge_document",
        resource_id=row.id,
        details={
            "knowledge_base_id": str(base.id),
            "filename": row.filename,
            "rag_engine": base.rag_engine,
            "status": response.document.status.value,
            "ingest_status": response.ingest_status.value if response.ingest_status else None,
            "cleanup": cleanup,
        },
    )
    await session.commit()
    return response


async def _cleanup_document_indexes_and_object(
    session: AsyncSession,
    *,
    base: KnowledgeBase,
    row: KnowledgeDocument,
) -> dict[str, Any]:
    cleanup: dict[str, Any] = {
        "object_deleted": False,
        "rag_deleted": False,
        "chunk_rows_deleted": False,
        "errors": [],
    }
    try:
        await session.execute(
            delete(KnowledgeChunk).where(
                cast(ColumnElement[bool], KnowledgeChunk.tenant_id == row.tenant_id),
                cast(
                    ColumnElement[bool], KnowledgeChunk.knowledge_base_id == row.knowledge_base_id
                ),
                cast(ColumnElement[bool], KnowledgeChunk.document_id == row.id),
            )
        )
        cleanup["chunk_rows_deleted"] = True
    except Exception as exc:
        cleanup["errors"].append(f"pgvector_cleanup_failed: {exc}")

    try:
        if base.rag_engine == RAGEngineType.PGVECTOR.value:
            cleanup["rag_deleted"] = True
        else:
            cleanup["rag_deleted"] = await _rag_router.delete_document(
                engine=_base_to_response(base).rag_engine,
                knowledge_base_id=str(base.id),
                document_id=row.rag_document_id or str(row.id),
            )
    except Exception as exc:
        cleanup["errors"].append(f"rag_cleanup_failed: {exc}")

    try:
        cleanup["object_deleted"] = await _storage.delete_object(_storage_ref_from_document(row))
    except Exception as exc:
        cleanup["errors"].append(f"object_cleanup_failed: {exc}")

    return cleanup


async def _cleanup_document_indexes(
    session: AsyncSession,
    *,
    base: KnowledgeBase,
    row: KnowledgeDocument,
) -> dict[str, Any]:
    cleanup: dict[str, Any] = {
        "object_deleted": False,
        "rag_deleted": False,
        "chunk_rows_deleted": False,
        "errors": [],
    }
    try:
        await session.execute(
            delete(KnowledgeChunk).where(
                cast(ColumnElement[bool], KnowledgeChunk.tenant_id == row.tenant_id),
                cast(
                    ColumnElement[bool], KnowledgeChunk.knowledge_base_id == row.knowledge_base_id
                ),
                cast(ColumnElement[bool], KnowledgeChunk.document_id == row.id),
            )
        )
        cleanup["chunk_rows_deleted"] = True
    except Exception as exc:
        cleanup["errors"].append(f"pgvector_cleanup_failed: {exc}")

    try:
        if base.rag_engine == RAGEngineType.PGVECTOR.value:
            cleanup["rag_deleted"] = True
        else:
            cleanup["rag_deleted"] = await _rag_router.delete_document(
                engine=_base_to_response(base).rag_engine,
                knowledge_base_id=str(base.id),
                document_id=row.rag_document_id or str(row.id),
            )
    except Exception as exc:
        cleanup["errors"].append(f"rag_cleanup_failed: {exc}")

    return cleanup


def _storage_ref_from_document(row: KnowledgeDocument) -> StoredObjectRef:
    return StoredObjectRef(
        bucket=row.storage_bucket,
        object_key=row.storage_object_key,
        content_type=row.content_type,
        size_bytes=row.size_bytes,
        checksum_sha256=row.checksum_sha256,
        metadata={
            "tenant_id": str(row.tenant_id),
            "knowledge_base_id": str(row.knowledge_base_id),
            "document_id": str(row.id),
            **_dict_metadata_value(row.metadata_json.get("storage_metadata")),
        },
    )


def _summarize_delete_cleanup(cleanup_results: list[dict[str, Any]]) -> dict[str, Any]:
    errors = [
        error
        for cleanup in cleanup_results
        for error in cleanup.get("errors", [])
        if isinstance(error, str)
    ]
    return {
        "documents_checked": len(cleanup_results),
        "objects_deleted": sum(1 for cleanup in cleanup_results if cleanup.get("object_deleted")),
        "rag_deleted": sum(1 for cleanup in cleanup_results if cleanup.get("rag_deleted")),
        "chunk_rows_deleted": sum(
            1 for cleanup in cleanup_results if cleanup.get("chunk_rows_deleted")
        ),
        "errors": errors,
    }


async def _complete_document_row(
    session: AsyncSession,
    base: KnowledgeBase,
    row: KnowledgeDocument,
    payload: DocumentUploadCompleteRequest,
    principal: Principal,
) -> DocumentUploadCompleteResponse:
    if row.status == KnowledgeDocumentStatus.DELETED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Deleted documents cannot complete upload.",
        )
    if row.status not in {
        KnowledgeDocumentStatus.PENDING_UPLOAD.value,
        KnowledgeDocumentStatus.UPLOADED.value,
        KnowledgeDocumentStatus.FAILED.value,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document upload cannot be completed from status {row.status}.",
        )

    now = _utcnow()
    row.size_bytes = payload.size_bytes if payload.size_bytes is not None else row.size_bytes
    row.checksum_sha256 = (
        payload.checksum_sha256 if payload.checksum_sha256 is not None else row.checksum_sha256
    )
    row.status = KnowledgeDocumentStatus.UPLOADED.value
    row.error_message = None
    row.metadata_json = {
        **row.metadata_json,
        **payload.metadata,
        "upload_completed_at": now.isoformat(),
    }
    if payload.etag is not None:
        row.metadata_json["etag"] = payload.etag
    row.updated_at = now
    base.updated_at = now
    await session.commit()
    await session.refresh(row)
    await session.refresh(base)

    if not payload.auto_ingest:
        return DocumentUploadCompleteResponse(
            document=_document_to_response(row),
            auto_ingest=False,
            ingest_status=None,
            message="Upload completed. Ingestion was not requested.",
            diagnostics={"rag_engine": base.rag_engine, "persistence": "postgresql"},
        )

    row.status = KnowledgeDocumentStatus.INGESTING.value
    row.updated_at = _utcnow()
    await session.commit()
    await session.refresh(row)

    try:
        ingest_request = IngestRequest(
            tenant_id=principal.tenant_id,
            knowledge_base_id=base.id,
            document_id=row.id,
            storage=StoredObjectRef(
                bucket=row.storage_bucket,
                object_key=row.storage_object_key,
                content_type=row.content_type,
                size_bytes=row.size_bytes,
                checksum_sha256=row.checksum_sha256,
                metadata={
                    "tenant_id": str(principal.tenant_id),
                    "knowledge_base_id": str(base.id),
                    "document_id": str(row.id),
                    **_dict_metadata_value(row.metadata_json.get("storage_metadata")),
                },
            ),
            parser_config=row.metadata_json.get("parser_config", {}),
            metadata=row.metadata_json,
        )
        if base.rag_engine == RAGEngineType.PGVECTOR.value:
            ingest_result = await _ingest_document_to_pgvector(session, row, ingest_request)
            clear_rag_caches()
        else:
            ingest_result = await _rag_router.ingest(
                ingest_request,
                engine=_base_to_response(base).rag_engine,
            )
        mapped_status = _map_ingest_status(ingest_result.status)
        result_metadata = {
            **row.metadata_json,
            **ingest_result.metadata,
            "ingest_status": ingest_result.status.value,
            "ingest_message": ingest_result.message,
            "ingest_updated_at": _utcnow().isoformat(),
        }
        if ingest_result.metadata.get("placeholder_adapter"):
            result_metadata["placeholder_ingest"] = True
            result_metadata["diagnostics"] = {
                **_dict_metadata_value(result_metadata.get("diagnostics")),
                "placeholder_adapter": True,
                "message": ingest_result.message,
            }

        row.status = mapped_status.value
        row.rag_document_id = ingest_result.external_document_id
        row.chunk_count = _extract_chunk_count(ingest_result.metadata)
        row.error_message = (
            ingest_result.message if mapped_status == KnowledgeDocumentStatus.FAILED else None
        )
        row.metadata_json = result_metadata
        row.updated_at = _utcnow()
        await session.commit()
        await session.refresh(row)
        return DocumentUploadCompleteResponse(
            document=_document_to_response(row),
            auto_ingest=True,
            ingest_status=mapped_status,
            message=ingest_result.message,
            diagnostics={
                "rag_engine": base.rag_engine,
                "adapter_status": ingest_result.status.value,
                "placeholder_ingest": result_metadata.get("placeholder_ingest", False),
                "persistence": "postgresql",
            },
        )
    except Exception as exc:
        row.status = KnowledgeDocumentStatus.FAILED.value
        row.error_message = str(exc)
        row.metadata_json = {
            **row.metadata_json,
            "ingest_status": DocumentIngestStatus.FAILED.value,
            "ingest_updated_at": _utcnow().isoformat(),
        }
        row.updated_at = _utcnow()
        await session.commit()
        await session.refresh(row)
        return DocumentUploadCompleteResponse(
            document=_document_to_response(row),
            auto_ingest=True,
            ingest_status=KnowledgeDocumentStatus.FAILED,
            message="Upload completed, but ingestion failed.",
            diagnostics={
                "rag_engine": base.rag_engine,
                "error": str(exc),
                "persistence": "postgresql",
            },
        )


async def _ingest_document_to_pgvector(
    session: AsyncSession,
    document: KnowledgeDocument,
    request: IngestRequest,
) -> IngestResult:
    vector_schema_ready = await _pgvector_chunk_schema_ready(session)
    raw = await _storage.get_object(request.storage)
    chunks = await _parse_document_chunks_nonblocking(
        raw,
        content_type=document.content_type,
        filename=document.filename,
        chunk_size=int(request.parser_config.get("chunk_size", 900)),
        overlap=int(request.parser_config.get("chunk_overlap", 120)),
    )
    await session.execute(
        delete(KnowledgeChunk).where(
            cast(ColumnElement[bool], KnowledgeChunk.document_id == document.id)
        )
    )
    now = _utcnow()
    chunk_rows: list[tuple[KnowledgeChunk, str]] = []
    fts_rows: list[tuple[KnowledgeChunk, str]] = []
    for index, (chunk_text, token_count, search_text, fts_text) in enumerate(chunks):
        chunk = KnowledgeChunk(
            tenant_id=document.tenant_id,
            knowledge_base_id=document.knowledge_base_id,
            document_id=document.id,
            chunk_index=index,
            text=chunk_text,
            token_count=token_count,
            source_name=document.filename,
            search_text=search_text,
            metadata_json={
                "filename": document.filename,
                "content_type": document.content_type,
                "storage_bucket": document.storage_bucket,
                "storage_object_key": document.storage_object_key,
                "retrieval_mode": "vector_with_text_fallback"
                if vector_schema_ready
                else "text_chunk_fallback",
                "vector_schema_ready": vector_schema_ready,
            },
            created_at=now,
            updated_at=now,
        )
        session.add(chunk)
        chunk_rows.append((chunk, chunk_text))
        fts_rows.append((chunk, fts_text))
    await session.flush()
    # Populate fts_tsvector for the newly inserted chunks so that hybrid
    # retrieval (vector + FTS + RRF) can use the GIN index.
    for chunk, fts_text in fts_rows:
        if fts_text:
            await session.execute(
                text(
                    "UPDATE knowledge_chunks SET fts_tsvector = to_tsvector('simple', :fts_text) WHERE id = :chunk_id"
                ),
                {"fts_text": fts_text, "chunk_id": chunk.id},
            )
    embedded_count = 0
    if vector_schema_ready:
        embedded_count = await _write_chunk_embeddings(session, chunk_rows)
    return IngestResult(
        document_id=document.id,
        status=DocumentIngestStatus.INDEXED,
        external_document_id=str(document.id),
        message=f"Indexed {len(chunks)} text chunk(s) into AgentHive pgvector fallback.",
        metadata={
            "chunk_count": len(chunks),
            "embedded_chunk_count": embedded_count,
            "vector_store": "pgvector",
            "retrieval_mode": "vector_with_text_fallback"
            if embedded_count
            else "text_chunk_fallback",
            "embedding_status": "ready" if embedded_count else "not_configured",
            "embedding_model_key": _embedding_service.model_key if embedded_count else None,
            "vector_schema_ready": vector_schema_ready,
        },
    )


async def _sha256_hex_nonblocking(data: bytes) -> str:
    """Hash potentially large uploads without blocking the request event loop."""
    return await asyncio.to_thread(_sha256_hex, data)


def _sha256_hex(data: bytes) -> str:
    """Compatibility wrapper retained for upload-ingest monkeypatches."""
    return document_processing.sha256_hex(data)


async def _parse_document_chunks_nonblocking(
    raw: bytes,
    *,
    content_type: str | None,
    filename: str,
    chunk_size: int,
    overlap: int,
) -> list[tuple[str, int, str, str]]:
    """Offload document parsing, OCR, chunking, and text-index preparation."""
    return await asyncio.to_thread(
        _parse_document_chunks,
        raw,
        content_type=content_type,
        filename=filename,
        chunk_size=chunk_size,
        overlap=overlap,
    )


def _parse_document_chunks(
    raw: bytes,
    *,
    content_type: str | None,
    filename: str,
    chunk_size: int,
    overlap: int,
) -> list[tuple[str, int, str, str]]:
    document_text = _decode_document_text(raw, content_type, filename)
    chunks = _chunk_text(document_text, chunk_size=chunk_size, overlap=overlap)
    return [
        (
            chunk,
            _rough_token_count(chunk),
            _normalize_search_text(chunk),
            _build_fts_text(chunk),
        )
        for chunk in chunks
    ]


async def _retrieve_pgvector_chunks(
    session: AsyncSession,
    request: RetrieveRequest,
) -> RetrieveResult:
    started = perf_counter()
    vector_schema_ready = await _pgvector_chunk_schema_ready(session)
    if vector_schema_ready:
        vector_result = await _retrieve_pgvector_embedding_chunks(session, request, started=started)
        if vector_result.chunks:
            return vector_result
    result = await session.execute(
        select(KnowledgeChunk)
        .where(
            cast(ColumnElement[bool], KnowledgeChunk.tenant_id == request.tenant_id),
            cast(
                ColumnElement[bool], KnowledgeChunk.knowledge_base_id == request.knowledge_base_id
            ),
        )
        .order_by(
            cast(Any, KnowledgeChunk.created_at).desc(), cast(Any, KnowledgeChunk.chunk_index).asc()
        )
        .limit(1000)
    )
    query_terms = _query_terms(request.query)
    scored: list[tuple[float, KnowledgeChunk]] = []
    for chunk in result.scalars():
        if not _chunk_matches_filters(chunk, request.filters):
            continue
        score = _score_chunk(chunk.search_text, query_terms, request.query)
        if request.score_threshold is not None and score < request.score_threshold:
            continue
        if score > 0 or not query_terms:
            scored.append((score, chunk))
    scored.sort(key=lambda item: (item[0], item[1].updated_at), reverse=True)
    selected = scored[: request.top_k]
    elapsed_ms = int((perf_counter() - started) * 1000)
    return RetrieveResult(
        chunks=[
            RAGChunk(
                chunk_id=str(chunk.id),
                document_id=chunk.document_id,
                text=chunk.text,
                score=score,
                source_name=chunk.source_name,
                metadata={
                    **chunk.metadata_json,
                    "chunk_index": chunk.chunk_index,
                    "token_count": chunk.token_count,
                },
            )
            for score, chunk in selected
        ],
        engine=RAGEngineType.PGVECTOR,
        elapsed_ms=elapsed_ms,
        diagnostics={
            "retrieval_mode": "text_chunk_fallback",
            "embedding_status": "ready_no_vector_hits" if vector_schema_ready else "not_configured",
            "vector_schema_ready": vector_schema_ready,
            "candidate_count": len(scored),
            "query_terms": query_terms,
        },
    )


async def _write_chunk_embeddings(
    session: AsyncSession,
    chunks: list[tuple[KnowledgeChunk, str]],
) -> int:
    written = 0
    for chunk, chunk_text in chunks:
        embedding = await embed_text_nonblocking(_embedding_service, chunk_text)
        await session.execute(
            text(
                """
                UPDATE knowledge_chunks
                SET embedding_model_key = :embedding_model_key,
                    embedding_dimensions = :embedding_dimensions,
                    embedding = CAST(:embedding AS vector),
                    metadata_json = metadata_json || CAST(:metadata_json AS jsonb)
                WHERE id = :chunk_id
                """
            ),
            {
                "chunk_id": chunk.id,
                "embedding_model_key": embedding.model_key,
                "embedding_dimensions": embedding.dimensions,
                "embedding": vector_literal(embedding.vector),
                "metadata_json": json.dumps(
                    {
                        "embedding_status": "ready",
                        "embedding_model_key": embedding.model_key,
                        "embedding_mode": embedding.mode,
                        "embedding_dimensions": embedding.dimensions,
                    },
                    ensure_ascii=False,
                ),
            },
        )
        written += 1
    return written


async def _retrieve_pgvector_embedding_chunks(
    session: AsyncSession,
    request: RetrieveRequest,
    *,
    started: float,
) -> RetrieveResult:
    query_embedding = await embed_text_nonblocking(_embedding_service, request.query)
    result = await session.execute(
        text(
            """
            SELECT
                id::text AS chunk_id,
                document_id,
                text,
                source_name,
                metadata_json,
                chunk_index,
                token_count,
                GREATEST(0, 1 - (embedding <=> CAST(:query_embedding AS vector))) AS score
            FROM knowledge_chunks
            WHERE tenant_id = :tenant_id
              AND knowledge_base_id = :knowledge_base_id
              AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:query_embedding AS vector)
            LIMIT :limit
            """
        ),
        {
            "tenant_id": request.tenant_id,
            "knowledge_base_id": request.knowledge_base_id,
            "query_embedding": vector_literal(query_embedding.vector),
            "limit": max(request.top_k * 5, request.top_k),
        },
    )
    vector_candidates: list[RAGChunk] = []
    candidate_count = 0
    for row in result.mappings().all():
        candidate_count += 1
        metadata = dict(row["metadata_json"] or {})
        pseudo_chunk = _ChunkFilterProxy(
            document_id=row["document_id"],
            source_name=row["source_name"],
        )
        if not _chunk_matches_filters(pseudo_chunk, request.filters):
            continue
        vector_score = round(float(row["score"] or 0), 4)
        lexical_score = _score_chunk(
            _normalize_search_text(str(row["text"] or "")),
            _query_terms(request.query),
            request.query,
        )
        score = round(max(vector_score, lexical_score), 4)
        if request.score_threshold is not None and score < request.score_threshold:
            continue
        vector_candidates.append(
            RAGChunk(
                chunk_id=str(row["chunk_id"]),
                document_id=row["document_id"],
                text=row["text"],
                score=score,
                source_name=row["source_name"],
                metadata={
                    **metadata,
                    "chunk_index": row["chunk_index"],
                    "token_count": row["token_count"],
                    "vector_score": vector_score,
                    "lexical_score": lexical_score,
                    "score_strategy": "vector_lexical_max",
                },
            )
        )
    vector_candidates.sort(
        key=lambda chunk: (
            float(chunk.score or 0),
            -int(chunk.metadata.get("chunk_index") or 0),
        ),
        reverse=True,
    )

    # Hybrid retrieval: fuse vector + FTS via RRF, then optionally rerank.
    hybrid_enabled = settings.rag_hybrid_retrieval_enabled
    reranker_enabled = settings.rag_reranker_enabled and bool(settings.rag_reranker_api_url)
    fts_candidate_count = 0
    if hybrid_enabled:
        fts_rows = await _retrieve_fts_chunks(session, request)
        fts_candidate_count = len(fts_rows)
        # Apply score threshold to FTS results too.
        if request.score_threshold is not None:
            fts_rows = [
                row for row in fts_rows if float(row["score"] or 0) >= request.score_threshold
            ]
        # RRF needs more candidates than top_k so the reranker has room.
        rrf_top_k = max(request.top_k * 3, request.top_k) if reranker_enabled else request.top_k
        chunks = _rrf_fuse(vector_candidates, fts_rows, top_k=rrf_top_k)
        score_strategy = "hybrid_rrf"
    else:
        chunks = vector_candidates[: request.top_k]
        score_strategy = "vector_lexical_max"

    if reranker_enabled and chunks:
        chunks = await _rerank_chunks(chunks, request.query)

    chunks = chunks[: request.top_k]

    elapsed_ms = int((perf_counter() - started) * 1000)
    diagnostics: dict[str, Any] = {
        "retrieval_mode": "hybrid" if hybrid_enabled else "vector_similarity",
        "embedding_status": "ready",
        "embedding_model_key": query_embedding.model_key,
        "embedding_mode": query_embedding.mode,
        "vector_schema_ready": True,
        "candidate_count": candidate_count,
        "score_strategy": score_strategy,
        "reranker_enabled": reranker_enabled,
    }
    if hybrid_enabled:
        diagnostics["fts_candidate_count"] = fts_candidate_count
    return RetrieveResult(
        chunks=chunks,
        engine=RAGEngineType.PGVECTOR,
        elapsed_ms=elapsed_ms,
        diagnostics=diagnostics,
    )


async def _pgvector_chunk_schema_ready(session: AsyncSession) -> bool:
    try:
        result = await session.execute(
            text(
                """
                SELECT
                    EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')
                    AND (
                        SELECT COUNT(*)
                        FROM information_schema.columns
                        WHERE table_name = 'knowledge_chunks'
                          AND column_name IN ('embedding', 'embedding_dimensions', 'embedding_model_key')
                    ) = 3
                    AND EXISTS (
                        SELECT 1
                        FROM pg_indexes
                        WHERE tablename = 'knowledge_chunks'
                          AND indexname = 'ix_knowledge_chunks_embedding_cosine'
                    )
                """
            )
        )
        return bool(result.scalar_one())
    except Exception:
        return False


async def _get_base_for_tenant_db(
    session: AsyncSession,
    knowledge_base_id: UUID,
    tenant_id: UUID,
) -> KnowledgeBase:
    row = await session.get(KnowledgeBase, knowledge_base_id)
    if row is None or row.tenant_id != tenant_id or row.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found.",
        )
    return row


async def _get_accessible_base_db(
    session: AsyncSession,
    knowledge_base_id: UUID,
    principal: Principal,
    *,
    require_write: bool,
) -> KnowledgeBase:
    row = await _get_base_for_tenant_db(session, knowledge_base_id, principal.tenant_id)
    await _assert_can_access_base(session, row, principal, require_write=require_write)
    return row


async def _assert_can_access_base(
    session: AsyncSession,
    base: KnowledgeBase,
    principal: Principal,
    *,
    require_write: bool,
) -> None:
    department_ids = await _principal_department_ids(session, principal)
    allowed = (
        _can_write_base(base, principal, department_ids)
        if require_write
        else _can_access_base(base, principal, department_ids)
    )
    if allowed:
        return
    action = "write" if require_write else "read"
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Knowledge base {action} access denied by visibility policy.",
    )


async def _principal_department_ids(
    session: AsyncSession,
    principal: Principal,
) -> set[UUID]:
    if _is_tenant_admin(principal):
        return set()
    result = await session.execute(
        select(UserDepartment.department_id)
        .join(
            Department,
            cast(ColumnElement[bool], Department.id == UserDepartment.department_id),
        )
        .where(
            cast(ColumnElement[bool], UserDepartment.user_id == principal.user_id),
            cast(ColumnElement[bool], Department.tenant_id == principal.tenant_id),
        )
    )
    return {UUID(str(value)) for value in result.scalars().all()}


def _can_access_base(
    base: KnowledgeBase,
    principal: Principal,
    principal_department_ids: set[UUID],
) -> bool:
    if _is_tenant_admin(principal):
        return True
    if str(principal.user_id) in _metadata_uuid_strings(base.metadata_json, "read_user_ids"):
        return True
    if str(principal.user_id) in _metadata_uuid_strings(base.metadata_json, "write_user_ids"):
        return True
    if base.visibility == KnowledgeBaseVisibility.TENANT.value:
        return True
    if base.visibility == KnowledgeBaseVisibility.PRIVATE.value:
        return str(base.metadata_json.get("owner_user_id")) == str(principal.user_id)
    if base.visibility == KnowledgeBaseVisibility.DEPARTMENT.value:
        allowed = {UUID(str(value)) for value in base.department_ids}
        return bool(allowed.intersection(principal_department_ids))
    return False


def _can_write_base(
    base: KnowledgeBase,
    principal: Principal,
    principal_department_ids: set[UUID],
) -> bool:
    if _is_tenant_admin(principal):
        return True
    if str(base.metadata_json.get("owner_user_id")) == str(principal.user_id):
        return True
    if str(principal.user_id) in _metadata_uuid_strings(base.metadata_json, "write_user_ids"):
        return True
    if base.visibility == KnowledgeBaseVisibility.DEPARTMENT.value:
        allowed = {UUID(str(value)) for value in base.department_ids}
        return bool(allowed.intersection(principal_department_ids)) and bool(
            base.metadata_json.get("department_members_can_write", False)
        )
    return False


def _metadata_uuid_strings(metadata: dict[str, Any], key: str) -> set[str]:
    raw = metadata.get(key)
    if not isinstance(raw, list):
        return set()
    return {str(value) for value in raw if value}


def _is_tenant_admin(principal: Principal) -> bool:
    return "tenant.admin" in principal.permissions


def _require_knowledge_permission(principal: Principal, permission: str) -> None:
    if _is_tenant_admin(principal) or permission in principal.permissions:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Permission required: {permission}",
    )


async def _validate_knowledge_department_ids(
    session: AsyncSession,
    department_ids: list[UUID],
    principal: Principal,
) -> list[UUID]:
    if not department_ids:
        return []
    unique_ids = list(dict.fromkeys(department_ids))
    result = await session.execute(
        select(Department.id).where(
            cast(ColumnElement[bool], Department.tenant_id == principal.tenant_id),
            cast(Any, Department.id).in_(unique_ids),
        )
    )
    existing = {UUID(str(value)) for value in result.scalars().all()}
    missing = [department_id for department_id in unique_ids if department_id not in existing]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="department_ids contains departments outside the current tenant or not found.",
        )
    if not _is_tenant_admin(principal):
        principal_department_ids = await _principal_department_ids(session, principal)
        if not set(unique_ids).issubset(principal_department_ids):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Non-admin users can only bind knowledge bases to their own departments.",
            )
    return unique_ids


async def _get_document_for_tenant_db(
    session: AsyncSession,
    *,
    knowledge_base_id: UUID,
    document_id: UUID,
    tenant_id: UUID,
) -> KnowledgeDocument:
    row = await session.get(KnowledgeDocument, document_id)
    if (
        row is None
        or row.tenant_id != tenant_id
        or row.knowledge_base_id != knowledge_base_id
        or row.deleted_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge document not found.",
        )
    return row


async def _count_documents_for_base(
    session: AsyncSession,
    knowledge_base_id: UUID,
    *,
    tenant_id: UUID,
) -> int:
    result = await session.execute(
        select(func.count(cast(Any, KnowledgeDocument.id))).where(
            cast(ColumnElement[bool], KnowledgeDocument.tenant_id == tenant_id),
            cast(ColumnElement[bool], KnowledgeDocument.knowledge_base_id == knowledge_base_id),
            cast(Any, KnowledgeDocument.deleted_at).is_(None),
            cast(
                ColumnElement[bool],
                KnowledgeDocument.status != KnowledgeDocumentStatus.DELETED.value,
            ),
        )
    )
    return int(result.scalar_one())


async def _mark_document_failed(
    session: AsyncSession,
    *,
    knowledge_base_id: UUID,
    document_id: UUID,
    tenant_id: UUID,
    message: str,
    metadata: dict[str, Any],
    principal: Principal,
) -> None:
    try:
        row = await _get_document_for_tenant_db(
            session,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            tenant_id=tenant_id,
        )
        row.status = KnowledgeDocumentStatus.FAILED.value
        row.error_message = message
        row.metadata_json = {**row.metadata_json, **metadata}
        row.updated_at = _utcnow()
        await session.commit()
    except (OSError, SQLAlchemyError, HTTPException):
        await _rollback_quietly(session)
        if _can_use_memory_fallback(principal):
            _memory_mark_document_failed(
                knowledge_base_id, document_id, tenant_id, message, metadata
            )


def _base_to_response(row: KnowledgeBase) -> KnowledgeBaseResponse:
    return KnowledgeBaseResponse(
        id=row.id,
        tenant_id=row.tenant_id,
        name=row.name,
        description=row.description,
        visibility=KnowledgeBaseVisibility(row.visibility),
        department_ids=[UUID(str(value)) for value in row.department_ids],
        rag_engine=cast(Any, row.rag_engine),
        embedding_model_key=row.embedding_model_key,
        retrieval_config=cast(Any, row.retrieval_config),
        status=KnowledgeBaseStatus(row.status),
        document_count=row.document_count,
        tags=list(row.tags),
        metadata=dict(row.metadata_json),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _document_to_response(row: KnowledgeDocument) -> KnowledgeDocumentResponse:
    return KnowledgeDocumentResponse(
        id=row.id,
        knowledge_base_id=row.knowledge_base_id,
        tenant_id=row.tenant_id,
        filename=row.filename,
        content_type=row.content_type,
        size_bytes=row.size_bytes,
        checksum_sha256=row.checksum_sha256,
        source=KnowledgeDocumentSource(row.source),
        status=KnowledgeDocumentStatus(row.status),
        storage_bucket=row.storage_bucket,
        storage_object_key=row.storage_object_key,
        rag_document_id=row.rag_document_id,
        chunk_count=row.chunk_count,
        error_message=row.error_message,
        metadata=dict(row.metadata_json),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _workbench_base_response(base: KnowledgeBaseResponse) -> WorkbenchKnowledgeBaseResponse:
    return WorkbenchKnowledgeBaseResponse(
        id=base.id,
        name=base.name,
        description=base.description,
        visibility=base.visibility,
        department_ids=base.department_ids,
        status=base.status,
        document_count=base.document_count,
        tags=base.tags,
        updated_at=base.updated_at,
    )


def _workbench_document_response(
    document: KnowledgeDocumentResponse,
) -> WorkbenchKnowledgeDocumentResponse:
    return WorkbenchKnowledgeDocumentResponse(
        id=document.id,
        knowledge_base_id=document.knowledge_base_id,
        filename=document.filename,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        source=document.source,
        status=document.status,
        chunk_count=document.chunk_count,
        updated_at=document.updated_at,
    )


def _decode_document_text(raw: bytes, content_type: str | None, filename: str) -> str:
    return document_processing.decode_document_text(raw, content_type, filename)


def _extract_pdf_text(raw: bytes) -> str:
    return document_processing.extract_pdf_text(raw)


def _extract_pdf_text_pypdf(raw: bytes) -> str:
    return document_processing.extract_pdf_text_pypdf(raw)


def _extract_pdf_text_fitz(raw: bytes) -> str:
    return document_processing.extract_pdf_text_fitz(raw)


def _extract_pdf_text_ocr(raw: bytes) -> str:
    return document_processing.extract_pdf_text_ocr(raw)


def _extract_docx_text(raw: bytes) -> str:
    return document_processing.extract_docx_text(raw)


def _extract_xlsx_text(raw: bytes) -> str:
    return document_processing.extract_xlsx_text(raw)


def _chunk_text(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    return document_processing.chunk_text(text, chunk_size=chunk_size, overlap=overlap)


def _query_terms(query: str) -> list[str]:
    return document_processing.query_terms(query)


def _normalize_search_text(value: str) -> str:
    return document_processing.normalize_search_text(value)


def _score_chunk(search_text: str, query_terms: list[str], raw_query: str) -> float:
    return document_processing.score_chunk(search_text, query_terms, raw_query)


def _build_fts_text(value: str) -> str:
    return document_processing.build_fts_text(value)


def _build_fts_query(query: str) -> str:
    return document_processing.build_fts_query(query)


async def _retrieve_fts_chunks(
    session: AsyncSession,
    request: RetrieveRequest,
) -> list[dict[str, Any]]:
    """Full-text search via PostgreSQL tsvector + GIN index."""
    fts_query = _build_fts_query(request.query)
    if not fts_query:
        return []
    result = await session.execute(
        text(
            """
            SELECT
                id::text AS chunk_id,
                document_id, text, source_name, metadata_json,
                chunk_index, token_count,
                ts_rank(fts_tsvector, to_tsquery('simple', :fts_query)) AS score
            FROM knowledge_chunks
            WHERE tenant_id = :tenant_id
              AND knowledge_base_id = :knowledge_base_id
              AND fts_tsvector @@ to_tsquery('simple', :fts_query)
            ORDER BY score DESC
            LIMIT :limit
            """
        ),
        {
            "tenant_id": request.tenant_id,
            "knowledge_base_id": request.knowledge_base_id,
            "fts_query": fts_query,
            "limit": max(request.top_k * 5, request.top_k),
        },
    )
    return [dict(row) for row in result.mappings().all()]


def _rrf_fuse(
    vector_chunks: list[RAGChunk],
    fts_rows: list[dict[str, Any]],
    *,
    k: int = 60,
    top_k: int,
) -> list[RAGChunk]:
    return retrieval_postprocessing.rrf_fuse(vector_chunks, fts_rows, k=k, top_k=top_k)


async def _rerank_chunks(
    chunks: list[RAGChunk],
    query: str,
) -> list[RAGChunk]:
    """Call the BGE-Reranker service to re-score query-chunk pairs."""
    if not settings.rag_reranker_enabled or not settings.rag_reranker_api_url:
        return chunks
    if not chunks:
        return chunks
    import httpx

    try:
        async with httpx.AsyncClient(
            timeout=settings.rag_reranker_request_timeout_seconds
        ) as client:
            response = await client.post(
                f"{settings.rag_reranker_api_url.rstrip('/')}/rerank",
                json={
                    "query": query,
                    "texts": [chunk.text for chunk in chunks],
                },
            )
            response.raise_for_status()
            data = response.json()
    except Exception:
        return chunks  # fail open — return original order if reranker is unavailable

    reranked: list[RAGChunk] = []
    for item in data.get("results", []):
        idx = int(item.get("index", -1))
        if 0 <= idx < len(chunks):
            chunk = chunks[idx]
            rerank_score = round(float(item["score"]), 4)
            chunk.metadata["rerank_score"] = rerank_score
            chunk.score = rerank_score
            reranked.append(chunk)
    return reranked if reranked else chunks


class _ChunkFilterProxy:
    def __init__(self, *, document_id: UUID, source_name: str | None) -> None:
        self.document_id = document_id
        self.source_name = source_name


def _chunk_matches_filters(
    chunk: KnowledgeChunk | _ChunkFilterProxy, filters: dict[str, Any]
) -> bool:
    return retrieval_postprocessing.chunk_matches_filters(
        document_id=chunk.document_id,
        source_name=chunk.source_name,
        filters=filters,
    )


def _rough_token_count(text: str) -> int:
    return document_processing.rough_token_count(text)


def _can_use_memory_fallback(principal: Principal) -> bool:
    return is_development_environment() or principal.is_development_fallback


async def _rollback_quietly(session: AsyncSession) -> None:
    try:
        await session.rollback()
    except Exception:
        return


def _storage_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Knowledge metadata storage is unavailable.",
    )
