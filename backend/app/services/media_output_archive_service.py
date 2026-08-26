import asyncio
import base64
import binascii
import hashlib
import ipaddress
import mimetypes
from pathlib import PurePosixPath
from collections.abc import Awaitable, Callable, Sequence
import socket
from urllib.parse import urljoin, urlparse

import httpx

from app.core.config import settings
from app.models.media import MediaGenerationJob
from app.rag.minio import MinIOObjectStorageAdapter
from app.rag.schemas import StoredObjectRef

AsyncClientFactory = Callable[..., httpx.AsyncClient]
OutputUrlResolver = Callable[[str, int], Awaitable[Sequence[str]]]
MAX_MEDIA_OUTPUT_REDIRECTS = 5


class MediaOutputArchiveError(RuntimeError):
    pass


async def archive_media_outputs(
    job: MediaGenerationJob,
    outputs: list[dict[str, object]] | None,
    *,
    storage: MinIOObjectStorageAdapter | None = None,
    client_factory: AsyncClientFactory | None = None,
    url_resolver: OutputUrlResolver | None = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    if not outputs:
        return [], {"archived_count": 0, "skipped_count": 0}
    storage_adapter = storage or MinIOObjectStorageAdapter()
    archived_outputs: list[dict[str, object]] = []
    archived_count = 0
    skipped_count = 0
    for index, output in enumerate(outputs):
        if _has_private_object_ref_fields(output):
            validate_media_output_storage_reference(job, output)
            archived_outputs.append(dict(output))
            skipped_count += 1
            continue
        data, content_type, source = await _read_output_bytes(
            output,
            client_factory=client_factory,
            url_resolver=url_resolver,
        )
        checksum = hashlib.sha256(data).hexdigest()
        object_key = _object_key(
            job, output, index=index, checksum=checksum, content_type=content_type
        )
        storage_ref = StoredObjectRef(
            bucket=media_output_bucket(job),
            object_key=object_key,
            content_type=content_type,
            size_bytes=len(data),
            checksum_sha256=checksum,
            metadata={
                "agenthive_job_id": str(job.id),
                "tenant_id": str(job.tenant_id),
                "media_kind": job.kind,
                "provider_key": job.provider_key,
                "model_key": job.model_key,
                "source": source,
            },
        )
        try:
            stored = await storage_adapter.put_object(storage_ref, data)
        except Exception as exc:
            raise MediaOutputArchiveError(f"Media output archival failed: {exc}") from exc
        archived_outputs.append(_archived_output(output, stored, checksum=checksum, source=source))
        archived_count += 1
    return archived_outputs, {
        "archived_count": archived_count,
        "skipped_count": skipped_count,
        "bucket": media_output_bucket(job),
    }


async def _read_output_bytes(
    output: dict[str, object],
    *,
    client_factory: AsyncClientFactory | None,
    url_resolver: OutputUrlResolver | None,
) -> tuple[bytes, str, str]:
    b64_json = output.get("b64_json")
    if isinstance(b64_json, str) and b64_json:
        return (
            _decode_b64_json(b64_json),
            str(output.get("mime_type") or "image/png"),
            "provider_b64_json",
        )
    url = output.get("url")
    if isinstance(url, str) and url:
        data, content_type = await _download_output(
            url,
            client_factory=client_factory,
            url_resolver=url_resolver,
        )
        return (
            data,
            str(output.get("mime_type") or content_type or _guess_content_type(url)),
            "provider_url",
        )
    raise MediaOutputArchiveError("Media output has no private object reference, url, or b64_json.")


def _decode_b64_json(value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise MediaOutputArchiveError("Media output b64_json is invalid.") from exc


async def _download_output(
    url: str,
    *,
    client_factory: AsyncClientFactory | None,
    url_resolver: OutputUrlResolver | None,
) -> tuple[bytes, str | None]:
    factory = client_factory or httpx.AsyncClient
    current_url = url
    try:
        # Reject unsupported schemes and non-public destinations before an
        # HTTP client is constructed. Besides failing faster, this keeps
        # ambient proxy configuration from affecting validation-only calls.
        await _assert_output_url_allowed(current_url, url_resolver=url_resolver)
        async with factory(timeout=60.0, follow_redirects=False) as client:
            for _redirect_count in range(MAX_MEDIA_OUTPUT_REDIRECTS + 1):
                response = await client.get(current_url)
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise MediaOutputArchiveError(
                            "Media output redirect is missing a Location header."
                        )
                    current_url = urljoin(current_url, location)
                    await _assert_output_url_allowed(current_url, url_resolver=url_resolver)
                    continue
                break
            else:
                raise MediaOutputArchiveError("Media output URL exceeded redirect limit.")
            response.raise_for_status()
            data = response.content
    except httpx.HTTPError as exc:
        raise MediaOutputArchiveError(
            f"Media output download failed: {exc.__class__.__name__}."
        ) from exc
    if len(data) > settings.media_output_download_max_bytes:
        raise MediaOutputArchiveError("Media output exceeds configured download size limit.")
    return data, response.headers.get("content-type")


async def _assert_output_url_allowed(
    url: str,
    *,
    url_resolver: OutputUrlResolver | None,
) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise MediaOutputArchiveError("Media output URL scheme is not allowed.")
    if not parsed.hostname:
        raise MediaOutputArchiveError("Media output URL host is missing.")
    host = parsed.hostname.strip().rstrip(".")
    if not host:
        raise MediaOutputArchiveError("Media output URL host is missing.")
    if host.lower() == "localhost":
        raise MediaOutputArchiveError("Media output URL host is not allowed.")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        _assert_public_output_address(host)
        return
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    addresses = await (url_resolver or _resolve_output_url_host)(host, port)
    if not addresses:
        raise MediaOutputArchiveError("Media output URL host could not be resolved.")
    for address in addresses:
        _assert_public_output_address(address)


async def _resolve_output_url_host(host: str, port: int) -> Sequence[str]:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return [host]
    try:
        loop = asyncio.get_running_loop()
        records = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise MediaOutputArchiveError("Media output URL host could not be resolved.") from exc
    return [record[4][0] for record in records if record and record[4]]


def _assert_public_output_address(address: str) -> None:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError as exc:
        raise MediaOutputArchiveError("Media output URL resolved to an invalid address.") from exc
    if (
        parsed.is_private
        or parsed.is_loopback
        or parsed.is_link_local
        or parsed.is_multicast
        or parsed.is_reserved
        or parsed.is_unspecified
    ):
        raise MediaOutputArchiveError("Media output URL resolved to a non-public address.")


def _object_key(
    job: MediaGenerationJob,
    output: dict[str, object],
    *,
    index: int,
    checksum: str,
    content_type: str,
) -> str:
    extension = _extension(output, content_type)
    prefix = media_output_object_key_prefix(job)
    return f"{prefix}{index + 1}-{checksum[:16]}{extension}"


def _extension(output: dict[str, object], content_type: str) -> str:
    existing = output.get("filename") or output.get("object_key") or output.get("url")
    if isinstance(existing, str):
        parsed_path = urlparse(existing).path
        guessed = mimetypes.guess_type(parsed_path)[0]
        suffix = mimetypes.guess_extension(guessed or content_type)
        if suffix:
            return suffix
    return mimetypes.guess_extension(content_type.split(";")[0].strip()) or ".bin"


def media_output_object_key_prefix(job: MediaGenerationJob) -> str:
    """Return the only object-key namespace trusted for a media job."""
    prefix = _media_output_base_prefix(job)
    return f"{prefix}/tenants/{job.tenant_id}/jobs/{job.id}/"


def _media_output_base_prefix(job: MediaGenerationJob) -> str:
    configured_tenant_id = job.output_storage.get("tenant_id")
    if configured_tenant_id is not None and str(configured_tenant_id) != str(job.tenant_id):
        raise MediaOutputArchiveError(
            "Media output storage tenant does not match the media generation job."
        )
    raw_prefix = job.output_storage.get("prefix")
    if raw_prefix is None:
        raw_prefix = f"generated/{job.kind}"
    if not isinstance(raw_prefix, str):
        raise MediaOutputArchiveError("Media output storage prefix is invalid.")
    prefix = raw_prefix.strip("/")
    if not _is_safe_object_key_path(prefix) or prefix != raw_prefix:
        raise MediaOutputArchiveError("Media output storage prefix is invalid.")
    return prefix


def media_output_bucket(job: MediaGenerationJob) -> str:
    """Return the bucket configured by the trusted job plan."""
    bucket = job.output_storage.get("bucket")
    if bucket is None:
        bucket = settings.media_output_bucket
    if not isinstance(bucket, str) or not bucket or bucket != bucket.strip():
        raise MediaOutputArchiveError("Media output storage bucket is invalid.")
    if "/" in bucket or "\\" in bucket or _has_control_characters(bucket):
        raise MediaOutputArchiveError("Media output storage bucket is invalid.")
    return bucket


def validate_media_output_storage_reference(
    job: MediaGenerationJob, output: dict[str, object]
) -> tuple[str, str]:
    """Fail closed unless an object reference belongs to this tenant and job."""
    bucket = output.get("bucket")
    object_key = output.get("object_key")
    if not isinstance(bucket, str) or not isinstance(object_key, str):
        raise MediaOutputArchiveError(
            "Media output private storage reference requires bucket and object_key."
        )
    expected_bucket = media_output_bucket(job)
    if bucket != expected_bucket:
        raise MediaOutputArchiveError("Media output bucket is not allowed for this job.")
    expected_prefix = media_output_object_key_prefix(job)
    legacy_prefix = f"{_media_output_base_prefix(job)}/{job.id}/"
    requires_legacy_owner_metadata = False
    if object_key.startswith(expected_prefix):
        relative_key = object_key.removeprefix(expected_prefix)
    elif object_key.startswith(legacy_prefix):
        relative_key = object_key.removeprefix(legacy_prefix)
        requires_legacy_owner_metadata = True
    else:
        raise MediaOutputArchiveError(
            "Media output object key is outside the job tenant storage prefix."
        )
    if not _is_safe_object_key_path(relative_key):
        raise MediaOutputArchiveError("Media output object key is invalid.")
    _validate_storage_owner_metadata(
        job,
        output,
        required=requires_legacy_owner_metadata,
    )
    return bucket, object_key


def validate_media_output_storage_references(
    job: MediaGenerationJob, outputs: list[dict[str, object]]
) -> list[dict[str, object]]:
    validated: list[dict[str, object]] = []
    for output in outputs:
        validate_media_output_storage_reference(job, output)
        validated.append(dict(output))
    return validated


def _has_private_object_ref_fields(output: dict[str, object]) -> bool:
    return "bucket" in output or "object_key" in output


def _validate_storage_owner_metadata(
    job: MediaGenerationJob,
    output: dict[str, object],
    *,
    required: bool,
) -> None:
    metadata = output.get("storage_metadata")
    if metadata is None:
        if required:
            raise MediaOutputArchiveError(
                "Legacy media output reference requires tenant and job ownership metadata."
            )
        return
    if not isinstance(metadata, dict):
        raise MediaOutputArchiveError("Media output storage metadata is invalid.")
    tenant_id = metadata.get("tenant_id")
    if (required and tenant_id is None) or (
        tenant_id is not None and str(tenant_id) != str(job.tenant_id)
    ):
        raise MediaOutputArchiveError("Media output storage metadata tenant does not match.")
    has_job_id = False
    for key in ("agenthive_job_id", "job_id"):
        metadata_job_id = metadata.get(key)
        if metadata_job_id is not None:
            has_job_id = True
            if str(metadata_job_id) != str(job.id):
                raise MediaOutputArchiveError("Media output storage metadata job does not match.")
    if required and not has_job_id:
        raise MediaOutputArchiveError("Media output storage metadata job does not match.")


def _is_safe_object_key_path(value: str) -> bool:
    if not value or value != value.strip() or "\\" in value or _has_control_characters(value):
        return False
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return False
    return PurePosixPath(value).as_posix() == value


def _has_control_characters(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def _archived_output(
    original: dict[str, object],
    stored: StoredObjectRef,
    *,
    checksum: str,
    source: str,
) -> dict[str, object]:
    sanitized = {key: value for key, value in original.items() if key not in {"b64_json"}}
    return {
        **sanitized,
        "bucket": stored.bucket,
        "object_key": stored.object_key,
        "mime_type": stored.content_type,
        "size_bytes": stored.size_bytes,
        "checksum_sha256": checksum,
        "archived": True,
        "archive_source": source,
        "storage_metadata": dict(stored.metadata),
        "original_url": original.get("url") if isinstance(original.get("url"), str) else None,
        "url": None,
    }


def _guess_content_type(url: str) -> str:
    guessed, _encoding = mimetypes.guess_type(urlparse(url).path)
    return guessed or "application/octet-stream"
