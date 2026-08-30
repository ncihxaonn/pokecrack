"""Fail-closed live PostgreSQL composition for the worker entry point.

Only job types with a bounded, database-backed implementation are registered
here. The collector supports fixed TCGdex catalog sync, explicitly enabled
YouTube metadata discovery, and a tiny allowlist of reviewed public studies;
AI and general URL collection remain unavailable.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path

from pokecrack_worker import __version__
from pokecrack_worker.collectors.base import CollectionService, CollectorError, HTTPClient
from pokecrack_worker.collectors.official_api.bluesky import (
    BlueskyError,
    BlueskyJetstreamCollector,
    BlueskyJetstreamTransport,
    WebsocketsBlueskyJetstreamTransport,
)
from pokecrack_worker.collectors.official_api.postgres import (
    BlueskyRequestDeferred,
    PostgresBlueskyJetstreamGate,
    PostgresPublicStudyGate,
    PostgresTCGdexCheckpointRepository,
    PostgresYouTubeDiscoveryGate,
    PublicStudyRequestDeferred,
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
    MatonYouTubeTransport,
    YouTubeDataClient,
    YouTubeError,
    YouTubeTransport,
)
from pokecrack_worker.collectors.scrapling.adapters.public_studies import RobotsTxtChecker
from pokecrack_worker.collectors.scrapling.http import ScraplingHTTPClient
from pokecrack_worker.collectors.scrapling.registry import build_live_static_registry
from pokecrack_worker.config.bluesky import BlueskyKeywordRegistry
from pokecrack_worker.config.public_studies import PUBLIC_STUDIES, PUBLIC_STUDIES_BY_KEY
from pokecrack_worker.config.registries import YouTubeQueryRegistry
from pokecrack_worker.config.settings import DataMode, Settings
from pokecrack_worker.config.source_policy import SourcePolicyRegistry
from pokecrack_worker.db import PsycopgQueryExecutor
from pokecrack_worker.jobs import (
    BlueskyDeletionWrite,
    BlueskyJetstreamCompletion,
    BlueskySourceItemWrite,
    CompletionEffect,
    Job,
    PostgresJobRepository,
    PublicStudyCompletion,
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
PUBLIC_STUDY_JOB_TYPE = "source.public_study.opening"
BLUESKY_JETSTREAM_JOB_TYPE = "source.bluesky.jetstream"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
SOURCES_CONFIG = PROJECT_ROOT / "config" / "sources.yaml"
YOUTUBE_QUERIES_CONFIG = PROJECT_ROOT / "config" / "youtube-queries.yaml"
BLUESKY_KEYWORDS_CONFIG = PROJECT_ROOT / "config" / "bluesky-keywords.yaml"

WORKER_HEARTBEAT_SQL = """
SELECT last_seen_at
FROM ingest.upsert_worker_heartbeat_v1(
    %(worker_id)s,
    %(worker_type)s,
    %(version)s,
    %(metadata)s::jsonb
)
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
        AND policies.max_pages_per_run = 1
        AND policies.max_items_per_run = 25
        AND policies.max_concurrency = 1
        AND policies.browser_profile IS NULL
        AND NOT policies.statistics_eligible_default
        AND policies.retention_days = 28
        AND policies.config = '{
          "metadata_only":true,
          "media_download":false,
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
),
bluesky_dependencies AS (
  SELECT COALESCE(
    to_regprocedure('ingest.begin_bluesky_jetstream_job(uuid,text,bigint)') IS NOT NULL
    AND to_regprocedure(
      'ingest.finalize_bluesky_jetstream_job(uuid,text,bigint,jsonb)'
    ) IS NOT NULL
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.begin_bluesky_jetstream_job(uuid,text,bigint)'),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure(
        'ingest.finalize_bluesky_jetstream_job(uuid,text,bigint,jsonb)'
      ),
      'EXECUTE'
    )
    AND EXISTS (
      SELECT 1
      FROM ingest.source_policies AS policies
      WHERE policies.source_key = 'bluesky_jetstream'
        AND policies.domain = 'jetstream.us-west.bsky.network'
        AND policies.enabled
        AND NOT policies.is_demo
        AND policies.source_kind = 'official_api'
        AND policies.collector_type = 'bluesky_jetstream'
        AND policies.access_mode = 'official_api'
        AND policies.robots_policy = 'not_applicable'
        AND (
          policies.routes = ARRAY['bluesky']::text[]
          OR policies.routes = ARRAY['bluesky_jetstream']::text[]
        )
        AND NOT policies.include_subdomains
        AND policies.min_delay_seconds = 1
        AND policies.max_pages_per_run = 1
        AND policies.max_items_per_run = 100
        AND policies.max_concurrency = 1
        AND policies.browser_profile IS NULL
        AND NOT policies.statistics_eligible_default
        AND policies.retention_days = 30
        AND policies.config = '{
          "collection":"app.bsky.feed.post",
          "endpoint":"wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents",
          "kinds":["commit"],
          "keyword_registry":"bluesky-keywords-v1",
          "max_candidates":100,
          "max_deletions":100,
          "max_events":10000,
          "max_excerpt_chars":500,
          "max_message_bytes":262144,
          "max_stream_bytes":2097152,
          "operations":["create","update","delete"],
          "statistics_eligible":false,
          "stream_window_seconds":40,
          "subprotocol":"xrpc.v1.json"
        }'::jsonb
        AND policies.version = 'bluesky-jetstream-v1'
        AND policies.expected_interval_seconds = 60
    ),
    false
  ) AS ready
),
public_study_dependencies AS (
  SELECT COALESCE(
    to_regclass('ingest.public_study_observations') IS NOT NULL
    AND to_regclass('ingest.public_study_coverage_observations') IS NOT NULL
    AND to_regprocedure('ingest.begin_public_study_job(uuid,text,bigint)') IS NOT NULL
    AND to_regprocedure(
      'ingest.begin_public_study_job_v2(uuid,text,bigint,text)'
    ) IS NOT NULL
    AND to_regprocedure(
      'ingest.finalize_public_study_job(uuid,text,bigint,jsonb)'
    ) IS NOT NULL
    AND to_regprocedure(
      'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'
    ) IS NOT NULL
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.begin_public_study_job(uuid,text,bigint)'),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.finalize_public_study_job(uuid,text,bigint,jsonb)'),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.begin_public_study_job_v2(uuid,text,bigint,text)'),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure(
        'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'
      ),
      'EXECUTE'
    )
    AND has_table_privilege(
      current_user,
      'ingest.public_study_observations',
      'SELECT'
    )
    AND NOT has_table_privilege(
      current_user,
      'ingest.public_study_observations',
      'INSERT'
    )
    AND NOT has_table_privilege(
      current_user,
      'ingest.public_study_observations',
      'UPDATE'
    )
    AND NOT has_table_privilege(
      current_user,
      'ingest.public_study_observations',
      'DELETE'
    )
    AND has_table_privilege(
      current_user,
      'ingest.public_study_coverage_observations',
      'SELECT'
    )
    AND NOT has_table_privilege(
      current_user,
      'ingest.public_study_coverage_observations',
      'INSERT'
    )
    AND NOT has_table_privilege(
      current_user,
      'ingest.public_study_coverage_observations',
      'UPDATE'
    )
    AND NOT has_table_privilege(
      current_user,
      'ingest.public_study_coverage_observations',
      'DELETE'
    )
    AND (
      SELECT
        count(*) = 5
        AND bool_and(
          policies.enabled
          AND NOT policies.is_demo
          AND policies.source_kind = 'public_web'
          AND policies.collector_type = 'scrapling_http'
          AND policies.access_mode = 'public'
          AND policies.robots_policy = 'respect'
          AND policies.routes = ARRAY['scrapling_http']::text[]
          AND NOT policies.include_subdomains
          AND policies.min_delay_seconds = 30
          AND policies.max_pages_per_run = 2
          AND policies.max_items_per_run = 1
          AND policies.max_concurrency = 1
          AND policies.browser_profile IS NULL
          AND policies.statistics_eligible_default
          AND policies.retention_days = 730
          AND policies.expected_interval_seconds = 86400
        )
        AND count(*) FILTER (
          WHERE policies.source_key = 'public_study_comicbook_us_55'
            AND policies.domain = 'comicbook.com'
            AND policies.base_url = 'https://comicbook.com/gaming/feature/pokemon-tcg-perfect-order-pull-rates-ex-illustration-rares-estimates'
            AND policies.version = 'public-study-comicbook-perfect-order-v1'
            AND policies.config ->> 'study_key' = 'comicbook-perfect-order-us-55-v1'
            AND policies.config ->> 'set_external_id' = 'me03'
            AND policies.config ->> 'country_code' = 'US'
            AND policies.config ->> 'pack_count' = '55'
            AND policies.config ->> 'qualifying_hit_pack_count' = '1'
        ) = 1
        AND count(*) FILTER (
          WHERE policies.source_key = 'public_study_wargamer_gb_17'
            AND policies.domain = 'www.wargamer.com'
            AND policies.base_url = 'https://www.wargamer.com/pokemon-trading-card-game/chaos-rising-preview'
            AND policies.version = 'public-study-wargamer-chaos-rising-v1'
            AND policies.config ->> 'study_key' = 'wargamer-chaos-rising-gb-17-v1'
            AND policies.config ->> 'set_external_id' = 'me04'
            AND policies.config ->> 'country_code' = 'GB'
            AND policies.config ->> 'pack_count' = '17'
            AND policies.config ->> 'qualifying_hit_pack_count' = '0'
        ) = 1
        AND count(*) FILTER (
          WHERE policies.source_key = 'public_study_cardchill_gb_90'
            AND policies.domain = 'cardchill.com'
            AND policies.base_url = 'https://cardchill.com/article/ripping-10-ascended-heroes-etbs-is-the-mega-attack-pull-rate-real'
            AND policies.version = 'public-study-cardchill-ascended-heroes-v1'
            AND policies.config ->> 'study_key' = 'cardchill-ascended-heroes-gb-90-v1'
            AND policies.config ->> 'set_external_id' = 'me02.5'
            AND policies.config ->> 'country_code' = 'GB'
            AND policies.config ->> 'pack_count' = '90'
            AND policies.config ->> 'qualifying_hit_pack_count' = '1'
        ) = 1
        AND count(*) FILTER (
          WHERE policies.source_key = 'public_study_bleedingcool_us_36'
            AND policies.domain = 'bleedingcool.com'
            AND policies.base_url = 'https://bleedingcool.com/games/opening-pokemon-tcg-mega-evolution-phantasmal-flames-products'
            AND policies.version = 'public-study-bleedingcool-phantasmal-flames-v1'
            AND policies.config ->> 'study_key' = 'bleedingcool-phantasmal-flames-us-36-v1'
            AND policies.config ->> 'set_external_id' = 'me02'
            AND policies.config ->> 'country_code' = 'US'
            AND policies.config ->> 'pack_count' = '36'
            AND policies.config ->> 'qualifying_hit_pack_count' = '1'
        ) = 1
        AND count(*) FILTER (
          WHERE policies.source_key = 'public_study_tcgtalk_sg_54'
            AND policies.domain = 'tcgtalk.com'
            AND policies.base_url = 'https://tcgtalk.com/blog/perfect-order-pull-rates-what-singapore-collectors-can-expect-1774442400232'
            AND policies.version = 'public-study-tcgtalk-perfect-order-v1'
            AND policies.config = '{
              "study_key":"tcgtalk-perfect-order-sg-54-v1",
              "canonical_url":"https://tcgtalk.com/blog/perfect-order-pull-rates-what-singapore-collectors-can-expect-1774442400232",
              "collector_version":"public-study-tcgtalk-perfect-order-v1",
              "parser_version":"tcgtalk-perfect-order-evidence-v1",
              "country_code":"SG",
              "country_name":"Singapore",
              "geography_basis":"publisher_country",
              "geography_confidence":"tier_b",
              "set_external_id":"me03",
              "product_scope":"booster_bundle",
              "pack_count":54,
              "qualifying_hit_pack_count":1,
              "qualifying_metric":"sir_pack",
              "metric_version":"global-sir-v1",
              "observed_at":"2026-03-25T12:40:00Z",
              "denominator_complete":true
            }'::jsonb
        ) = 1
      FROM ingest.source_policies AS policies
      WHERE policies.source_key IN (
        'public_study_comicbook_us_55',
        'public_study_wargamer_gb_17',
        'public_study_cardchill_gb_90',
        'public_study_bleedingcool_us_36',
        'public_study_tcgtalk_sg_54'
      )
    ),
    false
  ) AS ready
)
SELECT
  to_regprocedure('ingest.upsert_worker_heartbeat_v1(text,text,text,jsonb)') IS NOT NULL
  AND has_function_privilege(
    current_user,
    to_regprocedure('ingest.upsert_worker_heartbeat_v1(text,text,text,jsonb)'),
    'EXECUTE'
  )
  AND to_regprocedure(
    'ingest.pause_job_for_budget_v2(uuid,text,bigint,timestamptz)'
  ) IS NOT NULL
  AND has_function_privilege(
    current_user,
    to_regprocedure(
      'ingest.pause_job_for_budget_v2(uuid,text,bigint,timestamptz)'
    ),
    'EXECUTE'
  )
  AND NOT has_table_privilege(current_user, 'ingest.jobs', 'INSERT')
  AND NOT has_table_privilege(current_user, 'ingest.jobs', 'UPDATE')
  AND NOT has_table_privilege(current_user, 'ingest.jobs', 'DELETE')
  AND NOT has_table_privilege(current_user, 'ingest.worker_heartbeats', 'INSERT')
  AND NOT has_table_privilege(current_user, 'ingest.worker_heartbeats', 'UPDATE')
  AND NOT has_table_privilege(current_user, 'ingest.worker_heartbeats', 'DELETE')
  AND CASE %(worker_type)s
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
    AND (
      NOT %(bluesky_enabled)s::boolean
      OR (SELECT ready FROM bluesky_dependencies)
    )
    AND (
      NOT %(public_study_enabled)s::boolean
      OR (SELECT ready FROM public_study_dependencies)
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
      NOT %(public_study_enabled)s::boolean
      OR (
        to_regprocedure(
          'ingest.enqueue_scheduled_public_study_coverage_job_v1(text,timestamptz,text,integer,integer)'
        ) IS NOT NULL
        AND has_function_privilege(
          current_user,
          to_regprocedure(
            'ingest.enqueue_scheduled_public_study_coverage_job_v1(text,timestamptz,text,integer,integer)'
          ),
          'EXECUTE'
        )
      )
    )
    AND (
      NOT %(youtube_enabled)s::boolean
      OR (SELECT ready FROM youtube_dependencies)
    )
    AND (
      NOT %(bluesky_enabled)s::boolean
      OR (SELECT ready FROM bluesky_dependencies)
    )
    AND (
      NOT %(public_study_enabled)s::boolean
      OR (SELECT ready FROM public_study_dependencies)
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
    WorkerRole.COLLECTOR: (TCGDEX_SETS_JOB_TYPE,),
    WorkerRole.WATCHDOG: (CLEANUP_JOB_TYPE,),
}

