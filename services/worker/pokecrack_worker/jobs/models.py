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
_BLUESKY_AT_URI_PATTERN = re.compile(
    r"^at://did:[a-z0-9]+:[A-Za-z0-9._:%-]{1,240}/app\.bsky\.feed\.post/"
    r"[A-Za-z0-9._:%~-]{1,240}$"
)
_BLUESKY_PUBLIC_URL_PATTERN = re.compile(
    r"^https://bsky\.app/profile/did:[a-z0-9]+:[A-Za-z0-9._:%-]{1,240}/post/"
    r"[A-Za-z0-9._:%~-]{1,240}$"
)
_BLUESKY_MAX_CURSOR = 9_223_372_036_854_775_807
_BLUESKY_MAX_CANDIDATES = 100
_BLUESKY_MAX_DELETIONS = 100
_BLUESKY_MAX_EVENTS = 10_000
_BLUESKY_MAX_STREAM_BYTES = 2 * 1024 * 1024
_BLUESKY_MAX_EXCERPT_CHARS = 500
_NOSTR_RELAY_KEYS = frozenset({"primal", "nos_lol", "nostr_net"})
_NOSTR_MATCHED_TAGS = frozenset(
    {
        "pokemontcg",
        "pokemoncards",
        "ポケカ",
        "ポケモンカード",
        "포켓몬카드",
        "宝可梦卡牌",
        "寶可夢卡牌",
    }
)
_NOSTR_MAX_EVENTS = 100
_NOSTR_MAX_STREAM_BYTES = 2 * 1024 * 1024
_NOSTR_MAX_ITEMS = 100


