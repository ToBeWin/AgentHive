import asyncio
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.api.deps import Principal, require_permission
from app.core.config import settings
from app.core.database import get_session
from app.core.security import Permission
from app.schemas.knowledge import (
    DocumentUploadCompleteRequest,
    DocumentUploadCompleteResponse,
    DocumentUploadPrepareRequest,
    DocumentUploadPrepareResponse,
    KnowledgeBaseCreateRequest,
    KnowledgeGovernanceTargetsResponse,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    KnowledgeDeleteResponse,
    KnowledgeDocumentListResponse,
    RetrievalTestRequest,
    RetrievalTestResponse,
    WorkbenchKnowledgeBaseListResponse,
    WorkbenchKnowledgeDocumentListResponse,
)
from app.services.knowledge_service import (
    complete_document_upload,
    create_knowledge_base,
    delete_knowledge_base,
    delete_knowledge_document,
    list_knowledge_governance_targets,
    list_knowledge_bases,
    list_knowledge_documents,
    list_workbench_knowledge_bases,
    list_workbench_knowledge_documents,
    prepare_document_upload,
    reingest_knowledge_document,
    run_retrieval_test,
    upload_document_file,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
_MULTIPART_OVERHEAD_ALLOWANCE_BYTES = 1024 * 1024


@router.get("/governance-targets", response_model=KnowledgeGovernanceTargetsResponse)
async def read_knowledge_governance_targets(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[
        Principal,
        Depends(require_permission(Permission.KNOWLEDGE_WRITE)),
    ],
) -> KnowledgeGovernanceTargetsResponse:
    return await list_knowledge_governance_targets(session, principal)


@router.get("/bases", response_model=KnowledgeBaseListResponse)
async def read_knowledge_bases(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[
        Principal,
        Depends(require_permission(Permission.KNOWLEDGE_WRITE)),
    ],
) -> KnowledgeBaseListResponse:
    return await list_knowledge_bases(session, principal)


@router.get("/workbench/bases", response_model=WorkbenchKnowledgeBaseListResponse)
async def read_workbench_knowledge_bases(
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[
        Principal,
        Depends(require_permission(Permission.KNOWLEDGE_READ)),
    ],
) -> WorkbenchKnowledgeBaseListResponse:
    return await list_workbench_knowledge_bases(session, principal)


@router.get(
    "/workbench/bases/{id}/documents", response_model=WorkbenchKnowledgeDocumentListResponse
)
async def read_workbench_documents(
    id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[
        Principal,
        Depends(require_permission(Permission.KNOWLEDGE_READ)),
    ],
) -> WorkbenchKnowledgeDocumentListResponse:
    return await list_workbench_knowledge_documents(session, id, principal)


@router.post("/bases", response_model=KnowledgeBaseResponse, status_code=201)
async def create_base(
    payload: KnowledgeBaseCreateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[
        Principal,
        Depends(require_permission(Permission.KNOWLEDGE_WRITE)),
    ],
) -> KnowledgeBaseResponse:
    return await create_knowledge_base(session, payload, principal)


@router.get("/bases/{id}/documents", response_model=KnowledgeDocumentListResponse)
async def read_documents(
    id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[
        Principal,
        Depends(require_permission(Permission.KNOWLEDGE_WRITE)),
    ],
) -> KnowledgeDocumentListResponse:
    return await list_knowledge_documents(session, id, principal)


@router.post(
    "/bases/{id}/documents",
    response_model=DocumentUploadPrepareResponse,
    status_code=202,
)
async def prepare_upload(
    id: UUID,
    payload: DocumentUploadPrepareRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[
        Principal,
        Depends(require_permission(Permission.KNOWLEDGE_WRITE)),
    ],
) -> DocumentUploadPrepareResponse:
    return await prepare_document_upload(session, id, payload, principal)


@router.post(
    "/bases/{id}/documents/upload",
    response_model=DocumentUploadCompleteResponse,
    status_code=201,
)
async def upload_document(
    id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[
        Principal,
        Depends(require_permission(Permission.KNOWLEDGE_WRITE)),
    ],
) -> DocumentUploadCompleteResponse:
    _reject_oversized_upload(request)
    try:
        form = await request.form()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Multipart uploads require python-multipart to be installed.",
        ) from exc

    file_item = form.get("file")
    if not isinstance(file_item, StarletteUploadFile):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Multipart field 'file' is required.",
        )

    auto_ingest = _parse_form_bool(form.get("auto_ingest"), default=True)
    parser_config = _parse_form_json_object(form.get("parser_config"), field_name="parser_config")
    metadata = _parse_form_json_object(form.get("metadata"), field_name="metadata")
    data = await _read_upload_with_limit(file_item, settings.knowledge_upload_max_bytes)
    return await upload_document_file(
        session,
        id,
        filename=file_item.filename or "document",
        content_type=file_item.content_type,
        data=data,
        auto_ingest=auto_ingest,
        parser_config=parser_config,
        metadata=metadata,
        principal=principal,
    )


