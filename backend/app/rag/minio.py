from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path
from typing import Any, cast

from app.core.config import is_development_environment, settings
from app.rag.base import BaseObjectStorageAdapter
from app.rag.schemas import (
    ComponentStatus,
    HealthStatus,
    ObjectUploadPlan,
    StoredObjectRef,
)


class MinIOObjectStorageAdapter(BaseObjectStorageAdapter):
    """MinIO/S3-compatible object storage boundary."""

    adapter_name = "minio"

    async def prepare_upload(self, storage: StoredObjectRef) -> ObjectUploadPlan:
        configured = _minio_configured()
        sdk_available = _minio_sdk_available()
        if not configured and not _local_fallback_allowed():
            raise RuntimeError(
                "MinIO settings are required to prepare uploads outside development."
            )
        if not sdk_available and not _local_fallback_allowed():
            raise RuntimeError("MinIO SDK is required to prepare uploads outside development.")
        return ObjectUploadPlan(
            storage=storage,
            upload_url=None,
            headers={},
            placeholder=not configured or not sdk_available,
        )

    async def put_object(self, storage: StoredObjectRef, data: bytes) -> StoredObjectRef:
        if not data and storage.size_bytes not in {0, None}:
            raise ValueError("Object data is empty but storage size is non-zero.")

        try:
            stored = await asyncio.to_thread(_put_object_to_minio, storage, data)
            return stored
        except Exception as exc:
            if not _local_fallback_allowed():
                raise RuntimeError(f"MinIO upload failed: {exc}") from exc
            return await asyncio.to_thread(_put_object_to_local_fallback, storage, data, exc)

    async def get_object(self, storage: StoredObjectRef) -> bytes:
        local_path = storage.metadata.get("local_path")
        if isinstance(local_path, str) and _local_fallback_allowed():
            return await asyncio.to_thread(Path(local_path).read_bytes)
        try:
            return await asyncio.to_thread(_get_object_from_minio, storage)
        except Exception as exc:
            fallback_path = Path(
                settings.object_storage_fallback_path or ".agenthive/object-storage"
            )
            object_path = fallback_path / storage.bucket / storage.object_key
            if _local_fallback_allowed() and object_path.exists():
                return await asyncio.to_thread(object_path.read_bytes)
            raise RuntimeError(f"Object storage read failed: {exc}") from exc

    async def delete_object(self, storage: StoredObjectRef) -> bool:
        if _minio_sdk_available():
            try:
                await asyncio.to_thread(_delete_object_from_minio, storage)
                return True
            except Exception:
                if not _local_fallback_allowed():
                    raise
        local_path = storage.metadata.get("local_path")
        if isinstance(local_path, str) and _local_fallback_allowed():
            return await asyncio.to_thread(_delete_local_fallback_object, Path(local_path))
        return False

    async def health_check(self) -> HealthStatus:
        configured = _minio_configured()
        sdk_available = _minio_sdk_available()
        health_error: str | None = None
        reachable = False
        if configured and sdk_available:
            try:
                await asyncio.to_thread(_check_minio_reachable)
                reachable = True
            except Exception as exc:
                health_error = f"{exc.__class__.__name__}: {exc}"

        return HealthStatus(
            component="minio",
            status=ComponentStatus.NOT_CONFIGURED
            if not configured
            else ComponentStatus.HEALTHY
            if sdk_available and reachable
            else ComponentStatus.DEGRADED
            if is_development_environment()
            else ComponentStatus.ERROR,
            message=(
                "MinIO SDK, settings, and service reachability are healthy."
                if configured and sdk_available and reachable
                else f"MinIO is not reachable: {health_error}"
                if configured and sdk_available and health_error
                else "MinIO settings are present, but the MinIO SDK is unavailable."
                if configured
                else "MinIO settings are missing."
            ),
            details={
                "endpoint": settings.minio_endpoint,
                "secure": settings.minio_secure,
                "direct_backend_uploads": sdk_available,
                "presigned_uploads": False,
                "placeholder_adapter": not sdk_available,
                "local_fallback_allowed": _local_fallback_allowed(),
                "reachable": reachable,
                "health_error": health_error,
            },
        )


def _put_object_to_minio(storage: StoredObjectRef, data: bytes) -> StoredObjectRef:
    client = _minio_client()
    if not client.bucket_exists(storage.bucket):
        client.make_bucket(storage.bucket)
    metadata = {key: str(value) for key, value in storage.metadata.items()}
    client.put_object(
        bucket_name=storage.bucket,
        object_name=storage.object_key,
        data=BytesIO(data),
        length=len(data),
        content_type=storage.content_type or "application/octet-stream",
        metadata=metadata,
    )
    return storage.model_copy(
        update={
            "size_bytes": len(data),
            "metadata": {
                **storage.metadata,
                "storage_backend": "minio",
                "minio_endpoint": settings.minio_endpoint,
            },
        }
    )


def _delete_object_from_minio(storage: StoredObjectRef) -> None:
    _minio_client().remove_object(storage.bucket, storage.object_key)


def _get_object_from_minio(storage: StoredObjectRef) -> bytes:
    response = _minio_client().get_object(storage.bucket, storage.object_key)
    try:
        return cast(bytes, response.read())
    finally:
        response.close()
        response.release_conn()


def _check_minio_reachable() -> None:
    _minio_client().list_buckets()


def _put_object_to_local_fallback(
    storage: StoredObjectRef,
    data: bytes,
    cause: Exception,
) -> StoredObjectRef:
    base_path = Path(settings.object_storage_fallback_path or ".agenthive/object-storage")
    object_path = base_path / storage.bucket / storage.object_key
    object_path.parent.mkdir(parents=True, exist_ok=True)
    object_path.write_bytes(data)
    return storage.model_copy(
        update={
            "size_bytes": len(data),
            "metadata": {
                **storage.metadata,
                "storage_backend": "local-development-fallback",
                "local_path": str(object_path),
                "fallback_reason": f"{cause.__class__.__name__}: {cause}",
            },
        }
    )


def _delete_local_fallback_object(path: Path) -> bool:
    if not path.exists():
        return False
    path.unlink()
    return True


def _local_fallback_allowed() -> bool:
    return is_development_environment()


def _minio_configured() -> bool:
    return bool(settings.minio_endpoint and settings.minio_access_key and settings.minio_secret_key)


def _minio_client() -> Any:
    try:
        from minio import Minio
        import urllib3
    except ImportError as exc:
        raise RuntimeError("MinIO SDK is not installed.") from exc

    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
        http_client=urllib3.PoolManager(
            timeout=urllib3.Timeout(connect=1.5, read=3.0),
            retries=False,
        ),
    )


def _minio_sdk_available() -> bool:
    try:
        import minio  # noqa: F401
    except ImportError:
        return False
    return True
