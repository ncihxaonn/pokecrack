"""Generation-fenced PostgreSQL preflights for live official API requests."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from pokecrack_worker.config.public_studies import PUBLIC_STUDY_COVERAGE_KEYS
from pokecrack_worker.jobs import LeaseLostError, QueryExecutor

BEGIN_BLUESKY_JETSTREAM_SQL = """
SELECT *
FROM ingest.begin_bluesky_jetstream_job(
    job_id => %(job_id)s::uuid,
    worker_id => %(worker_id)s,
    lease_generation => %(lease_generation)s::bigint
)
""".strip()

BEGIN_NOSTR_RELAY_SQL = """
SELECT *
FROM ingest.begin_nostr_relay_job(
    job_id => %(job_id)s::uuid,
    worker_id => %(worker_id)s,
    lease_generation => %(lease_generation)s::bigint,
    relay_key => %(relay_key)s
)
""".strip()

BEGIN_TCGDEX_SETS_SQL = """
SELECT *
FROM ingest.begin_tcgdex_sets_job(
    job_id => %(job_id)s::uuid,
    worker_id => %(worker_id)s,
    lease_generation => %(lease_generation)s::bigint
)
""".strip()

BEGIN_YOUTUBE_DISCOVERY_SQL = """
SELECT *
FROM ingest.begin_youtube_discovery_job(
    job_id => %(job_id)s::uuid,
    worker_id => %(worker_id)s,
    lease_generation => %(lease_generation)s::bigint
)
""".strip()

BEGIN_PUBLIC_STUDY_SQL = """
SELECT *
FROM ingest.begin_public_study_job(
    job_id => %(job_id)s::uuid,
    worker_id => %(worker_id)s,
    lease_generation => %(lease_generation)s::bigint
)
""".strip()

BEGIN_PUBLIC_STUDY_COVERAGE_SQL = """
SELECT *
FROM ingest.begin_public_study_job_v2(
    job_id => %(job_id)s::uuid,
    worker_id => %(worker_id)s,
    lease_generation => %(lease_generation)s::bigint,
    study_key => %(study_key)s
)
""".strip()

_TCGDEX_ETAG_PATTERN = re.compile(r'(?:W/)?"[\x21\x23-\x7e]*"')


class TCGdexRequestDeferred(RuntimeError):
    """The shared database request gate is busy; retry without burning an attempt."""

    def __init__(self, retry_at: datetime) -> None:
        if retry_at.tzinfo is None or retry_at.utcoffset() is None:
            raise ValueError("TCGdex retry timestamp must be timezone-aware")
        self.retry_at = retry_at
        super().__init__("TCGdex request gate deferred")


class YouTubeRequestDeferred(RuntimeError):
    """The shared YouTube request gate is busy; retry without burning an attempt."""

    def __init__(self, retry_at: datetime) -> None:
        if retry_at.tzinfo is None or retry_at.utcoffset() is None:
            raise ValueError("YouTube retry timestamp must be timezone-aware")
        self.retry_at = retry_at
        super().__init__("YouTube request gate deferred")


class PublicStudyRequestDeferred(RuntimeError):
    """The reviewed public-study request gate is busy."""

    def __init__(self, retry_at: datetime) -> None:
        if retry_at.tzinfo is None or retry_at.utcoffset() is None:
            raise ValueError("public-study retry timestamp must be timezone-aware")
        self.retry_at = retry_at
        super().__init__("public-study request gate deferred")


class BlueskyRequestDeferred(RuntimeError):
    """The shared Bluesky request gate is busy; retry without burning an attempt."""

    def __init__(self, retry_at: datetime) -> None:
        if retry_at.tzinfo is None or retry_at.utcoffset() is None:
            raise ValueError("Bluesky retry timestamp must be timezone-aware")
        self.retry_at = retry_at
        super().__init__("Bluesky request gate deferred")


class NostrRequestDeferred(RuntimeError):
    def __init__(self, retry_at: datetime) -> None:
        if retry_at.tzinfo is None or retry_at.utcoffset() is None:
            raise ValueError("Nostr retry timestamp must be timezone-aware")
        self.retry_at = retry_at
        super().__init__("Nostr request gate deferred")


@dataclass(frozen=True, slots=True)
class TCGdexSetsCheckpoint:
    etag: str | None
    content_sha256: str | None
    item_count: int
    revision: int

    def __post_init__(self) -> None:
        if self.etag is not None:
            if not isinstance(self.etag, str):
                raise TypeError("TCGdex checkpoint ETag must be text or null")
            if len(self.etag) > 512 or _TCGDEX_ETAG_PATTERN.fullmatch(self.etag) is None:
                raise ValueError("TCGdex checkpoint ETag is invalid")
        if self.content_sha256 is not None and (
            not isinstance(self.content_sha256, str)
            or len(self.content_sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.content_sha256)
        ):
            raise ValueError("TCGdex checkpoint content hash is invalid")
        if (
            isinstance(self.item_count, bool)
            or not isinstance(self.item_count, int)
            or self.item_count < 0
            or self.item_count > 1000
        ):
            raise ValueError("TCGdex checkpoint item count is invalid")
        if (
            isinstance(self.revision, bool)
            or not isinstance(self.revision, int)
            or not 0 <= self.revision <= 9_223_372_036_854_775_806
        ):
            raise ValueError("TCGdex checkpoint revision is invalid")
        if self.revision == 0:
            if self.etag is not None or self.content_sha256 is not None or self.item_count != 0:
                raise ValueError("empty TCGdex checkpoint fields are inconsistent")
        elif self.content_sha256 is None or not 1 <= self.item_count <= 1000:
            raise ValueError("persisted TCGdex checkpoint fields are inconsistent")


class PostgresTCGdexCheckpointRepository:
    def __init__(self, executor: QueryExecutor) -> None:
        self._executor = executor

    def begin(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_generation: int,
    ) -> TCGdexSetsCheckpoint:
        """Authorize one network request under the exact current lease and policy."""

        rows = self._executor.query(
            BEGIN_TCGDEX_SETS_SQL,
            {
                "job_id": job_id,
                "worker_id": worker_id,
                "lease_generation": lease_generation,
            },
        )
        if not rows:
            raise LeaseLostError(job_id)
        row = rows[0]
        acquired = row.get("acquired")
        retry_at = row.get("retry_at")
        if acquired is False:
            if not isinstance(retry_at, datetime):
                raise TypeError("deferred TCGdex preflight requires a retry timestamp")
            raise TCGdexRequestDeferred(retry_at)
        if acquired is not True:
            raise TypeError("TCGdex preflight acquired flag must be boolean")
        if retry_at is not None:
            raise ValueError("acquired TCGdex preflight cannot include a retry timestamp")
        etag = row.get("etag")
        content_sha256 = row.get("content_sha256")
        item_count = row.get("item_count", 0)
        revision = row.get("revision")
        if etag is not None and not isinstance(etag, str):
            raise TypeError("TCGdex checkpoint ETag must be text or null")
        if content_sha256 is not None and not isinstance(content_sha256, str):
            raise TypeError("TCGdex checkpoint content hash must be text or null")
        if isinstance(item_count, bool) or not isinstance(item_count, int):
            raise TypeError("TCGdex checkpoint item count must be an integer")
        if isinstance(revision, bool) or not isinstance(revision, int):
            raise TypeError("TCGdex checkpoint revision must be an integer")
        return TCGdexSetsCheckpoint(
            etag=etag,
            content_sha256=content_sha256,
            item_count=item_count,
            revision=revision,
        )


class PostgresYouTubeDiscoveryGate:
    def __init__(self, executor: QueryExecutor) -> None:
        self._executor = executor

    def begin(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_generation: int,
    ) -> None:
        """Authorize at most one bounded search request under the lease."""

        rows = self._executor.query(
            BEGIN_YOUTUBE_DISCOVERY_SQL,
            {
                "job_id": job_id,
                "worker_id": worker_id,
                "lease_generation": lease_generation,
            },
        )
        if not rows:
            raise LeaseLostError(job_id)
        row = rows[0]
        acquired = row.get("acquired")
        retry_at = row.get("retry_at")
        if acquired is False:
            if not isinstance(retry_at, datetime):
                raise TypeError("deferred YouTube preflight requires a retry timestamp")
            raise YouTubeRequestDeferred(retry_at)
        if acquired is not True:
            raise TypeError("YouTube preflight acquired flag must be boolean")
        if retry_at is not None:
            raise ValueError("acquired YouTube preflight cannot include a retry timestamp")


class PostgresPublicStudyGate:
    def __init__(self, executor: QueryExecutor) -> None:
        self._executor = executor

    def begin(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_generation: int,
        study_key: str,
    ) -> None:
        """Authorize one exact reviewed public page request under the lease."""

        rows = self._executor.query(
            (
                BEGIN_PUBLIC_STUDY_COVERAGE_SQL
                if study_key in PUBLIC_STUDY_COVERAGE_KEYS
                else BEGIN_PUBLIC_STUDY_SQL
            ),
            {
                "job_id": job_id,
                "worker_id": worker_id,
                "lease_generation": lease_generation,
                "study_key": study_key,
            },
        )
        if not rows:
            raise LeaseLostError(job_id)
        row = rows[0]
        acquired = row.get("acquired")
        retry_at = row.get("retry_at")
        if acquired is False:
            if not isinstance(retry_at, datetime):
                raise TypeError("deferred public-study preflight requires a retry timestamp")
            raise PublicStudyRequestDeferred(retry_at)
        if acquired is not True:
            raise TypeError("public-study preflight acquired flag must be boolean")
        if retry_at is not None:
            raise ValueError("acquired public-study preflight cannot include a retry timestamp")


@dataclass(frozen=True, slots=True)
class BlueskyJetstreamCheckpoint:
    """Cursor returned by the fenced Bluesky request gate."""

    start_cursor: int | None


class PostgresBlueskyJetstreamGate:
    def __init__(self, executor: QueryExecutor) -> None:
        self._executor = executor

    def begin(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_generation: int,
    ) -> BlueskyJetstreamCheckpoint:
        rows = self._executor.query(
            BEGIN_BLUESKY_JETSTREAM_SQL,
            {
                "job_id": job_id,
                "worker_id": worker_id,
                "lease_generation": lease_generation,
            },
        )
        if not rows:
            raise LeaseLostError(job_id)
        row = rows[0]
        acquired = row.get("acquired")
        retry_at = row.get("retry_at")
        if acquired is False:
            if not isinstance(retry_at, datetime):
                raise TypeError("deferred Bluesky preflight requires a retry timestamp")
            raise BlueskyRequestDeferred(retry_at)
        if acquired is not True:
            raise TypeError("Bluesky preflight acquired flag must be boolean")
        if retry_at is not None:
            raise ValueError("acquired Bluesky preflight cannot include a retry timestamp")
        raw_cursor = row.get("start_cursor", row.get("cursor", row.get("last_cursor")))
        if raw_cursor is None:
            return BlueskyJetstreamCheckpoint(start_cursor=None)
        if isinstance(raw_cursor, bool):
            raise TypeError("Bluesky checkpoint cursor must be a nonnegative integer")
        if isinstance(raw_cursor, str):
            if not raw_cursor or not raw_cursor.isascii() or not raw_cursor.isdecimal():
                raise TypeError("Bluesky checkpoint cursor must be a nonnegative integer")
            if raw_cursor != "0" and raw_cursor.startswith("0"):
                raise ValueError("Bluesky checkpoint cursor must use canonical decimal text")
            raw_cursor = int(raw_cursor)
        if not isinstance(raw_cursor, int) or not 0 <= raw_cursor <= 9_223_372_036_854_775_807:
            raise ValueError("Bluesky checkpoint cursor is outside the approved range")
        return BlueskyJetstreamCheckpoint(start_cursor=raw_cursor)


@dataclass(frozen=True, slots=True)
class NostrRelayCheckpoint:
    since: datetime
    until: datetime
    checkpoint: datetime | None
    recent_candidate_ids: tuple[str, ...]


class PostgresNostrRelayGate:
    def __init__(self, executor: QueryExecutor) -> None:
        self._executor = executor

    def begin(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_generation: int,
        relay_key: str,
    ) -> NostrRelayCheckpoint:
        rows = self._executor.query(
            BEGIN_NOSTR_RELAY_SQL,
            {
                "job_id": job_id,
                "worker_id": worker_id,
                "lease_generation": lease_generation,
                "relay_key": relay_key,
            },
        )
        if not rows:
            raise LeaseLostError(job_id)
        row = rows[0]
        acquired = row.get("acquired")
        retry_at = row.get("retry_at")
        if acquired is False:
            if not isinstance(retry_at, datetime):
                raise TypeError("deferred Nostr preflight requires a retry timestamp")
            raise NostrRequestDeferred(retry_at)
        if acquired is not True or retry_at is not None:
            raise TypeError("Nostr preflight returned an invalid acquisition state")
        since = row.get("since")
        until = row.get("until")
        checkpoint = row.get("checkpoint")
        for name, value in (("since", since), ("until", until)):
            if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
                raise TypeError(f"Nostr {name} must be a timezone-aware timestamp")
        if checkpoint is not None and (
            not isinstance(checkpoint, datetime)
            or checkpoint.tzinfo is None
            or checkpoint.utcoffset() is None
        ):
            raise TypeError("Nostr checkpoint must be a timezone-aware timestamp or null")
        raw_ids = row.get("recent_candidate_ids")
        if not isinstance(raw_ids, list) or len(raw_ids) > 100:
            raise TypeError("Nostr recent candidate IDs must be a bounded JSON array")
        candidate_ids: list[str] = []
        for value in raw_ids:
            if (
                not isinstance(value, str)
                or len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
            ):
                raise TypeError("Nostr recent candidate ID is invalid")
            candidate_ids.append(value)
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("Nostr recent candidate IDs must be unique")
        assert isinstance(since, datetime)
        assert isinstance(until, datetime)
        return NostrRelayCheckpoint(
            since=since,
            until=until,
            checkpoint=checkpoint,
            recent_candidate_ids=tuple(candidate_ids),
        )
