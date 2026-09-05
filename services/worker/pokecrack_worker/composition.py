"""Fail-closed live PostgreSQL composition for the worker entry point.

Only job types with a bounded, database-backed implementation are registered
here. The collector supports fixed TCGdex catalog sync, explicitly enabled
YouTube metadata discovery, and a tiny allowlist of reviewed public studies;
AI and general URL collection remain unavailable.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit

from pokecrack_worker import __version__
from pokecrack_worker.collectors.base import CollectionService, CollectorError, HTTPClient
from pokecrack_worker.collectors.official_api.bluesky import (
    BlueskyCursorTooOldError,
    BlueskyError,
    BlueskyJetstreamCollector,
    BlueskyJetstreamTransport,
    WebsocketsBlueskyJetstreamTransport,
)
from pokecrack_worker.collectors.official_api.mastodon import (
    HTTPXMastodonTransport,
    MastodonError,
    MastodonPublicHashtagCollector,
    MastodonRateLimited,
    MastodonTransport,
)
from pokecrack_worker.collectors.official_api.nostr import (
    NostrError,
    NostrRelayCollector,
    NostrRelayTransport,
    WebsocketsNostrRelayTransport,
)
from pokecrack_worker.collectors.official_api.postgres import (
    BlueskyRequestDeferred,
    MastodonRequestDeferred,
    NostrRequestDeferred,
    PostgresBlueskyJetstreamGate,
    PostgresMastodonPublicHashtagGate,
    PostgresNostrRelayGate,
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
from pokecrack_worker.config.mastodon import MastodonRegistry
from pokecrack_worker.config.nostr import NostrRelayRegistry
from pokecrack_worker.config.public_studies import PUBLIC_STUDIES, PUBLIC_STUDIES_BY_KEY
from pokecrack_worker.config.registries import YouTubeQueryRegistry
from pokecrack_worker.config.settings import DataMode, Settings
from pokecrack_worker.config.source_policy import SourcePolicyRegistry
from pokecrack_worker.db import PsycopgQueryExecutor
from pokecrack_worker.jobs import (
    BlueskyCursorRecoveryCompletion,
    BlueskyDeletionWrite,
    BlueskyJetstreamCompletion,
    BlueskyPostgresJobRepository,
    BlueskySourceItemWrite,
    CompletionEffect,
    Job,
    MastodonPublicHashtagCompletion,
    MastodonStatusWrite,
    NostrCandidateWrite,
    NostrDeletionWrite,
    NostrPostgresJobRepository,
    NostrRelayCompletion,
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
    BLUESKY_COLLECTOR = "bluesky-collector"
    NOSTR_COLLECTOR = "nostr-collector"
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
NOSTR_RELAY_JOB_TYPE = "source.nostr.relay"
MASTODON_PUBLIC_HASHTAG_JOB_TYPE = "source.mastodon.public_hashtag"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
SOURCES_CONFIG = PROJECT_ROOT / "config" / "sources.yaml"
YOUTUBE_QUERIES_CONFIG = PROJECT_ROOT / "config" / "youtube-queries.yaml"
BLUESKY_KEYWORDS_CONFIG = PROJECT_ROOT / "config" / "bluesky-keywords.yaml"
NOSTR_RELAYS_CONFIG = PROJECT_ROOT / "config" / "nostr-relays.yaml"
MASTODON_CONFIG = PROJECT_ROOT / "config" / "mastodon.yaml"
MASTODON_INSTANCES_CONFIG = MASTODON_CONFIG

WORKER_HEARTBEAT_SQL = """
SELECT last_seen_at
FROM ingest.upsert_worker_heartbeat_v1(
    %(worker_id)s,
    %(worker_type)s,
    %(version)s,
    %(metadata)s::jsonb
)
""".strip()

NOSTR_WORKER_HEARTBEAT_SQL = """
SELECT last_seen_at
FROM ingest.upsert_nostr_worker_heartbeat_v1(
    %(worker_id)s,
    %(version)s,
    %(metadata)s::jsonb
)
""".strip()

BLUESKY_WORKER_HEARTBEAT_SQL = """
SELECT last_seen_at
FROM ingest.upsert_bluesky_worker_heartbeat_v1(
    %(worker_id)s,
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
    AND to_regprocedure(
      'ingest.recover_bluesky_cursor_too_old_job_v1(uuid,text,bigint,bigint)'
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
    AND has_function_privilege(
      current_user,
      to_regprocedure(
        'ingest.recover_bluesky_cursor_too_old_job_v1(uuid,text,bigint,bigint)'
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
          "stream_window_seconds":10,
          "subprotocol":"xrpc.v1.json"
        }'::jsonb
        AND policies.version = 'bluesky-jetstream-v1'
        AND policies.expected_interval_seconds = 60
    ),
    false
  ) AS ready
),
nostr_dependencies AS (
  SELECT COALESCE(
    to_regprocedure('ingest.begin_nostr_relay_job(uuid,text,bigint,text)') IS NOT NULL
    AND to_regprocedure(
      'ingest.finalize_nostr_relay_job(uuid,text,bigint,jsonb)'
    ) IS NOT NULL
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.begin_nostr_relay_job(uuid,text,bigint,text)'),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.finalize_nostr_relay_job(uuid,text,bigint,jsonb)'),
      'EXECUTE'
    )
    AND (
      SELECT
        count(*) = 3
        AND bool_and(
          policies.enabled
          AND NOT policies.is_demo
          AND policies.source_kind = 'public_web'
          AND policies.collector_type = 'nostr_relay'
          AND policies.access_mode = 'public'
          AND policies.robots_policy = 'not_applicable'
          AND policies.routes = ARRAY['nostr_relay']::text[]
          AND NOT policies.include_subdomains
          AND policies.min_delay_seconds = 1
          AND policies.max_pages_per_run = 1
          AND policies.max_items_per_run = 100
          AND policies.max_concurrency = 1
          AND policies.browser_profile IS NULL
          AND NOT policies.statistics_eligible_default
          AND policies.retention_days = 30
          AND policies.version = 'nostr-multi-relay-v1'
          AND policies.expected_interval_seconds = 60
          AND policies.config - 'relay_key' - 'endpoint' - 'nip11_url' = '{
            "protocol":"nip01",
            "required_nips":[1,9,11],
            "approved_tags":[
              "pokemontcg","PokemonTCG","pokemoncards","PokemonCards",
              "ポケカ","ポケモンカード","포켓몬카드","宝可梦卡牌","寶可夢卡牌"
            ],
            "replay_overlap_seconds":300,
            "stream_window_seconds":15,
            "max_events":100,
            "max_message_bytes":262144,
            "max_stream_bytes":2097152,
            "max_candidates":100,
            "max_deletions":100,
            "max_delete_targets":16,
            "statistics_eligible":false,
            "policy_state":"degraded_missing_relay_specific_terms"
          }'::jsonb
        )
        AND count(*) FILTER (
          WHERE policies.source_key = 'nostr_relay_primal'
            AND policies.domain = 'relay.primal.net'
            AND policies.base_url = 'wss://relay.primal.net/'
            AND policies.config ->> 'relay_key' = 'primal'
            AND policies.config ->> 'endpoint' = 'wss://relay.primal.net/'
            AND policies.config ->> 'nip11_url' = 'https://relay.primal.net/'
        ) = 1
        AND count(*) FILTER (
          WHERE policies.source_key = 'nostr_relay_nos_lol'
            AND policies.domain = 'nos.lol'
            AND policies.base_url = 'wss://nos.lol/'
            AND policies.config ->> 'relay_key' = 'nos_lol'
            AND policies.config ->> 'endpoint' = 'wss://nos.lol/'
            AND policies.config ->> 'nip11_url' = 'https://nos.lol/'
        ) = 1
        AND count(*) FILTER (
          WHERE policies.source_key = 'nostr_relay_nostr_net'
            AND policies.domain = 'relay.nostr.net'
            AND policies.base_url = 'wss://relay.nostr.net/'
            AND policies.config ->> 'relay_key' = 'nostr_net'
            AND policies.config ->> 'endpoint' = 'wss://relay.nostr.net/'
            AND policies.config ->> 'nip11_url' = 'https://relay.nostr.net/'
        ) = 1
      FROM ingest.source_policies AS policies
      WHERE policies.source_key IN (
        'nostr_relay_primal',
        'nostr_relay_nos_lol',
        'nostr_relay_nostr_net'
      )
    ),
    false
  ) AS ready
),
mastodon_dependencies AS (
  SELECT COALESCE(
    to_regprocedure(
      'ingest.begin_mastodon_public_hashtag_job(uuid,text,bigint,text,text)'
    ) IS NOT NULL
    AND to_regprocedure(
      'ingest.finalize_mastodon_public_hashtag_job(uuid,text,bigint,jsonb)'
    ) IS NOT NULL
    AND to_regprocedure(
      'ingest.record_mastodon_rate_limit(uuid,text,bigint,timestamptz)'
    ) IS NOT NULL
    AND has_function_privilege(
      current_user,
      to_regprocedure(
        'ingest.begin_mastodon_public_hashtag_job(uuid,text,bigint,text,text)'
      ),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure(
        'ingest.finalize_mastodon_public_hashtag_job(uuid,text,bigint,jsonb)'
      ),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure(
        'ingest.record_mastodon_rate_limit(uuid,text,bigint,timestamptz)'
      ),
      'EXECUTE'
    )
    AND (
      SELECT
        count(*) = 1
        AND bool_and(
          policies.enabled
          AND NOT policies.is_demo
          AND policies.source_kind = 'official_api'
          AND policies.collector_type = 'mastodon_rest'
          AND policies.access_mode = 'official_api'
          AND policies.robots_policy = 'not_applicable'
          AND policies.routes = ARRAY['mastodon_rest']::text[]
          AND NOT policies.include_subdomains
          AND policies.min_delay_seconds = 2
          AND policies.max_pages_per_run = 2
          AND policies.max_items_per_run = 80
          AND policies.max_concurrency = 1
          AND policies.browser_profile IS NULL
          AND NOT policies.statistics_eligible_default
          AND policies.retention_days = 30
          AND policies.version = 'mastodon-public-hashtag-v1'
          AND policies.expected_interval_seconds = 300
          AND policies.source_key = 'mastodon_social'
          AND policies.display_name = 'Mastodon public hashtag discovery'
          AND policies.domain = 'mastodon.social'
          AND policies.base_url = 'https://mastodon.social/'
          AND policies.config = '{
            "allow_redirects":false,
            "about_url":"https://mastodon.social/about",
            "approved_tags":{
              "pokeca_ja":"ポケカ",
              "pokemon_card_ja":"ポケモンカード",
              "pokemon_card_ko":"포켓몬카드",
              "pokemon_card_zh_hans":"宝可梦卡牌",
              "pokemon_card_zh_hant":"寶可夢卡牌",
              "pokemoncards":"pokemoncards",
              "pokemontcg":"pokemontcg"
            },
            "connect_timeout_seconds":10,
            "hashtag_base_url":"https://mastodon.social/api/v1/timelines/tag/",
            "instance_key":"mastodon_social",
            "instance_url":"https://mastodon.social/api/v2/instance",
            "limit":40,
            "max_items_per_run":80,
            "max_pages_per_run":2,
            "max_response_bytes":2097152,
            "official_docs_url":"https://docs.joinmastodon.org/methods/timelines/",
            "operator_acknowledgment":"recommended_before_production",
            "privacy_checked_at":"2026-08-31",
            "privacy_url":"https://mastodon.social/api/v1/instance/privacy_policy",
            "policy_state":"reviewed_public_api_2026-08-31",
            "read_timeout_seconds":15,
            "rate_limit_basis":"live_x_ratelimit_headers",
            "rate_limit_default_per_5m":300,
            "required_hashtag_access":{"local":"public","remote":"public"},
            "robots_checked_at":"2026-08-31",
            "robots_decision":"api_route_not_disallowed",
            "robots_url":"https://mastodon.social/robots.txt",
            "rules_url":"https://mastodon.social/api/v1/instance/rules",
            "rules_checked_at":"2026-08-31",
            "statistics_eligible":false,
            "tag_registry":"mastodon-tags-v1",
            "terms_checked_at":"2026-08-31",
            "terms_effective_date":"2026-08-31",
            "terms_url":"https://mastodon.social/api/v1/instance/terms_of_service",
            "checkpoint_retention":"opaque_cursor_persists_beyond_activity_ttl",
            "effective_max_requests_per_5m":150,
            "public_access_checked_at":"2026-08-31",
            "user_agent":"PokecrackMetadataCollector/0.1 (+https://pokecrack.vercel.app)"
          }'::jsonb
        )
      FROM ingest.source_policies AS policies
      WHERE policies.source_key = 'mastodon_social'
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
    AND to_regprocedure(
      'ingest.reviewed_public_study_gates_ready_v1()'
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
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.reviewed_public_study_gates_ready_v1()'),
      'EXECUTE'
    )
    AND ingest.reviewed_public_study_gates_ready_v1()
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
        count(*) = 10
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
        AND count(*) FILTER (
          WHERE policies.source_key = 'public_study_pokesup_jp_30'
            AND policies.display_name = 'PokeSup Abyss Eye 30-pack study'
            AND policies.domain = 'pokesup.com'
            AND policies.base_url = 'https://pokesup.com/blog/unboxing-m5/'
            AND policies.version = 'public-study-pokesup-abyss-eye-v1'
            AND policies.config = '{
              "study_key":"pokesup-abyss-eye-jp-30-v1",
              "canonical_url":"https://pokesup.com/blog/unboxing-m5/",
              "collector_version":"public-study-pokesup-abyss-eye-v1",
              "parser_version":"pokesup-abyss-eye-evidence-v1",
              "country_code":"JP",
              "country_name":"Japan",
              "geography_basis":"product_market",
              "geography_confidence":"tier_b",
              "set_external_id":"M5",
              "set_language":"ja",
              "set_name":"アビスアイ",
              "product_scope":"booster_box",
              "pack_count":30,
              "observed_at":"2026-05-22T12:01:44Z",
              "denominator_complete":true,
              "set_official_url":"https://www.pokemon-card.com/ex/m5/",
              "robots_url":"https://pokesup.com/robots.txt",
              "robots_checked_at":"2026-09-04",
              "terms_checked_at":"2026-09-04",
              "terms_status":"no_independent_terms_page",
              "rights_scope":"minimal_noncreative_facts_no_media_or_body_reuse"
            }'::jsonb
        ) = 1
        AND count(*) FILTER (
          WHERE policies.source_key = 'public_study_limitsend_kr_30'
            AND policies.display_name = 'LimitSend Inferno X 30-pack study'
            AND policies.domain = 'limitsend.tistory.com'
            AND policies.base_url = 'https://limitsend.tistory.com/entry/%%ED%%8F%%AC%%EC%%BC%%93%%EB%%AA%%AC%%EC%%B9%%B4%%EB%%93%%9C-%%EB%%82%%B1%%EA%%B0%%9C%%ED%%8C%%A9-%%EA%%B5%%AC%%EB%%A7%%A4%%EB%%A5%%BC-%%EC%%A1%%B0%%EC%%8B%%AC%%ED%%95%%B4%%EC%%95%%BC-%%ED%%95%%98%%EB%%8A%%94-%%EC%%9D%%B4%%EC%%9C%%A0%%EF%%BD%%9C%%EC%%9D%%B8%%ED%%8E%%98%%EB%%A5%%B4%%EB%%85%%B8X-%%EC%%A7%%81%%EC%%A0%%91-%%EA%%B0%%9C%%EB%%B4%%89%%ED%%95%%B4%%EB%%B3%%B4%%EB%%8B%%88'
            AND policies.version = 'public-study-limitsend-inferno-x-v1'
            AND policies.config = '{
              "study_key":"limitsend-inferno-x-kr-30-v1",
              "canonical_url":"https://limitsend.tistory.com/entry/%%ED%%8F%%AC%%EC%%BC%%93%%EB%%AA%%AC%%EC%%B9%%B4%%EB%%93%%9C-%%EB%%82%%B1%%EA%%B0%%9C%%ED%%8C%%A9-%%EA%%B5%%AC%%EB%%A7%%A4%%EB%%A5%%BC-%%EC%%A1%%B0%%EC%%8B%%AC%%ED%%95%%B4%%EC%%95%%BC-%%ED%%95%%98%%EB%%8A%%94-%%EC%%9D%%B4%%EC%%9C%%A0%%EF%%BD%%9C%%EC%%9D%%B8%%ED%%8E%%98%%EB%%A5%%B4%%EB%%85%%B8X-%%EC%%A7%%81%%EC%%A0%%91-%%EA%%B0%%9C%%EB%%B4%%89%%ED%%95%%B4%%EB%%B3%%B4%%EB%%8B%%88",
              "collector_version":"public-study-limitsend-inferno-x-v1",
              "parser_version":"limitsend-inferno-x-evidence-v1",
              "country_code":"KR",
              "country_name":"South Korea",
              "geography_basis":"product_market",
              "geography_confidence":"tier_b",
              "set_external_id":"M2",
              "set_language":"ko",
              "set_name":"인페르노X",
              "product_scope":"booster_box",
              "pack_count":30,
              "observed_at":"2026-08-20T14:20:28Z",
              "denominator_complete":true,
              "set_official_url":"https://pokemoncard.co.kr/card/838",
              "robots_url":"https://limitsend.tistory.com/robots.txt",
              "robots_checked_at":"2026-09-04",
              "terms_checked_at":"2026-09-04",
              "terms_status":"cc_by_nc_nd",
              "rights_scope":"minimal_noncreative_facts_no_media_or_body_reuse"
            }'::jsonb
        ) = 1
        AND count(*) FILTER (
          WHERE policies.source_key = 'public_study_buyfunlife_tw_40'
            AND policies.display_name = 'BuyFunLife Ninja Spinner 40-pack study'
            AND policies.domain = 'buyfunlife.com'
            AND policies.base_url = 'https://buyfunlife.com/pokemon-ninja-spinner-price-mur-guide/'
            AND policies.version = 'public-study-buyfunlife-ninja-spinner-v1'
            AND policies.config = '{
              "study_key":"buyfunlife-ninja-spinner-tw-40-v1",
              "canonical_url":"https://buyfunlife.com/pokemon-ninja-spinner-price-mur-guide/",
              "collector_version":"public-study-buyfunlife-ninja-spinner-v1",
              "parser_version":"buyfunlife-ninja-spinner-evidence-v1",
              "country_code":"TW",
              "country_name":"Taiwan",
              "geography_basis":"product_market",
              "geography_confidence":"tier_b",
              "set_external_id":"M4",
              "set_language":"zh-TW",
              "set_name":"忍者飛旋",
              "product_scope":"value_bundle",
              "pack_count":40,
              "observed_at":"2026-04-03T13:49:13Z",
              "denominator_complete":true,
              "set_official_url":"https://asia.pokemon-card.com/tw/archive/special/card/m4/",
              "robots_url":"https://buyfunlife.com/robots.txt",
              "robots_checked_at":"2026-09-04",
              "terms_checked_at":"2026-09-04",
              "terms_status":"site_disclaimer_reviewed",
              "rights_scope":"minimal_noncreative_facts_no_media_or_body_reuse"
            }'::jsonb
        ) = 1
        AND count(*) FILTER (
          WHERE policies.source_key = 'public_study_allonline_th_10'
            AND policies.display_name = 'ALL ONLINE Mega Dream ex 10-pack study'
            AND policies.domain = 'blog.allonline.7eleven.co.th'
            AND policies.base_url = 'https://blog.allonline.7eleven.co.th/collectibles-zone/pokemon-card-review-dream-evolution-ex-all-online/'
            AND policies.version = 'public-study-allonline-mega-dream-ex-v1'
            AND policies.config = '{
              "study_key":"allonline-mega-dream-ex-th-10-v1",
              "canonical_url":"https://blog.allonline.7eleven.co.th/collectibles-zone/pokemon-card-review-dream-evolution-ex-all-online/",
              "collector_version":"public-study-allonline-mega-dream-ex-v1",
              "parser_version":"allonline-mega-dream-ex-evidence-v1",
              "country_code":"TH",
              "country_name":"Thailand",
              "geography_basis":"product_market",
              "geography_confidence":"tier_b",
              "set_external_id":"MA3",
              "set_language":"th",
              "set_name":"วิวัฒนาการเมก้า ดรีมex",
              "product_scope":"booster_box",
              "pack_count":10,
              "observed_at":"2026-01-29T10:10:35Z",
              "denominator_complete":true,
              "set_official_url":"https://asia.pokemon-card.com/th/archives/6828/",
              "robots_url":"https://blog.allonline.7eleven.co.th/robots.txt",
              "robots_checked_at":"2026-09-04",
              "terms_checked_at":"2026-09-04",
              "terms_status":"allonline_terms_reviewed",
              "rights_scope":"minimal_noncreative_facts_no_media_or_body_reuse"
            }'::jsonb
        ) = 1
        AND count(*) FILTER (
          WHERE policies.source_key = 'public_study_pontocom_br_48'
            AND policies.display_name = 'PontoCOM Heróis Excelsos Brazil 48-pack study'
            AND policies.domain = 'pontocomdesenvolvimento.net'
            AND policies.base_url = 'https://pontocomdesenvolvimento.net/postagem/1028/herois-excelsos-vale-a-pena-abrir-uma-case-lacrada'
            AND policies.version = 'public-study-pontocom-herois-excelsos-v1'
            AND policies.config ->> 'study_key' = 'pontocom-herois-excelsos-br-48-v1'
            AND policies.config ->> 'country_code' = 'BR'
            AND policies.config ->> 'set_language' = 'pt-BR'
            AND policies.config ->> 'set_name' = 'Heróis Excelsos'
            AND policies.config ->> 'product_scope' = 'four_pack_blister'
            AND policies.config ->> 'pack_count' = '48'
            AND policies.config ->> 'qualifying_hit_pack_count' = '1'
            AND policies.config ->> 'qualifying_metric' = 'sir_pack'
            AND policies.config ->> 'metric_version' = 'global-sir-v1'
            AND policies.config ->> 'observed_at' = '2026-01-26T23:29:00Z'
            AND policies.config ->> 'denominator_complete' = 'true'
            AND policies.config ->> 'denominator_derivation' = '12×4'
            AND policies.config ->> 'video_id' = 'idfg-A54S1k'
            AND policies.config ->> 'video_review_method' = 'manual_timestamped_video_review'
            AND policies.config ->> 'robots_status' = '404_not_found_live_collection_blocked'
        ) = 1
      FROM ingest.source_policies AS policies
      WHERE policies.source_key IN (
        'public_study_comicbook_us_55',
        'public_study_wargamer_gb_17',
        'public_study_cardchill_gb_90',
        'public_study_bleedingcool_us_36',
        'public_study_tcgtalk_sg_54',
        'public_study_pokesup_jp_30',
        'public_study_limitsend_kr_30',
        'public_study_buyfunlife_tw_40',
        'public_study_allonline_th_10',
        'public_study_pontocom_br_48'
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
      NOT %(nostr_enabled)s::boolean
      OR (SELECT ready FROM nostr_dependencies)
    )
    AND (
      NOT %(mastodon_enabled)s::boolean
      OR (SELECT ready FROM mastodon_dependencies)
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
      NOT %(nostr_enabled)s::boolean
      OR (SELECT ready FROM nostr_dependencies)
    )
    AND (
      NOT %(mastodon_enabled)s::boolean
      OR (SELECT ready FROM mastodon_dependencies)
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

# The Bluesky collector has a separate database role and a source-scoped queue
# API. Keep this probe separate from the shared-worker probe so a Bluesky
# process cannot accidentally gain a dependency on a generic queue RPC or on
# another source's policy table contract.
BLUESKY_LIVE_ROLE_DEPENDENCIES_SQL = """
WITH bluesky_dependencies AS (
  SELECT COALESCE(
    to_regprocedure('ingest.enqueue_due_bluesky_jetstream_jobs_v1(text)') IS NOT NULL
    AND to_regprocedure('ingest.claim_bluesky_jetstream_jobs_v1(text,integer)') IS NOT NULL
    AND to_regprocedure(
      'ingest.heartbeat_bluesky_jetstream_job_v1(uuid,text,bigint,integer)'
    ) IS NOT NULL
    AND to_regprocedure(
      'ingest.fail_bluesky_jetstream_job_v1(uuid,text,bigint,text,text,boolean)'
    ) IS NOT NULL
    AND to_regprocedure(
      'ingest.pause_bluesky_jetstream_job_v1(uuid,text,bigint,timestamptz)'
    ) IS NOT NULL
    AND to_regprocedure('ingest.begin_bluesky_jetstream_job_v1(uuid,text,bigint)') IS NOT NULL
    AND to_regprocedure(
      'ingest.finalize_bluesky_jetstream_job_v1(uuid,text,bigint,jsonb)'
    ) IS NOT NULL
    AND to_regprocedure(
      'ingest.recover_bluesky_cursor_too_old_job_v2(uuid,text,bigint,bigint)'
    ) IS NOT NULL
    AND to_regprocedure('ingest.bluesky_worker_runtime_ready_v1()') IS NOT NULL
    AND to_regprocedure('ingest.get_bluesky_worker_policy_snapshot_v1()') IS NOT NULL
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.enqueue_due_bluesky_jetstream_jobs_v1(text)'),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.claim_bluesky_jetstream_jobs_v1(text,integer)'),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure(
        'ingest.heartbeat_bluesky_jetstream_job_v1(uuid,text,bigint,integer)'
      ),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure(
        'ingest.fail_bluesky_jetstream_job_v1(uuid,text,bigint,text,text,boolean)'
      ),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure(
        'ingest.pause_bluesky_jetstream_job_v1(uuid,text,bigint,timestamptz)'
      ),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.begin_bluesky_jetstream_job_v1(uuid,text,bigint)'),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure(
        'ingest.finalize_bluesky_jetstream_job_v1(uuid,text,bigint,jsonb)'
      ),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure(
        'ingest.recover_bluesky_cursor_too_old_job_v2(uuid,text,bigint,bigint)'
      ),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.bluesky_worker_runtime_ready_v1()'),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.get_bluesky_worker_policy_snapshot_v1()'),
      'EXECUTE'
    )
    AND ingest.bluesky_worker_runtime_ready_v1()
    AND (
      SELECT count(*) = 1
        AND bool_and(
          policies.source_key = 'bluesky_jetstream'
          AND policies.display_name = 'Bluesky Jetstream discovery'
          AND policies.source_kind = 'official_api'
          AND policies.domain = 'jetstream.us-west.bsky.network'
          AND policies.base_url =
            'wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents'
          AND policies.enabled
          AND policies.collector_type = 'bluesky_jetstream'
          AND policies.access_mode = 'official_api'
          AND policies.robots_policy = 'not_applicable'
          AND policies.routes = ARRAY['bluesky_jetstream']::text[]
          AND NOT policies.include_subdomains
          AND policies.min_delay_seconds = 1
          AND policies.max_pages_per_run = 1
          AND policies.max_items_per_run = 100
          AND policies.max_concurrency = 1
          AND policies.browser_profile IS NULL
          AND NOT policies.statistics_eligible_default
          AND policies.retention_days = 30
          AND policies.config = '{
            "endpoint":"wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents",
            "collection":"app.bsky.feed.post",
            "operations":["create","update","delete"],
            "kinds":["commit"],
            "subprotocol":"xrpc.v1.json",
            "stream_window_seconds":10,
            "max_events":10000,
            "max_message_bytes":262144,
            "max_stream_bytes":2097152,
            "max_candidates":100,
            "max_deletions":100,
            "max_excerpt_chars":500,
            "keyword_registry":"bluesky-keywords-v1",
            "statistics_eligible":false
          }'::jsonb
          AND policies.version = 'bluesky-jetstream-v1'
          AND policies.expected_interval_seconds = 60
          AND NOT policies.is_demo
        )
      FROM ingest.get_bluesky_worker_policy_snapshot_v1() AS policies
    ),
    false
  ) AS ready
)
SELECT %(worker_type)s = 'bluesky-collector'
  AND (SELECT ready FROM bluesky_dependencies)
  AND to_regprocedure(
    'ingest.upsert_bluesky_worker_heartbeat_v1(text,text,jsonb)'
  ) IS NOT NULL
  AND has_function_privilege(
    current_user,
    to_regprocedure(
      'ingest.upsert_bluesky_worker_heartbeat_v1(text,text,jsonb)'
    ),
    'EXECUTE'
  )
  AND NOT has_table_privilege(
    current_user,
    'ingest.jobs',
    'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN'
  )
  AND NOT has_any_column_privilege(
    current_user, 'ingest.jobs', 'SELECT,INSERT,UPDATE,REFERENCES'
  )
  AND NOT has_table_privilege(
    current_user,
    'ingest.worker_heartbeats',
    'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN'
  )
  AND NOT has_any_column_privilege(
    current_user, 'ingest.worker_heartbeats', 'SELECT,INSERT,UPDATE,REFERENCES'
  )
  AND NOT has_table_privilege(
    current_user,
    'ingest.source_request_gates',
    'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN'
  )
  AND NOT has_any_column_privilege(
    current_user, 'ingest.source_request_gates', 'SELECT,INSERT,UPDATE,REFERENCES'
  )
  AND NOT has_table_privilege(
    current_user,
    'ingest.bluesky_jetstream_candidates',
    'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN'
  )
  AND NOT has_any_column_privilege(
    current_user,
    'ingest.bluesky_jetstream_candidates',
    'SELECT,INSERT,UPDATE,REFERENCES'
  )
  AND NOT has_table_privilege(
    current_user,
    'ingest.bluesky_jetstream_observations',
    'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN'
  )
  AND NOT has_any_column_privilege(
    current_user,
    'ingest.bluesky_jetstream_observations',
    'SELECT,INSERT,UPDATE,REFERENCES'
  )
  AND NOT has_table_privilege(
    current_user,
    'ingest.bluesky_jetstream_checkpoints',
    'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN'
  )
  AND NOT has_any_column_privilege(
    current_user,
    'ingest.bluesky_jetstream_checkpoints',
    'SELECT,INSERT,UPDATE,REFERENCES'
  )
  AND NOT has_sequence_privilege(
    current_user,
    'ingest.bluesky_jetstream_observations_id_seq',
    'USAGE'
  )
  AND NOT has_sequence_privilege(
    current_user,
    'ingest.bluesky_jetstream_observations_id_seq',
    'SELECT'
  )
  AND NOT has_sequence_privilege(
    current_user,
    'ingest.bluesky_jetstream_observations_id_seq',
    'UPDATE'
  )
AS ready
""".strip()

# The Nostr collector has a separate database role and a source-scoped queue
# API.  Keep this probe separate from the shared-worker probe so a Nostr
# process cannot accidentally gain a dependency on a generic queue RPC or on
# another source's policy table contract.
NOSTR_LIVE_ROLE_DEPENDENCIES_SQL = """
WITH nostr_dependencies AS (
  SELECT COALESCE(
    to_regprocedure('ingest.enqueue_due_nostr_relay_jobs_v1(text)') IS NOT NULL
    AND to_regprocedure('ingest.claim_nostr_relay_jobs_v1(text,integer)') IS NOT NULL
    AND to_regprocedure(
      'ingest.heartbeat_nostr_relay_job_v1(uuid,text,bigint,integer)'
    ) IS NOT NULL
    AND to_regprocedure(
      'ingest.fail_nostr_relay_job_v1(uuid,text,bigint,text,text,boolean)'
    ) IS NOT NULL
    AND to_regprocedure(
      'ingest.pause_nostr_relay_job_v1(uuid,text,bigint,timestamptz)'
    ) IS NOT NULL
    AND to_regprocedure('ingest.begin_nostr_relay_job(uuid,text,bigint,text)') IS NOT NULL
    AND to_regprocedure(
      'ingest.finalize_nostr_relay_job(uuid,text,bigint,jsonb)'
    ) IS NOT NULL
    AND to_regprocedure('ingest.nostr_worker_runtime_ready_v1()') IS NOT NULL
    AND to_regprocedure(
      'ingest.get_nostr_worker_policy_snapshot_v1()'
    ) IS NOT NULL
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.enqueue_due_nostr_relay_jobs_v1(text)'),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.claim_nostr_relay_jobs_v1(text,integer)'),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure(
        'ingest.heartbeat_nostr_relay_job_v1(uuid,text,bigint,integer)'
      ),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure(
        'ingest.fail_nostr_relay_job_v1(uuid,text,bigint,text,text,boolean)'
      ),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure(
        'ingest.pause_nostr_relay_job_v1(uuid,text,bigint,timestamptz)'
      ),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.begin_nostr_relay_job(uuid,text,bigint,text)'),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.finalize_nostr_relay_job(uuid,text,bigint,jsonb)'),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.nostr_worker_runtime_ready_v1()'),
      'EXECUTE'
    )
    AND has_function_privilege(
      current_user,
      to_regprocedure('ingest.get_nostr_worker_policy_snapshot_v1()'),
      'EXECUTE'
    )
    AND ingest.nostr_worker_runtime_ready_v1()
    AND (
      SELECT
        count(*) = 3
        AND bool_and(
          policies.enabled
          AND NOT policies.is_demo
          AND policies.source_kind = 'public_web'
          AND policies.collector_type = 'nostr_relay'
          AND policies.access_mode = 'public'
          AND policies.robots_policy = 'not_applicable'
          AND policies.routes = ARRAY['nostr_relay']::text[]
          AND NOT policies.include_subdomains
          AND policies.min_delay_seconds = 1
          AND policies.max_pages_per_run = 1
          AND policies.max_items_per_run = 100
          AND policies.max_concurrency = 1
          AND policies.browser_profile IS NULL
          AND NOT policies.statistics_eligible_default
          AND policies.retention_days = 30
          AND policies.version = 'nostr-multi-relay-v1'
          AND policies.expected_interval_seconds = 60
          AND policies.config - 'relay_key' - 'endpoint' - 'nip11_url' = '{
            "protocol":"nip01",
            "required_nips":[1,9,11],
            "approved_tags":[
              "pokemontcg","PokemonTCG","pokemoncards","PokemonCards",
              "ポケカ","ポケモンカード","포켓몬카드","宝可梦卡牌","寶可夢卡牌"
            ],
            "replay_overlap_seconds":300,
            "stream_window_seconds":15,
            "max_events":100,
            "max_message_bytes":262144,
            "max_stream_bytes":2097152,
            "max_candidates":100,
            "max_deletions":100,
            "max_delete_targets":16,
            "statistics_eligible":false,
            "policy_state":"degraded_missing_relay_specific_terms"
          }'::jsonb
        )
        AND count(*) FILTER (
          WHERE policies.source_key = 'nostr_relay_primal'
            AND policies.display_name =
              'Nostr relay relay.primal.net discovery'
            AND policies.domain = 'relay.primal.net'
            AND policies.base_url = 'wss://relay.primal.net/'
            AND policies.config ->> 'relay_key' = 'primal'
            AND policies.config ->> 'endpoint' = 'wss://relay.primal.net/'
            AND policies.config ->> 'nip11_url' = 'https://relay.primal.net/'
        ) = 1
        AND count(*) FILTER (
          WHERE policies.source_key = 'nostr_relay_nos_lol'
            AND policies.display_name = 'Nostr relay nos.lol discovery'
            AND policies.domain = 'nos.lol'
            AND policies.base_url = 'wss://nos.lol/'
            AND policies.config ->> 'relay_key' = 'nos_lol'
            AND policies.config ->> 'endpoint' = 'wss://nos.lol/'
            AND policies.config ->> 'nip11_url' = 'https://nos.lol/'
        ) = 1
        AND count(*) FILTER (
          WHERE policies.source_key = 'nostr_relay_nostr_net'
            AND policies.display_name =
              'Nostr relay relay.nostr.net discovery'
            AND policies.domain = 'relay.nostr.net'
            AND policies.base_url = 'wss://relay.nostr.net/'
            AND policies.config ->> 'relay_key' = 'nostr_net'
            AND policies.config ->> 'endpoint' = 'wss://relay.nostr.net/'
            AND policies.config ->> 'nip11_url' = 'https://relay.nostr.net/'
        ) = 1
      FROM ingest.get_nostr_worker_policy_snapshot_v1() AS policies
    ),
    false
  ) AS ready
)
SELECT
  %(worker_type)s = 'nostr-collector'
  AND (SELECT ready FROM nostr_dependencies)
  AND to_regprocedure(
    'ingest.upsert_nostr_worker_heartbeat_v1(text,text,jsonb)'
  ) IS NOT NULL
  AND has_function_privilege(
    current_user,
    to_regprocedure(
      'ingest.upsert_nostr_worker_heartbeat_v1(text,text,jsonb)'
    ),
    'EXECUTE'
  )
  AND NOT has_table_privilege(
    current_user,
    'ingest.jobs',
    'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN'
  )
  AND NOT has_any_column_privilege(
    current_user, 'ingest.jobs', 'SELECT,INSERT,UPDATE,REFERENCES'
  )
  AND NOT has_table_privilege(
    current_user,
    'ingest.worker_heartbeats',
    'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN'
  )
  AND NOT has_any_column_privilege(
    current_user,
    'ingest.worker_heartbeats',
    'SELECT,INSERT,UPDATE,REFERENCES'
  )
  AND NOT has_table_privilege(
    current_user,
    'ingest.source_request_gates',
    'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN'
  )
  AND NOT has_any_column_privilege(
    current_user,
    'ingest.source_request_gates',
    'SELECT,INSERT,UPDATE,REFERENCES'
  )
  AND NOT has_table_privilege(
    current_user,
    'ingest.nostr_relay_candidates',
    'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN'
  )
  AND NOT has_any_column_privilege(
    current_user,
    'ingest.nostr_relay_candidates',
    'SELECT,INSERT,UPDATE,REFERENCES'
  )
  AND NOT has_table_privilege(
    current_user,
    'ingest.nostr_relay_observations',
    'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN'
  )
  AND NOT has_any_column_privilege(
    current_user,
    'ingest.nostr_relay_observations',
    'SELECT,INSERT,UPDATE,REFERENCES'
  )
  AND NOT has_table_privilege(
    current_user,
    'ingest.nostr_relay_checkpoints',
    'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN'
  )
  AND NOT has_any_column_privilege(
    current_user,
    'ingest.nostr_relay_checkpoints',
    'SELECT,INSERT,UPDATE,REFERENCES'
  )
  AND NOT has_sequence_privilege(
    current_user, 'ingest.nostr_relay_observations_id_seq', 'USAGE'
  )
  AND NOT has_sequence_privilege(
    current_user, 'ingest.nostr_relay_observations_id_seq', 'SELECT'
  )
  AND NOT has_sequence_privilege(
    current_user, 'ingest.nostr_relay_observations_id_seq', 'UPDATE'
  )
AS ready
""".strip()

_WORKER_JOB_TYPES: Mapping[WorkerRole, tuple[str, ...]] = {
    WorkerRole.COLLECTOR: (TCGDEX_SETS_JOB_TYPE,),
    WorkerRole.BLUESKY_COLLECTOR: (BLUESKY_JETSTREAM_JOB_TYPE,),
    WorkerRole.NOSTR_COLLECTOR: (NOSTR_RELAY_JOB_TYPE,),
    WorkerRole.WATCHDOG: (CLEANUP_JOB_TYPE,),
}

_SCHEDULE_FIELDS: tuple[tuple[str, str], ...] = (
    ("official_api", "schedule_official_api"),
    ("public_collection", "schedule_public_collection"),
    ("bluesky_collection", "schedule_bluesky_collection"),
    ("mastodon_collection", "schedule_mastodon_collection"),
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
    if name
    not in {
        "official_api",
        "public_collection",
        "bluesky_collection",
        "mastodon_collection",
        "catalog_sync",
        "cleanup",
    }
)


def _require_live_settings(settings: Settings) -> None:
    if settings.data_mode is not DataMode.LIVE:
        raise LiveCompositionError(
            "live_mode_required",
            "the PostgreSQL composition root requires DATA_MODE=live",
        )
    if settings.worker_role == WorkerRole.NOSTR_COLLECTOR.value:
        if settings.nostr_supabase_db_url is None:
            raise LiveCompositionError(
                "database_configuration_missing",
                "live Nostr collector requires NOSTR_SUPABASE_DB_URL",
            )
    elif settings.worker_role == WorkerRole.BLUESKY_COLLECTOR.value:
        if settings.bluesky_supabase_db_url is None:
            raise LiveCompositionError(
                "database_configuration_missing",
                "live Bluesky collector requires BLUESKY_SUPABASE_DB_URL",
            )
    elif settings.supabase_db_url is None:
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
    if role is WorkerRole.NOSTR_COLLECTOR:
        if not settings.nostr_collection_enabled:
            raise LiveCompositionError(
                "nostr_role_configuration_invalid",
                "WORKER_ROLE=nostr-collector requires NOSTR_COLLECTION_ENABLED=true",
            )
        if (
            settings.youtube_collection_enabled
            or settings.bluesky_collection_enabled
            or settings.public_study_collection_enabled
        ):
            raise LiveCompositionError(
                "nostr_role_configuration_invalid",
                "WORKER_ROLE=nostr-collector allows only NOSTR_COLLECTION_ENABLED",
            )
        return job_types
    if role is WorkerRole.BLUESKY_COLLECTOR:
        if not settings.bluesky_collection_enabled:
            raise LiveCompositionError(
                "bluesky_role_configuration_invalid",
                "WORKER_ROLE=bluesky-collector requires BLUESKY_COLLECTION_ENABLED=true",
            )
        if (
            settings.youtube_collection_enabled
            or settings.public_study_collection_enabled
            or settings.nostr_collection_enabled
            or settings.mastodon_collection_enabled
        ):
            raise LiveCompositionError(
                "bluesky_role_configuration_invalid",
                "WORKER_ROLE=bluesky-collector allows only BLUESKY_COLLECTION_ENABLED",
            )
        return job_types
    if role is not WorkerRole.COLLECTOR:
        return job_types
    if settings.nostr_collection_enabled:
        raise LiveCompositionError(
            "nostr_role_required",
            "NOSTR_COLLECTION_ENABLED requires WORKER_ROLE=nostr-collector",
        )
    if settings.bluesky_collection_enabled:
        raise LiveCompositionError(
            "bluesky_role_required",
            "BLUESKY_COLLECTION_ENABLED requires WORKER_ROLE=bluesky-collector",
        )
    enabled = list(job_types)
    if settings.youtube_collection_enabled:
        enabled.append(YOUTUBE_DISCOVERY_JOB_TYPE)
    if settings.public_study_collection_enabled:
        enabled.append(PUBLIC_STUDY_JOB_TYPE)
    if settings.mastodon_collection_enabled:
        enabled.append(MASTODON_PUBLIC_HASHTAG_JOB_TYPE)
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


_NOSTR_DATABASE_ROLE = "pokecrack_nostr_worker"
_NOSTR_DATABASE_LOGIN = "pokecrack_nostr_worker_login"
_RUNTIME_EVIDENCE_DATABASE_ROLE = "pokecrack_runtime_monitor"
_RUNTIME_EVIDENCE_DATABASE_LOGIN = "pokecrack_runtime_monitor_login"
_RUNTIME_EVIDENCE_CONNECT_TIMEOUT_SECONDS = 10
_RUNTIME_EVIDENCE_STATEMENT_TIMEOUT_SECONDS = 30
_NOSTR_DATABASE_QUERY_OPTIONS = frozenset(
    {
        "application_name",
        "channel_binding",
        "connect_timeout",
        "gssencmode",
        "options",
        "require_auth",
        "sslcert",
        "sslcrl",
        "sslcrldir",
        "sslkey",
        "sslmode",
        "sslnegotiation",
        "sslrootcert",
        "target_session_attrs",
    }
)
_NOSTR_DATABASE_SSL_MODES = frozenset({"require", "verify-ca", "verify-full"})
_BLUESKY_DATABASE_ROLE = "pokecrack_bluesky_worker"
_BLUESKY_DATABASE_LOGIN = "pokecrack_bluesky_worker_login"
_BLUESKY_DATABASE_SSL_MODES = _NOSTR_DATABASE_SSL_MODES
_BLUESKY_DATABASE_CONNECT_TIMEOUT = re.compile(r"^[1-9][0-9]*$")
_BLUESKY_DATABASE_MAX_CONNECT_TIMEOUT_SECONDS = 60


def _dsn_with_fixed_nostr_role(dsn: str) -> str:
    """Return a URL DSN with exactly one fixed Nostr role option."""

    parts = urlsplit(dsn)
    if (
        parts.scheme not in {"postgres", "postgresql"}
        or not parts.netloc
        or parts.fragment
        or unquote(parts.username or "") != _NOSTR_DATABASE_LOGIN
        or not parts.password
    ):
        raise LiveCompositionError(
            "nostr_database_url_invalid",
            "NOSTR_SUPABASE_DB_URL must use the dedicated worker login in an unfragmented PostgreSQL URL",
        )
    try:
        query = parse_qsl(
            parts.query,
            keep_blank_values=True,
            strict_parsing=True,
            max_num_fields=32,
        )
    except ValueError as error:
        raise LiveCompositionError(
            "nostr_database_url_invalid",
            "NOSTR_SUPABASE_DB_URL has an invalid query string",
        ) from error
    fixed_option = f"-c role={_NOSTR_DATABASE_ROLE}"
    query_keys = [key for key, _value in query]
    if len(query_keys) != len(set(query_keys)):
        raise LiveCompositionError(
            "nostr_database_url_invalid",
            "NOSTR_SUPABASE_DB_URL has duplicate query options",
        )
    if not set(query_keys) <= _NOSTR_DATABASE_QUERY_OPTIONS:
        raise LiveCompositionError(
            "nostr_database_url_invalid",
            "NOSTR_SUPABASE_DB_URL has an unsupported query option",
        )
    query_values = dict(query)
    if query_values.get("sslmode") not in _NOSTR_DATABASE_SSL_MODES:
        raise LiveCompositionError(
            "nostr_database_url_invalid",
            "NOSTR_SUPABASE_DB_URL requires sslmode=require or stronger",
        )
    existing_options = [value for key, value in query if key == "options"]
    if existing_options and existing_options != [fixed_option]:
        raise LiveCompositionError(
            "nostr_database_role_options_invalid",
            "NOSTR_SUPABASE_DB_URL may contain only the fixed Nostr role option",
        )
    if not existing_options:
        query.append(("options", fixed_option))
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query, quote_via=quote),
            "",
        )
    )


