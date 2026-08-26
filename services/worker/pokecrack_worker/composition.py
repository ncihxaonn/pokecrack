"""Fail-closed live PostgreSQL composition for the worker entry point.

Only job types with a bounded, database-backed implementation are registered
here.  Collector, AI, and aggregation services remain deliberately unavailable
until their persistence and external-service boundaries are implemented.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from pokecrack_worker import __version__
from pokecrack_worker.config.settings import DataMode, Settings
from pokecrack_worker.db import PsycopgQueryExecutor
from pokecrack_worker.jobs import CompletionEffect, Job, PostgresJobRepository, QueryExecutor
from pokecrack_worker.runtime import JobHandler, WorkerRuntime
from pokecrack_worker.scheduler import CronExpression, ScheduleEntry, Scheduler


class WorkerRole(StrEnum):
    COLLECTOR = "collector"
    AI_WORKER = "ai-worker"
    AGGREGATOR = "aggregator"
    SCHEDULER = "scheduler"
    WATCHDOG = "watchdog"


class LiveCompositionError(RuntimeError):
    """A safe-to-report live configuration boundary failure."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.safe_message = message
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class HeartbeatResult:
    worker_id: str
    worker_role: WorkerRole
    last_seen_at: datetime


CLEANUP_JOB_TYPE = "maintenance.cleanup"

WORKER_HEARTBEAT_SQL = """
WITH database_probe AS (
    SELECT 1 AS reachable
)
INSERT INTO ingest.worker_heartbeats AS heartbeats (
    worker_id, worker_type, version, last_seen_at, metadata, is_demo
)
SELECT
    %(worker_id)s, %(worker_type)s, %(version)s, clock_timestamp(), %(metadata)s::jsonb, false
FROM database_probe
ON CONFLICT (worker_id) DO UPDATE
SET worker_type = EXCLUDED.worker_type,
    version = EXCLUDED.version,
    last_seen_at = EXCLUDED.last_seen_at,
    metadata = heartbeats.metadata || EXCLUDED.metadata
WHERE not heartbeats.is_demo
RETURNING last_seen_at
""".strip()

_WORKER_JOB_TYPES: Mapping[WorkerRole, tuple[str, ...]] = {
    WorkerRole.WATCHDOG: (CLEANUP_JOB_TYPE,),
}

_SCHEDULE_FIELDS: tuple[tuple[str, str], ...] = (
    ("official_api", "schedule_official_api"),
    ("public_collection", "schedule_public_collection"),
    ("auth_collection", "schedule_auth_collection"),
    ("catalog_sync", "schedule_catalog_sync"),
    ("aggregates", "schedule_aggregates"),
    ("cleanup", "schedule_cleanup"),
    ("backup", "schedule_backup"),
    ("browser_check", "schedule_browser_check"),
)

UNWIRED_SCHEDULE_NAMES = tuple(name for name, _field_name in _SCHEDULE_FIELDS if name != "cleanup")


def _require_live_settings(settings: Settings) -> None:
    if settings.data_mode is not DataMode.LIVE:
        raise LiveCompositionError(
            "live_mode_required",
            "the PostgreSQL composition root requires DATA_MODE=live",
        )
    if settings.supabase_db_url is None:
        raise LiveCompositionError(
            "database_configuration_missing",
            "live mode requires a PostgreSQL database URL",
        )
    if settings.worker_max_concurrency != 1:
        raise LiveCompositionError(
            "unsupported_worker_concurrency",
            "the live worker currently requires WORKER_MAX_CONCURRENCY=1",
        )


def require_supported_role(settings: Settings) -> WorkerRole:
    """Return the exact configured role without guessing or falling back."""

    _require_live_settings(settings)
    if settings.worker_role is None:
        raise LiveCompositionError(
            "worker_role_missing",
            "live mode requires an explicit WORKER_ROLE",
        )
    try:
        return WorkerRole(settings.worker_role)
    except ValueError as error:
        raise LiveCompositionError(
            "unsupported_worker_role",
            "WORKER_ROLE is not supported by this worker build",
        ) from error


def require_worker_job_types(settings: Settings) -> tuple[str, ...]:
    """Return only job types that the configured worker can safely execute."""

    role = require_supported_role(settings)
    job_types = _WORKER_JOB_TYPES.get(role)
    if not job_types:
        raise LiveCompositionError(
            "worker_role_not_ready",
            "the configured role has no safe live job handlers in this build",
        )
    return job_types


