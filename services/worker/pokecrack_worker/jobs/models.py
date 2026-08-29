"""Immutable job records shared by queue backends."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pokecrack_worker.config.public_studies import PUBLIC_STUDIES_BY_KEY
from pokecrack_worker.deduplication.fingerprints import content_sha256

_TCGDEX_ETAG_PATTERN = re.compile(r'(?:W/)?"[\x21\x23-\x7e]*"')
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
    """Minimal API fields accepted by the isolated YouTube discovery finalizer."""

    external_id: str
    source_url: str
    title: str | None
    published_at: datetime | None
    collector_version: str
    source_policy_version: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.external_id, str)
            or _YOUTUBE_ID_PATTERN.fullmatch(self.external_id) is None
        ):
            raise ValueError("YouTube external ID is invalid")
        expected_url = f"https://www.youtube.com/watch?v={self.external_id}"
        if self.source_url != expected_url:
            raise ValueError("YouTube source URL must use the exact canonical watch form")
        if self.title is not None and (
            not isinstance(self.title, str)
            or len(self.title) > 500
            or any(unicodedata.category(character).startswith("C") for character in self.title)
        ):
            raise ValueError("YouTube title is invalid")
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
        if self.collector_version != "youtube-global-discovery-v1":
            raise ValueError("YouTube collector version is not approved")
        if self.source_policy_version != "youtube-global-discovery-v1":
            raise ValueError("YouTube source policy version is not approved")

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
            "title": self.title,
            "published_at": published_at,
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
            or len(self.items) > 25
            or any(not isinstance(item, YouTubeSourceItemWrite) for item in self.items)
        ):
            raise ValueError("YouTube completion requires 0 to 25 typed items")
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
class PublicStudyCompletion:
    """Evidence-only result for one immutable reviewed public study."""

    study_key: str
    source_url: str
    title: str
    evidence_excerpt: str
    evidence_sha256: str
    collector_version: str
    parser_version: str
    source_policy_version: str

    def __post_init__(self) -> None:
        identity = PUBLIC_STUDIES_BY_KEY.get(self.study_key)
        if identity is None or self.source_url != identity.source_url:
            raise ValueError("public study identity is not approved")
        if (
            not isinstance(self.title, str)
            or not 1 <= len(self.title) <= 500
            or any(unicodedata.category(character).startswith("C") for character in self.title)
        ):
            raise ValueError("public study title is invalid")
        if (
            not isinstance(self.evidence_excerpt, str)
            or not 1 <= len(self.evidence_excerpt) <= 2_000
            or any(
                unicodedata.category(character) == "Cc" and character not in "\n\t"
                for character in self.evidence_excerpt
            )
        ):
            raise ValueError("public study evidence excerpt is invalid")
        if (
            not isinstance(self.evidence_sha256, str)
            or len(self.evidence_sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.evidence_sha256)
        ):
            raise ValueError("public study evidence hash is invalid")
        if self.evidence_sha256 != content_sha256(self.evidence_excerpt):
            raise ValueError("public study evidence hash does not match the excerpt")
        if self.collector_version != identity.collector_version:
            raise ValueError("public study collector version is not approved")
        if self.parser_version != identity.parser_version:
            raise ValueError("public study parser version is not approved")
        if self.source_policy_version != identity.collector_version:
            raise ValueError("public study source policy version is not approved")

    def as_payload(self) -> dict[str, Any]:
        self.__post_init__()
        return {
            "version": 1,
            "study_key": self.study_key,
            "source_url": self.source_url,
            "title": self.title,
            "evidence_excerpt": self.evidence_excerpt,
            "evidence_sha256": self.evidence_sha256,
            "collector_version": self.collector_version,
            "parser_version": self.parser_version,
            "source_policy_version": self.source_policy_version,
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
