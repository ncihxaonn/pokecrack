"""PostgreSQL job repository using one-statement atomic claims."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any, Protocol

from pokecrack_worker.config.public_studies import PUBLIC_STUDY_COVERAGE_KEYS

from .models import (
    BlueskyCursorRecoveryCompletion,
    BlueskyJetstreamCompletion,
    CompletionEffect,
    Job,
    JobStatus,
    MastodonPublicHashtagCompletion,
    NostrRelayCompletion,
    PublicStudyCompletion,
    TCGdexSetsSyncCompletion,
    YouTubeDiscoveryCompletion,
)
from .repository import LeaseLostError


def _is_public_study_coverage_key(study_key: object) -> bool:
    """Keep enqueue and completion routing on the reviewed coverage allowlist."""

    return isinstance(study_key, str) and study_key in PUBLIC_STUDY_COVERAGE_KEYS


class QueryExecutor(Protocol):
    """Small injectable contract used by psycopg and deterministic tests."""

    def query(self, sql: str, params: Mapping[str, object]) -> Sequence[Mapping[str, Any]]: ...


ENQUEUE_SQL = """
SELECT *
FROM ingest.enqueue_job_v1(
    %(kind)s,
    %(payload)s::jsonb,
    %(priority)s,
    %(dedupe_key)s,
    %(available_at)s,
    %(max_attempts)s
)
""".strip()

CLAIM_SQL = """
SELECT *
FROM ingest.claim_jobs_v2(
    worker_id => %(worker_id)s,
    job_types => %(kinds)s::text[],
    batch_size => 1,
    lease_seconds => %(lease_seconds)s
)
""".strip()

# Nostr workers use fixed, source-scoped queue wrappers.  They deliberately do
# not accept a caller-provided job-type array: the database function owns the
# ``source.nostr.relay`` allowlist as well as the role boundary.
NOSTR_JOB_TYPE = "source.nostr.relay"
BLUESKY_JOB_TYPE = "source.bluesky.jetstream"

NOSTR_CLAIM_SQL = """
WITH due_jobs AS MATERIALIZED (
    SELECT ingest.enqueue_due_nostr_relay_jobs_v1(
        p_worker_id => %(worker_id)s
    ) AS scheduled_count
)
SELECT claimed.*
FROM due_jobs
CROSS JOIN LATERAL ingest.claim_nostr_relay_jobs_v1(
    p_worker_id => %(worker_id)s,
    p_lease_seconds => %(lease_seconds)s::integer
) AS claimed
WHERE due_jobs.scheduled_count = 3
""".strip()

# Bluesky workers use fixed, source-scoped queue wrappers. They deliberately
# do not accept a caller-provided job-type array: the database function owns
# the ``source.bluesky.jetstream`` allowlist and current-minute schedule.
BLUESKY_CLAIM_SQL = """
WITH due_jobs AS MATERIALIZED (
    SELECT ingest.enqueue_due_bluesky_jetstream_jobs_v1(
        p_worker_id => %(worker_id)s
    ) AS scheduled_count
)
SELECT claimed.*
FROM due_jobs
CROSS JOIN LATERAL ingest.claim_bluesky_jetstream_jobs_v1(
    p_worker_id => %(worker_id)s,
    p_lease_seconds => %(lease_seconds)s::integer
) AS claimed
WHERE due_jobs.scheduled_count = 1
""".strip()

ENQUEUE_SCHEDULED_SQL = """
SELECT *
FROM ingest.enqueue_scheduled_job_v1(
    %(schedule_name)s,
    %(scheduled_for)s,
    %(kind)s,
    %(payload)s::jsonb,
    %(priority)s,
    %(max_attempts)s
)
""".strip()

ENQUEUE_PUBLIC_STUDY_COVERAGE_SQL = """
SELECT *
FROM ingest.enqueue_public_study_coverage_job_v1(
    %(study_key)s,
    %(priority)s,
    %(dedupe_key)s,
    %(available_at)s,
    %(max_attempts)s
)
""".strip()

ENQUEUE_SCHEDULED_PUBLIC_STUDY_COVERAGE_SQL = """
SELECT *
FROM ingest.enqueue_scheduled_public_study_coverage_job_v1(
    %(schedule_name)s,
    %(scheduled_for)s,
    %(study_key)s,
    %(priority)s,
    %(max_attempts)s
)
""".strip()


HEARTBEAT_SQL = """
SELECT *
FROM ingest.heartbeat_job_v2(
    job_id => %(job_id)s::uuid,
    worker_id => %(worker_id)s,
    lease_generation => %(lease_generation)s::bigint,
    lease_seconds => %(lease_seconds)s::integer
)
""".strip()

NOSTR_HEARTBEAT_SQL = """
SELECT *
FROM ingest.heartbeat_nostr_relay_job_v1(
    p_job_id => %(job_id)s::uuid,
    p_worker_id => %(worker_id)s,
    p_lease_generation => %(lease_generation)s::bigint,
    p_lease_seconds => %(lease_seconds)s::integer
)
""".strip()

BLUESKY_HEARTBEAT_SQL = """
SELECT *
FROM ingest.heartbeat_bluesky_jetstream_job_v1(
    p_job_id => %(job_id)s::uuid,
    p_worker_id => %(worker_id)s,
    p_lease_generation => %(lease_generation)s::bigint,
    p_lease_seconds => %(lease_seconds)s::integer
)
""".strip()

FAIL_SQL = """
SELECT *
FROM ingest.fail_job_v2(
    job_id => %(job_id)s::uuid,
    worker_id => %(worker_id)s,
    lease_generation => %(lease_generation)s::bigint,
    error_code => %(error_code)s,
    error_message => %(error_message)s,
    retryable => %(retryable)s::boolean
)
""".strip()

NOSTR_FAIL_SQL = """
SELECT *
FROM ingest.fail_nostr_relay_job_v1(
    p_job_id => %(job_id)s::uuid,
    p_worker_id => %(worker_id)s,
    p_lease_generation => %(lease_generation)s::bigint,
    p_error_code => %(error_code)s,
    p_error_message => %(error_message)s,
    p_retryable => %(retryable)s::boolean
)
""".strip()

BLUESKY_FAIL_SQL = """
SELECT *
FROM ingest.fail_bluesky_jetstream_job_v1(
    p_job_id => %(job_id)s::uuid,
    p_worker_id => %(worker_id)s,
    p_lease_generation => %(lease_generation)s::bigint,
    p_error_code => %(error_code)s,
    p_error_message => %(error_message)s,
    p_retryable => %(retryable)s::boolean
)
""".strip()

COMPLETE_SQL = """
SELECT *
FROM ingest.complete_job_v2(
    %(job_id)s::uuid,
    %(worker_id)s,
    %(lease_generation)s::bigint
)
""".strip()

FINALIZE_CLEANUP_SQL = """
SELECT *
FROM ingest.finalize_cleanup_job(
    job_id => %(job_id)s::uuid,
    worker_id => %(worker_id)s,
    lease_generation => %(lease_generation)s::bigint
)
""".strip()

FINALIZE_TCGDEX_SETS_SQL = """
SELECT *
FROM ingest.finalize_tcgdex_sets_job(
    job_id => %(job_id)s::uuid,
    worker_id => %(worker_id)s,
    lease_generation => %(lease_generation)s::bigint,
    result => %(result)s::jsonb
)
""".strip()

FINALIZE_YOUTUBE_DISCOVERY_SQL = """
SELECT *
FROM ingest.finalize_youtube_discovery_job(
    job_id => %(job_id)s::uuid,
    worker_id => %(worker_id)s,
    lease_generation => %(lease_generation)s::bigint,
    result => %(result)s::jsonb
)
""".strip()

FINALIZE_PUBLIC_STUDY_SQL = """
SELECT *
FROM ingest.finalize_public_study_job(
    job_id => %(job_id)s::uuid,
    worker_id => %(worker_id)s,
    lease_generation => %(lease_generation)s::bigint,
    result => %(result)s::jsonb
)
""".strip()

FINALIZE_PUBLIC_STUDY_COVERAGE_SQL = """
SELECT *
FROM ingest.finalize_public_study_coverage_job_v1(
    job_id => %(job_id)s::uuid,
    worker_id => %(worker_id)s,
    lease_generation => %(lease_generation)s::bigint,
    study_key => %(study_key)s,
    result => %(result)s::jsonb
)
""".strip()

FINALIZE_BLUESKY_JETSTREAM_SQL = """
SELECT *
FROM ingest.finalize_bluesky_jetstream_job_v1(
    job_id => %(job_id)s::uuid,
    worker_id => %(worker_id)s,
    lease_generation => %(lease_generation)s::bigint,
    result => %(result)s::jsonb
)
""".strip()

RECOVER_BLUESKY_CURSOR_TOO_OLD_SQL = """
SELECT *
FROM ingest.recover_bluesky_cursor_too_old_job_v2(
    job_id => %(job_id)s::uuid,
    worker_id => %(worker_id)s,
    lease_generation => %(lease_generation)s::bigint,
    expected_start_cursor => %(start_cursor)s::bigint
)
""".strip()

FINALIZE_NOSTR_RELAY_SQL = """
SELECT *
FROM ingest.finalize_nostr_relay_job(
    job_id => %(job_id)s::uuid,
    worker_id => %(worker_id)s,
    lease_generation => %(lease_generation)s::bigint,
    result => %(result)s::jsonb
)
""".strip()

FINALIZE_MASTODON_PUBLIC_HASHTAG_SQL = """
SELECT *
FROM ingest.finalize_mastodon_public_hashtag_job(
    job_id => %(job_id)s::uuid,
    worker_id => %(worker_id)s,
    lease_generation => %(lease_generation)s::bigint,
    result => %(result)s::jsonb
)
""".strip()

PAUSE_BUDGET_SQL = """
SELECT *
FROM ingest.pause_job_for_budget_v2(
    %(job_id)s::uuid,
    %(worker_id)s,
    %(lease_generation)s::bigint,
    %(retry_at)s
)
""".strip()

NOSTR_PAUSE_BUDGET_SQL = """
SELECT *
FROM ingest.pause_nostr_relay_job_v1(
    p_job_id => %(job_id)s::uuid,
    p_worker_id => %(worker_id)s,
    p_lease_generation => %(lease_generation)s::bigint,
    p_retry_at => %(retry_at)s::timestamptz
)
""".strip()

BLUESKY_PAUSE_BUDGET_SQL = """
SELECT *
FROM ingest.pause_bluesky_jetstream_job_v1(
    p_job_id => %(job_id)s::uuid,
    p_worker_id => %(worker_id)s,
    p_lease_generation => %(lease_generation)s::bigint,
    p_retry_at => %(retry_at)s::timestamptz
)
""".strip()

_COMPLETION_EFFECT_SQL: Mapping[CompletionEffect, str] = {
    CompletionEffect.PRUNE_EXPIRED_EPHEMERA: FINALIZE_CLEANUP_SQL,
}


_STORAGE_TO_RUNTIME = {
    "pending": JobStatus.PENDING,
    "running": JobStatus.RUNNING,
    "completed": JobStatus.COMPLETED,
    "failed": JobStatus.FAILED,
    "dead": JobStatus.DEAD,
    "cancelled": JobStatus.CANCELLED,
}


def job_from_row(row: Mapping[str, Any]) -> Job:
    status = _STORAGE_TO_RUNTIME[str(row["status"])]
    error_message = row.get("last_error_message")
    error_code = row.get("last_error_code")
    return Job(
        id=str(row["id"]),
        kind=str(row.get("job_type", row.get("kind"))),
        payload=dict(row.get("payload") or {}),
        status=status,
        priority=int(row.get("priority", 0)),
        available_at=row["available_at"],
        attempts=int(row.get("attempts", 0)),
        max_attempts=int(row.get("max_attempts", 5)),
        lease_generation=int(row["lease_generation"]),
        leased_by=row.get("locked_by"),
        leased_at=row.get("locked_at"),
        lease_expires_at=row.get("lock_expires_at"),
        heartbeat_at=row.get("updated_at") if status is JobStatus.RUNNING else None,
        last_error=(
            str(error_message)
            if error_message is not None
            else str(error_code)
            if error_code is not None
            else None
        ),
        finished_at=row.get("completed_at"),
        dedupe_key=row.get("dedupe_key"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class PostgresJobRepository:
    """Queue adapter whose claim remains atomic across worker processes."""

    def __init__(self, executor: QueryExecutor) -> None:
        self._executor = executor

    def enqueue(
        self,
        kind: str,
        payload: Mapping[str, Any] | None = None,
        *,
        priority: int = 0,
        now: datetime,
        max_attempts: int = 5,
        dedupe_key: str | None = None,
        available_at: datetime | None = None,
    ) -> Job:
        job_payload = dict(payload or {})
        coverage_study_key = job_payload.get("study_key")
        coverage_enqueue = (
            kind == "source.public_study.opening"
            and set(job_payload) == {"study_key"}
            and _is_public_study_coverage_key(coverage_study_key)
        )
        if coverage_enqueue:
            sql = ENQUEUE_PUBLIC_STUDY_COVERAGE_SQL
            params: dict[str, object] = {
                "study_key": coverage_study_key,
                "priority": priority,
                "dedupe_key": dedupe_key,
                "available_at": available_at or now,
                "max_attempts": max_attempts,
            }
        else:
            sql = ENQUEUE_SQL
            params = {
                "kind": kind,
                "payload": json.dumps(job_payload, separators=(",", ":")),
                "priority": priority,
                "dedupe_key": dedupe_key,
                "available_at": available_at or now,
                "max_attempts": max_attempts,
            }
        rows = self._executor.query(sql, params)
        if not rows:
            raise RuntimeError("job enqueue returned no row")
        return job_from_row(rows[0])

    def enqueue_scheduled(
        self,
        kind: str,
        payload: Mapping[str, Any] | None = None,
        *,
        schedule_name: str,
        scheduled_for: datetime,
        priority: int = 0,
        now: datetime,
        max_attempts: int = 5,
    ) -> Job:
        del now
        job_payload = dict(payload or {})
        coverage_study_key = job_payload.get("study_key")
        coverage_enqueue = (
            kind == "source.public_study.opening"
            and set(job_payload) == {"study_key"}
            and _is_public_study_coverage_key(coverage_study_key)
        )
        if coverage_enqueue:
            sql = ENQUEUE_SCHEDULED_PUBLIC_STUDY_COVERAGE_SQL
            params = {
                "schedule_name": schedule_name,
                "scheduled_for": scheduled_for,
                "study_key": coverage_study_key,
                "priority": priority,
                "max_attempts": max_attempts,
            }
        else:
            sql = ENQUEUE_SCHEDULED_SQL
            params = {
                "schedule_name": schedule_name,
                "scheduled_for": scheduled_for,
                "kind": kind,
                "payload": json.dumps(job_payload, separators=(",", ":")),
                "priority": priority,
                "max_attempts": max_attempts,
            }
        rows = self._executor.query(sql, params)
        if not rows:
            raise RuntimeError("scheduled job enqueue returned no row")
        return job_from_row(rows[0])

    def lease(
        self,
        worker_id: str,
        *,
        now: datetime,
        lease_for: timedelta,
        kinds: set[str] | None = None,
    ) -> Job | None:
        del now
        lease_seconds = int(lease_for.total_seconds())
        if lease_for != timedelta(seconds=lease_seconds) or not 1 <= lease_seconds <= 86_400:
            raise ValueError("lease_for must be a whole number of seconds between 1 and 86400")
        rows = self._executor.query(
            CLAIM_SQL,
            {
                "worker_id": worker_id,
                "lease_seconds": lease_seconds,
                "kinds": sorted(kinds) if kinds else None,
            },
        )
        return job_from_row(rows[0]) if rows else None

    def heartbeat(
        self,
        job_id: str,
        *,
        worker_id: str,
        lease_generation: int,
        now: datetime,
        lease_for: timedelta,
    ) -> Job:
        del now
        lease_seconds = int(lease_for.total_seconds())
        if lease_for != timedelta(seconds=lease_seconds) or not 1 <= lease_seconds <= 86_400:
            raise ValueError("lease_for must be a whole number of seconds between 1 and 86400")
        rows = self._executor.query(
            HEARTBEAT_SQL,
            {
                "job_id": job_id,
                "worker_id": worker_id,
                "lease_generation": lease_generation,
                "lease_seconds": lease_seconds,
            },
        )
        if not rows:
            raise LeaseLostError(job_id)
        return job_from_row(rows[0])

    def complete(
        self,
        job_id: str,
        *,
        worker_id: str,
        lease_generation: int,
        now: datetime,
        effect: CompletionEffect
        | PublicStudyCompletion
        | TCGdexSetsSyncCompletion
        | YouTubeDiscoveryCompletion
        | BlueskyJetstreamCompletion
        | BlueskyCursorRecoveryCompletion
        | NostrRelayCompletion
        | MastodonPublicHashtagCompletion
        | None = None,
    ) -> Job:
        del now
        params: dict[str, object] = {
            "job_id": job_id,
            "worker_id": worker_id,
            "lease_generation": lease_generation,
        }
        sql: str | None
        if effect is None:
            sql = COMPLETE_SQL
        elif isinstance(effect, TCGdexSetsSyncCompletion):
            sql = FINALIZE_TCGDEX_SETS_SQL
            params["result"] = json.dumps(
                effect.as_payload(), separators=(",", ":"), sort_keys=True
            )
        elif isinstance(effect, YouTubeDiscoveryCompletion):
            sql = FINALIZE_YOUTUBE_DISCOVERY_SQL
            params["result"] = json.dumps(
                effect.as_payload(), separators=(",", ":"), sort_keys=True
            )
        elif isinstance(effect, PublicStudyCompletion):
            sql = (
                FINALIZE_PUBLIC_STUDY_COVERAGE_SQL
                if _is_public_study_coverage_key(effect.study_key)
                else FINALIZE_PUBLIC_STUDY_SQL
            )
            params["study_key"] = effect.study_key
            params["result"] = json.dumps(
                effect.as_payload(), separators=(",", ":"), sort_keys=True
            )
        elif isinstance(effect, BlueskyJetstreamCompletion):
            sql = FINALIZE_BLUESKY_JETSTREAM_SQL
            params["result"] = json.dumps(
                effect.as_payload(), separators=(",", ":"), sort_keys=True
            )
        elif isinstance(effect, BlueskyCursorRecoveryCompletion):
            sql = RECOVER_BLUESKY_CURSOR_TOO_OLD_SQL
            params["start_cursor"] = effect.start_cursor
        elif isinstance(effect, NostrRelayCompletion):
            sql = FINALIZE_NOSTR_RELAY_SQL
            params["result"] = json.dumps(
                effect.as_payload(), separators=(",", ":"), sort_keys=True
            )
        elif isinstance(effect, MastodonPublicHashtagCompletion):
            sql = FINALIZE_MASTODON_PUBLIC_HASHTAG_SQL
            params["result"] = json.dumps(
                effect.as_payload(), separators=(",", ":"), sort_keys=True
            )
        else:
            sql = _COMPLETION_EFFECT_SQL.get(effect)
        if sql is None:
            raise ValueError("unsupported completion effect")
        rows = self._executor.query(sql, params)
        if not rows:
            raise LeaseLostError(job_id)
        return job_from_row(rows[0])

    def pause_for_budget(
        self,
        job_id: str,
        *,
        worker_id: str,
        lease_generation: int,
        now: datetime,
        retry_at: datetime,
    ) -> Job:
        del now
        rows = self._executor.query(
            PAUSE_BUDGET_SQL,
            {
                "job_id": job_id,
                "worker_id": worker_id,
                "lease_generation": lease_generation,
                "retry_at": retry_at,
            },
        )
        if not rows:
            raise LeaseLostError(job_id)
        return job_from_row(rows[0])

    def fail(
        self,
        job_id: str,
        error: str,
        *,
        worker_id: str,
        lease_generation: int,
        now: datetime,
        error_code: str = "job_failed",
        retryable: bool = True,
    ) -> Job:
        del now
        rows = self._executor.query(
            FAIL_SQL,
            {
                "job_id": job_id,
                "worker_id": worker_id,
                "lease_generation": lease_generation,
                "error_code": error_code[:160],
                "error_message": error[:8_000],
                "retryable": retryable,
            },
        )
        if not rows:
            raise LeaseLostError(job_id)
        return job_from_row(rows[0])


class BlueskyPostgresJobRepository:
    """Source-scoped queue adapter for the dedicated Bluesky worker role.

    Every queue lifecycle call below uses a fixed Bluesky-only database
    wrapper. The worker cannot widen the claim set to another source and the
    typed completion paths keep cursor persistence and stale-cursor recovery
    behind the same generation-fenced finalizers used by the collector.
    """

    def __init__(self, executor: QueryExecutor) -> None:
        self._executor = executor

    @staticmethod
    def _lease_seconds(lease_for: timedelta) -> int:
        lease_seconds = int(lease_for.total_seconds())
        if lease_for != timedelta(seconds=lease_seconds) or not 1 <= lease_seconds <= 86_400:
            raise ValueError("lease_for must be a whole number of seconds between 1 and 86400")
        return lease_seconds

    def claim_bluesky_jetstream_jobs(
        self,
        worker_id: str,
        *,
        now: datetime,
        lease_for: timedelta,
    ) -> Job | None:
        del now
        rows = self._executor.query(
            BLUESKY_CLAIM_SQL,
            {
                "worker_id": worker_id,
                "lease_seconds": self._lease_seconds(lease_for),
            },
        )
        return job_from_row(rows[0]) if rows else None

    def heartbeat_bluesky_jetstream_job(
        self,
        job_id: str,
        *,
        worker_id: str,
        lease_generation: int,
        now: datetime,
        lease_for: timedelta,
    ) -> Job:
        del now
        rows = self._executor.query(
            BLUESKY_HEARTBEAT_SQL,
            {
                "job_id": job_id,
                "worker_id": worker_id,
                "lease_generation": lease_generation,
                "lease_seconds": self._lease_seconds(lease_for),
            },
        )
        if not rows:
            raise LeaseLostError(job_id)
        return job_from_row(rows[0])

    def complete_bluesky_jetstream_job(
        self,
        job_id: str,
        *,
        worker_id: str,
        lease_generation: int,
        now: datetime,
        effect: CompletionEffect
        | PublicStudyCompletion
        | TCGdexSetsSyncCompletion
        | YouTubeDiscoveryCompletion
        | BlueskyJetstreamCompletion
        | BlueskyCursorRecoveryCompletion
        | NostrRelayCompletion
        | MastodonPublicHashtagCompletion
        | None = None,
    ) -> Job:
        del now
        params: dict[str, object] = {
            "job_id": job_id,
            "worker_id": worker_id,
            "lease_generation": lease_generation,
        }
        if isinstance(effect, BlueskyJetstreamCompletion):
            sql = FINALIZE_BLUESKY_JETSTREAM_SQL
            params["result"] = json.dumps(
                effect.as_payload(), separators=(",", ":"), sort_keys=True
            )
        elif isinstance(effect, BlueskyCursorRecoveryCompletion):
            sql = RECOVER_BLUESKY_CURSOR_TOO_OLD_SQL
            params["start_cursor"] = effect.start_cursor
        else:
            raise ValueError(
                "Bluesky jobs require a BlueskyJetstreamCompletion or "
                "BlueskyCursorRecoveryCompletion effect"
            )
        rows = self._executor.query(sql, params)
        if not rows:
            raise LeaseLostError(job_id)
        return job_from_row(rows[0])

    def pause_bluesky_jetstream_job(
        self,
        job_id: str,
        *,
        worker_id: str,
        lease_generation: int,
        now: datetime,
        retry_at: datetime,
    ) -> Job:
        del now
        rows = self._executor.query(
            BLUESKY_PAUSE_BUDGET_SQL,
            {
                "job_id": job_id,
                "worker_id": worker_id,
                "lease_generation": lease_generation,
                "retry_at": retry_at,
            },
        )
        if not rows:
            raise LeaseLostError(job_id)
        return job_from_row(rows[0])

    def fail_bluesky_jetstream_job(
        self,
        job_id: str,
        error: str,
        *,
        worker_id: str,
        lease_generation: int,
        now: datetime,
        error_code: str = "job_failed",
        retryable: bool = True,
    ) -> Job:
        del now
        rows = self._executor.query(
            BLUESKY_FAIL_SQL,
            {
                "job_id": job_id,
                "worker_id": worker_id,
                "lease_generation": lease_generation,
                "error_code": error_code[:160],
                "error_message": error[:8_000],
                "retryable": retryable,
            },
        )
        if not rows:
            raise LeaseLostError(job_id)
        return job_from_row(rows[0])

    def lease(
        self,
        worker_id: str,
        *,
        now: datetime,
        lease_for: timedelta,
        kinds: set[str] | None = None,
    ) -> Job | None:
        if kinds is not None and kinds != {BLUESKY_JOB_TYPE}:
            raise ValueError("Bluesky workers may claim only source.bluesky.jetstream jobs")
        return self.claim_bluesky_jetstream_jobs(
            worker_id,
            now=now,
            lease_for=lease_for,
        )

    def heartbeat(
        self,
        job_id: str,
        *,
        worker_id: str,
        lease_generation: int,
        now: datetime,
        lease_for: timedelta,
    ) -> Job:
        return self.heartbeat_bluesky_jetstream_job(
            job_id,
            worker_id=worker_id,
            lease_generation=lease_generation,
            now=now,
            lease_for=lease_for,
        )

    def complete(
        self,
        job_id: str,
        *,
        worker_id: str,
        lease_generation: int,
        now: datetime,
        effect: CompletionEffect
        | PublicStudyCompletion
        | TCGdexSetsSyncCompletion
        | YouTubeDiscoveryCompletion
        | BlueskyJetstreamCompletion
        | BlueskyCursorRecoveryCompletion
        | NostrRelayCompletion
        | MastodonPublicHashtagCompletion
        | None = None,
    ) -> Job:
        return self.complete_bluesky_jetstream_job(
            job_id,
            worker_id=worker_id,
            lease_generation=lease_generation,
            now=now,
            effect=effect,
        )

    def pause_for_budget(
        self,
        job_id: str,
        *,
        worker_id: str,
        lease_generation: int,
        now: datetime,
        retry_at: datetime,
    ) -> Job:
        return self.pause_bluesky_jetstream_job(
            job_id,
            worker_id=worker_id,
            lease_generation=lease_generation,
            now=now,
            retry_at=retry_at,
        )

    def fail(
        self,
        job_id: str,
        error: str,
        *,
        worker_id: str,
        lease_generation: int,
        now: datetime,
        error_code: str = "job_failed",
        retryable: bool = True,
    ) -> Job:
        return self.fail_bluesky_jetstream_job(
            job_id,
            error,
            worker_id=worker_id,
            lease_generation=lease_generation,
            now=now,
            error_code=error_code,
            retryable=retryable,
        )


class NostrPostgresJobRepository:
    """Source-scoped queue adapter for the dedicated Nostr worker role.

    The runtime protocol still uses ``lease``/``heartbeat``/``complete`` and
    friends, but every implementation below calls a fixed Nostr-only database
    wrapper.  In particular, this class never passes a caller-controlled job
    type list to the generic queue RPC.
    """

    def __init__(self, executor: QueryExecutor) -> None:
        self._executor = executor

    @staticmethod
    def _lease_seconds(lease_for: timedelta) -> int:
        lease_seconds = int(lease_for.total_seconds())
        if lease_for != timedelta(seconds=lease_seconds) or not 1 <= lease_seconds <= 86_400:
            raise ValueError("lease_for must be a whole number of seconds between 1 and 86400")
        return lease_seconds

    def claim_nostr_relay_jobs(
        self,
        worker_id: str,
        *,
        now: datetime,
        lease_for: timedelta,
    ) -> Job | None:
        del now
        rows = self._executor.query(
            NOSTR_CLAIM_SQL,
            {
                "worker_id": worker_id,
                "lease_seconds": self._lease_seconds(lease_for),
            },
        )
        return job_from_row(rows[0]) if rows else None

    def heartbeat_nostr_relay_job(
        self,
        job_id: str,
        *,
        worker_id: str,
        lease_generation: int,
        now: datetime,
        lease_for: timedelta,
    ) -> Job:
        del now
        rows = self._executor.query(
            NOSTR_HEARTBEAT_SQL,
            {
                "job_id": job_id,
                "worker_id": worker_id,
                "lease_generation": lease_generation,
                "lease_seconds": self._lease_seconds(lease_for),
            },
        )
        if not rows:
            raise LeaseLostError(job_id)
        return job_from_row(rows[0])

    def complete_nostr_relay_job(
        self,
        job_id: str,
        *,
        worker_id: str,
        lease_generation: int,
        now: datetime,
        effect: CompletionEffect
        | PublicStudyCompletion
        | TCGdexSetsSyncCompletion
        | YouTubeDiscoveryCompletion
        | BlueskyJetstreamCompletion
        | BlueskyCursorRecoveryCompletion
        | NostrRelayCompletion
        | MastodonPublicHashtagCompletion
        | None = None,
    ) -> Job:
        del now
        if not isinstance(effect, NostrRelayCompletion):
            raise ValueError("Nostr jobs require a NostrRelayCompletion effect")
        rows = self._executor.query(
            FINALIZE_NOSTR_RELAY_SQL,
            {
                "job_id": job_id,
                "worker_id": worker_id,
                "lease_generation": lease_generation,
                "result": json.dumps(effect.as_payload(), separators=(",", ":"), sort_keys=True),
            },
        )
        if not rows:
            raise LeaseLostError(job_id)
        return job_from_row(rows[0])

    def pause_nostr_relay_job(
        self,
        job_id: str,
        *,
        worker_id: str,
        lease_generation: int,
        now: datetime,
        retry_at: datetime,
    ) -> Job:
        del now
        rows = self._executor.query(
            NOSTR_PAUSE_BUDGET_SQL,
            {
                "job_id": job_id,
                "worker_id": worker_id,
                "lease_generation": lease_generation,
                "retry_at": retry_at,
            },
        )
        if not rows:
            raise LeaseLostError(job_id)
        return job_from_row(rows[0])

    def fail_nostr_relay_job(
        self,
        job_id: str,
        error: str,
        *,
        worker_id: str,
        lease_generation: int,
        now: datetime,
        error_code: str = "job_failed",
        retryable: bool = True,
    ) -> Job:
        del now
        rows = self._executor.query(
            NOSTR_FAIL_SQL,
            {
                "job_id": job_id,
                "worker_id": worker_id,
                "lease_generation": lease_generation,
                "error_code": error_code[:160],
                "error_message": error[:8_000],
                "retryable": retryable,
            },
        )
        if not rows:
            raise LeaseLostError(job_id)
        return job_from_row(rows[0])

    def lease(
        self,
        worker_id: str,
        *,
        now: datetime,
        lease_for: timedelta,
        kinds: set[str] | None = None,
    ) -> Job | None:
        if kinds is not None and kinds != {NOSTR_JOB_TYPE}:
            raise ValueError("Nostr workers may claim only source.nostr.relay jobs")
        return self.claim_nostr_relay_jobs(
            worker_id,
            now=now,
            lease_for=lease_for,
        )

    def heartbeat(
        self,
        job_id: str,
        *,
        worker_id: str,
        lease_generation: int,
        now: datetime,
        lease_for: timedelta,
    ) -> Job:
        return self.heartbeat_nostr_relay_job(
            job_id,
            worker_id=worker_id,
            lease_generation=lease_generation,
            now=now,
            lease_for=lease_for,
        )

    def complete(
        self,
        job_id: str,
        *,
        worker_id: str,
        lease_generation: int,
        now: datetime,
        effect: CompletionEffect
        | PublicStudyCompletion
        | TCGdexSetsSyncCompletion
        | YouTubeDiscoveryCompletion
        | BlueskyJetstreamCompletion
        | BlueskyCursorRecoveryCompletion
        | NostrRelayCompletion
        | MastodonPublicHashtagCompletion
        | None = None,
    ) -> Job:
        return self.complete_nostr_relay_job(
            job_id,
            worker_id=worker_id,
            lease_generation=lease_generation,
            now=now,
            effect=effect,
        )

    def pause_for_budget(
        self,
        job_id: str,
        *,
        worker_id: str,
        lease_generation: int,
        now: datetime,
        retry_at: datetime,
    ) -> Job:
        return self.pause_nostr_relay_job(
            job_id,
            worker_id=worker_id,
            lease_generation=lease_generation,
            now=now,
            retry_at=retry_at,
        )

    def fail(
        self,
        job_id: str,
        error: str,
        *,
        worker_id: str,
        lease_generation: int,
        now: datetime,
        error_code: str = "job_failed",
        retryable: bool = True,
    ) -> Job:
        return self.fail_nostr_relay_job(
            job_id,
            error,
            worker_id=worker_id,
            lease_generation=lease_generation,
            now=now,
            error_code=error_code,
            retryable=retryable,
        )
