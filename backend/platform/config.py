"""StackSense application configuration."""

from functools import lru_cache
from typing import Any

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from the environment."""

    app_name: str = "StackSense API"
    app_version: str = "0.1.0"
    app_env: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    storage_root: str = "data/storage"

    # Repository source acquisition
    allowed_source_roots: list[str] = [
        "data/staged",
        "/var/stacksense/staged",
    ]
    github_acquisition_timeout_seconds: int = 60
    github_acquisition_user_agent: str = "StackSense-Ingestion/0.1.0"

    jwt_secret_key: SecretStr = SecretStr(
        "stacksense-insecure-dev-secret-key-change-in-production-at-least-32-bytes"
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30
    bcrypt_rounds: int = 12

    @field_validator("allowed_source_roots", mode="before")
    @classmethod
    def _parse_allowed_source_roots(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [p.strip() for p in v.split(",") if p.strip()]
        if isinstance(v, list):
            return [str(p).strip() for p in v if str(p).strip()]
        return []

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()
