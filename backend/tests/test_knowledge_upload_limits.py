from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.datastructures import Headers, UploadFile

from app.api.v1.knowledge import _read_upload_with_limit, _reject_oversized_upload
from app.core.config import settings


def _upload(data: bytes) -> UploadFile:
    return UploadFile(file=BytesIO(data), filename="document.txt", headers=Headers())


@pytest.mark.asyncio
async def test_read_upload_with_limit_accepts_document_at_limit() -> None:
    async def run_in_worker(function, *args):
        return function(*args)

    with patch(
        "app.api.v1.knowledge.asyncio.to_thread",
        new_callable=AsyncMock,
        side_effect=run_in_worker,
    ) as to_thread:
        assert await _read_upload_with_limit(_upload(b"1234"), 4) == b"1234"

    to_thread.assert_awaited_once()


@pytest.mark.asyncio
async def test_read_upload_with_limit_rejects_document_above_limit() -> None:
    with pytest.raises(HTTPException) as raised:
        await _read_upload_with_limit(_upload(b"12345"), 4)

    assert raised.value.status_code == 413


def test_declared_request_size_is_rejected_before_multipart_parsing() -> None:
    previous_limit = settings.knowledge_upload_max_bytes
    settings.knowledge_upload_max_bytes = 4
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/knowledge/bases/id/documents/upload",
            "headers": [(b"content-length", str(1024 * 1024 + 5).encode())],
        }
    )
    try:
        with pytest.raises(HTTPException) as raised:
            _reject_oversized_upload(request)
    finally:
        settings.knowledge_upload_max_bytes = previous_limit

    assert raised.value.status_code == 413
