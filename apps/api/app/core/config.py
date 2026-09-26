from functools import lru_cache

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.knowledge.rag_config import RETRIEVAL_CONFIG_VERSION


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file="../../.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "LexAware Student API"
    app_version: str = "0.1.0"
    environment: str = Field(default="development")

    api_v1_prefix: str = "/api/v1"

    postgres_db: str = "lexaware"
    postgres_user: str = "lexaware"
    postgres_password: str = "change-me"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    redis_host: str = "localhost"
    redis_port: int = 6379

    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "lexaware"
    s3_secret_key: str = "change-me-minio"
    s3_bucket: str = "lexaware-documents-private"
    s3_region: str = "us-east-1"
    document_max_upload_bytes: int = Field(default=10_485_760, ge=1024, le=52_428_800)
    document_worker_poll_seconds: float = Field(default=2.0, gt=0, le=60)
    document_worker_max_attempts: int = Field(default=3, ge=1, le=10)
    document_extraction_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    clamav_host: str = "clamav"
    clamav_port: int = Field(default=3310, ge=1, le=65535)
    clamav_timeout_seconds: float = Field(default=30.0, gt=0, le=120)

    # ------------------------------------------------------------------
    # Authentication
    # NOTE: auth_secret_key is NOT used to sign the current opaque session
    # tokens (which derive their security from cryptographic randomness).
    # It is retained here for future HMAC/webhook signing operations and
    # is documented in ADR 0004.
    # ------------------------------------------------------------------
    auth_secret_key: str = Field(default="change-me-in-production")
    access_token_expire_minutes: int = Field(default=15)

    # Rate limiting â€” intentionally permissive to accommodate shared college
    # networks (hostels, labs). Layered per-IP + per-email enforcement.
    auth_rate_limit_max_ip_attempts: int = Field(default=20)
    auth_rate_limit_max_email_attempts: int = Field(default=10)
    auth_rate_limit_window_seconds: int = Field(default=900)  # 15 minutes

    # CORS â€” only the configured web app origin is allowed when credentials
    # (cookies) are in use. Wildcard + credentials is disallowed by the spec.
    web_app_url: str = Field(default="http://localhost:5173")

    # AI providers are opt-in. Keys remain secret values and are never included in
    # settings reprs, audit metadata, or provider error messages.
    ai_provider: str = "disabled"
    gemini_model: str = "gemini-3.8-flash"
    gemini_api_key: SecretStr | None = None
    gemini_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    gemini_temperature: float = Field(default=0.0, ge=0, le=1)
    gemini_max_output_tokens: int = Field(default=2048, ge=128, le=8192)
    embedding_provider: str = "disabled"
    embedding_model: str = "gemini-embedding-001"
    embedding_dimension: int = Field(default=768, ge=128, le=3072)
    retrieval_config_version: str = RETRIEVAL_CONFIG_VERSION

    @field_validator("ai_provider", "embedding_provider", mode="before")
    @classmethod
    def normalize_provider_name(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("Provider name must be text.")
        return value.strip().lower()

    @model_validator(mode="after")
    def validate_ai_configuration(self) -> Settings:
        if self.ai_provider not in {"disabled", "gemini"}:
            raise ValueError("AI_PROVIDER must be 'disabled' or 'gemini'.")
        if self.embedding_provider not in {"disabled", "gemini"}:
            raise ValueError("EMBEDDING_PROVIDER must be 'disabled' or 'gemini'.")
        key_missing = (
            self.gemini_api_key is None or not self.gemini_api_key.get_secret_value().strip()
        )
        if self.ai_provider == "gemini" and key_missing:
            raise ValueError("GEMINI_API_KEY is required when AI_PROVIDER=gemini.")
        if self.embedding_provider == "gemini" and key_missing:
            raise ValueError("GEMINI_API_KEY is required when EMBEDDING_PROVIDER=gemini.")
        if self.embedding_dimension != 768:
            raise ValueError("The configured Gemini embedding dimension must match pgvector (768).")
        if not self.retrieval_config_version.strip():
            raise ValueError("RETRIEVAL_CONFIG_VERSION cannot be empty.")
        return self

    @property
    def database_url(self) -> str:
        """Return the async PostgreSQL connection URL."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:"
            f"{self.postgres_password}@{self.postgres_host}:"
            f"{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def is_production(self) -> bool:
        """Return True when running in production mode."""
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings instance."""
    return Settings()
