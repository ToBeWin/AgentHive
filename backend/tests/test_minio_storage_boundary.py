import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.config import settings
from app.rag.minio import MinIOObjectStorageAdapter
from app.rag.schemas import StoredObjectRef


class MinIOStorageBoundaryTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.original_environment = settings.environment
        self.original_minio_endpoint = settings.minio_endpoint
        self.original_minio_access_key = settings.minio_access_key
        self.original_minio_secret_key = settings.minio_secret_key

    async def asyncTearDown(self) -> None:
        settings.environment = self.original_environment
        settings.minio_endpoint = self.original_minio_endpoint
        settings.minio_access_key = self.original_minio_access_key
        settings.minio_secret_key = self.original_minio_secret_key

    async def test_development_prepare_upload_can_return_placeholder_without_sdk(self) -> None:
        settings.environment = "development"
        adapter = MinIOObjectStorageAdapter()

        with patch("app.rag.minio._minio_sdk_available", return_value=False):
            plan = await adapter.prepare_upload(
                StoredObjectRef(bucket="agenthive", object_key="doc.txt", size_bytes=4)
            )

        self.assertTrue(plan.placeholder)
        self.assertEqual("agenthive", plan.storage.bucket)

    async def test_production_prepare_upload_requires_minio_sdk(self) -> None:
        settings.environment = "production"
        adapter = MinIOObjectStorageAdapter()

        with (
            patch("app.rag.minio._minio_sdk_available", return_value=False),
            self.assertRaises(RuntimeError) as raised,
        ):
            await adapter.prepare_upload(
                StoredObjectRef(bucket="agenthive", object_key="doc.txt", size_bytes=4)
            )

        self.assertIn("MinIO SDK is required", str(raised.exception))

    async def test_prod_alias_prepare_upload_requires_minio_sdk(self) -> None:
        settings.environment = "prod"
        adapter = MinIOObjectStorageAdapter()

        with (
            patch("app.rag.minio._minio_sdk_available", return_value=False),
            self.assertRaises(RuntimeError) as raised,
        ):
            await adapter.prepare_upload(
                StoredObjectRef(bucket="agenthive", object_key="doc.txt", size_bytes=4)
            )

        self.assertIn("MinIO SDK is required", str(raised.exception))

    async def test_development_environment_match_is_case_insensitive(self) -> None:
        settings.environment = "Development"
        adapter = MinIOObjectStorageAdapter()

        with patch("app.rag.minio._minio_sdk_available", return_value=False):
            plan = await adapter.prepare_upload(
                StoredObjectRef(bucket="agenthive", object_key="doc.txt", size_bytes=4)
            )

        self.assertTrue(plan.placeholder)

    async def test_production_prepare_upload_requires_minio_configuration(self) -> None:
        settings.environment = "production"
        settings.minio_endpoint = ""
        adapter = MinIOObjectStorageAdapter()

        with self.assertRaises(RuntimeError) as raised:
            await adapter.prepare_upload(
                StoredObjectRef(bucket="agenthive", object_key="doc.txt", size_bytes=4)
            )

        self.assertIn("MinIO settings are required", str(raised.exception))

    async def test_development_can_read_local_fallback_path(self) -> None:
        settings.environment = "development"
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = Path(temp_dir) / "doc.txt"
            local_path.write_bytes(b"fallback-content")
            adapter = MinIOObjectStorageAdapter()

            data = await adapter.get_object(
                StoredObjectRef(
                    bucket="agenthive",
                    object_key="doc.txt",
                    metadata={"local_path": str(local_path)},
                )
            )

        self.assertEqual(b"fallback-content", data)

    async def test_production_ignores_local_fallback_path(self) -> None:
        settings.environment = "production"
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = Path(temp_dir) / "doc.txt"
            local_path.write_bytes(b"must-not-read")
            adapter = MinIOObjectStorageAdapter()

            with (
                patch(
                    "app.rag.minio._get_object_from_minio", side_effect=RuntimeError("minio down")
                ),
                self.assertRaises(RuntimeError) as raised,
            ):
                await adapter.get_object(
                    StoredObjectRef(
                        bucket="agenthive",
                        object_key="doc.txt",
                        metadata={"local_path": str(local_path)},
                    )
                )

        self.assertIn("Object storage read failed", str(raised.exception))

    async def test_production_upload_failure_does_not_write_local_fallback(self) -> None:
        settings.environment = "production"
        adapter = MinIOObjectStorageAdapter()

        with (
            patch("app.rag.minio._put_object_to_minio", side_effect=RuntimeError("minio down")),
            patch("app.rag.minio._put_object_to_local_fallback") as fallback,
            self.assertRaises(RuntimeError) as raised,
        ):
            await adapter.put_object(
                StoredObjectRef(bucket="agenthive", object_key="doc.txt", size_bytes=4),
                b"data",
            )

        fallback.assert_not_called()
        self.assertIn("MinIO upload failed", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