_SCHEDULE_FIELDS: tuple[tuple[str, str], ...] = (
    ("official_api", "schedule_official_api"),
    ("public_collection", "schedule_public_collection"),
    ("bluesky_collection", "schedule_bluesky_collection"),
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
    if name not in {"official_api", "public_collection", "catalog_sync", "cleanup"}
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
    if role is not WorkerRole.COLLECTOR:
        return job_types
    enabled = list(job_types)
    if settings.youtube_collection_enabled:
        enabled.append(YOUTUBE_DISCOVERY_JOB_TYPE)
    if settings.public_study_collection_enabled:
        enabled.append(PUBLIC_STUDY_JOB_TYPE)
    if settings.bluesky_collection_enabled:
        enabled.append(BLUESKY_JETSTREAM_JOB_TYPE)
    return tuple(enabled)


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
            "bluesky_enabled": settings.bluesky_collection_enabled,
            "public_study_enabled": settings.public_study_collection_enabled,
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
    transport: YouTubeTransport | None,
    clock: Callable[[], datetime] | None,
) -> JobHandler:
    if not settings.youtube_collection_enabled:
        raise RuntimeError("YouTube discovery handler requires explicit credentials and enablement")
    direct_credential = (
        settings.youtube_api_key.get_secret_value().strip()
        if settings.youtube_api_key is not None
        else ""
    )
    maton_credential = (
        settings.maton_api_key.get_secret_value().strip()
        if settings.maton_api_key is not None
        else ""
    )
    if direct_credential:
        credential = direct_credential
        resolved_transport = transport or HTTPXYouTubeTransport()
    elif maton_credential and settings.youtube_maton_connection_id is not None:
        credential = maton_credential
        resolved_transport = transport or MatonYouTubeTransport(
            connection_id=str(settings.youtube_maton_connection_id)
        )
    else:
        raise RuntimeError("YouTube discovery handler requires explicit credentials and enablement")
    registry = YouTubeQueryRegistry.from_yaml(YOUTUBE_QUERIES_CONFIG)
    gates = PostgresYouTubeDiscoveryGate(executor)
    client = YouTubeDataClient(
        api_key=credential,
        transport=resolved_transport,
        policies=SourcePolicyRegistry.from_yaml(SOURCES_CONFIG),
        clock=clock,
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
            writes.append(
                YouTubeSourceItemWrite(
                    external_id=candidate.external_id or "",
                    source_url=candidate.source_url,
                    title=candidate.title,
                    published_at=candidate.published_at,
                    collector_version=candidate.collector_version,
                    source_policy_version=candidate.source_policy_version,
                )
            )
        return YouTubeDiscoveryCompletion(query_name=query.name, items=tuple(writes))

    return discover


def _bluesky_jetstream_handler(
    *,
    settings: Settings,
    executor: QueryExecutor,
    worker_id: str,
    transport: BlueskyJetstreamTransport | None,
) -> JobHandler:
    if not settings.bluesky_collection_enabled:
        raise RuntimeError("Bluesky Jetstream handler requires explicit enablement")
    registry = BlueskyKeywordRegistry.from_yaml(BLUESKY_KEYWORDS_CONFIG)
    gates = PostgresBlueskyJetstreamGate(executor)
    resolved_transport = transport or WebsocketsBlueskyJetstreamTransport()
    collector = BlueskyJetstreamCollector(
        transport=resolved_transport,
        keywords=registry,
        policies=SourcePolicyRegistry.from_yaml(SOURCES_CONFIG),
    )

    def discover(job: Job) -> BlueskyJetstreamCompletion:
        if job.kind != BLUESKY_JETSTREAM_JOB_TYPE or job.payload:
            raise ValueError("Bluesky Jetstream jobs require an empty payload")
        try:
            checkpoint = gates.begin(
                job_id=job.id,
                worker_id=worker_id,
                lease_generation=job.lease_generation,
            )
        except BlueskyRequestDeferred as deferred:
            raise JobDeferred(
                retry_at=deferred.retry_at,
                code="bluesky_request_deferred",
            ) from None
        try:
            result = collector.collect(start_cursor=checkpoint.start_cursor)
        except BlueskyError as error:
            raise JobExecutionError(code=error.code, retryable=error.retryable) from None
        return BlueskyJetstreamCompletion(
            start_cursor=result.start_cursor,
            end_cursor=result.end_cursor,
            events_seen=result.events_seen,
            bytes_seen=result.bytes_seen,
            candidates=tuple(
                BlueskySourceItemWrite(
                    cursor=item.cursor,
                    at_uri=item.at_uri,
                    public_url=item.public_url,
                    text_excerpt=item.text_excerpt,
                    record_sha256=item.record_sha256,
                    published_at=item.published_at,
                )
                for item in result.candidates
            ),
            deletions=tuple(
                BlueskyDeletionWrite(at_uri=item.at_uri, cursor=item.cursor)
                for item in result.deletions
            ),
        )

    return discover


def _public_study_handler(
    *,
    settings: Settings,
    executor: QueryExecutor,
    worker_id: str,
    http_client: HTTPClient | None,
    robots_sleeper: Callable[[float], None] | None,
) -> JobHandler:
    if not settings.public_study_collection_enabled or not settings.scrapling_enabled:
        raise RuntimeError("public-study handler requires explicit Scrapling enablement")
    client = http_client or ScraplingHTTPClient.live(
        timeout_seconds=settings.scrapling_request_timeout_seconds
    )
    robots = (
        RobotsTxtChecker(
            client=client,
            timeout_seconds=settings.scrapling_request_timeout_seconds,
            followup_delay_seconds=30.0,
        )
        if robots_sleeper is None
        else RobotsTxtChecker(
            client=client,
            timeout_seconds=settings.scrapling_request_timeout_seconds,
            followup_delay_seconds=30.0,
            sleeper=robots_sleeper,
        )
    )
    service = CollectionService(
        policies=SourcePolicyRegistry.from_yaml(SOURCES_CONFIG),
        http_adapters=build_live_static_registry(http_client=client),
        robots=robots,
    )
    gates = PostgresPublicStudyGate(executor)

    def collect_study(job: Job) -> PublicStudyCompletion:
        if job.kind != PUBLIC_STUDY_JOB_TYPE or set(job.payload) != {"study_key"}:
            raise ValueError("public-study jobs require the exact study_key payload")
        study_key = job.payload.get("study_key")
        if not isinstance(study_key, str):
            raise ValueError("public-study study_key must be text")
        identity = PUBLIC_STUDIES_BY_KEY.get(study_key)
        if identity is None:
            raise ValueError("public-study study_key is not approved")
        try:
            gates.begin(
                job_id=job.id,
                worker_id=worker_id,
                lease_generation=job.lease_generation,
                study_key=study_key,
            )
        except PublicStudyRequestDeferred as deferred:
            raise JobDeferred(
                retry_at=deferred.retry_at,
                code="public_study_request_deferred",
            ) from None
        try:
            candidates = service.collect_url(identity.fetch_url, route="static")
        except CollectorError as error:
            raise JobExecutionError(
                code="public_study_contract_failed",
                retryable=False,
            ) from error
        if len(candidates) != 1:
            raise JobExecutionError(code="public_study_result_invalid", retryable=False)
        candidate = candidates[0]
        if (
            candidate.external_id != study_key
            or candidate.title is None
            or candidate.text is None
            or candidate.content_sha256 is None
            or candidate.metadata
            != {"study_key": study_key, "parser_version": identity.parser_version}
        ):
            raise JobExecutionError(code="public_study_result_invalid", retryable=False)
        return PublicStudyCompletion(
            study_key=study_key,
            source_url=identity.source_url,
            title=candidate.title,
            evidence_excerpt=candidate.text,
            evidence_sha256=candidate.content_sha256,
            collector_version=candidate.collector_version,
            parser_version=identity.parser_version,
            source_policy_version=candidate.source_policy_version,
        )

    return collect_study


def _handlers_for_role(
    role: WorkerRole,
    *,
    settings: Settings,
    executor: QueryExecutor,
    worker_id: str,
    tcgdex_transport: TCGdexTransport | None,
    youtube_transport: YouTubeTransport | None,
    bluesky_transport: BlueskyJetstreamTransport | None,
    public_study_http_client: HTTPClient | None,
    public_study_robots_sleeper: Callable[[float], None] | None,
    clock: Callable[[], datetime] | None,
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
                transport=youtube_transport,
                clock=clock,
            )
        if settings.public_study_collection_enabled:
            handlers[PUBLIC_STUDY_JOB_TYPE] = _public_study_handler(
                settings=settings,
                executor=executor,
                worker_id=worker_id,
                http_client=public_study_http_client,
                robots_sleeper=public_study_robots_sleeper,
            )
        if settings.bluesky_collection_enabled:
            handlers[BLUESKY_JETSTREAM_JOB_TYPE] = _bluesky_jetstream_handler(
                settings=settings,
                executor=executor,
                worker_id=worker_id,
                transport=bluesky_transport,
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
    bluesky_transport: BlueskyJetstreamTransport | None = None,
    public_study_http_client: HTTPClient | None = None,
    public_study_robots_sleeper: Callable[[float], None] | None = None,
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
        bluesky_transport=bluesky_transport,
        public_study_http_client=public_study_http_client,
        public_study_robots_sleeper=public_study_robots_sleeper,
        clock=clock,
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
    public_studies = (
        tuple(
            ScheduleEntry(
                name=f"public_study_{study.study_key}",
                job_type=PUBLIC_STUDY_JOB_TYPE,
                cron=settings.schedule_public_collection,
                payload={"study_key": study.study_key},
                priority=14,
                max_attempts=min(3, settings.worker_max_attempts),
                catch_up_within=timedelta(hours=12),
                catch_up_check_interval=timedelta(hours=1),
            )
            for study in PUBLIC_STUDIES
        )
        if settings.public_study_collection_enabled
        else ()
    )
    bluesky = (
        (
            ScheduleEntry(
                name="bluesky_jetstream",
                job_type=BLUESKY_JETSTREAM_JOB_TYPE,
                cron=settings.schedule_bluesky_collection,
                payload={},
                priority=-50,
                max_attempts=min(3, settings.worker_max_attempts),
            ),
        )
        if settings.bluesky_collection_enabled
        else ()
    )
    cleanup_catch_up = (
        timedelta(hours=36)
        if settings.bluesky_collection_enabled
        else timedelta(hours=12)
        if settings.youtube_collection_enabled
        else None
    )
    cleanup = (
        ScheduleEntry(
            name="cleanup",
            job_type=CLEANUP_JOB_TYPE,
            cron=settings.schedule_cleanup,
            priority=10,
            max_attempts=settings.worker_max_attempts,
            # YouTube has a two-day expiry margin; Bluesky uses the full
            # reviewed retention window, so a restart must catch a missed
            # daily cleanup independently of whether YouTube is enabled.
            catch_up_within=cleanup_catch_up,
            catch_up_check_interval=(timedelta(hours=1) if cleanup_catch_up else None),
        ),
    )
    return catalog + youtube + public_studies + bluesky + cleanup


def build_live_scheduler(
    settings: Settings,
    *,
    executor: QueryExecutor | None = None,
) -> Scheduler:
    entries = live_schedule_entries(settings)
    database = executor or executor_from_settings(settings)
    return Scheduler(PostgresJobRepository(database), entries)
