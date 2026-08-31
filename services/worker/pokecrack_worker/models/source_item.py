"""Unified, privacy-preserving candidate emitted by every collector."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pokecrack_worker.deduplication.fingerprints import content_sha256
from pokecrack_worker.deduplication.urls import canonicalize_url, extract_platform_id


class CollectorType(StrEnum):
    OFFICIAL_API = "official_api"
    BLUESKY_JETSTREAM = "bluesky_jetstream"
    NOSTR_RELAY = "nostr_relay"
    SCRAPLING_HTTP = "scrapling_http"
    SCRAPLING_DYNAMIC = "scrapling_dynamic"
    OPENCLI_AUTHENTICATED = "opencli_authenticated"
    MANUAL_IMPORT = "manual_import"
    DISABLED = "disabled"


def hash_author(author: str) -> str:
    """Return a stable namespace-separated digest; raw handles are never retained."""

    normalized = " ".join(author.casefold().strip().split())
    if not normalized:
        raise ValueError("author must not be empty")
    return hashlib.sha256(f"pokecrack-author-v1:{normalized}".encode()).hexdigest()


class SourceItemCandidate(BaseModel):
    """Exact collector DTO plus excluded normalized/deduplication fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    platform: str = Field(default="web", min_length=1, max_length=64)
    external_id: str | None = Field(default=None, max_length=256)
    source_url: str = Field(max_length=2_048)
    title: str | None = Field(default=None, max_length=500)
    text: str | None = Field(default=None, max_length=20_000)
    published_at: datetime | None = None
    author_hash: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    media_urls: tuple[str, ...] = Field(default=(), max_length=12)
    metadata: dict[str, Any] = Field(default_factory=dict)
    collector: CollectorType
    collector_version: str = Field(default="fixture-v1", min_length=1, max_length=128)
    source_policy_version: str = Field(default="1", min_length=1, max_length=64)

    normalized_url: str | None = Field(default=None, exclude=True)
    source_domain: str | None = Field(default=None, exclude=True)
    content_hash: str | None = Field(default=None, exclude=True)
    collected_at: datetime = Field(default_factory=lambda: datetime.now(UTC), exclude=True)

    @model_validator(mode="before")
    @classmethod
    def normalize_bounded_field_aliases(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        data = dict(value)
        if "text" not in data and "content" in data:
            data["text"] = data.pop("content")
        if "text" not in data and "excerpt" in data:
            excerpt = data.pop("excerpt")
            if isinstance(excerpt, str) and len(excerpt) > 4_000:
                raise ValueError("string_too_long: legacy excerpt exceeds 4000 characters")
            data["text"] = excerpt
        else:
            data.pop("excerpt", None)
        if "external_id" not in data and "platform_id" in data:
            data["external_id"] = data.pop("platform_id")
        if "media_urls" not in data and "image_urls" in data:
            data["media_urls"] = data.pop("image_urls")
        return data

    @field_validator("media_urls")
    @classmethod
    def validate_media_urls(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        for value in values:
            canonicalize_url(value)
        return values

    @field_validator("published_at", "collected_at")
    @classmethod
    def timestamps_must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def derive_identities(self) -> Self:
        normalized = canonicalize_url(self.source_url)
        identity = extract_platform_id(normalized)
        domain = urlsplit(normalized).hostname
        digest = content_sha256(self.text) if self.text is not None else None
        if identity is not None:
            if self.platform not in {identity.platform, "web"}:
                raise ValueError("platform conflicts with source URL identity")
            if self.external_id not in {None, identity.external_id}:
                raise ValueError("external_id conflicts with source URL identity")
            object.__setattr__(self, "platform", identity.platform)
            object.__setattr__(self, "external_id", identity.external_id)
        object.__setattr__(self, "normalized_url", normalized)
        object.__setattr__(self, "source_domain", domain)
        object.__setattr__(self, "content_hash", digest)
        return self

    @property
    def canonical_url(self) -> str | None:
        return self.normalized_url

    @property
    def platform_id(self) -> str | None:
        return self.external_id

    @property
    def content_sha256(self) -> str | None:
        return self.content_hash

    @property
    def content(self) -> str | None:
        return self.text

    @property
    def excerpt(self) -> str | None:
        return self.text[:4_000] if self.text is not None else None

    @property
    def image_urls(self) -> tuple[str, ...]:
        return self.media_urls