def _dsn_with_fixed_runtime_evidence_role(dsn: str) -> str:
    """Return a monitor DSN that cannot silently run as an unapproved login."""

    parts = urlsplit(dsn)
    if (
        parts.scheme not in {"postgres", "postgresql"}
        or not parts.netloc
        or unquote(parts.username or "") != _RUNTIME_EVIDENCE_DATABASE_LOGIN
        or parts.fragment
    ):
        raise LiveCompositionError(
            "runtime_evidence_database_url_invalid",
            "RUNTIME_RELEASE_EVIDENCE_DB_URL must use the dedicated monitor login in an unfragmented PostgreSQL URL",
        )
    try:
        query = parse_qsl(
            parts.query,
            keep_blank_values=True,
            strict_parsing=True,
            max_num_fields=32,
        )
    except ValueError as error:
        raise LiveCompositionError(
            "runtime_evidence_database_url_invalid",
            "RUNTIME_RELEASE_EVIDENCE_DB_URL has an invalid query string",
        ) from error
    query_keys = [key for key, _value in query]
    if len(query_keys) != len(set(query_keys)):
        raise LiveCompositionError(
            "runtime_evidence_database_url_invalid",
            "RUNTIME_RELEASE_EVIDENCE_DB_URL has duplicate query options",
        )
    if not set(query_keys) <= _NOSTR_DATABASE_QUERY_OPTIONS:
        raise LiveCompositionError(
            "runtime_evidence_database_url_invalid",
            "RUNTIME_RELEASE_EVIDENCE_DB_URL has an unsupported query option",
        )
    query_values = dict(query)
    if query_values.get("sslmode") not in _NOSTR_DATABASE_SSL_MODES:
        raise LiveCompositionError(
            "runtime_evidence_database_url_invalid",
            "RUNTIME_RELEASE_EVIDENCE_DB_URL requires sslmode=require or stronger",
        )
    fixed_option = f"-c role={_RUNTIME_EVIDENCE_DATABASE_ROLE}"
    existing_options = [value for key, value in query if key == "options"]
    if existing_options and existing_options != [fixed_option]:
        raise LiveCompositionError(
            "runtime_evidence_database_url_invalid",
            "RUNTIME_RELEASE_EVIDENCE_DB_URL may contain only the fixed monitor role option",
        )
    if not existing_options:
        query.append(("options", fixed_option))
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query, quote_via=quote),
            "",
        )
    )


