"""Minimal command-local settings; reviewer commands never read the worker DSN."""

from __future__ import annotations

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from pokecrack_worker.config.settings import DataMode


class SubmitOperatorSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    data_mode: DataMode = DataMode.DEMO
    supabase_db_url: SecretStr | None = None

    @field_validator("supabase_db_url", mode="before")
    @classmethod
    def empty_secret_is_missing(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value


class ReviewOperatorSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    data_mode: DataMode = DataMode.DEMO
    authorized_opening_review_db_url: SecretStr | None = None
    authorized_opening_review_hmac_key: SecretStr | None = None

    @field_validator(
        "authorized_opening_review_db_url",
        "authorized_opening_review_hmac_key",
        mode="before",
    )
    @classmethod
    def empty_secret_is_missing(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value
