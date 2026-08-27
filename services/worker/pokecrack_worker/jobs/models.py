"""Immutable job records shared by queue backends."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

_TCGDEX_ETAG_PATTERN = re.compile(r'(?:W/)?"[\x21\x23-\x7e]*"')
_LOWER_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_YOUTUBE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
_YOUTUBE_PUBLISHED_AT_MIN = datetime(2005, 1, 1, tzinfo=UTC)
_YOUTUBE_QUERY_NAMES = frozenset(
    {
        "pokemon-tcg-booster-box-opening",
        "pokemon-tcg-etb-opening",
        "pokemon-tcg-booster-bundle-opening",
        "pokemon-tcg-pack-opening",
        "pokemon-tcg-opening-batch-code",
    }
)
_YOUTUBE_METADATA_KEYS = frozenset(
    {
        "query_name",
        "metadata_only",
        "media_download",
        "discovery_scope",
        "geography_status",
        "evidence_tier",
        "statistics_eligible",
        "parser_version",
        "channel_country_code",
        "geography_basis",
    }
)


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD = "dead"
    CANCELLED = "cancelled"


class CompletionEffect(StrEnum):
    """Database effects that a repository may finalize atomically with a job."""

    PRUNE_EXPIRED_EPHEMERA = "prune_expired_ephemera"


@dataclass(frozen=True, slots=True)
class TCGdexSetWrite:
    external_id: str
    name: str
    card_count_total: int
    card_count_official: int

    def __post_init__(self) -> None:
        if not isinstance(self.external_id, str) or not isinstance(self.name, str):
            raise TypeError("TCGdex set ID and name must be text")
        if (
            not self.external_id
            or self.external_id != self.external_id.strip()
            or len(self.external_id) > 160
            or any(ord(character) < 32 or ord(character) == 127 for character in self.external_id)
        ):
            raise ValueError("TCGdex set ID must contain 1 to 160 characters")
        if (
            not self.name
            or self.name != self.name.strip()
            or len(self.name) > 160
            or any(ord(character) < 32 or ord(character) == 127 for character in self.name)
        ):
            raise ValueError("TCGdex set name must contain 1 to 160 characters")
        if (
            isinstance(self.card_count_total, bool)
            or isinstance(self.card_count_official, bool)
            or not isinstance(self.card_count_total, int)
            or not isinstance(self.card_count_official, int)
            or self.card_count_total < 0
            or self.card_count_official < 0
            or self.card_count_total > 1_000_000
            or self.card_count_official > 1_000_000
            or self.card_count_official > self.card_count_total
        ):
            raise ValueError("TCGdex card counts must be ordered non-negative integers")


class TCGdexSyncOutcome(StrEnum):
    CHANGED = "changed"
    UNCHANGED = "unchanged"
    NOT_MODIFIED = "not_modified"


@dataclass(frozen=True, slots=True)
class TCGdexSetsSyncCompletion:
    """Bounded input for the one TCGdex catalog finalizer."""

    outcome: TCGdexSyncOutcome
    expected_revision: int
    etag: str | None
    content_sha256: str
    sets: tuple[TCGdexSetWrite, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, TCGdexSyncOutcome):
            raise TypeError("TCGdex completion outcome must be a TCGdexSyncOutcome")
        if (
            isinstance(self.expected_revision, bool)
            or not isinstance(self.expected_revision, int)
            or not 0 <= self.expected_revision <= 9_223_372_036_854_775_806
        ):
            raise ValueError("TCGdex expected revision is invalid")
        if self.etag is not None:
            if not isinstance(self.etag, str):
                raise TypeError("TCGdex ETag must be text or null")
            if len(self.etag) > 512 or _TCGDEX_ETAG_PATTERN.fullmatch(self.etag) is None:
                raise ValueError("TCGdex ETag must be a bounded HTTP field value")
        if not isinstance(self.content_sha256, str):
            raise TypeError("TCGdex content SHA-256 must be text")
        if len(self.content_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.content_sha256
        ):
            raise ValueError("TCGdex content SHA-256 must be lowercase hexadecimal")
        if not isinstance(self.sets, tuple) or any(
            not isinstance(item, TCGdexSetWrite) for item in self.sets
        ):
            raise TypeError("TCGdex completion sets must be a tuple of TCGdexSetWrite")
        if self.outcome is TCGdexSyncOutcome.CHANGED:
            if not 1 <= len(self.sets) <= 1000:
                raise ValueError("changed TCGdex completion requires 1 to 1000 sets")
            identifiers = [item.external_id for item in self.sets]
            if len(identifiers) != len(set(identifiers)):
                raise ValueError("TCGdex completion set IDs must be unique")
        elif self.sets:
            raise ValueError("unchanged TCGdex completion must not carry catalog rows")
        elif self.expected_revision < 1:
            raise ValueError("unchanged TCGdex completion requires an existing revision")

    def as_payload(self) -> dict[str, Any]:
        return {
            "version": 1,
            "expected_revision": self.expected_revision,
            "outcome": self.outcome.value,
            "etag": self.etag,
            "content_sha256": self.content_sha256,
            "sets": [
                {
                    "id": item.external_id,
                    "name": item.name,
                    "card_count_total": item.card_count_total,
                    "card_count_official": item.card_count_official,
                }
                for item in self.sets
            ],
        }


@dataclass(frozen=True, slots=True)
class YouTubeSourceItemWrite:
    """Exact, activity-only row accepted by the YouTube discovery finalizer."""

    external_id: str
    source_url: str
    normalized_url: str
    title: str | None
    text_excerpt: str | None
    published_at: datetime | None
    author_hash: str | None
    content_hash: str | None
    language: str
    metadata: Mapping[str, Any]
    collector_version: str
    source_policy_version: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.external_id, str)
            or _YOUTUBE_ID_PATTERN.fullmatch(self.external_id) is None
        ):
            raise ValueError("YouTube external ID is invalid")
        expected_url = f"https://www.youtube.com/watch?v={self.external_id}"
        if self.source_url != expected_url or self.normalized_url != expected_url:
            raise ValueError("YouTube source URLs must use the exact canonical watch form")
        if self.title is not None and (
            not isinstance(self.title, str)
            or len(self.title) > 500
            or any(unicodedata.category(character).startswith("C") for character in self.title)
        ):
            raise ValueError("YouTube title is invalid")
        if self.text_excerpt is not None and (
            not isinstance(self.text_excerpt, str)
            or len(self.text_excerpt) > 20_000
            or any(
                unicodedata.category(character).startswith("C") and character not in "\t\n\r"
                for character in self.text_excerpt
            )
        ):
            raise ValueError("YouTube text_excerpt is invalid")
        if self.published_at is not None:
            if (
                not isinstance(self.published_at, datetime)
                or self.published_at.tzinfo is None
                or self.published_at.utcoffset() is None
            ):
                raise ValueError("YouTube published_at must be timezone-aware or null")
            published_at = self.published_at.astimezone(UTC)
            if not _YOUTUBE_PUBLISHED_AT_MIN <= published_at <= datetime.now(UTC):
                raise ValueError("YouTube published_at is outside the approved range")
        for name, value in (
            ("author_hash", self.author_hash),
            ("content_hash", self.content_hash),
        ):
            if value is not None and (
                not isinstance(value, str) or _LOWER_SHA256_PATTERN.fullmatch(value) is None
            ):
                raise ValueError(f"YouTube {name} must be lowercase SHA-256 or null")
        if self.language != "en":
            raise ValueError("YouTube global discovery v1 uses the English query language")
        if self.collector_version != "youtube-global-discovery-v1":
            raise ValueError("YouTube collector version is not approved")
        if self.source_policy_version != "youtube-global-discovery-v1":
            raise ValueError("YouTube source policy version is not approved")
        self._validate_metadata()

    def _validate_metadata(self) -> None:
        if not isinstance(self.metadata, Mapping) or set(self.metadata) != _YOUTUBE_METADATA_KEYS:
            raise ValueError("YouTube activity metadata keys are invalid")
        metadata = self.metadata
        boolean_constants = {
            "metadata_only": True,
            "media_download": False,
            "statistics_eligible": False,
        }
        if any(metadata.get(key) is not value for key, value in boolean_constants.items()):
            raise ValueError("YouTube activity metadata booleans are invalid")
        string_constants = {
            "discovery_scope": "global",
            "evidence_tier": "D",
            "parser_version": "youtube-metadata-v1",
        }
        if any(
            type(metadata.get(key)) is not str or metadata.get(key) != value
            for key, value in string_constants.items()
        ):
            raise ValueError("YouTube activity metadata constants are invalid")
        query_name = metadata.get("query_name")
        if not isinstance(query_name, str) or query_name not in _YOUTUBE_QUERY_NAMES:
            raise ValueError("YouTube metadata query name is not approved")
        country = metadata.get("channel_country_code")
        geography_status = metadata.get("geography_status")
        geography_basis = metadata.get("geography_basis")
        if country is None:
            if geography_status != "unresolved" or geography_basis != "unresolved":
                raise ValueError("unresolved YouTube geography metadata is inconsistent")
        elif (
            not isinstance(country, str)
            or re.fullmatch(r"[A-Z]{2}", country) is None
            or geography_status != "channel_country_proxy"
            or geography_basis != "youtube_channel_country"
        ):
            raise ValueError("YouTube channel-country proxy metadata is invalid")

    def as_payload(self) -> dict[str, Any]:
        self.__post_init__()
        published_at = (
            self.published_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
            if self.published_at is not None
            else None
        )
        return {
            "external_id": self.external_id,
            "source_url": self.source_url,
            "normalized_url": self.normalized_url,
            "title": self.title,
            "text_excerpt": self.text_excerpt,
            "published_at": published_at,
            "author_hash": self.author_hash,
            "content_hash": self.content_hash,
            "language": self.language,
            "metadata": dict(self.metadata),
            "collector_version": self.collector_version,
            "source_policy_version": self.source_policy_version,
        }


@dataclass(frozen=True, slots=True)
class YouTubeDiscoveryCompletion:
    """One exact allowlisted query and its bounded atomic persistence input."""

    query_name: str
    items: tuple[YouTubeSourceItemWrite, ...]

    def __post_init__(self) -> None:
        if self.query_name not in _YOUTUBE_QUERY_NAMES:
            raise ValueError("YouTube completion query name is not approved")
        if (
            not isinstance(self.items, tuple)
            or len(self.items) > 50
            or any(not isinstance(item, YouTubeSourceItemWrite) for item in self.items)
        ):
            raise ValueError("YouTube completion requires 0 to 50 typed items")
        if any(item.metadata.get("query_name") != self.query_name for item in self.items):
            raise ValueError("YouTube completion item query provenance is inconsistent")
        external_ids = [item.external_id for item in self.items]
        if len(external_ids) != len(set(external_ids)):
            raise ValueError("YouTube completion external IDs must be unique")

    def as_payload(self) -> dict[str, Any]:
        self.__post_init__()
        return {
            "version": 1,
            "query_name": self.query_name,
            "items": [item.as_payload() for item in self.items],
        }


@dataclass(frozen=True, slots=True)
class Job:
    id: str
    kind: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    status: JobStatus = JobStatus.PENDING
    priority: int = 0
    available_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    attempts: int = 0
    max_attempts: int = 5
    lease_generation: int = 0
    leased_by: str | None = None
    leased_at: datetime | None = None
    lease_expires_at: datetime | None = None
    heartbeat_at: datetime | None = None
    last_error: str | None = None
    finished_at: datetime | None = None
    dedupe_key: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def job_type(self) -> str:
        return self.kind