def _dsn_with_fixed_bluesky_role(dsn: str) -> str:
    """Return a URL DSN with exactly one fixed Bluesky role option."""

    parts = urlsplit(dsn)
    if (
        parts.scheme not in {"postgres", "postgresql"}
        or not parts.netloc
        or parts.fragment
        or unquote(parts.username or "") != _BLUESKY_DATABASE_LOGIN
        or not parts.password
    ):
        raise LiveCompositionError(
            "bluesky_database_url_invalid",
            "BLUESKY_SUPABASE_DB_URL must use the dedicated worker login in an unfragmented PostgreSQL URL",
        )
    try:
        query = parse_qsl(
            parts.query,
            keep_blank_values=True,
            strict_parsing=True,
            max_num_fields=32,
        )
    except ValueError as error:
        raise LiveCompositionError(
            "bluesky_database_url_invalid",
            "BLUESKY_SUPABASE_DB_URL has an invalid query string",
        ) from error
    fixed_option = f"-c role={_BLUESKY_DATABASE_ROLE}"
    query_keys = [key for key, _value in query]
    if len(query_keys) != len(set(query_keys)):
        raise LiveCompositionError(
            "bluesky_database_url_invalid",
            "BLUESKY_SUPABASE_DB_URL has duplicate query options",
        )
    if not set(query_keys) <= _NOSTR_DATABASE_QUERY_OPTIONS:
        raise LiveCompositionError(
            "bluesky_database_url_invalid",
            "BLUESKY_SUPABASE_DB_URL has an unsupported query option",
        )
    query_values = dict(query)
    if query_values.get("sslmode") not in _BLUESKY_DATABASE_SSL_MODES:
        raise LiveCompositionError(
            "bluesky_database_url_invalid",
            "BLUESKY_SUPABASE_DB_URL requires sslmode=require or stronger",
        )
    connect_timeout = query_values.get("connect_timeout")
    if (
        connect_timeout is None
        or _BLUESKY_DATABASE_CONNECT_TIMEOUT.fullmatch(connect_timeout) is None
        or len(connect_timeout) > len(str(_BLUESKY_DATABASE_MAX_CONNECT_TIMEOUT_SECONDS))
        or int(connect_timeout) > _BLUESKY_DATABASE_MAX_CONNECT_TIMEOUT_SECONDS
    ):
        raise LiveCompositionError(
            "bluesky_database_url_invalid",
            "BLUESKY_SUPABASE_DB_URL requires a positive bounded connect_timeout",
        )
    existing_options = [value for key, value in query if key == "options"]
    if existing_options and existing_options != [fixed_option]:
        raise LiveCompositionError(
            "bluesky_database_role_options_invalid",
            "BLUESKY_SUPABASE_DB_URL may contain only the fixed Bluesky role option",
        )
    if not existing_options:
        query.append(("options", fixed_option))
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query, quote_via=quote),
            "",
        )
    )


