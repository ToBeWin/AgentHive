import base64
import unittest
from uuid import uuid4

import httpx

from app.core.config import settings
from app.models.media import MediaGenerationJob
from app.rag.schemas import StoredObjectRef
from app.services.media_output_archive_service import MediaOutputArchiveError, archive_media_outputs


class MediaOutputArchiveServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.original_bucket = settings.media_output_bucket
        self.original_max_bytes = settings.media_output_download_max_bytes
        settings.media_output_bucket = "agenthive-media-test"
        settings.media_output_download_max_bytes = 1024

    async def asyncTearDown(self) -> None:
        settings.media_output_bucket = self.original_bucket
        settings.media_output_download_max_bytes = self.original_max_bytes

    async def test_url_output_is_downloaded_and_written_to_private_storage(self):
        storage = FakeStorage()
        job = _job(kind="image")

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual("https://cdn.example.com/result.png", str(request.url))
            return httpx.Response(
                200, content=b"image-bytes", headers={"content-type": "image/png"}
            )

        outputs, metadata = await archive_media_outputs(
            job,
            [{"url": "https://cdn.example.com/result.png", "mime_type": "image/png"}],
            storage=storage,
            client_factory=_client_factory(handler),
            url_resolver=_resolver("93.184.216.34"),
        )

        self.assertEqual(1, metadata["archived_count"])
        self.assertEqual("agenthive-media-test", outputs[0]["bucket"])
        self.assertTrue(
            str(outputs[0]["object_key"]).startswith(
                f"generated/image/tenants/{job.tenant_id}/jobs/{job.id}/"
            )
        )
        self.assertTrue(str(outputs[0]["object_key"]).endswith(".png"))
        self.assertEqual("https://cdn.example.com/result.png", outputs[0]["original_url"])
        self.assertIsNone(outputs[0]["url"])
        self.assertEqual(b"image-bytes", storage.objects[0][1])

    async def test_b64_output_is_decoded_and_not_persisted_as_inline_json(self):
        storage = FakeStorage()
        raw = b"png-bytes"

        outputs, metadata = await archive_media_outputs(
            _job(kind="image"),
            [{"b64_json": base64.b64encode(raw).decode(), "mime_type": "image/png"}],
            storage=storage,
        )

        self.assertEqual(1, metadata["archived_count"])
        self.assertNotIn("b64_json", outputs[0])
        self.assertEqual(raw, storage.objects[0][1])
        self.assertEqual("provider_b64_json", outputs[0]["archive_source"])

    async def test_private_object_output_is_not_reuploaded(self):
        storage = FakeStorage()
        job = _job(kind="video")
        object_key = f"generated/video/tenants/{job.tenant_id}/jobs/{job.id}/result.mp4"

        outputs, metadata = await archive_media_outputs(
            job,
            [{"bucket": "agenthive-media-test", "object_key": object_key}],
            storage=storage,
        )

        self.assertEqual(0, metadata["archived_count"])
        self.assertEqual(1, metadata["skipped_count"])
        self.assertEqual([], storage.objects)
        self.assertEqual(object_key, outputs[0]["object_key"])

    async def test_legacy_archived_output_with_owner_metadata_remains_compatible(self):
        job = _job(kind="video")
        object_key = f"generated/video/{job.id}/result.mp4"

        outputs, metadata = await archive_media_outputs(
            job,
            [
                {
                    "bucket": "agenthive-media-test",
                    "object_key": object_key,
                    "storage_metadata": {
                        "tenant_id": str(job.tenant_id),
                        "agenthive_job_id": str(job.id),
                    },
                }
            ],
            storage=FakeStorage(),
        )

        self.assertEqual(1, metadata["skipped_count"])
        self.assertEqual(object_key, outputs[0]["object_key"])

    async def test_legacy_private_object_without_owner_metadata_is_rejected(self):
        job = _job(kind="video")

        with self.assertRaises(MediaOutputArchiveError) as error:
            await archive_media_outputs(
                job,
                [
                    {
                        "bucket": "agenthive-media-test",
                        "object_key": f"generated/video/{job.id}/result.mp4",
                    }
                ],
                storage=FakeStorage(),
            )

        self.assertIn("requires tenant and job ownership metadata", str(error.exception))

    async def test_private_object_output_rejects_untrusted_bucket(self):
        job = _job(kind="video")
        object_key = f"generated/video/tenants/{job.tenant_id}/jobs/{job.id}/result.mp4"

        with self.assertRaises(MediaOutputArchiveError) as error:
            await archive_media_outputs(
                job,
                [{"bucket": "another-tenant-bucket", "object_key": object_key}],
                storage=FakeStorage(),
            )

        self.assertIn("bucket is not allowed", str(error.exception))

    async def test_private_object_output_rejects_foreign_tenant_prefix(self):
        job = _job(kind="video")
        object_key = f"generated/video/tenants/{uuid4()}/jobs/{job.id}/result.mp4"

        with self.assertRaises(MediaOutputArchiveError) as error:
            await archive_media_outputs(
                job,
                [{"bucket": "agenthive-media-test", "object_key": object_key}],
                storage=FakeStorage(),
            )

        self.assertIn("outside the job tenant storage prefix", str(error.exception))

    async def test_private_object_output_rejects_foreign_job_prefix(self):
        job = _job(kind="video")
        object_key = f"generated/video/tenants/{job.tenant_id}/jobs/{uuid4()}/result.mp4"

        with self.assertRaises(MediaOutputArchiveError) as error:
            await archive_media_outputs(
                job,
                [{"bucket": "agenthive-media-test", "object_key": object_key}],
                storage=FakeStorage(),
            )

        self.assertIn("outside the job tenant storage prefix", str(error.exception))

    async def test_download_size_limit_blocks_archival(self):
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"x" * 2048)

        with self.assertRaises(MediaOutputArchiveError) as error:
            await archive_media_outputs(
                _job(kind="video"),
                [{"url": "https://cdn.example.com/large.mp4"}],
                storage=FakeStorage(),
                client_factory=_client_factory(handler),
                url_resolver=_resolver("93.184.216.34"),
            )

        self.assertIn("size limit", str(error.exception))

    async def test_url_output_allows_public_redirect_chain(self):
        storage = FakeStorage()

        def handler(request: httpx.Request) -> httpx.Response:
            if str(request.url) == "https://cdn.example.com/start":
                return httpx.Response(
                    302, headers={"location": "https://assets.example.com/final.png"}
                )
            self.assertEqual("https://assets.example.com/final.png", str(request.url))
            return httpx.Response(
                200, content=b"redirected-image", headers={"content-type": "image/png"}
            )

        outputs, metadata = await archive_media_outputs(
            _job(kind="image"),
            [{"url": "https://cdn.example.com/start"}],
            storage=storage,
            client_factory=_client_factory(handler),
            url_resolver=_resolver("93.184.216.34"),
        )

        self.assertEqual(1, metadata["archived_count"])
        self.assertEqual(b"redirected-image", storage.objects[0][1])
        self.assertEqual("provider_url", outputs[0]["archive_source"])

    async def test_url_output_blocks_redirect_to_private_ip(self):
        storage = FakeStorage()

        def handler(request: httpx.Request) -> httpx.Response:
            if str(request.url) == "https://cdn.example.com/start":
                return httpx.Response(
                    302, headers={"location": "http://169.254.169.254/latest/meta-data"}
                )
            raise AssertionError(f"unexpected redirected request to {request.url}")

        with self.assertRaises(MediaOutputArchiveError) as error:
            await archive_media_outputs(
                _job(kind="video"),
                [{"url": "https://cdn.example.com/start"}],
                storage=storage,
                client_factory=_client_factory(handler),
                url_resolver=_resolver("93.184.216.34"),
            )

        self.assertIn("non-public address", str(error.exception))
        self.assertEqual([], storage.objects)

    async def test_url_output_blocks_localhost(self):
        storage = FakeStorage()

        with self.assertRaises(MediaOutputArchiveError) as error:
            await archive_media_outputs(
                _job(kind="video"),
                [{"url": "http://localhost/result.mp4"}],
                storage=storage,
                client_factory=_client_factory(
                    lambda _request: httpx.Response(200, content=b"video")
                ),
                url_resolver=_resolver("127.0.0.1"),
            )

        self.assertIn("host is not allowed", str(error.exception))
        self.assertEqual([], storage.objects)

    async def test_url_output_blocks_private_ip_literal(self):
        storage = FakeStorage()

        with self.assertRaises(MediaOutputArchiveError) as error:
            await archive_media_outputs(
                _job(kind="video"),
                [{"url": "http://10.0.0.5/result.mp4"}],
                storage=storage,
                client_factory=_client_factory(
                    lambda _request: httpx.Response(200, content=b"video")
                ),
            )

        self.assertIn("non-public address", str(error.exception))
        self.assertEqual([], storage.objects)

    async def test_url_output_blocks_dns_resolution_to_private_ip(self):
        storage = FakeStorage()

        with self.assertRaises(MediaOutputArchiveError) as error:
            await archive_media_outputs(
                _job(kind="video"),
                [{"url": "https://cdn.example.com/result.mp4"}],
                storage=storage,
                client_factory=_client_factory(
                    lambda _request: httpx.Response(200, content=b"video")
                ),
                url_resolver=_resolver("192.168.1.10"),
            )

        self.assertIn("non-public address", str(error.exception))
        self.assertEqual([], storage.objects)

    async def test_url_output_blocks_unsupported_scheme(self):
        storage = FakeStorage()

        with self.assertRaises(MediaOutputArchiveError) as error:
            await archive_media_outputs(
                _job(kind="video"),
                [{"url": "file:///etc/passwd"}],
                storage=storage,
            )

        self.assertIn("scheme is not allowed", str(error.exception))
        self.assertEqual([], storage.objects)


