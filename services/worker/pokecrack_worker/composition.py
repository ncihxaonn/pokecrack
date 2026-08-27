"""Fail-closed live PostgreSQL composition for the worker entry point.

Only job types with a bounded, database-backed implementation are registered
here. The collector supports fixed TCGdex catalog sync plus explicitly enabled
YouTube metadata discovery; AI and general URL collection remain unavailable.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from time import monotonic, sleep

from pokecrack_worker import __version__
from pokecrack_worker.collectors.official_api.postgres import (
    PostgresTCGdexCheckpointRepository,
    PostgresYouTubeDiscoveryGate,
    TCGdexRequestDeferred,
    YouTubeRequestDeferred,
)
from pokecrack_worker.collectors.official_api.tcgdex import (
    HTTPXTCGdexTransport,
    InMemoryTCGdexSetsCache,
    TCGdexSetsClient,
    TCGdexSetsSnapshot,
    TCGdexSetsSyncOutcome,
    TCGdexTransport,
)
from pokecrack_worker.collectors.official_api.youtube import (
    HTTPXYouTubeTransport,
    YouTubeDataClient,
    YouTubeError,
    YouTubeTransport,
)
from pokecrack_worker.config.registries import YouTubeQueryRegistry
from pokecrack_worker.config.settings import DataMode, Settings
from pokecrack_worker.config.source_policy import SourcePolicyRegistry
from pokecrack_worker.db import PsycopgQueryExecutor
from pokecrack_worker.jobs import (
    CompletionEffect,
    Job,
    PostgresJobRepository,
    QueryExecutor,
    TCGdexSetsSyncCompletion,
    TCGdexSetWrite,
    TCGdexSyncOutcome,
    YouTubeDiscoveryCompletion,
    YouTubeSourceItemWrite,
)
from pokecrack_worker.runtime import JobDeferred, JobExecutionError, JobHandler, WorkerRuntime
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
TCGDEX_SETS_JOB_TYPE = "catalog.tcgdex.sets.sync"
YOUTUBE_DISCOVERY_JOB_TYPE = "source.youtube.discovery"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
SOURCES_CONFIG = PROJECT_ROOT / "config" / "sources.yaml"
YOUTUBE_QUERIES_CONFIG = PROJECT_ROOT / "config" / "youtube-queries.yaml"

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

LIVE_ROLE_DEPENDENCIES_SQL = """
WITH youtube_dependencies AS (
  SELECT COALESCE(
    to_regprocedure('ingest.begin_youtube_discovery_job(uuid,text,bigint)') IS NOT NULL
    AND to_regprocedure(
      'ingest.finalize_youtube_discovery_job(uuid,text,bigint,jsonb)'
    ) IS NOT NULL
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.begin_youtube_discovery_job(uuid,text,bigint)'),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.finalize_youtube_discovery_job(uuid,text,bigint,jsonb)'),
      'EXECUTE'
    )
    AND EXISTS (
      SELECT 1
      FROM ingest.source_policies AS policies
      WHERE policies.source_key = 'youtube_discovery'
        AND policies.display_name = 'YouTube Global Discovery API'
        AND policies.domain = 'youtube.googleapis.com'
        AND policies.base_url = 'https://youtube.googleapis.com/youtube/v3'
        AND policies.enabled
        AND NOT policies.is_demo
        AND policies.source_kind = 'official_api'
        AND policies.collector_type = 'official_api'
        AND policies.access_mode = 'official_api'
        AND policies.robots_policy = 'not_applicable'
        AND policies.routes = ARRAY['official_api']::text[]
        AND NOT policies.include_subdomains
        AND policies.min_delay_seconds = 2
        AND policies.max_pages_per_run = 2
        AND policies.max_items_per_run = 50
        AND policies.max_concurrency = 1
        AND policies.browser_profile IS NULL
        AND NOT policies.statistics_eligible_default
        AND policies.retention_days = 28
        AND policies.config = '{
          "metadata_only":true,
          "media_download":false,
          "discovery_scope":"global",
          "geography_status":"unresolved",
          "evidence_tier":"D",
          "statistics_eligible":false,
          "parser_version":"youtube-metadata-v1",
          "max_response_bytes":2097152,
          "query_allowlist":[
            "pokemon-tcg-booster-box-opening",
            "pokemon-tcg-etb-opening",
            "pokemon-tcg-booster-bundle-opening",
            "pokemon-tcg-pack-opening",
            "pokemon-tcg-opening-batch-code"
          ]
        }'::jsonb
        AND policies.version = 'youtube-global-discovery-v1'
        AND policies.expected_interval_seconds = 21600
    ),
    false
  ) AS ready
)
SELECT CASE %(worker_type)s
  WHEN 'collector' THEN
    to_regclass('ingest.source_request_gates') IS NOT NULL
    AND to_regprocedure('ingest.claim_jobs_v2(text,text[],integer,integer)') IS NOT NULL
    AND to_regprocedure('ingest.heartbeat_job_v2(uuid,text,bigint,integer)') IS NOT NULL
    AND to_regprocedure('ingest.fail_job_v2(uuid,text,bigint,text,text,boolean)') IS NOT NULL
    AND to_regprocedure('ingest.begin_tcgdex_sets_job(uuid,text,bigint)') IS NOT NULL
    AND to_regprocedure('ingest.finalize_tcgdex_sets_job(uuid,text,bigint,jsonb)') IS NOT NULL
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.claim_jobs_v2(text,text[],integer,integer)'),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.heartbeat_job_v2(uuid,text,bigint,integer)'),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.fail_job_v2(uuid,text,bigint,text,text,boolean)'),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.begin_tcgdex_sets_job(uuid,text,bigint)'),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.finalize_tcgdex_sets_job(uuid,text,bigint,jsonb)'),
      'EXECUTE'
    )
    AND EXISTS (
      SELECT 1
      FROM ingest.source_policies AS policies
      WHERE policies.source_key = 'tcgdex_catalog'
        AND policies.display_name = 'TCGdex Catalog API'
        AND policies.domain = 'api.tcgdex.net'
        AND policies.base_url = 'https://api.tcgdex.net/v2'
        AND policies.enabled
        AND NOT policies.is_demo
        AND policies.source_kind = 'official_api'
        AND policies.collector_type = 'official_api'
        AND policies.access_mode = 'official_api'
        AND policies.robots_policy = 'not_applicable'
        AND policies.routes = ARRAY['official_api']::text[]
        AND NOT policies.include_subdomains
        AND policies.min_delay_seconds = 10
        AND policies.max_pages_per_run = 1
        AND policies.max_items_per_run = 1000
        AND policies.max_concurrency = 1
        AND policies.browser_profile IS NULL
        AND NOT policies.statistics_eligible_default
        AND policies.retention_days = 365
        AND policies.config = '{"scope":"sets","metadata_only":true}'::jsonb
        AND policies.version = 'tcgdex-sets-v1'
        AND policies.expected_interval_seconds = 86400
    )
    AND (
      NOT %(youtube_enabled)s::boolean
      OR (SELECT ready FROM youtube_dependencies)
    )
  WHEN 'scheduler' THEN
    to_regprocedure(
      'ingest.enqueue_scheduled_job_v1(text,timestamptz,text,jsonb,integer,integer)'
    ) IS NOT NULL
    AND has_function_privilege(
      current_user,
      to_regprocedure(
        'ingest.enqueue_scheduled_job_v1(text,timestamptz,text,jsonb,integer,integer)'
      ),
      'EXECUTE'
    )
    AND (
      NOT %(youtube_enabled)s::boolean
      OR (SELECT ready FROM youtube_dependencies)
    )
  WHEN 'watchdog' THEN
    to_regclass('ingest.source_request_gates') IS NOT NULL
    AND to_regprocedure('ingest.claim_jobs_v2(text,text[],integer,integer)') IS NOT NULL
    AND to_regprocedure('ingest.heartbeat_job_v2(uuid,text,bigint,integer)') IS NOT NULL
    AND to_regprocedure('ingest.fail_job_v2(uuid,text,bigint,text,text,boolean)') IS NOT NULL
    AND to_regprocedure('ingest.finalize_cleanup_job(uuid,text,bigint)') IS NOT NULL
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.claim_jobs_v2(text,text[],integer,integer)'),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.heartbeat_job_v2(uuid,text,bigint,integer)'),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.fail_job_v2(uuid,text,bigint,text,text,boolean)'),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.finalize_cleanup_job(uuid,text,bigint)'),
      'EXECUTE'
    )
  ELSE false
