from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    @property
    def database_url(self) -> str:
        """Return the async PostgreSQL connection URL."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:"
            f"{self.postgres_password}@{self.postgres_host}:"
            f"{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings instance."""
    return Settings()
