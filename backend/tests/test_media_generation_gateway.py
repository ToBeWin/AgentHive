import unittest
from uuid import uuid4

from pydantic import ValidationError

from app.api.deps import Principal
from app.media.gateway import build_media_generation_plan, list_media_model_capabilities
from app.media.schemas import (
    MediaAssetKind,
    MediaAssetRef,
    MediaGenerationKind,
    MediaGenerationMode,
    MediaGenerationRequest,
    MediaProviderType,
)


class MediaGenerationGatewayTests(unittest.TestCase):
    def test_catalog_exposes_configurable_image_and_video_routes(self) -> None:
        models = list_media_model_capabilities()
        image_models = {
            model.model_key for model in models if model.kind == MediaGenerationKind.IMAGE
        }
        video_models = {
            model.model_key for model in models if model.kind == MediaGenerationKind.VIDEO
        }

        self.assertIn("openai/gpt-image-2", image_models)
        self.assertIn("google/nano-banana", image_models)
        self.assertIn("volcengine/seedance-2.0", video_models)
        self.assertIn("openai-compatible-video", video_models)

    def test_catalog_marks_models_active_when_provider_is_configured(self) -> None:
        models = list_media_model_capabilities(
            provider_statuses={
                MediaProviderType.NANO_BANANA: True,
                MediaProviderType.VOLCENGINE_SEEDANCE: False,
            },
            provider_diagnostics={
                MediaProviderType.OPENAI_IMAGES: ["OPENAI_IMAGES_API_KEY"],
                MediaProviderType.NANO_BANANA: [],
                MediaProviderType.VOLCENGINE_SEEDANCE: ["VOLCENGINE_SEEDANCE_API_KEY"],
                MediaProviderType.OPENAI_COMPATIBLE_MEDIA: ["MEDIA_OPENAI_COMPATIBLE_BASE_URL"],
                MediaProviderType.CUSTOM: ["custom_media_provider_adapter"],
            },
        )
        model_by_key = {model.model_key: model for model in models}

        self.assertEqual("active", model_by_key["google/nano-banana"].status)
        self.assertEqual([], model_by_key["google/nano-banana"].configuration_issues)
        self.assertEqual("not_configured", model_by_key["volcengine/seedance-2.0"].status)
        self.assertEqual(
            ["VOLCENGINE_SEEDANCE_API_KEY"],
            model_by_key["volcengine/seedance-2.0"].configuration_issues,
        )
        self.assertIn(
            "VOLCENGINE_SEEDANCE_API_KEY",
            model_by_key["volcengine/seedance-2.0"].configuration_hint or "",
        )

    def test_image_generation_plan_uses_minio_storage_contract(self) -> None:
        principal = Principal(tenant_id=uuid4(), user_id=uuid4(), permissions={"agents:write"})
        request = MediaGenerationRequest(
            kind=MediaGenerationKind.IMAGE,
            mode=MediaGenerationMode.MANUAL_PROMPT,
            prompt="生成一张白底运动鞋商品主图",
            model_key="google/nano-banana",
            reference_assets=[
                MediaAssetRef(
                    kind=MediaAssetKind.IMAGE, bucket="agenthive-assets", object_key="ref/shoe.png"
                )
            ],
            image_count=2,
            aspect_ratio="1:1",
        )

        plan = build_media_generation_plan(request, principal, agent_key="image_generation")

        self.assertEqual("google/nano-banana", plan.model_key)
        self.assertEqual("minio", plan.output_storage["driver"])
        self.assertEqual("generated/image_generation", plan.output_storage["prefix"])
        self.assertEqual(2, plan.estimated_output_count)
        self.assertEqual("0.060000", str(plan.estimated_cost_usd))
        self.assertEqual("output", plan.pricing["unit"])
        self.assertEqual(1, plan.reference_asset_count)
        self.assertEqual({"image": 1}, plan.normalized_parameters["reference_assets"]["by_kind"])
        self.assertEqual({"minio": 1}, plan.normalized_parameters["reference_assets"]["locations"])
        self.assertEqual(
            "minio_bucket_object_key",
            plan.execution["reference_asset_policy"]["internal_assets"],
        )

    def test_reference_asset_url_accepts_public_https(self) -> None:
        asset = MediaAssetRef(
            kind=MediaAssetKind.IMAGE,
            url="https://cdn.example.com/products/ref-shoe.png",
            mime_type="image/png",
        )

        self.assertEqual("https://cdn.example.com/products/ref-shoe.png", asset.url)

    def test_reference_asset_url_rejects_unsafe_targets(self) -> None:
        for unsafe_url in (
            "file:///etc/passwd",
            "javascript:alert(1)",
            "https://user:pass@cdn.example.com/ref.png",
            "http://localhost/ref.png",
            "http://127.0.0.1/ref.png",
            "http://10.0.0.8/ref.png",
            "http://169.254.169.254/latest/meta-data",
            "https://minio.internal/ref.png",
        ):
            with self.subTest(unsafe_url=unsafe_url):
                with self.assertRaises(ValidationError):
                    MediaAssetRef(kind=MediaAssetKind.IMAGE, url=unsafe_url)

    def test_default_route_prefers_configured_provider_when_model_is_not_explicit(self) -> None:
        principal = Principal(tenant_id=uuid4(), user_id=uuid4(), permissions={"agents:write"})
        request = MediaGenerationRequest(
            kind=MediaGenerationKind.IMAGE,
            mode=MediaGenerationMode.MANUAL_PROMPT,
            prompt="生成一张商品图",
            routing_key="image-generation",
        )

        plan = build_media_generation_plan(
            request,
            principal,
            provider_statuses={
                MediaProviderType.OPENAI_IMAGES: False,
                MediaProviderType.NANO_BANANA: True,
                MediaProviderType.OPENAI_COMPATIBLE_MEDIA: False,
            },
        )

        self.assertEqual("google/nano-banana", plan.model_key)
        self.assertEqual(MediaProviderType.NANO_BANANA, plan.provider_type)

    def test_video_generation_defaults_to_seedance_and_fills_timing(self) -> None:
        principal = Principal(tenant_id=uuid4(), user_id=uuid4(), permissions={"agents:write"})
        request = MediaGenerationRequest(
            kind=MediaGenerationKind.VIDEO,
            mode=MediaGenerationMode.NATURAL_LANGUAGE,
            prompt="用参考图生成一条 5 秒的鞋子上脚短视频",
            routing_key="video-generation",
            reference_assets=[
                MediaAssetRef(
                    kind=MediaAssetKind.IMAGE, bucket="agenthive-assets", object_key="ref/shoe.png"
                )
            ],
            resolution="1080p",
        )

        plan = build_media_generation_plan(request, principal, agent_key="video_generation")

        self.assertEqual("volcengine/seedance-2.0", plan.model_key)
        self.assertEqual("async_job", plan.execution["mode"])
        self.assertEqual(5, plan.normalized_parameters["duration_seconds"])
        self.assertEqual(24, plan.normalized_parameters["fps"])
        self.assertEqual("0.400000", str(plan.estimated_cost_usd))
        self.assertEqual("second", plan.pricing["unit"])

    def test_natural_language_image_command_infers_commerce_parameters(self) -> None:
        principal = Principal(tenant_id=uuid4(), user_id=uuid4(), permissions={"agents:write"})
        request = MediaGenerationRequest(
            kind=MediaGenerationKind.IMAGE,
            mode=MediaGenerationMode.NATURAL_LANGUAGE,
            prompt="帮我生成4张 1:1 高清白底商品图，适合淘宝主图",
            model_key="google/nano-banana",
        )

        plan = build_media_generation_plan(request, principal, agent_key="image_generation")

        self.assertEqual(4, plan.normalized_parameters["image_count"])
        self.assertEqual("1:1", plan.normalized_parameters["aspect_ratio"])
        self.assertEqual("1080p", plan.normalized_parameters["resolution"])
        self.assertEqual(4, plan.estimated_output_count)
        self.assertEqual("0.120000", str(plan.estimated_cost_usd))
        self.assertEqual(
            ["aspect_ratio", "resolution", "image_count"],
            plan.normalized_parameters["command_interpretation"]["inferred_fields"],
        )

    def test_natural_language_video_command_infers_timing_and_resolution(self) -> None:
        principal = Principal(tenant_id=uuid4(), user_id=uuid4(), permissions={"agents:write"})
        request = MediaGenerationRequest(
            kind=MediaGenerationKind.VIDEO,
            mode=MediaGenerationMode.NATURAL_LANGUAGE,
            prompt="用参考图生成一个 16:9、8秒、30fps、1080p 的电商卖点短视频",
            routing_key="video-generation",
        )

        plan = build_media_generation_plan(request, principal, agent_key="video_generation")

        self.assertEqual("16:9", plan.normalized_parameters["aspect_ratio"])
        self.assertEqual("1080p", plan.normalized_parameters["resolution"])
        self.assertEqual(8.0, plan.normalized_parameters["duration_seconds"])
        self.assertEqual(30, plan.normalized_parameters["fps"])
        self.assertEqual("0.640000", str(plan.estimated_cost_usd))

    def test_explicit_media_parameters_override_natural_language_inference(self) -> None:
        principal = Principal(tenant_id=uuid4(), user_id=uuid4(), permissions={"agents:write"})
        request = MediaGenerationRequest(
            kind=MediaGenerationKind.IMAGE,
            mode=MediaGenerationMode.NATURAL_LANGUAGE,
            prompt="生成4张 1:1 高清商品图",
            model_key="google/nano-banana",
            image_count=2,
            aspect_ratio="3:4",
            resolution="2048x2048",
        )

        plan = build_media_generation_plan(request, principal, agent_key="image_generation")

        self.assertEqual(2, plan.normalized_parameters["image_count"])
        self.assertEqual("3:4", plan.normalized_parameters["aspect_ratio"])
        self.assertEqual("2048x2048", plan.normalized_parameters["resolution"])
        self.assertNotIn("command_interpretation", plan.normalized_parameters)

    def test_invalid_natural_language_fps_is_not_inferred(self) -> None:
        principal = Principal(tenant_id=uuid4(), user_id=uuid4(), permissions={"agents:write"})
        request = MediaGenerationRequest(
            kind=MediaGenerationKind.VIDEO,
            mode=MediaGenerationMode.NATURAL_LANGUAGE,
            prompt="生成一条5秒120fps的电商视频",
            routing_key="video-generation",
        )

        plan = build_media_generation_plan(request, principal, agent_key="video_generation")

        self.assertEqual(5.0, plan.normalized_parameters["duration_seconds"])
        self.assertEqual(24, plan.normalized_parameters["fps"])
        self.assertEqual(
            ["duration_seconds"],
            plan.normalized_parameters["command_interpretation"]["inferred_fields"],
        )

    def test_image_generation_rejects_video_timing_options(self) -> None:
        with self.assertRaises(ValidationError):
            MediaGenerationRequest(
                kind=MediaGenerationKind.IMAGE,
                prompt="生成商品图",
                duration_seconds=5,
            )

    def test_video_generation_rejects_multi_output_contract(self) -> None:
        with self.assertRaises(ValidationError):
            MediaGenerationRequest(
                kind=MediaGenerationKind.VIDEO,
                prompt="生成商品视频",
                image_count=2,
            )


if __name__ == "__main__":
    unittest.main()