class FakeStorage:
    def __init__(self):
        self.objects: list[tuple[StoredObjectRef, bytes]] = []

    async def put_object(self, storage: StoredObjectRef, data: bytes) -> StoredObjectRef:
        self.objects.append((storage, data))
        return storage.model_copy(
            update={"metadata": {**storage.metadata, "storage_backend": "fake"}}
        )


def _job(*, kind: str) -> MediaGenerationJob:
    return MediaGenerationJob(
        id=uuid4(),
        tenant_id=uuid4(),
        user_id=uuid4(),
        kind=kind,
        mode="manual_prompt",
        status="running",
        provider_key="openai" if kind == "image" else "volcengine",
        provider_type="openai_images" if kind == "image" else "volcengine_seedance",
        model_key="openai/gpt-image-2" if kind == "image" else "volcengine/seedance-2.0",
        routing_key="image-generation" if kind == "image" else "video-generation",
        prompt="test prompt",
        normalized_parameters={},
        output_storage={"driver": "minio", "prefix": f"generated/{kind}"},
        metadata_json={},
    )


def _client_factory(handler):
    transport = httpx.MockTransport(handler)

    def factory(**kwargs):
        return httpx.AsyncClient(transport=transport, **kwargs)

    return factory


def _resolver(*addresses: str):
    async def resolve(_host: str, _port: int):
        return list(addresses)

    return resolve


if __name__ == "__main__":
    unittest.main()
