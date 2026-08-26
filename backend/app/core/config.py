from urllib.parse import unquote, urlparse
from ipaddress import ip_network

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET_KEY = "agenthive-development-secret-change-me-before-production"
PLACEHOLDER_SECRET_FRAGMENTS = (
    "change-me",
    "changeme",
    "replace-with",
    "development-secret",
    "dev-secret",
)


class Settings(BaseSettings):
    app_name: str = Field(default="AgentHive", validation_alias="AGENTHIVE_APP_NAME")
    app_version: str = Field(default="0.3.0-alpha.2", validation_alias="AGENTHIVE_APP_VERSION")
    environment: str = Field(default="development", validation_alias="AGENTHIVE_ENVIRONMENT")
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"],
        validation_alias="AGENTHIVE_CORS_ORIGINS",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://agenthive:agenthive@localhost:5432/agenthive",
        validation_alias=AliasChoices("DATABASE_URL", "AGENTHIVE_DATABASE_URL"),
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias=AliasChoices("REDIS_URL", "AGENTHIVE_REDIS_URL"),
    )
    minio_endpoint: str = Field(
        default="localhost:9000",
        validation_alias=AliasChoices("MINIO_ENDPOINT", "AGENTHIVE_MINIO_ENDPOINT"),
    )
    minio_access_key: str = Field(
        default="agenthive",
        validation_alias=AliasChoices("MINIO_ACCESS_KEY", "AGENTHIVE_MINIO_ACCESS_KEY"),
    )
    minio_secret_key: str = Field(
        default="agenthive_minio_password",
        validation_alias=AliasChoices("MINIO_SECRET_KEY", "AGENTHIVE_MINIO_SECRET_KEY"),
    )
    minio_secure: bool = Field(
        default=False,
        validation_alias=AliasChoices("MINIO_SECURE", "AGENTHIVE_MINIO_SECURE"),
    )
    object_storage_fallback_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "OBJECT_STORAGE_FALLBACK_PATH",
            "AGENTHIVE_OBJECT_STORAGE_FALLBACK_PATH",
        ),
    )
    litellm_base_url: str = Field(
        default="http://localhost:4000",
        validation_alias=AliasChoices("LITELLM_BASE_URL", "AGENTHIVE_LITELLM_BASE_URL"),
    )
    litellm_master_key: str = Field(
        default="",
        validation_alias=AliasChoices("LITELLM_MASTER_KEY", "AGENTHIVE_LITELLM_MASTER_KEY"),
    )
    frontend_health_url: str = Field(
        default="",
        validation_alias=AliasChoices("FRONTEND_HEALTH_URL", "AGENTHIVE_FRONTEND_HEALTH_URL"),
    )
    public_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("PUBLIC_BASE_URL", "AGENTHIVE_PUBLIC_BASE_URL"),
    )
    openai_compatible_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "OPENAI_COMPATIBLE_BASE_URL",
            "AGENTHIVE_OPENAI_COMPATIBLE_BASE_URL",
        ),
    )
    openai_compatible_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "OPENAI_COMPATIBLE_API_KEY",
            "AGENTHIVE_OPENAI_COMPATIBLE_API_KEY",
        ),
    )
    media_openai_compatible_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "MEDIA_OPENAI_COMPATIBLE_BASE_URL",
            "AGENTHIVE_MEDIA_OPENAI_COMPATIBLE_BASE_URL",
        ),
    )
    media_openai_compatible_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "MEDIA_OPENAI_COMPATIBLE_API_KEY",
            "AGENTHIVE_MEDIA_OPENAI_COMPATIBLE_API_KEY",
        ),
    )
    media_openai_compatible_image_path: str = Field(
        default="/images/generations",
        validation_alias=AliasChoices(
            "MEDIA_OPENAI_COMPATIBLE_IMAGE_PATH",
            "AGENTHIVE_MEDIA_OPENAI_COMPATIBLE_IMAGE_PATH",
        ),
    )
    media_openai_compatible_video_path: str = Field(
        default="/videos/generations",
        validation_alias=AliasChoices(
            "MEDIA_OPENAI_COMPATIBLE_VIDEO_PATH",
            "AGENTHIVE_MEDIA_OPENAI_COMPATIBLE_VIDEO_PATH",
        ),
    )
    media_openai_compatible_status_path: str | None = Field(
        default="/jobs/{external_job_id}",
        validation_alias=AliasChoices(
            "MEDIA_OPENAI_COMPATIBLE_STATUS_PATH",
            "AGENTHIVE_MEDIA_OPENAI_COMPATIBLE_STATUS_PATH",
        ),
    )
    media_provider_timeout_seconds: float = Field(
        default=120.0,
        validation_alias=AliasChoices(
            "MEDIA_PROVIDER_TIMEOUT_SECONDS",
            "AGENTHIVE_MEDIA_PROVIDER_TIMEOUT_SECONDS",
        ),
    )
    # ---- Local / on-prem inference engines (P1: 离网模型支持) ----------
    # These expose OpenAI-compatible endpoints and typically require no auth
    # on localhost. Setting the base_url activates the catalog provider.
    ollama_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OLLAMA_BASE_URL", "AGENTHIVE_OLLAMA_BASE_URL"),
    )
    ollama_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OLLAMA_API_KEY", "AGENTHIVE_OLLAMA_API_KEY"),
    )
    vllm_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("VLLM_BASE_URL", "AGENTHIVE_VLLM_BASE_URL"),
    )
    vllm_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("VLLM_API_KEY", "AGENTHIVE_VLLM_API_KEY"),
    )
    sglang_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SGLANG_BASE_URL", "AGENTHIVE_SGLANG_BASE_URL"),
    )
    sglang_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("SGLANG_API_KEY", "AGENTHIVE_SGLANG_API_KEY"),
    )
    lmstudio_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LMSTUDIO_BASE_URL", "AGENTHIVE_LMSTUDIO_BASE_URL"),
    )
    lmstudio_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("LMSTUDIO_API_KEY", "AGENTHIVE_LMSTUDIO_API_KEY"),
    )
    xinference_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("XINFERENCE_BASE_URL", "AGENTHIVE_XINFERENCE_BASE_URL"),
    )
    xinference_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("XINFERENCE_API_KEY", "AGENTHIVE_XINFERENCE_API_KEY"),
    )
    localai_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LOCALAI_BASE_URL", "AGENTHIVE_LOCALAI_BASE_URL"),
    )
    localai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("LOCALAI_API_KEY", "AGENTHIVE_LOCALAI_API_KEY"),
    )
    media_output_bucket: str = Field(
        default="agenthive-media",
        validation_alias=AliasChoices("MEDIA_OUTPUT_BUCKET", "AGENTHIVE_MEDIA_OUTPUT_BUCKET"),
    )
    media_output_download_max_bytes: int = Field(
        default=262_144_000,
        validation_alias=AliasChoices(
            "MEDIA_OUTPUT_DOWNLOAD_MAX_BYTES",
            "AGENTHIVE_MEDIA_OUTPUT_DOWNLOAD_MAX_BYTES",
        ),
    )
    media_webhook_secret: str = Field(
        default="",
        validation_alias=AliasChoices("MEDIA_WEBHOOK_SECRET", "AGENTHIVE_MEDIA_WEBHOOK_SECRET"),
    )
    media_webhook_public_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "MEDIA_WEBHOOK_PUBLIC_URL",
            "AGENTHIVE_MEDIA_WEBHOOK_PUBLIC_URL",
        ),
    )
    openai_images_base_url: str | None = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices("OPENAI_IMAGES_BASE_URL", "AGENTHIVE_OPENAI_IMAGES_BASE_URL"),
    )
    openai_images_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_IMAGES_API_KEY", "AGENTHIVE_OPENAI_IMAGES_API_KEY"),
    )
    nano_banana_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("NANO_BANANA_BASE_URL", "AGENTHIVE_NANO_BANANA_BASE_URL"),
    )
    nano_banana_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("NANO_BANANA_API_KEY", "AGENTHIVE_NANO_BANANA_API_KEY"),
    )
    volcengine_seedance_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "VOLCENGINE_SEEDANCE_BASE_URL", "AGENTHIVE_VOLCENGINE_SEEDANCE_BASE_URL"
        ),
    )
    volcengine_seedance_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "VOLCENGINE_SEEDANCE_API_KEY", "AGENTHIVE_VOLCENGINE_SEEDANCE_API_KEY"
        ),
    )
    volcengine_seedance_status_path: str | None = Field(
        default="/jobs/{external_job_id}",
        validation_alias=AliasChoices(
            "VOLCENGINE_SEEDANCE_STATUS_PATH",
            "AGENTHIVE_VOLCENGINE_SEEDANCE_STATUS_PATH",
        ),
    )
    secret_key: str = Field(
        default=DEFAULT_SECRET_KEY,
        validation_alias=AliasChoices("SECRET_KEY", "AGENTHIVE_SECRET_KEY"),
    )
    access_token_expire_minutes: int = Field(
        default=60 * 12,
        validation_alias=AliasChoices(
            "ACCESS_TOKEN_EXPIRE_MINUTES",
            "AGENTHIVE_ACCESS_TOKEN_EXPIRE_MINUTES",
        ),
    )
    auth_cookie_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("AUTH_COOKIE_ENABLED", "AGENTHIVE_AUTH_COOKIE_ENABLED"),
    )
    auth_cookie_secure: bool = Field(
        default=False,
        validation_alias=AliasChoices("AUTH_COOKIE_SECURE", "AGENTHIVE_AUTH_COOKIE_SECURE"),
    )
    knowledge_upload_max_bytes: int = Field(
        default=50 * 1024 * 1024,
        gt=0,
        validation_alias=AliasChoices(
            "KNOWLEDGE_UPLOAD_MAX_BYTES", "AGENTHIVE_KNOWLEDGE_UPLOAD_MAX_BYTES"
        ),
    )
    login_failure_limit: int = Field(
        default=5,
        validation_alias=AliasChoices("LOGIN_FAILURE_LIMIT", "AGENTHIVE_LOGIN_FAILURE_LIMIT"),
    )
    login_failure_window_seconds: int = Field(
        default=15 * 60,
        validation_alias=AliasChoices(
            "LOGIN_FAILURE_WINDOW_SECONDS",
            "AGENTHIVE_LOGIN_FAILURE_WINDOW_SECONDS",
        ),
    )
    security_headers_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "SECURITY_HEADERS_ENABLED", "AGENTHIVE_SECURITY_HEADERS_ENABLED"
        ),
    )
    rate_limit_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("RATE_LIMIT_ENABLED", "AGENTHIVE_RATE_LIMIT_ENABLED"),
    )
    rate_limit_requests: int = Field(
        default=120,
        validation_alias=AliasChoices("RATE_LIMIT_REQUESTS", "AGENTHIVE_RATE_LIMIT_REQUESTS"),
    )
    rate_limit_window_seconds: int = Field(
        default=60,
        validation_alias=AliasChoices(
            "RATE_LIMIT_WINDOW_SECONDS", "AGENTHIVE_RATE_LIMIT_WINDOW_SECONDS"
        ),
    )
    rate_limit_backend: str = Field(
        default="memory",
        pattern=r"^(memory|redis)$",
        validation_alias=AliasChoices("RATE_LIMIT_BACKEND", "AGENTHIVE_RATE_LIMIT_BACKEND"),
    )
    trusted_proxy_cidrs: list[str] = Field(
        default_factory=lambda: ["127.0.0.1/32", "::1/128"],
        validation_alias=AliasChoices("TRUSTED_PROXY_CIDRS", "AGENTHIVE_TRUSTED_PROXY_CIDRS"),
    )
    access_log_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("ACCESS_LOG_ENABLED", "AGENTHIVE_ACCESS_LOG_ENABLED"),
    )
    access_log_exclude_paths: list[str] = Field(
        default_factory=lambda: [
            "/api/docs",
            "/api/openapi.json",
            "/api/v1/health",
            "/widget/",
        ],
        validation_alias=AliasChoices(
            "ACCESS_LOG_EXCLUDE_PATHS", "AGENTHIVE_ACCESS_LOG_EXCLUDE_PATHS"
        ),
    )
    metrics_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("METRICS_ENABLED", "AGENTHIVE_METRICS_ENABLED"),
    )
    sentry_dsn: str = Field(
        default="",
        validation_alias=AliasChoices("SENTRY_DSN", "AGENTHIVE_SENTRY_DSN"),
    )
    sentry_traces_sample_rate: float = Field(
        default=0.0,
        validation_alias=AliasChoices(
            "SENTRY_TRACES_SAMPLE_RATE", "AGENTHIVE_SENTRY_TRACES_SAMPLE_RATE"
        ),
    )
    widget_cors_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("WIDGET_CORS_ENABLED", "AGENTHIVE_WIDGET_CORS_ENABLED"),
    )
    widget_cors_origins: list[str] = Field(
        default_factory=lambda: ["*"],
        validation_alias=AliasChoices("WIDGET_CORS_ORIGINS", "AGENTHIVE_WIDGET_CORS_ORIGINS"),
    )
    llm_circuit_breaker_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "LLM_CIRCUIT_BREAKER_ENABLED", "AGENTHIVE_LLM_CIRCUIT_BREAKER_ENABLED"
        ),
    )
    llm_circuit_breaker_failure_threshold: int = Field(
        default=5,
        ge=1,
        validation_alias=AliasChoices(
            "LLM_CIRCUIT_BREAKER_FAILURE_THRESHOLD",
            "AGENTHIVE_LLM_CIRCUIT_BREAKER_FAILURE_THRESHOLD",
        ),
    )
    llm_circuit_breaker_cooldown_seconds: float = Field(
        default=30.0,
        ge=1.0,
        validation_alias=AliasChoices(
            "LLM_CIRCUIT_BREAKER_COOLDOWN_SECONDS",
            "AGENTHIVE_LLM_CIRCUIT_BREAKER_COOLDOWN_SECONDS",
        ),
    )
    llm_circuit_breaker_success_threshold: int = Field(
        default=2,
        ge=1,
        validation_alias=AliasChoices(
            "LLM_CIRCUIT_BREAKER_SUCCESS_THRESHOLD",
            "AGENTHIVE_LLM_CIRCUIT_BREAKER_SUCCESS_THRESHOLD",
        ),
    )
    # Cost-aware routing: when enabled and a policy's metadata declares
    # ``routing_strategy=cost_priority``, the router sorts equal-priority
    # candidates by ascending estimated cost (input+output per 1k tokens)
    # instead of leaving them in deployment order. Disabled by default so
    # existing tenants keep priority-only behaviour.
    llm_cost_aware_routing_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "LLM_COST_AWARE_ROUTING_ENABLED",
            "AGENTHIVE_LLM_COST_AWARE_ROUTING_ENABLED",
        ),
    )
    agent_concurrency_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "AGENT_CONCURRENCY_ENABLED", "AGENTHIVE_AGENT_CONCURRENCY_ENABLED"
        ),
    )
    agent_concurrency_tenant_limit: int = Field(
        default=40,
        validation_alias=AliasChoices(
            "AGENT_CONCURRENCY_TENANT_LIMIT", "AGENTHIVE_AGENT_CONCURRENCY_TENANT_LIMIT"
        ),
    )
    agent_concurrency_user_limit: int = Field(
        default=4,
        validation_alias=AliasChoices(
            "AGENT_CONCURRENCY_USER_LIMIT", "AGENTHIVE_AGENT_CONCURRENCY_USER_LIMIT"
        ),
    )
    agent_concurrency_agent_limit: int = Field(
        default=12,
        validation_alias=AliasChoices(
            "AGENT_CONCURRENCY_AGENT_LIMIT", "AGENTHIVE_AGENT_CONCURRENCY_AGENT_LIMIT"
        ),
    )
    agent_concurrency_wait_timeout_seconds: float = Field(
        default=0.2,
        validation_alias=AliasChoices(
            "AGENT_CONCURRENCY_WAIT_TIMEOUT_SECONDS",
            "AGENTHIVE_AGENT_CONCURRENCY_WAIT_TIMEOUT_SECONDS",
        ),
    )
    jwt_algorithm: str = Field(default="HS256", validation_alias="AGENTHIVE_JWT_ALGORITHM")
    license_public_key_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "LICENSE_PUBLIC_KEY_PATH", "AGENTHIVE_LICENSE_PUBLIC_KEY_PATH"
        ),
    )
    install_id_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices("INSTALL_ID_PATH", "AGENTHIVE_INSTALL_ID_PATH"),
    )
    ragflow_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RAGFLOW_URL", "AGENTHIVE_RAGFLOW_URL"),
    )
    ragflow_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("RAGFLOW_API_KEY", "AGENTHIVE_RAGFLOW_API_KEY"),
    )
    ragflow_health_path: str = Field(
        default="/health",
        validation_alias=AliasChoices("RAGFLOW_HEALTH_PATH", "AGENTHIVE_RAGFLOW_HEALTH_PATH"),
    )
    ragflow_ingest_path: str = Field(
        default="/api/v1/agenthive/ingest",
        validation_alias=AliasChoices("RAGFLOW_INGEST_PATH", "AGENTHIVE_RAGFLOW_INGEST_PATH"),
    )
    ragflow_retrieve_path: str = Field(
        default="/api/v1/agenthive/retrieve",
        validation_alias=AliasChoices("RAGFLOW_RETRIEVE_PATH", "AGENTHIVE_RAGFLOW_RETRIEVE_PATH"),
    )
    ragflow_delete_path: str = Field(
        default="/api/v1/agenthive/documents/{knowledge_base_id}/{document_id}",
        validation_alias=AliasChoices("RAGFLOW_DELETE_PATH", "AGENTHIVE_RAGFLOW_DELETE_PATH"),
    )
    ragflow_request_timeout_seconds: float = Field(
        default=10.0,
        validation_alias=AliasChoices(
            "RAGFLOW_REQUEST_TIMEOUT_SECONDS",
            "AGENTHIVE_RAGFLOW_REQUEST_TIMEOUT_SECONDS",
        ),
    )
    ragflow_health_timeout_seconds: float = Field(
        default=3.0,
        validation_alias=AliasChoices(
            "RAGFLOW_HEALTH_TIMEOUT_SECONDS",
            "AGENTHIVE_RAGFLOW_HEALTH_TIMEOUT_SECONDS",
        ),
    )
    ragflow_max_retries: int = Field(
        default=2,
        validation_alias=AliasChoices("RAGFLOW_MAX_RETRIES", "AGENTHIVE_RAGFLOW_MAX_RETRIES"),
    )
    ragflow_retry_backoff_seconds: float = Field(
        default=0.5,
        validation_alias=AliasChoices(
            "RAGFLOW_RETRY_BACKOFF_SECONDS",
            "AGENTHIVE_RAGFLOW_RETRY_BACKOFF_SECONDS",
        ),
    )
    ragflow_fallback_to_pgvector: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "RAGFLOW_FALLBACK_TO_PGVECTOR",
            "AGENTHIVE_RAGFLOW_FALLBACK_TO_PGVECTOR",
        ),
    )
    channel_token_refresh_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "CHANNEL_TOKEN_REFRESH_ENABLED",
            "AGENTHIVE_CHANNEL_TOKEN_REFRESH_ENABLED",
        ),
    )
    channel_token_refresh_ahead_seconds: int = Field(
        default=300,
        validation_alias=AliasChoices(
            "CHANNEL_TOKEN_REFRESH_AHEAD_SECONDS",
            "AGENTHIVE_CHANNEL_TOKEN_REFRESH_AHEAD_SECONDS",
        ),
    )
    channel_token_request_timeout_seconds: float = Field(
        default=8.0,
        validation_alias=AliasChoices(
            "CHANNEL_TOKEN_REQUEST_TIMEOUT_SECONDS",
            "AGENTHIVE_CHANNEL_TOKEN_REQUEST_TIMEOUT_SECONDS",
        ),
    )
    channel_token_max_retries: int = Field(
        default=2,
        validation_alias=AliasChoices(
            "CHANNEL_TOKEN_MAX_RETRIES",
            "AGENTHIVE_CHANNEL_TOKEN_MAX_RETRIES",
        ),
    )
    channel_token_retry_backoff_seconds: float = Field(
        default=0.5,
        validation_alias=AliasChoices(
            "CHANNEL_TOKEN_RETRY_BACKOFF_SECONDS",
            "AGENTHIVE_CHANNEL_TOKEN_RETRY_BACKOFF_SECONDS",
        ),
    )
    rag_embedding_mode: str = Field(
        default="deterministic_local",
        validation_alias=AliasChoices("RAG_EMBEDDING_MODE", "AGENTHIVE_RAG_EMBEDDING_MODE"),
    )
    rag_embedding_model_key: str = Field(
        default="agenthive-local-hash-v1",
        validation_alias=AliasChoices(
            "RAG_EMBEDDING_MODEL_KEY", "AGENTHIVE_RAG_EMBEDDING_MODEL_KEY"
        ),
    )
    rag_embedding_dimensions: int = Field(
        default=1536,
        validation_alias=AliasChoices(
            "RAG_EMBEDDING_DIMENSIONS", "AGENTHIVE_RAG_EMBEDDING_DIMENSIONS"
        ),
    )
    rag_embedding_provider: str = Field(
        default="local_hash",
        validation_alias=AliasChoices("RAG_EMBEDDING_PROVIDER", "AGENTHIVE_RAG_EMBEDDING_PROVIDER"),
    )
    rag_embedding_api_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "RAG_EMBEDDING_API_BASE_URL", "AGENTHIVE_RAG_EMBEDDING_API_BASE_URL"
        ),
    )
    rag_embedding_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("RAG_EMBEDDING_API_KEY", "AGENTHIVE_RAG_EMBEDDING_API_KEY"),
    )
    rag_embedding_request_timeout_seconds: float = Field(
        default=30.0,
        validation_alias=AliasChoices(
            "RAG_EMBEDDING_REQUEST_TIMEOUT_SECONDS",
            "AGENTHIVE_RAG_EMBEDDING_REQUEST_TIMEOUT_SECONDS",
        ),
    )
    rag_embedding_max_retries: int = Field(
        default=2,
        validation_alias=AliasChoices(
            "RAG_EMBEDDING_MAX_RETRIES",
            "AGENTHIVE_RAG_EMBEDDING_MAX_RETRIES",
        ),
    )
    rag_embedding_retry_backoff_seconds: float = Field(
        default=0.5,
        validation_alias=AliasChoices(
            "RAG_EMBEDDING_RETRY_BACKOFF_SECONDS",
            "AGENTHIVE_RAG_EMBEDDING_RETRY_BACKOFF_SECONDS",
        ),
    )
    rag_embedding_circuit_breaker_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "RAG_EMBEDDING_CIRCUIT_BREAKER_ENABLED",
            "AGENTHIVE_RAG_EMBEDDING_CIRCUIT_BREAKER_ENABLED",
        ),
    )
    rag_hybrid_retrieval_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "RAG_HYBRID_RETRIEVAL_ENABLED",
            "AGENTHIVE_RAG_HYBRID_RETRIEVAL_ENABLED",
        ),
    )
    rag_reranker_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "RAG_RERANKER_ENABLED",
            "AGENTHIVE_RAG_RERANKER_ENABLED",
        ),
    )
    rag_reranker_api_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "RAG_RERANKER_API_URL",
            "AGENTHIVE_RAG_RERANKER_API_URL",
        ),
    )
    rag_reranker_request_timeout_seconds: float = Field(
        default=15.0,
        validation_alias=AliasChoices(
            "RAG_RERANKER_REQUEST_TIMEOUT_SECONDS",
            "AGENTHIVE_RAG_RERANKER_REQUEST_TIMEOUT_SECONDS",
        ),
    )
    rag_embedding_circuit_breaker_failure_threshold: int = Field(
        default=5,
        validation_alias=AliasChoices(
            "RAG_EMBEDDING_CIRCUIT_BREAKER_FAILURE_THRESHOLD",
            "AGENTHIVE_RAG_EMBEDDING_CIRCUIT_BREAKER_FAILURE_THRESHOLD",
        ),
    )
    rag_embedding_circuit_breaker_reset_timeout_seconds: float = Field(
        default=60.0,
        validation_alias=AliasChoices(
            "RAG_EMBEDDING_CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS",
            "AGENTHIVE_RAG_EMBEDDING_CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS",
        ),
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()


def normalized_environment(config: Settings = settings) -> str:
    return config.environment.strip().lower()


def is_development_environment(config: Settings = settings) -> bool:
    return normalized_environment(config) == "development"


def is_production_environment(config: Settings = settings) -> bool:
    return normalized_environment(config) in {"production", "prod"}


def production_config_issues(config: Settings = settings) -> list[str]:
    if not is_production_environment(config):
        return []

    issues: list[str] = []
    _append_database_url_issue(issues, config.database_url)
    _append_install_identity_issue(issues, config.install_id_path)
    _append_weak_secret_issue(
        issues,
        name="SECRET_KEY",
        value=config.secret_key,
        min_length=32,
        disallow_values={DEFAULT_SECRET_KEY},
    )
    _append_weak_secret_issue(
        issues,
        name="LITELLM_MASTER_KEY",
        value=config.litellm_master_key,
        min_length=24,
    )
    _append_weak_secret_issue(
        issues,
        name="MEDIA_WEBHOOK_SECRET",
        value=config.media_webhook_secret,
        min_length=24,
    )
    _append_weak_secret_issue(
        issues,
        name="MINIO_SECRET_KEY",
        value=config.minio_secret_key,
        min_length=16,
        disallow_values={"agenthive_minio_password"},
    )

    parsed_redis_url = urlparse(config.redis_url)
    redis_password = unquote(parsed_redis_url.password) if parsed_redis_url.password else None
    _append_weak_secret_issue(
        issues,
        name="REDIS_PASSWORD",
        value=redis_password or "",
        min_length=12,
    )
    if config.rate_limit_enabled and config.rate_limit_backend != "redis":
        issues.append("RATE_LIMIT_BACKEND must use Redis in production")
    _append_network_boundary_issues(issues, config)
    if not config.auth_cookie_enabled:
        issues.append("AUTH_COOKIE_ENABLED must be enabled in production")
    if config.auth_cookie_enabled and not config.auth_cookie_secure:
        issues.append("AUTH_COOKIE_SECURE must be enabled in production")
    return issues


def _append_network_boundary_issues(issues: list[str], config: Settings) -> None:
    if "*" in config.cors_origins:
        issues.append("CORS_ORIGINS must not allow wildcard origins in production")

    if not config.trusted_proxy_cidrs:
        issues.append("TRUSTED_PROXY_CIDRS must not be empty in production")
        return
    for cidr in config.trusted_proxy_cidrs:
        try:
            network = ip_network(cidr, strict=False)
        except ValueError:
            issues.append(f"TRUSTED_PROXY_CIDRS contains an invalid CIDR: {cidr}")
            continue
        if network.prefixlen == 0:
            issues.append("TRUSTED_PROXY_CIDRS must not trust every address in production")


def _append_database_url_issue(issues: list[str], value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"postgresql", "postgresql+asyncpg"}:
        issues.append("DATABASE_URL must use PostgreSQL in production")
        return
    if not parsed.hostname:
        issues.append("DATABASE_URL must include a PostgreSQL host in production")


def _append_install_identity_issue(issues: list[str], value: str | None) -> None:
    normalized = (value or "").strip()
    if not normalized:
        issues.append("INSTALL_ID_PATH is required in production")
        return
    if not normalized.startswith("/"):
        issues.append("INSTALL_ID_PATH must be an absolute path in production")
    if normalized in {"/tmp", "/private/tmp"} or normalized.startswith(("/tmp/", "/private/tmp/")):
        issues.append("INSTALL_ID_PATH must not use a temporary directory in production")


def assert_production_config_safe(config: Settings = settings) -> None:
    issues = production_config_issues(config)
    if issues:
        raise RuntimeError("AgentHive production configuration is unsafe: " + "; ".join(issues))


def _append_weak_secret_issue(
    issues: list[str],
    *,
    name: str,
    value: str,
    min_length: int,
    disallow_values: set[str] | None = None,
) -> None:
    normalized = value.strip()
    lowered = normalized.lower()
    if not normalized:
        issues.append(f"{name} is required in production")
        return
    if len(normalized) < min_length:
        issues.append(f"{name} must be at least {min_length} characters")
    if disallow_values and normalized in disallow_values:
        issues.append(f"{name} uses a built-in development value")
    if any(fragment in lowered for fragment in PLACEHOLDER_SECRET_FRAGMENTS):
        issues.append(f"{name} still contains a placeholder fragment")
