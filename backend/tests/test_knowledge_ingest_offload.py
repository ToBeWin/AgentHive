import asyncio
from hashlib import sha256
from threading import get_ident
from unittest.mock import patch

import pytest

from app.services.knowledge_service import (
    _parse_document_chunks,
    _parse_document_chunks_nonblocking,
    _sha256_hex,
    _sha256_hex_nonblocking,
)


@pytest.mark.asyncio
async def test_large_document_hash_runs_outside_event_loop_thread() -> None:
    event_loop_thread = get_ident()
    worker_threads: list[int] = []

    def tracked_hash(data: bytes) -> str:
        worker_threads.append(get_ident())
        return _sha256_hex(data)

    with patch(
        "app.services.knowledge_service._sha256_hex",
        side_effect=tracked_hash,
    ):
        checksum = await _sha256_hex_nonblocking(b"knowledge document")

    assert checksum == sha256(b"knowledge document").hexdigest()
    assert worker_threads
    assert worker_threads[0] != event_loop_thread


@pytest.mark.asyncio
async def test_document_parse_and_chunk_pipeline_runs_outside_event_loop_thread() -> None:
    event_loop_thread = get_ident()
    worker_threads: list[int] = []

    def tracked_parse(*args: object, **kwargs: object) -> list[tuple[str, int, str, str]]:
        worker_threads.append(get_ident())
        return _parse_document_chunks(*args, **kwargs)  # type: ignore[arg-type]

    with patch(
        "app.services.knowledge_service._parse_document_chunks",
        side_effect=tracked_parse,
    ):
        chunks = await _parse_document_chunks_nonblocking(
            b"Refund policy\n\nReturns are accepted within 30 days.",
            content_type="text/plain",
            filename="policy.txt",
            chunk_size=900,
            overlap=120,
        )

    assert chunks[0][0] == "Refund policy\n\nReturns are accepted within 30 days."
    assert chunks[0][1] > 0
    assert chunks[0][2] == "refund policy returns are accepted within 30 days"
    assert worker_threads
    assert worker_threads[0] != event_loop_thread


@pytest.mark.asyncio
async def test_slow_document_parser_does_not_block_event_loop_progress() -> None:
    parser_started = asyncio.Event()
    release_parser = asyncio.Event()
    event_loop = asyncio.get_running_loop()

    def slow_parse(*_args: object, **_kwargs: object) -> list[tuple[str, int, str, str]]:
        event_loop.call_soon_threadsafe(parser_started.set)
        release_parser_waiter = asyncio.run_coroutine_threadsafe(release_parser.wait(), event_loop)
        release_parser_waiter.result(timeout=1)
        return [("chunk", 1, "chunk", "chunk")]

    with patch(
        "app.services.knowledge_service._parse_document_chunks",
        side_effect=slow_parse,
    ):
        parse_task = asyncio.create_task(
            _parse_document_chunks_nonblocking(
                b"data",
                content_type="text/plain",
                filename="document.txt",
                chunk_size=900,
                overlap=120,
            )
        )
        await asyncio.wait_for(parser_started.wait(), timeout=0.5)

        event_loop_progress = asyncio.Event()
        event_loop.call_soon(event_loop_progress.set)
        await asyncio.wait_for(event_loop_progress.wait(), timeout=0.1)

        release_parser.set()
        assert await parse_task == [("chunk", 1, "chunk", "chunk")]
