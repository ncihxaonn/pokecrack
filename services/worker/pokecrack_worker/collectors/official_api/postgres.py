"""Generation-fenced PostgreSQL preflights for live official API requests."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from pokecrack_worker.jobs import LeaseLostError, QueryExecutor

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
    ) -> None:
        """Authorize one exact reviewed public page request under the lease."""

        rows = self._executor.query(
            BEGIN_PUBLIC_STUDY_SQL,
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
                raise TypeError("deferred public-study preflight requires a retry timestamp")
            raise PublicStudyRequestDeferred(retry_at)
        if acquired is not True:
            raise TypeError("public-study preflight acquired flag must be boolean")
        if retry_at is not None:
            raise ValueError("acquired public-study preflight cannot include a retry timestamp")
