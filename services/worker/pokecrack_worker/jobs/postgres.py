"""PostgreSQL job repository using one-statement atomic claims."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any, Protocol

from .models import (
    CompletionEffect,
    Job,
    JobStatus,
    PublicStudyCompletion,
    TCGdexSetsSyncCompletion,
    YouTubeDiscoveryCompletion,
)
from .repository import LeaseLostError


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


HEARTBEAT_SQL = """
SELECT *
FROM ingest.heartbeat_job_v2(
    job_id => %(job_id)s::uuid,
    worker_id => %(worker_id)s,
    lease_generation => %(lease_generation)s::bigint,
    lease_seconds => %(lease_seconds)s::integer
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

PAUSE_BUDGET_SQL = """
SELECT *
FROM ingest.pause_job_for_budget_v2(
    %(job_id)s::uuid,
    %(worker_id)s,
    %(lease_generation)s::bigint,
    %(retry_at)s
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
        rows = self._executor.query(
            ENQUEUE_SQL,
            {
                "kind": kind,
                "payload": json.dumps(dict(payload or {}), separators=(",", ":")),
                "priority": priority,
                "dedupe_key": dedupe_key,
                "available_at": available_at or now,
                "max_attempts": max_attempts,
            },
        )
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
        rows = self._executor.query(
            ENQUEUE_SCHEDULED_SQL,
            {
                "schedule_name": schedule_name,
                "scheduled_for": scheduled_for,
                "kind": kind,
                "payload": json.dumps(dict(payload or {}), separators=(",", ":")),
                "priority": priority,
                "max_attempts": max_attempts,
            },
        )
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
            sql = FINALIZE_PUBLIC_STUDY_SQL
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
