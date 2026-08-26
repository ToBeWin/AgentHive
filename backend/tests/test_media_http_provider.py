import json
import unittest
from uuid import uuid4

import httpx

from app.media.http_provider import HTTPMediaProviderAdapter
from app.media.providers import MediaProviderNotConfiguredError
from app.media.schemas import MediaGenerationJobStatus, MediaProviderType
from app.models.media import MediaGenerationJob


class HTTPMediaProviderAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_probe_calls_readonly_path_with_authorization(self):
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["url"] = str(request.url)
            captured["auth"] = request.headers.get("authorization")
            return httpx.Response(200, json={"data": []})

        adapter = HTTPMediaProviderAdapter(
            provider_type=MediaProviderType.OPENAI_COMPATIBLE_MEDIA,
            base_url="https://media.example.com/v1",
            api_key="media-key",
            client_factory=_client_factory(handler),
        )

        result = await adapter.probe(probe_path="/models")

        self.assertTrue(result.ok)
        self.assertEqual(200, result.status_code)
        self.assertTrue(result.metadata["live_network_call"])
        self.assertEqual("GET", captured["method"])
        self.assertEqual("https://media.example.com/v1/models", captured["url"])
        self.assertEqual("Bearer media-key", captured["auth"])

    async def test_probe_reports_http_failure_without_response_body(self):
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": {"message": "bad key"}})

        adapter = HTTPMediaProviderAdapter(
            provider_type=MediaProviderType.OPENAI_COMPATIBLE_MEDIA,
            base_url="https://media.example.com/v1",
            api_key="media-key",
            client_factory=_client_factory(handler),
        )

        result = await adapter.probe(probe_path="models")

        self.assertFalse(result.ok)
        self.assertEqual(401, result.status_code)
        self.assertEqual("/models", result.metadata["probe_path"])
        self.assertNotIn("bad key", result.message)

    async def test_unconfigured_provider_fails_closed(self):
        adapter = HTTPMediaProviderAdapter(
            provider_type=MediaProviderType.OPENAI_COMPATIBLE_MEDIA,
            base_url=None,
            api_key="",
        )

        with self.assertRaises(MediaProviderNotConfiguredError) as error:
            await adapter.submit(_job(kind="image"))

        self.assertFalse(error.exception.metadata["live_network_call"])
        self.assertEqual(["base_url", "api_key"], error.exception.metadata["missing"])

    async def test_image_generation_parses_openai_style_outputs(self):
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["auth"] = request.headers.get("authorization")
            captured["payload"] = json.loads(request.content.decode())
            return httpx.Response(
                200,
                json={
                    "id": "img-response-1",
                    "data": [
                        {
                            "url": "https://cdn.example.com/generated.png",
                            "revised_prompt": "clean product image",
                        }
                    ],
                },
            )

        adapter = HTTPMediaProviderAdapter(
            provider_type=MediaProviderType.OPENAI_COMPATIBLE_MEDIA,
            base_url="https://media.example.com/v1",
            api_key="media-key",
            client_factory=_client_factory(handler),
        )

        result = await adapter.submit(_job(kind="image"))

        self.assertEqual(MediaGenerationJobStatus.SUCCEEDED, result.status)
        self.assertEqual("https://cdn.example.com/generated.png", result.outputs[0]["url"])
        self.assertEqual("clean product image", result.outputs[0]["revised_prompt"])
        self.assertEqual("img-response-1", result.external_job_id)
        self.assertEqual("https://media.example.com/v1/images/generations", captured["url"])
        self.assertEqual("Bearer media-key", captured["auth"])
        payload = captured["payload"]
        self.assertIsInstance(payload, dict)
        self.assertEqual("openai-compatible-image", payload["model"])
        self.assertEqual("url", payload["response_format"])
        self.assertNotIn("callback_url", payload)

    async def test_video_generation_parses_async_submission(self):
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["payload"] = json.loads(request.content.decode())
            return httpx.Response(
                200,
                json={
                    "task_id": "video-task-1",
                    "status": "submitted",
                },
            )

        adapter = HTTPMediaProviderAdapter(
            provider_type=MediaProviderType.OPENAI_COMPATIBLE_MEDIA,
            base_url="https://media.example.com/v1",
            api_key="media-key",
            callback_url="https://agenthive.example.com/api/v1/media/webhooks/provider",
            webhook_secret="webhook-secret-0123456789",
            client_factory=_client_factory(handler),
        )

        result = await adapter.submit(_job(kind="video"))

        self.assertEqual(MediaGenerationJobStatus.RUNNING, result.status)
        self.assertEqual("video-task-1", result.external_job_id)
        self.assertEqual("submitted", result.metadata["provider_status"])
        payload = captured["payload"]
        self.assertIsInstance(payload, dict)
        self.assertEqual(
            "https://agenthive.example.com/api/v1/media/webhooks/provider", payload["callback_url"]
        )
        self.assertEqual(
            {"X-AgentHive-Media-Webhook-Secret": "webhook-secret-0123456789"},
            payload["webhook"]["headers"],
        )

    async def test_image_generation_parses_provider_url_aliases(self):
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "request_id": "nano-request-1",
                    "status": "success",
                    "images": [
                        {
                            "image_url": "https://cdn.example.com/nano-product.png",
                            "width": 1024,
                            "height": 1024,
                        }
                    ],
                },
            )

        adapter = HTTPMediaProviderAdapter(
            provider_type=MediaProviderType.NANO_BANANA,
            base_url="https://media.example.com/v1",
            api_key="media-key",
            client_factory=_client_factory(handler),
        )

        result = await adapter.submit(_job(kind="image"))

        self.assertEqual(MediaGenerationJobStatus.SUCCEEDED, result.status)
        self.assertEqual("nano-request-1", result.external_job_id)
        self.assertEqual("https://cdn.example.com/nano-product.png", result.outputs[0]["url"])
        self.assertEqual("image", result.outputs[0]["kind"])

    async def test_poll_video_generation_parses_nested_video_aliases(self):
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "task_id": "seedance-task-1",
                    "status": "done",
                    "result": {
                        "videos": [
                            {
                                "video_url": "https://cdn.example.com/seedance-product.mp4",
                                "duration": 6,
                            }
                        ]
                    },
                },
            )

        adapter = HTTPMediaProviderAdapter(
            provider_type=MediaProviderType.VOLCENGINE_SEEDANCE,
            base_url="https://media.example.com/v1",
            api_key="media-key",
            status_path="/tasks/{external_job_id}",
            client_factory=_client_factory(handler),
        )
        job = _job(kind="video")
        job.external_job_id = "seedance-task-1"

        result = await adapter.poll(job)

        self.assertEqual(MediaGenerationJobStatus.SUCCEEDED, result.status)
        self.assertEqual("https://cdn.example.com/seedance-product.mp4", result.outputs[0]["url"])
        self.assertEqual("video", result.outputs[0]["kind"])
        self.assertEqual(6, result.outputs[0]["duration_seconds"])

    async def test_poll_video_generation_status_parses_outputs(self):
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["url"] = str(request.url)
            captured["auth"] = request.headers.get("authorization")
            return httpx.Response(
                200,
                json={
                    "id": "video-task-1",
                    "status": "completed",
                    "outputs": [
                        {
                            "url": "https://cdn.example.com/generated.mp4",
                            "mime_type": "video/mp4",
                            "duration_seconds": 5,
                        }
                    ],
                },
            )

        adapter = HTTPMediaProviderAdapter(
            provider_type=MediaProviderType.OPENAI_COMPATIBLE_MEDIA,
            base_url="https://media.example.com/v1",
            api_key="media-key",
            status_path="/tasks/{external_job_id}",
            client_factory=_client_factory(handler),
        )
        job = _job(kind="video")
        job.external_job_id = "video-task-1"

        result = await adapter.poll(job)

        self.assertEqual(MediaGenerationJobStatus.SUCCEEDED, result.status)
        self.assertEqual("https://cdn.example.com/generated.mp4", result.outputs[0]["url"])
        self.assertEqual("GET", captured["method"])
        self.assertEqual("https://media.example.com/v1/tasks/video-task-1", captured["url"])
        self.assertEqual("Bearer media-key", captured["auth"])
        self.assertTrue(result.metadata["status_poll"])

    async def test_http_error_is_sanitized(self):
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"error": {"message": "rate limited"}})

        adapter = HTTPMediaProviderAdapter(
            provider_type=MediaProviderType.OPENAI_COMPATIBLE_MEDIA,
            base_url="https://media.example.com/v1",
            api_key="media-key",
            client_factory=_client_factory(handler),
        )

        with self.assertRaisesRegex(RuntimeError, "HTTP 429"):
            await adapter.submit(_job(kind="image"))


def _job(*, kind: str) -> MediaGenerationJob:
    return MediaGenerationJob(
        id=uuid4(),
        tenant_id=uuid4(),
        user_id=uuid4(),
        kind=kind,
        mode="manual_prompt",
        status="queued",
        provider_key="openai_compatible_media",
        provider_type="openai_compatible_media",
        model_key="openai-compatible-video" if kind == "video" else "openai-compatible-image",
        routing_key="private-video-generation" if kind == "video" else "private-image-generation",
        prompt="test prompt",
        reference_assets=[],
        normalized_parameters={
            "image_count": 1,
            "resolution": "1024x1024" if kind == "image" else "720p",
            "duration_seconds": 5 if kind == "video" else None,
            "fps": 24 if kind == "video" else None,
        },
        output_storage={"driver": "minio"},
        metadata_json={},
    )


def _client_factory(handler):
    transport = httpx.MockTransport(handler)

    def factory(**kwargs):
        return httpx.AsyncClient(transport=transport, **kwargs)

    return factory


if __name__ == "__main__":
    unittest.main()
