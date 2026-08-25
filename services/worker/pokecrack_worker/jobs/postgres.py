"""PostgreSQL job repository using one-statement atomic claims."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any, Protocol

from .models import Job, JobStatus
from .repository import LeaseLostError


class QueryExecutor(Protocol):
    """Small injectable contract used by psycopg and deterministic tests."""

    def query(self, sql: str, params: Mapping[str, object]) -> Sequence[Mapping[str, Any]]: ...


ENQUEUE_SQL = """
INSERT INTO ingest.jobs AS jobs (
    job_type, payload, status, priority, dedupe_key, available_at,
    attempts, max_attempts, created_at, updated_at
)
VALUES (
    %(kind)s, %(payload)s::jsonb, 'pending', %(priority)s, %(dedupe_key)s,
    %(available_at)s, 0, %(max_attempts)s, %(now)s, %(now)s
)
ON CONFLICT (job_type, dedupe_key)
    WHERE dedupe_key IS NOT NULL AND status IN ('pending', 'running')
DO UPDATE SET updated_at = jobs.updated_at
RETURNING jobs.*
""".strip()

CLAIM_SQL = """
SELECT *
FROM ingest.claim_jobs(
    worker_id => %(worker_id)s,
    job_types => %(kinds)s::text[],
    batch_size => 1,
    lease_seconds => %(lease_seconds)s
)
""".strip()


HEARTBEAT_SQL = """
WITH lease_clock AS (SELECT clock_timestamp() AS now)
UPDATE ingest.jobs
SET lock_expires_at = lease_clock.now + make_interval(secs => %(lease_seconds)s),
    updated_at = lease_clock.now
FROM lease_clock
WHERE id = %(job_id)s
  AND status = 'running'
  AND locked_by = %(worker_id)s
  AND lock_expires_at > lease_clock.now
RETURNING *
""".strip()

FAIL_SQL = """
WITH lease_clock AS (SELECT clock_timestamp() AS now)
UPDATE ingest.jobs
SET status = CASE WHEN attempts >= max_attempts THEN 'dead' ELSE 'pending' END,
    available_at = CASE
        WHEN attempts >= max_attempts THEN available_at
        ELSE lease_clock.now + make_interval(
            secs => LEAST(
                3600,
                30 * POWER(2, LEAST(10, GREATEST(0, attempts - 1)))
            )::integer
        )
    END,
    locked_by = NULL,
    locked_at = NULL,
    lock_expires_at = NULL,
    completed_at = CASE WHEN attempts >= max_attempts THEN lease_clock.now ELSE NULL END,
    last_error_code = %(error_code)s,
    last_error_message = %(error_message)s,
    updated_at = lease_clock.now
FROM lease_clock
WHERE id = %(job_id)s
  AND status = 'running'
  AND locked_by = %(worker_id)s
  AND lock_expires_at > lease_clock.now
RETURNING *
""".strip()

COMPLETE_SQL = """
WITH lease_clock AS (SELECT clock_timestamp() AS now)
UPDATE ingest.jobs
SET status = 'completed',
    locked_by = NULL,
    locked_at = NULL,
    lock_expires_at = NULL,
    completed_at = lease_clock.now,
    last_error_code = NULL,
    last_error_message = NULL,
    updated_at = lease_clock.now
FROM lease_clock
WHERE id = %(job_id)s
  AND status = 'running'
  AND locked_by = %(worker_id)s
  AND lock_expires_at > lease_clock.now
RETURNING *
""".strip()

PAUSE_BUDGET_SQL = """
WITH lease_clock AS (SELECT clock_timestamp() AS now)
UPDATE ingest.jobs
SET status = 'pending',
    attempts = GREATEST(0, attempts - 1),
    available_at = %(retry_at)s,
    locked_by = NULL,
    locked_at = NULL,
    lock_expires_at = NULL,
    completed_at = NULL,
    last_error_code = NULL,
    last_error_message = NULL,
    updated_at = lease_clock.now
FROM lease_clock
WHERE id = %(job_id)s
  AND status = 'running'
  AND locked_by = %(worker_id)s
  AND lock_expires_at > lease_clock.now
RETURNING *
""".strip()


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
                "now": now,
            },
        )
        if not rows:
            raise RuntimeError("job enqueue returned no row")
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
                "lease_seconds": lease_seconds,
            },
        )
        if not rows:
            raise LeaseLostError(job_id)
        return job_from_row(rows[0])

    def complete(self, job_id: str, *, worker_id: str, now: datetime) -> Job:
        del now
        rows = self._executor.query(
            COMPLETE_SQL,
            {"job_id": job_id, "worker_id": worker_id},
        )
        if not rows:
            raise LeaseLostError(job_id)
        return job_from_row(rows[0])

    def pause_for_budget(
        self,
        job_id: str,
        *,
        worker_id: str,
        now: datetime,
        retry_at: datetime,
    ) -> Job:
        del now
        rows = self._executor.query(
            PAUSE_BUDGET_SQL,
            {
                "job_id": job_id,
                "worker_id": worker_id,
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
        now: datetime,
        error_code: str = "job_failed",
    ) -> Job:
        del now
        rows = self._executor.query(
            FAIL_SQL,
            {
                "job_id": job_id,
                "worker_id": worker_id,
                "error_code": error_code[:160],
                "error_message": error[:8_000],
            },
        )
        if not rows:
            raise LeaseLostError(job_id)
        return job_from_row(rows[0])