def _lower_hex(value: object, *, length: int, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{field} must be {length} lowercase hexadecimal characters")
    return value


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


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


def _bluesky_cursor(value: object, *, field: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"Bluesky {field} must be a nonnegative integer")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and value and value.isascii() and value.isdecimal():
        if value != "0" and value.startswith("0"):
            raise ValueError(f"Bluesky {field} must use canonical decimal text")
        parsed = int(value)
    else:
        raise TypeError(f"Bluesky {field} must be a nonnegative integer")
    if not 0 <= parsed <= _BLUESKY_MAX_CURSOR:
        raise ValueError(f"Bluesky {field} is outside the approved range")
    return parsed


@dataclass(frozen=True, slots=True)
class BlueskySourceItemWrite:
    """Minimal activity fields accepted by the isolated Jetstream finalizer."""

    cursor: int | str
    at_uri: str
    public_url: str
    text_excerpt: str | None
    record_sha256: str
    published_at: datetime | None

    def __post_init__(self) -> None:
        parsed_cursor = _bluesky_cursor(self.cursor, field="candidate cursor")
        object.__setattr__(self, "cursor", parsed_cursor)
        if _BLUESKY_AT_URI_PATTERN.fullmatch(self.at_uri) is None:
            raise ValueError("Bluesky AT URI is invalid")
        if _BLUESKY_PUBLIC_URL_PATTERN.fullmatch(self.public_url) is None:
            raise ValueError("Bluesky public URL is invalid")
        at_parts = self.at_uri.removeprefix("at://").split("/", 2)
        expected_url = f"https://bsky.app/profile/{at_parts[0]}/post/{at_parts[2].split('/')[-1]}"
        if self.public_url != expected_url:
            raise ValueError("Bluesky public URL does not match the AT URI")
        if self.text_excerpt is not None:
            if (
                not isinstance(self.text_excerpt, str)
                or not 1 <= len(self.text_excerpt) <= _BLUESKY_MAX_EXCERPT_CHARS
                or any(
                    unicodedata.category(character) == "Cc" and character not in "\n\t"
                    for character in self.text_excerpt
                )
            ):
                raise ValueError("Bluesky text excerpt is invalid")
        if (
            not isinstance(self.record_sha256, str)
            or len(self.record_sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.record_sha256)
        ):
            raise ValueError("Bluesky record SHA-256 must be lowercase hexadecimal")
        if self.published_at is not None and (
            not isinstance(self.published_at, datetime)
            or self.published_at.tzinfo is None
            or self.published_at.utcoffset() is None
        ):
            raise ValueError("Bluesky published_at must be timezone-aware or null")

    def as_payload(self) -> dict[str, Any]:
        self.__post_init__()
        published_at = (
            self.published_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
            if self.published_at is not None
            else None
        )
        return {
            "cursor": self.cursor,
            "at_uri": self.at_uri,
            "public_url": self.public_url,
            "text_excerpt": self.text_excerpt,
            "record_sha256": self.record_sha256,
            "published_at": published_at,
        }


@dataclass(frozen=True, slots=True)
class BlueskyDeletionWrite:
    at_uri: str
    cursor: int | str

    def __post_init__(self) -> None:
        if _BLUESKY_AT_URI_PATTERN.fullmatch(self.at_uri) is None:
            raise ValueError("Bluesky deletion AT URI is invalid")
        parsed = _bluesky_cursor(self.cursor, field="deletion cursor")
        object.__setattr__(self, "cursor", parsed)

    def as_payload(self) -> dict[str, Any]:
        self.__post_init__()
        return {"at_uri": self.at_uri, "cursor": self.cursor}


@dataclass(frozen=True, slots=True)
class BlueskyJetstreamCompletion:
    """Bounded atomic persistence input for one Jetstream stream slice."""

    start_cursor: int | str | None
    end_cursor: int | str | None
    events_seen: int
    bytes_seen: int
    candidates: tuple[BlueskySourceItemWrite, ...] = ()
    deletions: tuple[BlueskyDeletionWrite, ...] = ()

    def __post_init__(self) -> None:
        start = (
            _bluesky_cursor(self.start_cursor, field="start_cursor")
            if self.start_cursor is not None
            else None
        )
        end = (
            _bluesky_cursor(self.end_cursor, field="end_cursor")
            if self.end_cursor is not None
            else None
        )
        if start is not None:
            object.__setattr__(self, "start_cursor", start)
        if end is not None:
            object.__setattr__(self, "end_cursor", end)
        if start is not None and end is not None and end < start:
            raise ValueError("Bluesky end cursor must not precede start cursor")
        if (
            isinstance(self.events_seen, bool)
            or not isinstance(self.events_seen, int)
            or not 0 <= self.events_seen <= _BLUESKY_MAX_EVENTS
        ):
            raise ValueError("Bluesky events_seen is outside the approved range")
        if (
            isinstance(self.bytes_seen, bool)
            or not isinstance(self.bytes_seen, int)
            or not 0 <= self.bytes_seen <= _BLUESKY_MAX_STREAM_BYTES
        ):
            raise ValueError("Bluesky bytes_seen is outside the approved range")
        if (
            not isinstance(self.candidates, tuple)
            or len(self.candidates) > _BLUESKY_MAX_CANDIDATES
            or any(not isinstance(item, BlueskySourceItemWrite) for item in self.candidates)
        ):
            raise ValueError("Bluesky completion requires 0 to 100 typed candidates")
        if (
            not isinstance(self.deletions, tuple)
            or len(self.deletions) > _BLUESKY_MAX_DELETIONS
            or any(not isinstance(item, BlueskyDeletionWrite) for item in self.deletions)
        ):
            raise ValueError("Bluesky completion requires 0 to 100 typed deletions")
        candidate_ids = [item.at_uri for item in self.candidates]
        deletion_ids = [item.at_uri for item in self.deletions]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("Bluesky candidate AT URIs must be unique")
        if len(deletion_ids) != len(set(deletion_ids)):
            raise ValueError("Bluesky deletion AT URIs must be unique")

    def as_payload(self) -> dict[str, Any]:
        self.__post_init__()
        return {
            "version": "1.0.0",
            "start_cursor": self.start_cursor,
            "end_cursor": self.end_cursor,
            "events_seen": self.events_seen,
            "bytes_seen": self.bytes_seen,
            "candidates": [item.as_payload() for item in self.candidates],
            "deletions": [item.as_payload() for item in self.deletions],
        }


# Short aliases keep collector and repository call sites readable while the
# persisted DTO names remain explicit about their source boundary.
BlueskyCandidateWrite = BlueskySourceItemWrite
BlueskyDeletion = BlueskyDeletionWrite


@dataclass(frozen=True, slots=True)
class NostrCandidateWrite:
    event_id: str
    author_sha256: str
    published_at: datetime
    content_sha256: str
    matched_tags: tuple[str, ...]
    relay_key: str

    def __post_init__(self) -> None:
        _lower_hex(self.event_id, length=64, field="Nostr event ID")
        _lower_hex(self.author_sha256, length=64, field="Nostr author hash")
        _lower_hex(self.content_sha256, length=64, field="Nostr content hash")
        if self.relay_key not in _NOSTR_RELAY_KEYS:
            raise ValueError("Nostr relay key is not approved")
        if (
            not isinstance(self.published_at, datetime)
            or self.published_at.tzinfo is None
            or self.published_at.utcoffset() is None
        ):
            raise ValueError("Nostr published_at must be timezone-aware")
        if (
            not isinstance(self.matched_tags, tuple)
            or not 1 <= len(self.matched_tags) <= len(_NOSTR_MATCHED_TAGS)
            or len(self.matched_tags) != len(set(self.matched_tags))
            or any(tag not in _NOSTR_MATCHED_TAGS for tag in self.matched_tags)
        ):
            raise ValueError("Nostr matched tags are invalid")

    def as_payload(self) -> dict[str, Any]:
        self.__post_init__()
        return {
            "event_id": self.event_id,
            "author_sha256": self.author_sha256,
            "published_at": _utc_text(self.published_at),
            "content_sha256": self.content_sha256,
            "matched_tags": list(self.matched_tags),
            "relay_key": self.relay_key,
            "activity_only": True,
            "statistics_eligible": False,
        }


@dataclass(frozen=True, slots=True)
class NostrDeletionWrite:
    event_id: str
    author_sha256: str
    published_at: datetime
    relay_key: str
    target_event_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _lower_hex(self.event_id, length=64, field="Nostr deletion event ID")
        _lower_hex(self.author_sha256, length=64, field="Nostr deletion author hash")
        if self.relay_key not in _NOSTR_RELAY_KEYS:
            raise ValueError("Nostr relay key is not approved")
        if (
            not isinstance(self.published_at, datetime)
            or self.published_at.tzinfo is None
            or self.published_at.utcoffset() is None
        ):
            raise ValueError("Nostr deletion published_at must be timezone-aware")
        if (
            not isinstance(self.target_event_ids, tuple)
            or not 1 <= len(self.target_event_ids) <= 16
            or len(self.target_event_ids) != len(set(self.target_event_ids))
        ):
            raise ValueError("Nostr deletion targets are invalid")
        for target in self.target_event_ids:
            _lower_hex(target, length=64, field="Nostr deletion target")

    def as_payload(self) -> dict[str, Any]:
        self.__post_init__()
        return {
            "event_id": self.event_id,
            "author_sha256": self.author_sha256,
            "published_at": _utc_text(self.published_at),
            "kind": 5,
            "relay_key": self.relay_key,
            "target_event_ids": list(self.target_event_ids),
        }


@dataclass(frozen=True, slots=True)
class NostrRelayCompletion:
    relay_key: str
    since: datetime
    until: datetime
    checkpoint: datetime | None
    incomplete: bool
    events_seen: int
    bytes_seen: int
    candidates: tuple[NostrCandidateWrite, ...] = ()
    deletions: tuple[NostrDeletionWrite, ...] = ()

    def __post_init__(self) -> None:
        if self.relay_key not in _NOSTR_RELAY_KEYS:
            raise ValueError("Nostr relay key is not approved")
        for name, value in (("since", self.since), ("until", self.until)):
            if (
                not isinstance(value, datetime)
                or value.tzinfo is None
                or value.utcoffset() is None
            ):
                raise ValueError(f"Nostr {name} must be timezone-aware")
        if self.since >= self.until:
            raise ValueError("Nostr collection window must be ordered")
        if self.checkpoint is not None and (
            not isinstance(self.checkpoint, datetime)
            or self.checkpoint.tzinfo is None
            or self.checkpoint.utcoffset() is None
        ):
            raise ValueError("Nostr checkpoint must be timezone-aware or null")
        if self.incomplete is not False:
            raise ValueError("Nostr completion cannot advance an incomplete slice")
        if (
            isinstance(self.events_seen, bool)
            or not isinstance(self.events_seen, int)
            or not 0 <= self.events_seen <= _NOSTR_MAX_EVENTS
        ):
            raise ValueError("Nostr events_seen is outside the approved range")
        if (
            isinstance(self.bytes_seen, bool)
            or not isinstance(self.bytes_seen, int)
            or not 0 <= self.bytes_seen <= _NOSTR_MAX_STREAM_BYTES
        ):
            raise ValueError("Nostr bytes_seen is outside the approved range")
        if (
            not isinstance(self.candidates, tuple)
            or len(self.candidates) > _NOSTR_MAX_ITEMS
            or any(not isinstance(item, NostrCandidateWrite) for item in self.candidates)
        ):
            raise ValueError("Nostr candidates are invalid")
        if (
            not isinstance(self.deletions, tuple)
            or len(self.deletions) > _NOSTR_MAX_ITEMS
            or any(not isinstance(item, NostrDeletionWrite) for item in self.deletions)
        ):
            raise ValueError("Nostr deletions are invalid")
        if any(item.relay_key != self.relay_key for item in self.candidates) or any(
            item.relay_key != self.relay_key for item in self.deletions
        ):
            raise ValueError("Nostr item relay key must match its completion")
        event_ids = [item.event_id for item in self.candidates] + [
            item.event_id for item in self.deletions
        ]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("Nostr completion event IDs must be unique")
        if len(event_ids) > self.events_seen:
            raise ValueError("Nostr completion items cannot exceed events_seen")

    def as_payload(self) -> dict[str, Any]:
        self.__post_init__()
        return {
            "version": "1.0.0",
            "relay_key": self.relay_key,
            "since": _utc_text(self.since),
            "until": _utc_text(self.until),
            "checkpoint": _utc_text(self.checkpoint) if self.checkpoint is not None else None,
            "incomplete": self.incomplete,
            "events_seen": self.events_seen,
            "bytes_seen": self.bytes_seen,
            "candidates": [item.as_payload() for item in self.candidates],
            "deletions": [item.as_payload() for item in self.deletions],
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