def require_scheduler_role(settings: Settings) -> WorkerRole:
    role = require_supported_role(settings)
    if role is not WorkerRole.SCHEDULER:
        raise LiveCompositionError(
            "scheduler_role_required",
            "the live scheduler command requires WORKER_ROLE=scheduler",
        )
    return role


def role_is_ready(role: WorkerRole) -> bool:
    """Whether this build has a safe live command for the role."""

    return role is WorkerRole.SCHEDULER or role in _WORKER_JOB_TYPES


def executor_from_settings(settings: Settings) -> PsycopgQueryExecutor:
    _require_live_settings(settings)
    assert settings.supabase_db_url is not None
    return PsycopgQueryExecutor.from_dsn(settings.supabase_db_url.get_secret_value())


def write_health_heartbeat(
    settings: Settings,
    *,
    executor: QueryExecutor | None = None,
) -> HeartbeatResult:
    """Probe PostgreSQL and atomically upsert the calling service heartbeat."""

    role = require_supported_role(settings)
    if not role_is_ready(role):
        raise LiveCompositionError(
            "worker_role_not_ready",
            "the configured role has no safe live command in this build",
        )
    database = executor or executor_from_settings(settings)
    rows = database.query(
        WORKER_HEARTBEAT_SQL,
        {
            "worker_id": settings.worker_id,
            "worker_type": role.value,
            "version": __version__,
            "metadata": json.dumps(
                {
                    "command": "health",
                    "data_mode": settings.data_mode.value,
                    "max_concurrency": settings.worker_max_concurrency,
                    "role_ready": role_is_ready(role),
                },
                separators=(",", ":"),
                sort_keys=True,
            ),
        },
    )
    if not rows or not isinstance(rows[0].get("last_seen_at"), datetime):
        raise RuntimeError("worker heartbeat upsert returned no valid timestamp")
    last_seen_at = rows[0]["last_seen_at"]
    assert isinstance(last_seen_at, datetime)
    if last_seen_at.tzinfo is None or last_seen_at.utcoffset() is None:
        raise RuntimeError("worker heartbeat timestamp must be timezone-aware")
    return HeartbeatResult(
        worker_id=settings.worker_id,
        worker_role=role,
        last_seen_at=last_seen_at,
    )


def _cleanup_handler() -> JobHandler:
    def cleanup(job: Job) -> CompletionEffect:
        if job.kind != CLEANUP_JOB_TYPE or job.payload:
            raise ValueError("maintenance cleanup jobs require an empty payload")
        return CompletionEffect.PRUNE_EXPIRED_EPHEMERA

    return cleanup


def _handlers_for_role(role: WorkerRole) -> Mapping[str, JobHandler]:
    if role is WorkerRole.WATCHDOG:
        return {CLEANUP_JOB_TYPE: _cleanup_handler()}
    return {}


def build_live_worker_runtime(
    settings: Settings,
    *,
    executor: QueryExecutor | None = None,
    clock: Callable[[], datetime] | None = None,
) -> WorkerRuntime:
    """Compose the live queue with a non-empty allowlist of concrete handlers."""

    expected_job_types = require_worker_job_types(settings)
    role = require_supported_role(settings)
    database = executor or executor_from_settings(settings)
    handlers = _handlers_for_role(role)
    if tuple(handlers) != expected_job_types:
        raise RuntimeError("live worker handler registry is inconsistent")
    return WorkerRuntime(
        PostgresJobRepository(database),
        handlers=handlers,
        worker_id=settings.worker_id,
        lease_for=timedelta(seconds=settings.worker_lease_seconds),
        poll_seconds=settings.worker_poll_seconds,
        clock=clock,
        require_completion_effect=True,
    )


def live_schedule_entries(settings: Settings) -> tuple[ScheduleEntry, ...]:
    """Validate every configured cron but expose only implemented job types."""

    require_scheduler_role(settings)
    for _name, field_name in _SCHEDULE_FIELDS:
        CronExpression.parse(str(getattr(settings, field_name)))
    return (
        ScheduleEntry(
            name="cleanup",
            job_type=CLEANUP_JOB_TYPE,
            cron=settings.schedule_cleanup,
            priority=10,
            max_attempts=settings.worker_max_attempts,
        ),
    )


def build_live_scheduler(
    settings: Settings,
    *,
    executor: QueryExecutor | None = None,
) -> Scheduler:
    entries = live_schedule_entries(settings)
    database = executor or executor_from_settings(settings)
    return Scheduler(PostgresJobRepository(database), entries)
