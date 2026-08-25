"""Environment configuration for the worker.

Defaults are deliberately network-free: demo data, fixture AI, and no database or
YouTube credentials. Live modes fail closed during settings validation.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DataMode(StrEnum):
    DEMO = "demo"
    LIVE = "live"


class AIProviderName(StrEnum):
    FIXTURE = "fixture"
    HTTP = "http"
    OPENAI_COMPATIBLE = "openai_compatible"


class Settings(BaseSettings):
    """Validated worker settings loaded directly from the documented env names."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    data_mode: DataMode = DataMode.DEMO
    supabase_db_url: SecretStr | None = None

    ai_provider: AIProviderName = AIProviderName.FIXTURE
    ai_base_url: str = "https://api.openai.com/v1"
    ai_api_key: SecretStr | None = None
    ai_extract_model: str | None = None
    ai_validate_model: str | None = None
    ai_escalate_model: str | None = None
    ai_daily_budget_aud: Decimal = Field(default=Decimal("5"), ge=0)
    ai_monthly_soft_budget_aud: Decimal = Field(default=Decimal("50"), ge=0)
    ai_min_accept_confidence: float = Field(default=0.92, ge=0, le=1)
    ai_min_field_confidence: float = Field(default=0.85, ge=0, le=1)
    ai_max_source_items_per_run: int = Field(default=100, ge=1)
    ai_max_text_chars: int = Field(default=20_000, ge=1, le=20_000)
    ai_max_images: int = Field(default=6, ge=0)
    ai_max_keyframes: int = Field(default=12, ge=0)
    ai_max_video_seconds: int = Field(default=900, ge=0)
    ai_concurrency: int = Field(default=2, ge=1, le=32)
    ai_request_timeout_seconds: float = Field(default=30, gt=0, le=120)
    ai_max_retries: int = Field(default=0, ge=0, le=0)
    ai_retry_backoff_seconds: float = Field(default=0.5, ge=0, le=30)
    ai_max_output_tokens: int = Field(default=4096, ge=1, le=32_768)
    ai_input_per_million_aud: Decimal = Field(default=Decimal("0"), ge=0)
    ai_output_per_million_aud: Decimal = Field(default=Decimal("0"), ge=0)

    youtube_api_key: SecretStr | None = None

    scrapling_enabled: bool = True
    scrapling_http_concurrency: int = Field(default=4, ge=1, le=32)
    scrapling_per_domain_concurrency: int = Field(default=2, ge=1, le=8)
    scrapling_browser_concurrency: int = Field(default=1, ge=1, le=4)
    scrapling_request_timeout_seconds: float = Field(default=30, gt=0, le=120)
    scrapling_default_delay_seconds: float = Field(default=8, ge=0, le=86_400)
    scrapling_dynamic_enabled: bool = False
    scrapling_save_raw_html: Literal[False] = False
    scrapling_max_raw_text_chars: int = Field(default=20_000, ge=1, le=20_000)

    worker_id: str = "demo-worker"
    worker_poll_seconds: float = Field(default=10, gt=0)
    worker_max_concurrency: int = Field(default=2, ge=1)
    worker_lease_seconds: int = Field(default=300, ge=10)
    worker_max_attempts: int = Field(default=5, ge=1)

    bayes_prior_strength: float = Field(default=50, gt=0)
    min_rate_display_packs: int = Field(default=30, ge=1)
    min_signal_packs: int = Field(default=200, ge=1)
    min_signal_sources: int = Field(default=3, ge=1)
    min_watch_probability: float = Field(default=0.90, ge=0, le=1)
    min_anomaly_probability: float = Field(default=0.95, ge=0, le=1)
    min_practical_uplift: float = Field(default=0.20, ge=0)

    database_warning_mb: int = Field(default=350, ge=0)
    database_critical_mb: int = Field(default=425, ge=0)
    storage_warning_mb: int = Field(default=700, ge=0)
    storage_critical_mb: int = Field(default=850, ge=0)
    monthly_egress_warning_gb: float = Field(default=3.5, ge=0)

    backup_dir: Path = Path("/opt/pokecrack/backups")
    backup_retention_daily: int = Field(default=7, ge=0)
    backup_retention_weekly: int = Field(default=4, ge=0)
    profile_backup_enabled: bool = False
    profile_backup_encryption_key_file: Path | None = None

    schedule_official_api: str = "0 */6 * * *"
    schedule_public_collection: str = "15 */6 * * *"
    schedule_auth_collection: str = "30 */12 * * *"
    schedule_catalog_sync: str = "0 2 * * *"
    schedule_aggregates: str = "5 * * * *"
    schedule_cleanup: str = "30 3 * * *"
    schedule_backup: str = "0 4 * * *"
    schedule_browser_check: str = "*/30 * * * *"

    @field_validator(
        "supabase_db_url",
        "ai_api_key",
        "youtube_api_key",
        mode="before",
    )
    @classmethod
    def empty_secret_is_missing(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("ai_extract_model", "ai_validate_model", "ai_escalate_model", mode="before")
    @classmethod
    def empty_model_is_missing(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def validate_live_boundaries(self) -> Self:
        if self.data_mode is DataMode.LIVE and self.supabase_db_url is None:
            raise ValueError("live DATA_MODE requires SUPABASE_DB_URL")
        if self.ai_provider is not AIProviderName.FIXTURE:
            missing: list[str] = []
            if self.ai_api_key is None:
                missing.append("AI_API_KEY")
            if not self.ai_extract_model:
                missing.append("AI_EXTRACT_MODEL")
            if not self.ai_validate_model:
                missing.append("AI_VALIDATE_MODEL")
            if not self.ai_escalate_model:
                missing.append("AI_ESCALATE_MODEL")
            if self.ai_input_per_million_aud <= 0:
                missing.append("AI_INPUT_PER_MILLION_AUD")
            if self.ai_output_per_million_aud <= 0:
                missing.append("AI_OUTPUT_PER_MILLION_AUD")
            if missing:
                raise ValueError("network AI provider requires " + ", ".join(missing))
        if self.database_warning_mb > self.database_critical_mb:
            raise ValueError("DATABASE_WARNING_MB must not exceed DATABASE_CRITICAL_MB")
        if self.storage_warning_mb > self.storage_critical_mb:
            raise ValueError("STORAGE_WARNING_MB must not exceed STORAGE_CRITICAL_MB")
        if self.min_watch_probability > self.min_anomaly_probability:
            raise ValueError("MIN_WATCH_PROBABILITY must not exceed MIN_ANOMALY_PROBABILITY")
        return self