def _reject_oversized_upload(request: Request) -> None:
    content_length = request.headers.get("content-length")
    if content_length is None:
        return
    try:
        declared_size = int(content_length)
    except ValueError:
        return
    request_limit = settings.knowledge_upload_max_bytes + _MULTIPART_OVERHEAD_ALLOWANCE_BYTES
    if declared_size > request_limit:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Knowledge document upload exceeds the configured size limit.",
        )


async def _read_upload_with_limit(file: StarletteUploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(min(1024 * 1024, max_bytes - total + 1)):
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Knowledge document upload exceeds the configured size limit.",
            )
        chunks.append(chunk)
    # Joining a maximum-sized multipart upload copies every byte. Keep that
    # memory-bound operation off the request event loop as well.
    return await asyncio.to_thread(b"".join, chunks)


@router.delete("/bases/{id}", response_model=KnowledgeDeleteResponse)
async def delete_base(
    id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[
        Principal,
        Depends(require_permission(Permission.KNOWLEDGE_WRITE)),
    ],
) -> KnowledgeDeleteResponse:
    return await delete_knowledge_base(
        session,
        id,
        principal,
        request_id=getattr(request.state, "request_id", None),
    )


@router.delete("/bases/{id}/documents/{document_id}", response_model=KnowledgeDeleteResponse)
async def delete_document(
    id: UUID,
    document_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[
        Principal,
        Depends(require_permission(Permission.KNOWLEDGE_WRITE)),
    ],
) -> KnowledgeDeleteResponse:
    return await delete_knowledge_document(
        session,
        id,
        document_id,
        principal,
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/bases/{id}/documents/{document_id}/reingest",
    response_model=DocumentUploadCompleteResponse,
)
async def reingest_document(
    id: UUID,
    document_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[
        Principal,
        Depends(require_permission(Permission.KNOWLEDGE_WRITE)),
    ],
) -> DocumentUploadCompleteResponse:
    return await reingest_knowledge_document(
        session,
        id,
        document_id,
        principal,
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/bases/{id}/documents/{document_id}/complete-upload",
    response_model=DocumentUploadCompleteResponse,
)
async def complete_upload(
    id: UUID,
    document_id: UUID,
    payload: DocumentUploadCompleteRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[
        Principal,
        Depends(require_permission(Permission.KNOWLEDGE_WRITE)),
    ],
) -> DocumentUploadCompleteResponse:
    return await complete_document_upload(session, id, document_id, payload, principal)


@router.post("/bases/{id}/retrieval-test", response_model=RetrievalTestResponse)
async def retrieval_test(
    id: UUID,
    payload: RetrievalTestRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[
        Principal,
        Depends(require_permission(Permission.KNOWLEDGE_WRITE)),
    ],
) -> RetrievalTestResponse:
    return await run_retrieval_test(session, id, payload, principal)


def _parse_form_bool(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="auto_ingest must be a boolean value.",
    )


def _parse_form_json_object(value: object, *, field_name: str) -> dict[str, object]:
    if value in {None, ""}:
        return {}
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{field_name} must be a JSON object.",
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{field_name} must be a JSON object.",
        )
    return parsed
