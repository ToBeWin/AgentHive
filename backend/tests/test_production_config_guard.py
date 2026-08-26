import unittest

from app.core.config import (
    assert_production_config_safe,
    is_development_environment,
    is_production_environment,
    production_config_issues,
    settings,
)


def _strong_fixture(prefix: str) -> str:
    return f"{prefix}-" + ("x" * 48)


class ProductionConfigGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self._environment = settings.environment
        self._database_url = settings.database_url
        self._secret_key = settings.secret_key
        self._litellm_master_key = settings.litellm_master_key
        self._media_webhook_secret = settings.media_webhook_secret
        self._minio_secret_key = settings.minio_secret_key
        self._redis_url = settings.redis_url
        self._install_id_path = settings.install_id_path
        self._rate_limit_backend = settings.rate_limit_backend
        self._auth_cookie_enabled = settings.auth_cookie_enabled
        self._auth_cookie_secure = settings.auth_cookie_secure
        self._cors_origins = settings.cors_origins
        self._trusted_proxy_cidrs = settings.trusted_proxy_cidrs

    def tearDown(self) -> None:
        settings.environment = self._environment
        settings.database_url = self._database_url
        settings.secret_key = self._secret_key
        settings.litellm_master_key = self._litellm_master_key
        settings.media_webhook_secret = self._media_webhook_secret
        settings.minio_secret_key = self._minio_secret_key
        settings.redis_url = self._redis_url
        settings.install_id_path = self._install_id_path
        settings.rate_limit_backend = self._rate_limit_backend
        settings.auth_cookie_enabled = self._auth_cookie_enabled
        settings.auth_cookie_secure = self._auth_cookie_secure
        settings.cors_origins = self._cors_origins
        settings.trusted_proxy_cidrs = self._trusted_proxy_cidrs

    def test_development_environment_allows_default_local_values(self):
        settings.environment = "development"
        settings.database_url = "sqlite:///local-cache.db"
        settings.secret_key = "agenthive-development-secret-change-me-before-production"
        settings.litellm_master_key = ""
        settings.media_webhook_secret = ""
        settings.minio_secret_key = "agenthive_minio_password"
        settings.redis_url = "redis://localhost:6379/0"
        settings.install_id_path = None
        settings.rate_limit_backend = "memory"
        settings.auth_cookie_enabled = False
        settings.auth_cookie_secure = False

        self.assertEqual([], production_config_issues())
        assert_production_config_safe()

    def test_production_rejects_default_and_placeholder_secrets(self):
        settings.environment = "production"
        settings.database_url = (
            "postgresql+asyncpg://agenthive:strong-password@postgres:5432/agenthive"
        )
        settings.secret_key = "agenthive-development-secret-change-me-before-production"
        settings.litellm_master_key = "sk-change-me-litellm-master-key"
        settings.media_webhook_secret = "change-me-media-webhook-secret"
        settings.minio_secret_key = "agenthive_minio_password"
        settings.redis_url = "redis://:change-me-redis@redis:6379/0"
        settings.install_id_path = "/data/agenthive/install-identity.json"
        settings.rate_limit_backend = "redis"
        settings.auth_cookie_enabled = True
        settings.auth_cookie_secure = True

        issues = production_config_issues()

        self.assertGreaterEqual(len(issues), 4)
        self.assertTrue(any("SECRET_KEY" in issue for issue in issues))
        self.assertTrue(any("LITELLM_MASTER_KEY" in issue for issue in issues))
        self.assertTrue(any("MEDIA_WEBHOOK_SECRET" in issue for issue in issues))
        self.assertTrue(any("MINIO_SECRET_KEY" in issue for issue in issues))
        self.assertTrue(any("REDIS_PASSWORD" in issue for issue in issues))
        with self.assertRaisesRegex(RuntimeError, "production configuration is unsafe"):
            assert_production_config_safe()

    def test_production_accepts_strong_runtime_secrets(self):
        settings.environment = "production"
        settings.database_url = (
            "postgresql+asyncpg://agenthive:strong-password@postgres:5432/agenthive"
        )
        settings.secret_key = _strong_fixture("fixture-secret")
        settings.litellm_master_key = _strong_fixture("fixture-model")
        settings.media_webhook_secret = "media-webhook-0123456789abcdef"
        settings.minio_secret_key = "minio-0123456789abcdef"
        settings.redis_url = "redis://:redis-0123456789abcdef@redis:6379/0"
        settings.install_id_path = "/data/agenthive/install-identity.json"
        settings.rate_limit_backend = "redis"
        settings.auth_cookie_enabled = True
        settings.auth_cookie_secure = True

        self.assertEqual([], production_config_issues())
        assert_production_config_safe()

    def test_production_rejects_non_postgres_business_database(self):
        settings.environment = "production"
        settings.database_url = "sqlite:///agenthive.db"
        settings.secret_key = _strong_fixture("fixture-secret")
        settings.litellm_master_key = _strong_fixture("fixture-model")
        settings.media_webhook_secret = "media-webhook-0123456789abcdef"
        settings.minio_secret_key = "minio-0123456789abcdef"
        settings.redis_url = "redis://:redis-0123456789abcdef@redis:6379/0"
        settings.install_id_path = "/data/agenthive/install-identity.json"
        settings.rate_limit_backend = "redis"
        settings.auth_cookie_enabled = True
        settings.auth_cookie_secure = True

        issues = production_config_issues()

        self.assertTrue(any("DATABASE_URL" in issue for issue in issues))
        with self.assertRaisesRegex(RuntimeError, "DATABASE_URL must use PostgreSQL"):
            assert_production_config_safe()

    def test_production_requires_persistent_install_identity_path(self):
        settings.environment = "production"
        settings.database_url = (
            "postgresql+asyncpg://agenthive:strong-password@postgres:5432/agenthive"
        )
        settings.secret_key = _strong_fixture("fixture-secret")
        settings.litellm_master_key = _strong_fixture("fixture-model")
        settings.media_webhook_secret = "media-webhook-0123456789abcdef"
        settings.minio_secret_key = "minio-0123456789abcdef"
        settings.redis_url = "redis://:redis-0123456789abcdef@redis:6379/0"
        settings.install_id_path = None
        settings.rate_limit_backend = "redis"
        settings.auth_cookie_enabled = True
        settings.auth_cookie_secure = True

        issues = production_config_issues()

        self.assertTrue(any("INSTALL_ID_PATH is required" in issue for issue in issues))
        with self.assertRaisesRegex(RuntimeError, "INSTALL_ID_PATH is required"):
            assert_production_config_safe()

    def test_production_rejects_temporary_install_identity_path(self):
        settings.environment = "production"
        settings.database_url = (
            "postgresql+asyncpg://agenthive:strong-password@postgres:5432/agenthive"
        )
        settings.secret_key = _strong_fixture("fixture-secret")
        settings.litellm_master_key = _strong_fixture("fixture-model")
        settings.media_webhook_secret = "media-webhook-0123456789abcdef"
        settings.minio_secret_key = "minio-0123456789abcdef"
        settings.redis_url = "redis://:redis-0123456789abcdef@redis:6379/0"
        settings.install_id_path = "/tmp/agenthive/install-identity.json"
        settings.rate_limit_backend = "redis"
        settings.auth_cookie_enabled = True
        settings.auth_cookie_secure = True

        issues = production_config_issues()

        self.assertTrue(any("temporary directory" in issue for issue in issues))
        with self.assertRaisesRegex(RuntimeError, "temporary directory"):
            assert_production_config_safe()

    def test_environment_helpers_normalize_case_and_prod_alias(self):
        settings.environment = "Development"
        self.assertTrue(is_development_environment())
        self.assertFalse(is_production_environment())

        settings.environment = "prod"
        self.assertFalse(is_development_environment())
        self.assertTrue(is_production_environment())

    def test_production_requires_distributed_rate_limiting(self):
        settings.environment = "production"
        settings.database_url = (
            "postgresql+asyncpg://agenthive:strong-password@postgres:5432/agenthive"
        )
        settings.secret_key = _strong_fixture("fixture-secret")
        settings.litellm_master_key = _strong_fixture("fixture-model")
        settings.media_webhook_secret = "media-webhook-0123456789abcdef"
        settings.minio_secret_key = "minio-0123456789abcdef"
        settings.redis_url = "redis://:redis-0123456789abcdef@redis:6379/0"
        settings.install_id_path = "/data/agenthive/install-identity.json"
        settings.rate_limit_backend = "memory"
        settings.auth_cookie_enabled = True
        settings.auth_cookie_secure = True

        issues = production_config_issues()

        self.assertIn("RATE_LIMIT_BACKEND must use Redis in production", issues)

    def test_production_requires_secure_cookie_authentication(self):
        settings.environment = "production"
        settings.database_url = (
            "postgresql+asyncpg://agenthive:strong-password@postgres:5432/agenthive"
        )
        settings.secret_key = _strong_fixture("fixture-secret")
        settings.litellm_master_key = _strong_fixture("fixture-model")
        settings.media_webhook_secret = "media-webhook-0123456789abcdef"
        settings.minio_secret_key = "minio-0123456789abcdef"
        settings.redis_url = "redis://:redis-0123456789abcdef@redis:6379/0"
        settings.install_id_path = "/data/agenthive/install-identity.json"
        settings.rate_limit_backend = "redis"
        settings.auth_cookie_enabled = False
        settings.auth_cookie_secure = False

        issues = production_config_issues()

        self.assertIn("AUTH_COOKIE_ENABLED must be enabled in production", issues)
        settings.auth_cookie_enabled = True
        issues = production_config_issues()
        self.assertIn("AUTH_COOKIE_SECURE must be enabled in production", issues)

    def test_production_rejects_unsafe_network_boundaries(self):
        settings.environment = "production"
        settings.database_url = (
            "postgresql+asyncpg://agenthive:strong-password@postgres:5432/agenthive"
        )
        settings.secret_key = _strong_fixture("fixture-secret")
        settings.litellm_master_key = _strong_fixture("fixture-model")
        settings.media_webhook_secret = "media-webhook-0123456789abcdef"
        settings.minio_secret_key = "minio-0123456789abcdef"
        settings.redis_url = "redis://:redis-0123456789abcdef@redis:6379/0"
        settings.install_id_path = "/data/agenthive/install-identity.json"
        settings.rate_limit_backend = "redis"
        settings.auth_cookie_enabled = True
        settings.auth_cookie_secure = True
        settings.cors_origins = ["*"]
        settings.trusted_proxy_cidrs = ["0.0.0.0/0", "not-a-cidr"]

        issues = production_config_issues()

        self.assertIn("CORS_ORIGINS must not allow wildcard origins in production", issues)
        self.assertIn("TRUSTED_PROXY_CIDRS must not trust every address in production", issues)
        self.assertIn("TRUSTED_PROXY_CIDRS contains an invalid CIDR: not-a-cidr", issues)


if __name__ == "__main__":
    unittest.main()