def executor_from_settings(settings: Settings) -> PsycopgQueryExecutor:
    _require_live_settings(settings)
    role = require_supported_role(settings)
    if role is WorkerRole.NOSTR_COLLECTOR:
        assert settings.nostr_supabase_db_url is not None
        return PsycopgQueryExecutor.from_dsn(
            _dsn_with_fixed_nostr_role(settings.nostr_supabase_db_url.get_secret_value()),
            retry_connection=True,
        )
    if role is WorkerRole.BLUESKY_COLLECTOR:
        assert settings.bluesky_supabase_db_url is not None
        return PsycopgQueryExecutor.from_dsn(
            _dsn_with_fixed_bluesky_role(settings.bluesky_supabase_db_url.get_secret_value())
        )
    assert settings.supabase_db_url is not None
    return PsycopgQueryExecutor.from_dsn(settings.supabase_db_url.get_secret_value())


def runtime_release_evidence_executor(settings: Settings) -> PsycopgQueryExecutor:
    """Build the dedicated monitor connection; worker roles cannot call the RPC."""

    _require_live_settings(settings)
    if settings.runtime_release_evidence_db_url is None:
        raise LiveCompositionError(
            "runtime_evidence_database_url_missing",
            "runtime release verification requires the dedicated monitor database URL",
        )
    return PsycopgQueryExecutor.from_dsn(
        _dsn_with_fixed_runtime_evidence_role(
            settings.runtime_release_evidence_db_url.get_secret_value()
        ),
        connect_timeout_seconds=_RUNTIME_EVIDENCE_CONNECT_TIMEOUT_SECONDS,
        statement_timeout_seconds=_RUNTIME_EVIDENCE_STATEMENT_TIMEOUT_SECONDS,
    )


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
    dependency_sql = (
        NOSTR_LIVE_ROLE_DEPENDENCIES_SQL
        if role is WorkerRole.NOSTR_COLLECTOR
        else BLUESKY_LIVE_ROLE_DEPENDENCIES_SQL
        if role is WorkerRole.BLUESKY_COLLECTOR
        else LIVE_ROLE_DEPENDENCIES_SQL
    )
    dependency_params: Mapping[str, object]
    if role in {WorkerRole.NOSTR_COLLECTOR, WorkerRole.BLUESKY_COLLECTOR}:
        dependency_params = {"worker_type": role.value}
    else:
        dependency_params = {
            "worker_type": role.value,
            "youtube_enabled": settings.youtube_collection_enabled,
            "bluesky_enabled": settings.bluesky_collection_enabled,
            "nostr_enabled": settings.nostr_collection_enabled,
            "mastodon_enabled": settings.mastodon_collection_enabled,
            "public_study_enabled": settings.public_study_collection_enabled,
        }
    dependency_rows = database.query(dependency_sql, dependency_params)
    if not dependency_rows or dependency_rows[0].get("ready") is not True:
        raise LiveCompositionError(
            "live_dependencies_unavailable",
            "the configured role database dependencies are unavailable",
        )
    heartbeat_sql = (
        NOSTR_WORKER_HEARTBEAT_SQL
        if role is WorkerRole.NOSTR_COLLECTOR
        else BLUESKY_WORKER_HEARTBEAT_SQL
        if role is WorkerRole.BLUESKY_COLLECTOR
        else WORKER_HEARTBEAT_SQL
    )
    metadata_values: dict[str, object] = {
        "command": "health",
        "data_mode": settings.data_mode.value,
        "max_concurrency": settings.worker_max_concurrency,
        "role_ready": role_is_ready(role),
    }
    metadata = json.dumps(
        metadata_values,
        separators=(",", ":"),
        sort_keys=True,
    )
    heartbeat_params: dict[str, object] = {
        "worker_id": settings.worker_id,
        "version": __version__,
        "metadata": metadata,
    }
    if role not in {WorkerRole.NOSTR_COLLECTOR, WorkerRole.BLUESKY_COLLECTOR}:
        heartbeat_params["worker_type"] = role.value
    rows = database.query(heartbeat_sql, heartbeat_params)
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

    def discover(job: Job) -> BlueskyJetstreamCompletion | BlueskyCursorRecoveryCompletion:
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
        except BlueskyCursorTooOldError:
            if checkpoint.start_cursor is None:
                raise JobExecutionError(
                    code="bluesky_cursor_reset_invalid",
                    retryable=False,
                ) from None
            return BlueskyCursorRecoveryCompletion(start_cursor=checkpoint.start_cursor)
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


