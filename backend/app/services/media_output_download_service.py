from dataclasses import dataclass
from pathlib import PurePosixPath
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal
from app.models.media import MediaGenerationJob
from app.rag.minio import MinIOObjectStorageAdapter
from app.rag.schemas import StoredObjectRef
from app.services.audit_service import record_audit_event
from app.services.media_generation_service import _assert_media_generation_job_access
from app.services.media_output_archive_service import (
    MediaOutputArchiveError,
    validate_media_output_storage_reference,
)


@dataclass(frozen=True)
class MediaOutputDownload:
    data: bytes
    content_type: str
    filename: str
    size_bytes: int


async def download_media_generation_output(
    session: AsyncSession,
    principal: Principal,
    job_id: UUID,
    output_index: int,
    *,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    storage: MinIOObjectStorageAdapter | None = None,
) -> MediaOutputDownload:
    if output_index < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Output index must be >= 0."
        )
    job = await session.get(MediaGenerationJob, job_id)
    if job is None or job.tenant_id != principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Media generation job not found."
        )
    await _assert_media_generation_job_access(session, principal, job)
    if output_index >= len(job.outputs):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Media generation output not found."
        )
    output = job.outputs[output_index]
    try:
        bucket, object_key = validate_media_output_storage_reference(job, output)
    except MediaOutputArchiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    content_type = _string_value(output.get("mime_type")) or "application/octet-stream"
    storage_ref = StoredObjectRef(
        bucket=bucket,
        object_key=object_key,
        content_type=content_type,
        size_bytes=_int_value(output.get("size_bytes")),
        checksum_sha256=_string_value(output.get("checksum_sha256")),
        metadata=_dict_value(output.get("storage_metadata")),
    )
    try:
        data = await (storage or MinIOObjectStorageAdapter()).get_object(storage_ref)
    except Exception as exc:
        await record_audit_event(
            session,
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            request_id=request_id,
            action="media.output.download",
            status="failure",
            resource_type="media_generation_job",
            resource_id=job.id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "output_index": output_index,
                "bucket": bucket,
                "object_key": object_key,
                "content_type": content_type,
                "error_type": exc.__class__.__name__,
            },
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Media output storage read failed: {exc}",
        ) from exc
    await record_audit_event(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        request_id=request_id,
        action="media.output.download",
        resource_type="media_generation_job",
        resource_id=job.id,
        ip_address=ip_address,
        user_agent=user_agent,
        details={
            "output_index": output_index,
            "bucket": bucket,
            "object_key": object_key,
            "content_type": content_type,
            "size_bytes": len(data),
        },
    )
    await session.commit()
    return MediaOutputDownload(
        data=data,
        content_type=content_type,
        filename=_download_filename(job, output_index, object_key, content_type),
        size_bytes=len(data),
    )


def _download_filename(
    job: MediaGenerationJob, output_index: int, object_key: str, content_type: str
) -> str:
    name = PurePosixPath(object_key).name or f"agenthive-media-output-{output_index + 1}"
    if "." not in name:
        suffix = _suffix_for_content_type(content_type)
        name = f"{name}{suffix}"
    return f"agenthive-{job.kind}-{job.id}-{output_index + 1}-{_sanitize_filename(name)}"


def _suffix_for_content_type(content_type: str) -> str:
    normalized = content_type.split(";", 1)[0].strip().lower()
    if normalized == "image/png":
        return ".png"
    if normalized in {"image/jpeg", "image/jpg"}:
        return ".jpg"
    if normalized == "image/webp":
        return ".webp"
    if normalized == "video/mp4":
        return ".mp4"
    if normalized == "video/webm":
        return ".webm"
    return ".bin"


def _sanitize_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_", "."} else "-" for char in value)[
        :180
    ]


def _string_value(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _int_value(value: object) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def _dict_value(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}
