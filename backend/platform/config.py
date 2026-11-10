"""StackSense application configuration."""

from functools import lru_cache
from typing import Any

from pydantic import Field, SecretStr, field_validator, model_validator
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

    # Analysis execution & lifecycle configuration (Phase 3 Module 1)
    analysis_max_duration_seconds: int = Field(default=1800, ge=1)
    analysis_stage_timeout_seconds: int = Field(default=600, ge=1)
    analysis_heartbeat_interval_seconds: int = Field(default=30, ge=1)
    analysis_stale_job_threshold_seconds: int = Field(default=120, ge=1)
    analysis_max_diagnostics_per_analysis: int = Field(default=1000, ge=1)
    analysis_default_page_size: int = 20
    analysis_max_page_size: int = 100

    # Celery & RabbitMQ orchestration (Phase 3 Module 1 Batch 3)
    celery_broker_url: str = "amqp://guest:guest@localhost:5672//"
    celery_result_backend: str | None = None
    analysis_queue_name: str = "analysis.jobs"
    analysis_worker_concurrency: int = 2
    analysis_worker_prefetch_multiplier: int = 1
    analysis_max_retries: int = Field(default=3, ge=0)
    analysis_retry_backoff_seconds: int = Field(default=5, ge=1)
    analysis_dispatch_recovery_interval_seconds: int = Field(default=60, ge=1)
    internal_api_secret_key: SecretStr = SecretStr(
        "internal-analysis-secret-key-change-in-production"
    )
    platform_api_base_url: str = "http://localhost:5000/api/v1/internal"
    platform_api_secret_key: SecretStr = SecretStr(
        "internal-platform-secret-key-change-in-production"
    )
    platform_api_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    platform_artifact_fetch_concurrency: int = Field(default=8, ge=1, le=32)
    sse_poll_interval_seconds: float = 0.5

    # Repository inspection & syntax analysis (Phase 3 Module 2)
    parser_per_file_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    parser_max_file_size_bytes: int = Field(default=5 * 1024 * 1024, gt=0)
    parser_max_memory_mb: int = Field(default=512, ge=64, le=4096)
    parser_max_stderr_bytes: int = Field(default=1024 * 1024, gt=0)
    parser_max_facts_per_artifact: int = Field(default=25_000, ge=1)
    parser_max_facts_per_analysis: int = Field(default=250_000, ge=1)
    parser_max_serialized_f2_bytes: int = Field(default=50 * 1024 * 1024, ge=1024)
    parser_worker_count: int = Field(default=4, ge=1, le=16)
    parser_worker_max_requests: int = Field(default=64, ge=1, le=1000)

    # Intermediate Representation (Phase 3 Module 3)
    ir_max_entities: int = Field(default=150_000, ge=1)
    ir_max_relationships: int = Field(default=500_000, ge=1)
    ir_max_evidence: int = Field(default=500_000, ge=1)
    ir_max_unresolved_references: int = Field(default=150_000, ge=1)
    ir_max_conflicts: int = Field(default=25_000, ge=1)
    ir_max_serialized_bytes: int = Field(default=512 * 1024 * 1024, ge=1024)

    # Architecture Model construction (Phase 3 Module 4)
    architecture_max_entities: int = Field(default=25_000, ge=1)
    architecture_max_relationships: int = Field(default=50_000, ge=1)
    architecture_max_evidence: int = Field(default=75_000, ge=1)
    architecture_max_unresolved_relationships: int = Field(default=10_000, ge=1)
    architecture_max_conflicts: int = Field(default=5_000, ge=1)
    architecture_max_serialized_bytes: int = Field(
        default=128 * 1024 * 1024,
        ge=1024,
    )

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

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> Settings:
        if self.app_env.lower() in {"production", "prod"} and (
            self.internal_api_secret_key.get_secret_value()
            == "internal-analysis-secret-key-change-in-production"
        ):
            raise ValueError("INTERNAL_API_SECRET_KEY must be changed in production")
        if self.app_env.lower() in {"production", "prod"} and (
            self.platform_api_secret_key.get_secret_value()
            == "internal-platform-secret-key-change-in-production"
        ):
            raise ValueError("PLATFORM_API_SECRET_KEY must be changed in production")
        if self.analysis_stage_timeout_seconds > self.analysis_max_duration_seconds:
            raise ValueError(
                "analysis stage timeout cannot exceed analysis max duration"
            )
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()