def _nostr_relay_handler(
    *,
    settings: Settings,
    executor: QueryExecutor,
    worker_id: str,
    transport: NostrRelayTransport | None,
) -> JobHandler:
    if not settings.nostr_collection_enabled:
        raise RuntimeError("Nostr relay handler requires explicit enablement")
    registry = NostrRelayRegistry.from_yaml(NOSTR_RELAYS_CONFIG)
    collector = NostrRelayCollector(
        transport=transport or WebsocketsNostrRelayTransport(),
        registry=registry,
    )
    gates = PostgresNostrRelayGate(executor)

    def discover(job: Job) -> NostrRelayCompletion:
        if job.kind != NOSTR_RELAY_JOB_TYPE or set(job.payload) != {"relay_key"}:
            raise ValueError("Nostr jobs require the exact relay_key payload")
        relay_key = job.payload.get("relay_key")
        if not isinstance(relay_key, str):
            raise ValueError("Nostr relay_key must be text")
        registry.require(relay_key)
        try:
            checkpoint = gates.begin(
                job_id=job.id,
                worker_id=worker_id,
                lease_generation=job.lease_generation,
                relay_key=relay_key,
            )
        except NostrRequestDeferred as deferred:
            raise JobDeferred(
                retry_at=deferred.retry_at,
                code="nostr_request_deferred",
            ) from None
        try:
            result = collector.collect(
                relay_key=relay_key,
                since=checkpoint.since,
                until=checkpoint.until,
                checkpoint=checkpoint.checkpoint,
                known_event_ids=checkpoint.recent_candidate_ids,
            )
        except NostrError as error:
            raise JobExecutionError(code=error.code, retryable=error.retryable) from None
        return NostrRelayCompletion(
            relay_key=result.relay_key,
            since=result.since,
            until=result.until,
            checkpoint=result.checkpoint,
            incomplete=result.incomplete,
            events_seen=result.events_seen,
            bytes_seen=result.bytes_seen,
            candidates=tuple(
                NostrCandidateWrite(
                    event_id=item.event_id,
                    author_sha256=item.author_sha256,
                    published_at=item.published_at,
                    content_sha256=item.content_sha256,
                    matched_tags=item.matched_tags,
                    relay_key=item.relay_key,
                )
                for item in result.candidates
            ),
            deletions=tuple(
                NostrDeletionWrite(
                    event_id=item.event_id,
                    author_sha256=item.author_sha256,
                    published_at=item.published_at,
                    relay_key=item.relay_key,
                    target_event_ids=item.target_event_ids,
                )
                for item in result.deletions
            ),
        )

    return discover