END AS ready
""".strip()

_WORKER_JOB_TYPES: Mapping[WorkerRole, tuple[str, ...]] = {
    WorkerRole.COLLECTOR: (TCGDEX_SETS_JOB_TYPE, YOUTUBE_DISCOVERY_JOB_TYPE),
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

UNWIRED_SCHEDULE_NAMES = tuple(
    name
    for name, _field_name in _SCHEDULE_FIELDS
    if name not in {"official_api", "catalog_sync", "cleanup"}
)


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
    if role is WorkerRole.COLLECTOR and not settings.youtube_collection_enabled:
        return (TCGDEX_SETS_JOB_TYPE,)
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
    dependency_rows = database.query(
        LIVE_ROLE_DEPENDENCIES_SQL,
        {
            "worker_type": role.value,
            "youtube_enabled": settings.youtube_collection_enabled,
        },
    )
    if not dependency_rows or dependency_rows[0].get("ready") is not True:
        raise LiveCompositionError(
            "live_dependencies_unavailable",
            "the configured role database dependencies are unavailable",
        )
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


def _tcgdex_sets_handler(
    *,
    executor: QueryExecutor,
    worker_id: str,
    transport: TCGdexTransport,
    clock: Callable[[], datetime] | None,
) -> JobHandler:
    checkpoints = PostgresTCGdexCheckpointRepository(executor)
    policies = SourcePolicyRegistry.from_yaml(SOURCES_CONFIG)
    now = clock or (lambda: datetime.now(UTC))

    def sync_sets(job: Job) -> TCGdexSetsSyncCompletion:
        if job.kind != TCGDEX_SETS_JOB_TYPE or job.payload:
            raise ValueError("TCGdex catalog jobs require an empty payload")
        try:
            checkpoint = checkpoints.begin(
                job_id=job.id,
                worker_id=worker_id,
                lease_generation=job.lease_generation,
            )
        except TCGdexRequestDeferred as deferred:
            raise JobDeferred(
                retry_at=deferred.retry_at,
                code="tcgdex_request_deferred",
            ) from None
        cache = InMemoryTCGdexSetsCache()
        if checkpoint.content_sha256 is not None:
            cache.put(
                TCGdexSetsSnapshot(
                    sets=(),
                    etag=checkpoint.etag,
                    content_sha256=checkpoint.content_sha256,
                    synced_at=now(),
                )
            )
        attempt = TCGdexSetsClient(
            transport=transport,
            cache=cache,
            policies=policies,
            clock=clock,
        ).sync_safe()
        if attempt.result is None:
            raise JobExecutionError(
                code=attempt.error_code or "tcgdex_sync_failed",
                retryable=attempt.retryable,
            )
        result = attempt.result
        outcome = TCGdexSyncOutcome(result.outcome.value)
        writes = (
            tuple(
                TCGdexSetWrite(
                    external_id=item.set_id,
                    name=item.name,
                    card_count_total=item.card_count_total,
                    card_count_official=item.card_count_official,
                )
                for item in result.snapshot.sets
            )
            if result.outcome is TCGdexSetsSyncOutcome.CHANGED
            else ()
        )
        return TCGdexSetsSyncCompletion(
            outcome=outcome,
            expected_revision=checkpoint.revision,
            etag=result.snapshot.etag,
            content_sha256=result.snapshot.content_sha256,
            sets=writes,
        )

    return sync_sets


def _youtube_discovery_handler(
    *,
    settings: Settings,
    executor: QueryExecutor,
    worker_id: str,
    transport: YouTubeTransport,
    clock: Callable[[], datetime] | None,
    monotonic_clock: Callable[[], float],
    sleeper: Callable[[float], None],
) -> JobHandler:
    if not settings.youtube_collection_enabled or settings.youtube_api_key is None:
        raise RuntimeError("YouTube discovery handler requires explicit credentials and enablement")
    registry = YouTubeQueryRegistry.from_yaml(YOUTUBE_QUERIES_CONFIG)
    gates = PostgresYouTubeDiscoveryGate(executor)
    client = YouTubeDataClient(
        api_key=settings.youtube_api_key.get_secret_value(),
        transport=transport,
        policies=SourcePolicyRegistry.from_yaml(SOURCES_CONFIG),
        clock=clock,
        monotonic_clock=monotonic_clock,
        sleeper=sleeper,
    )

    def discover(job: Job) -> YouTubeDiscoveryCompletion:
        if job.kind != YOUTUBE_DISCOVERY_JOB_TYPE or set(job.payload) != {"query_name"}:
            raise ValueError("YouTube discovery jobs require the exact query_name payload")
        query_name = job.payload.get("query_name")
        if not isinstance(query_name, str):
            raise ValueError("YouTube query_name must be text")
        query = registry.require(query_name)
        try:
            gates.begin(
                job_id=job.id,
                worker_id=worker_id,
                lease_generation=job.lease_generation,
            )
        except YouTubeRequestDeferred as deferred:
            raise JobDeferred(
                retry_at=deferred.retry_at,
                code="youtube_request_deferred",
            ) from None
        try:
            candidates = client.discover(query)
        except YouTubeError as error:
            raise JobExecutionError(code=error.code, retryable=error.retryable) from None
        writes: list[YouTubeSourceItemWrite] = []
        for candidate in candidates:
            if candidate.normalized_url is None:
                raise RuntimeError("YouTube candidate normalization is unavailable")
            writes.append(
                YouTubeSourceItemWrite(
                    external_id=candidate.external_id or "",
                    source_url=candidate.source_url,
                    normalized_url=candidate.normalized_url,
                    title=candidate.title,
                    text_excerpt=None,
                    published_at=candidate.published_at,
                    author_hash=None,
                    content_hash=None,
                    language=None,
                    metadata=dict(candidate.metadata),
                    collector_version=candidate.collector_version,
                    source_policy_version=candidate.source_policy_version,
                )
            )
        return YouTubeDiscoveryCompletion(query_name=query.name, items=tuple(writes))

    return discover


def _handlers_for_role(
    role: WorkerRole,
    *,
    settings: Settings,
    executor: QueryExecutor,
    worker_id: str,
    tcgdex_transport: TCGdexTransport | None,
    youtube_transport: YouTubeTransport | None,
    clock: Callable[[], datetime] | None,
    monotonic_clock: Callable[[], float],
    sleeper: Callable[[float], None],
) -> Mapping[str, JobHandler]:
    if role is WorkerRole.COLLECTOR:
        handlers: dict[str, JobHandler] = {
            TCGDEX_SETS_JOB_TYPE: _tcgdex_sets_handler(
                executor=executor,
                worker_id=worker_id,
                transport=tcgdex_transport or HTTPXTCGdexTransport(),
                clock=clock,
            )
        }
        if settings.youtube_collection_enabled:
            handlers[YOUTUBE_DISCOVERY_JOB_TYPE] = _youtube_discovery_handler(
                settings=settings,
                executor=executor,
                worker_id=worker_id,
                transport=youtube_transport or HTTPXYouTubeTransport(),
                clock=clock,
                monotonic_clock=monotonic_clock,
                sleeper=sleeper,
            )
        return handlers
    if role is WorkerRole.WATCHDOG:
        return {CLEANUP_JOB_TYPE: _cleanup_handler()}
    return {}


def build_live_worker_runtime(
    settings: Settings,
    *,
    executor: QueryExecutor | None = None,
    clock: Callable[[], datetime] | None = None,
    tcgdex_transport: TCGdexTransport | None = None,
    youtube_transport: YouTubeTransport | None = None,
    monotonic_clock: Callable[[], float] = monotonic,
    sleeper: Callable[[float], None] = sleep,
) -> WorkerRuntime:
    """Compose the live queue with a non-empty allowlist of concrete handlers."""

    expected_job_types = require_worker_job_types(settings)
    role = require_supported_role(settings)
    database = executor or executor_from_settings(settings)
    handlers = _handlers_for_role(
        role,
        settings=settings,
        executor=database,
        worker_id=settings.worker_id,
        tcgdex_transport=tcgdex_transport,
        youtube_transport=youtube_transport,
        clock=clock,
        monotonic_clock=monotonic_clock,
        sleeper=sleeper,
    )
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
    catalog = (
        ScheduleEntry(
            name="catalog_sync",
            job_type=TCGDEX_SETS_JOB_TYPE,
            cron=settings.schedule_catalog_sync,
            priority=20,
            max_attempts=min(3, settings.worker_max_attempts),
            catch_up_within=timedelta(hours=36),
            catch_up_check_interval=timedelta(hours=1),
        ),
    )
    youtube = (
        tuple(
            ScheduleEntry(
                name=f"youtube_{query.name}",
                job_type=YOUTUBE_DISCOVERY_JOB_TYPE,
                cron=settings.schedule_official_api,
                payload={"query_name": query.name},
                priority=15,
                max_attempts=min(3, settings.worker_max_attempts),
                catch_up_within=timedelta(hours=12),
                catch_up_check_interval=timedelta(hours=1),
            )
            for query in YouTubeQueryRegistry.from_yaml(YOUTUBE_QUERIES_CONFIG).queries
        )
        if settings.youtube_collection_enabled
        else ()
    )
    cleanup = (
        ScheduleEntry(
            name="cleanup",
            job_type=CLEANUP_JOB_TYPE,
            cron=settings.schedule_cleanup,
            priority=10,
            max_attempts=settings.worker_max_attempts,
        ),
    )
    return catalog + youtube + cleanup


def build_live_scheduler(
    settings: Settings,
    *,
    executor: QueryExecutor | None = None,
) -> Scheduler:
    entries = live_schedule_entries(settings)
    database = executor or executor_from_settings(settings)
    return Scheduler(PostgresJobRepository(database), entries)