def _mastodon_public_hashtag_handler(
    *,
    settings: Settings,
    executor: QueryExecutor,
    worker_id: str,
    transport: MastodonTransport | None,
) -> JobHandler:
    if not settings.mastodon_collection_enabled:
        raise RuntimeError("Mastodon handler requires explicit enablement")
    registry = MastodonRegistry.from_yaml(MASTODON_CONFIG)
    collector = MastodonPublicHashtagCollector(
        transport=transport or HTTPXMastodonTransport(),
        registry=registry,
    )
    gates = PostgresMastodonPublicHashtagGate(executor)

    def discover(job: Job) -> MastodonPublicHashtagCompletion:
        if job.kind != MASTODON_PUBLIC_HASHTAG_JOB_TYPE or set(job.payload) != {
            "instance_key",
            "tag_key",
        }:
            raise ValueError("Mastodon jobs require the exact instance_key/tag_key payload")
        instance_key = job.payload.get("instance_key")
        tag_key = job.payload.get("tag_key")
        if not isinstance(instance_key, str) or not isinstance(tag_key, str):
            raise ValueError("Mastodon instance_key and tag_key must be text")
        registry.require_instance(instance_key)
        registry.require_tag(tag_key)
        try:
            checkpoint = gates.begin(
                job_id=job.id,
                worker_id=worker_id,
                lease_generation=job.lease_generation,
                instance_key=instance_key,
                tag_key=tag_key,
            )
        except MastodonRequestDeferred as deferred:
            raise JobDeferred(
                retry_at=deferred.retry_at,
                code="mastodon_request_deferred",
            ) from None
        try:
            result = collector.collect(
                instance_key=instance_key,
                tag_key=tag_key,
                start_status_id=checkpoint.last_status_id,
            )
        except MastodonRateLimited as error:
            if error.retry_at is not None:
                gates.record_rate_limit(
                    job_id=job.id,
                    worker_id=worker_id,
                    lease_generation=job.lease_generation,
                    retry_at=error.retry_at,
                )
                raise JobDeferred(
                    retry_at=error.retry_at,
                    code="mastodon_rate_limited",
                    pause_applied=True,
                ) from None
            raise JobExecutionError(code=error.code, retryable=True) from None
        except MastodonError as error:
            raise JobExecutionError(code=error.code, retryable=error.retryable) from None
        return MastodonPublicHashtagCompletion(
            instance_key=result.instance_key,
            tag_key=result.tag_key,
            start_status_id=result.start_status_id,
            end_status_id=result.end_status_id,
            incomplete=result.incomplete,
            requests_made=result.requests_made,
            statuses_seen=result.statuses_seen,
            bytes_seen=result.bytes_seen,
            candidates=tuple(
                MastodonStatusWrite(
                    status_id=item.status_id,
                    status_key_sha256=item.status_key_sha256,
                    published_at=item.published_at,
                    matched_tags=item.matched_tags,
                )
                for item in result.candidates
            ),
            rate_limit_limit=result.rate_limit_limit,
            rate_limit_remaining=result.rate_limit_remaining,
            rate_limit_reset_at=result.rate_limit_reset_at,
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
    nostr_transport: NostrRelayTransport | None,
    mastodon_transport: MastodonTransport | None,
    public_study_http_client: HTTPClient | None,
    public_study_robots_sleeper: Callable[[float], None] | None,
    clock: Callable[[], datetime] | None,
) -> Mapping[str, JobHandler]:
    if role is WorkerRole.BLUESKY_COLLECTOR:
        return {
            BLUESKY_JETSTREAM_JOB_TYPE: _bluesky_jetstream_handler(
                settings=settings,
                executor=executor,
                worker_id=worker_id,
                transport=bluesky_transport,
            )
        }
    if role is WorkerRole.NOSTR_COLLECTOR:
        return {
            NOSTR_RELAY_JOB_TYPE: _nostr_relay_handler(
                settings=settings,
                executor=executor,
                worker_id=worker_id,
                transport=nostr_transport,
            )
        }
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
        if settings.mastodon_collection_enabled:
            handlers[MASTODON_PUBLIC_HASHTAG_JOB_TYPE] = _mastodon_public_hashtag_handler(
                settings=settings,
                executor=executor,
                worker_id=worker_id,
                transport=mastodon_transport,
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
    nostr_transport: NostrRelayTransport | None = None,
    mastodon_transport: MastodonTransport | None = None,
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
        nostr_transport=nostr_transport,
        mastodon_transport=mastodon_transport,
        public_study_http_client=public_study_http_client,
        public_study_robots_sleeper=public_study_robots_sleeper,
        clock=clock,
    )
    if tuple(handlers) != expected_job_types:
        raise RuntimeError("live worker handler registry is inconsistent")
    repository = (
        BlueskyPostgresJobRepository(database)
        if role is WorkerRole.BLUESKY_COLLECTOR
        else NostrPostgresJobRepository(database)
        if role is WorkerRole.NOSTR_COLLECTOR
        else PostgresJobRepository(database)
    )
    return WorkerRuntime(
        repository,
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
    mastodon_registry = (
        MastodonRegistry.from_yaml(MASTODON_CONFIG)
        if settings.mastodon_collection_enabled
        else None
    )
    mastodon = (
        tuple(
            ScheduleEntry(
                name=f"{instance.key}_{tag.key}",
                job_type=MASTODON_PUBLIC_HASHTAG_JOB_TYPE,
                cron=settings.schedule_mastodon_collection,
                payload={"instance_key": instance.key, "tag_key": tag.key},
                priority=-48,
                max_attempts=min(3, settings.worker_max_attempts),
            )
            for instance in mastodon_registry.instances
            for tag in mastodon_registry.tags
        )
        if mastodon_registry is not None
        else ()
    )
    cleanup = (
        ScheduleEntry(
            name="cleanup",
            job_type=CLEANUP_JOB_TYPE,
            cron=settings.schedule_cleanup,
            priority=10,
            max_attempts=settings.worker_max_attempts,
            # Cleanup is source-agnostic. Preserve the reviewed 36-hour
            # recovery bound even when only the isolated Nostr collector is
            # enabled and the generic scheduler owns no Nostr configuration.
            catch_up_within=timedelta(hours=36),
            catch_up_check_interval=timedelta(hours=1),
        ),
    )
    # Bluesky is scheduled by its fixed source-scoped claim wrapper. Keeping
    # it out of this scheduler prevents a generic queue producer from creating
    # jobs that a broad collector could accidentally claim.
    return catalog + youtube + public_studies + mastodon + cleanup


def build_live_scheduler(
    settings: Settings,
    *,
    executor: QueryExecutor | None = None,
) -> Scheduler:
    entries = live_schedule_entries(settings)
    database = executor or executor_from_settings(settings)
    return Scheduler(PostgresJobRepository(database), entries)
