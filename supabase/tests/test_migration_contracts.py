import hashlib
import re
from decimal import Decimal
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SUPABASE_CONFIG = (ROOT / "config.toml").read_text()
MIGRATION_WORKFLOW = (ROOT.parent / ".github/workflows/migrate-database.yml").read_text()
CATALOG = (ROOT / "migrations/20260825000100_catalog.sql").read_text()
INGEST = (ROOT / "migrations/20260825000200_ingest.sql").read_text()
ANALYTICS = (ROOT / "migrations/20260825000300_analytics.sql").read_text()
PUBLIC = (ROOT / "migrations/20260825000400_public_tables.sql").read_text()
RPC = (ROOT / "migrations/20260825000500_public_rpc_security.sql").read_text()
FENCING = (ROOT / "migrations/20260827000000_job_lease_fencing.sql").read_text()
TCGDEX_PIPELINE = (ROOT / "migrations/20260828000000_tcgdex_sets_pipeline.sql").read_text()
BACKUP_GATE_LOCK = (
    ROOT / "migrations/20260828500000_backup_request_gate_lock.sql"
).read_text()
ADMIN_SESSION_FENCE = (
    ROOT / "migrations/20260828750000_admin_session_fence.sql"
).read_text()
YOUTUBE_PIPELINE = (ROOT / "migrations/20260829000000_youtube_global_discovery.sql").read_text()
GLOBAL_DASHBOARD = (ROOT / "migrations/20260830000000_global_live_dashboard.sql").read_text()
PUBLIC_STUDY_PIPELINE = (
    ROOT / "migrations/20260831000000_public_study_pipeline.sql"
).read_text()
PUBLIC_PIPELINE_SNAPSHOT = (
    ROOT / "migrations/20260901000000_public_pipeline_snapshot.sql"
).read_text()
REVIEWED_GLOBAL_EVIDENCE = (
    ROOT / "migrations/20260902000000_reviewed_global_evidence.sql"
).read_text()
BLUESKY_JETSTREAM = (
    ROOT / "migrations/20260903000000_bluesky_jetstream_discovery.sql"
).read_text()
BLUESKY_RUNTIME_BOUNDS = (
    ROOT / "migrations/20260905000000_bluesky_runtime_bounds.sql"
).read_text()
NOSTR_MULTI_RELAY = (
    ROOT / "migrations/20260906000000_nostr_multi_relay_discovery.sql"
).read_text()
NOSTR_CLEANUP_CAPACITY = (
    ROOT / "migrations/20260909000000_nostr_cleanup_capacity.sql"
).read_text()
NOSTR_WORKER_ISOLATION = (
    ROOT / "migrations/20260910000000_nostr_worker_role_isolation.sql"
).read_text()
MASTODON_PUBLIC_HASHTAG = (
    ROOT / "migrations/20260912000000_mastodon_public_hashtag_discovery.sql"
).read_text()
MASTODON_COMPLIANCE_HARDENING = (
    ROOT / "migrations/20260912010000_mastodon_compliance_hardening.sql"
).read_text()
DATABASE_TYPES = (ROOT / "types/database.ts").read_text()
SEED = (ROOT / "seed.sql").read_text()


def _split_sql_values(value_list: str) -> list[str]:
    values: list[str] = []
    start = 0
    depth = 0
    quoted = False
    index = 0
    while index < len(value_list):
        character = value_list[index]
        if character == "'":
            if quoted and index + 1 < len(value_list) and value_list[index + 1] == "'":
                index += 2
                continue
            quoted = not quoted
        elif not quoted:
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
            elif character == "," and depth == 0:
                values.append(value_list[start:index].strip())
                start = index + 1
        index += 1
    values.append(value_list[start:].strip())
    return values


def _seed_rows(table: str) -> list[dict[str, str]]:
    match = re.search(
        rf"insert into {re.escape(table)} \((.*?)\) values\s*(.*?)\s*on conflict do nothing;",
        SEED,
        flags=re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"missing seed insert for {table}")
    columns = [column.strip() for column in match.group(1).split(",")]
    body = match.group(2)
    row_values: list[str] = []
    quoted = False
    depth = 0
    start: int | None = None
    index = 0
    while index < len(body):
        character = body[index]
        if character == "'":
            if quoted and index + 1 < len(body) and body[index + 1] == "'":
                index += 2
                continue
            quoted = not quoted
        elif not quoted:
            if character == "(":
                if depth == 0:
                    start = index + 1
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0 and start is not None:
                    row_values.append(body[start:index])
                    start = None
        index += 1
    rows = [_split_sql_values(row) for row in row_values]
    if any(len(row) != len(columns) for row in rows):
        raise AssertionError(f"could not parse seed values for {table}")
    return [dict(zip(columns, row, strict=True)) for row in rows]


def _sql_text(value: str) -> str:
    stripped = value.strip()
    if not (stripped.startswith("'") and stripped.endswith("'")):
        raise AssertionError(f"expected SQL text literal, got {value}")
    return stripped[1:-1].replace("''", "'")


class IngestMigrationContractTests(unittest.TestCase):
    def test_bluesky_jetstream_is_bounded_private_and_public_safe(self) -> None:
        lowered = BLUESKY_JETSTREAM.casefold()
        compact = " ".join(lowered.split())
        self.assertEqual(lowered.count("begin;"), 1)
        self.assertEqual(lowered.count("commit;"), 1)
        self.assertIn("'bluesky_jetstream'", lowered)
        self.assertIn("'source.bluesky.jetstream'", lowered)
        self.assertIn("jetstream.us-west.bsky.network", lowered)
        self.assertIn("'xrpc.v1.json'", lowered)
        self.assertIn('"stream_window_seconds":40', lowered)
        self.assertIn('"max_events":10000', lowered)
        self.assertIn('"max_stream_bytes":2097152', lowered)
        self.assertIn('"keyword_registry":"bluesky-keywords-v1"', lowered)

        for table in (
            "bluesky_jetstream_candidates",
            "bluesky_jetstream_observations",
            "bluesky_jetstream_checkpoints",
        ):
            self.assertIn(f"alter table ingest.{table} force row level security", compact)
            self.assertIn(f"grant select on table ingest.{table} to service_role", compact)
            for mutation in ("insert", "update", "delete"):
                self.assertNotIn(f"grant {mutation} on table ingest.{table}", compact)

        finalizer = lowered.split(
            "create or replace function ingest.finalize_bluesky_jetstream_job", 1
        )[1].split(
            "alter function ingest.finalize_bluesky_jetstream_job", 1
        )[0]
        for fragment in (
            "security definer",
            "set search_path = pg_catalog",
            "for update of jobs",
            "result ->> 'version' <> '1.0.0'",
            "result_events_seen > 10000",
            "result_bytes_seen > 2097152",
            "candidate_count > 100",
            "deletion_count > 100",
            "result_start_cursor is distinct from checkpoint.last_cursor",
            "checkpoints.last_cursor is not distinct from result_start_cursor",
            "candidate_cursor <= result_start_cursor",
            "deletion_cursor <= result_start_cursor",
            "completion_time + interval '1 day'",
            "deleted_at = null",
        ):
            self.assertIn(fragment, finalizer)
        deletion_loop = finalizer.split(
            "for deletion_record in", 2
        )[-1]
        self.assertIn("insert into ingest.bluesky_jetstream_observations", deletion_loop)
        self.assertIn("update ingest.bluesky_jetstream_candidates", deletion_loop)
        self.assertNotIn("insert into ingest.bluesky_jetstream_candidates", deletion_loop)

        self.assertIn("prune_bluesky_jetstream_v1", lowered)
        self.assertIn("for update of candidates skip locked", lowered)
        self.assertIn("for update of observations skip locked", lowered)
        self.assertNotIn("delete from ingest.bluesky_jetstream_checkpoints", lowered)

        public_rpc = lowered.split(
            "create or replace function public.get_public_social_discovery_v1()", 1
        )[1].split(
            "alter function public.get_public_social_discovery_v1()", 1
        )[0]
        for public_key in (
            "'schemaversion'",
            "'sources'",
            "'lastcollectedat'",
            "'bluesky_jetstream'",
            "'https://bsky.network/docs/jetstream/'",
        ):
            self.assertIn(public_key, public_rpc)
        self.assertIn(
            "revoke all on function public.get_public_social_discovery_v1() from public, anon, authenticated, service_role",
            compact,
        )
        self.assertIn(
            "grant execute on function public.get_public_social_discovery_v1() to anon, authenticated",
            compact,
        )
        self.assertNotIn(
            "grant execute on function public.get_public_social_discovery_v1() to service_role",
            compact,
        )
        for type_name in (
            "bluesky_jetstream_candidates:",
            "bluesky_jetstream_observations:",
            "bluesky_jetstream_checkpoints:",
            "begin_bluesky_jetstream_job:",
            "finalize_bluesky_jetstream_job:",
            "get_public_social_discovery_v1:",
        ):
            self.assertIn(type_name, DATABASE_TYPES)

    def test_nostr_multi_relay_is_bounded_private_hashed_and_public_safe(self) -> None:
        lowered = NOSTR_MULTI_RELAY.casefold()
        compact = " ".join(lowered.split())
        self.assertEqual(lowered.count("begin;"), 1)
        self.assertEqual(lowered.count("commit;"), 1)
        for relay in (
            "wss://relay.primal.net/",
            "wss://nos.lol/",
            "wss://relay.nostr.net/",
        ):
            self.assertIn(relay, lowered)
        self.assertIn("'nostr_relay'", lowered)
        self.assertIn("'source.nostr.relay'", lowered)
        self.assertIn("'nip01'", lowered)
        self.assertIn("last_checkpoint timestamptz", lowered)
        self.assertIn("policy_state", lowered)
        self.assertIn("degraded_missing_relay_specific_terms", lowered)
        for table in (
            "nostr_relay_candidates",
            "nostr_relay_observations",
            "nostr_relay_checkpoints",
        ):
            self.assertIn(f"alter table ingest.{table} force row level security", compact)
            self.assertIn(f"grant select on table ingest.{table} to service_role", compact)
            for mutation in ("insert", "update", "delete"):
                self.assertNotIn(f"grant {mutation} on table ingest.{table}", compact)

        candidate_table = lowered.split(
            "create table ingest.nostr_relay_candidates", 1
        )[1].split("create index nostr_candidates_active_idx", 1)[0]
        observation_table = lowered.split(
            "create table ingest.nostr_relay_observations", 1
        )[1].split("create index nostr_observations_expiry_idx", 1)[0]
        for table in (candidate_table, observation_table):
            self.assertIn("author_sha256", table)
            self.assertNotIn("pubkey", table)
            self.assertNotIn("signature", table)
            self.assertNotIn("public_url", table)
        finalizer = lowered.split(
            "create or replace function ingest.finalize_nostr_relay_job", 1
        )[1].split(
            "alter function ingest.finalize_nostr_relay_job", 1
        )[0]
        for fragment in (
            "security definer",
            "set search_path = pg_catalog",
            "for update of jobs",
            "result ->> 'version' <> '1.0.0'",
            "result_events_seen > 100",
            "result_bytes_seen > 2097152",
            "candidate_count > 100",
            "deletion_count > 100",
            "author_sha256",
            "request_gate.acquired_at",
            "result_until <> request_gate.acquired_at",
            "result_until <= checkpoint_row.last_checkpoint",
            "result_checkpoint is distinct from checkpoint_row.last_checkpoint",
            "deletion_published_at >= existing_candidate.published_at",
            "existing_candidate.author_sha256 = deletion_author_sha256",
            "jobs.lease_generation = $3",
            "gates.owner_lease_generation = $3",
            "insert into ingest.nostr_relay_observations",
            "update ingest.nostr_relay_candidates",
        ):
            self.assertIn(fragment, finalizer)
        self.assertNotIn("pubkey", finalizer)
        self.assertNotIn("signature", finalizer)
        self.assertIn("prune_nostr_relay_v1", lowered)
        self.assertNotIn("delete from ingest.nostr_relay_checkpoints", lowered)
        self.assertIn("payload ->> 'relay_key'", lowered)
        self.assertIn("complete_job_v2", lowered)
        self.assertIn("window_until <= checkpoint_row.last_checkpoint", lowered)
        self.assertIn(
            "checkpoint_row.last_checkpoint + interval '1 second'", lowered
        )
        self.assertIn("lease_checked_at + interval '1 second'", lowered)
        self.assertIn(
            "schedule_name <> ('nostr_' || (payload ->> 'relay_key'))", lowered
        )
        self.assertIn(
            "if p_job_type = 'source.bluesky.jetstream' and p_payload <> '{}'::jsonb then",
            lowered,
        )
        public_rpc = lowered.split(
            "create or replace function public.get_public_social_discovery_v2()", 1
        )[1].split("alter function public.get_public_social_discovery_v2()", 1)[0]
        for public_key in (
            "'schemaversion'",
            "'sources'",
            "'nostr_multi_relay'",
            "'https://bsky.network/docs/jetstream/'",
            "'https://github.com/nostr-protocol/nips/blob/master/01.md'",
            "'lastcollectedat'",
        ):
            self.assertIn(public_key, public_rpc)
        self.assertIn("get_public_social_discovery_v1()", public_rpc)
        self.assertIn(
            "grant execute on function public.get_public_social_discovery_v2() to anon, authenticated",
            compact,
        )
        self.assertNotIn(
            "grant execute on function public.get_public_social_discovery_v2() to service_role",
            compact,
        )
        for type_name in (
            "nostr_relay_candidates:",
            "nostr_relay_observations:",
            "nostr_relay_checkpoints:",
            "begin_nostr_relay_job:",
            "finalize_nostr_relay_job:",
            "get_public_social_discovery_v2:",
        ):
            self.assertIn(type_name, DATABASE_TYPES)

    def test_nostr_cleanup_capacity_closes_the_36_hour_outage_bound(self) -> None:
        lowered = NOSTR_CLEANUP_CAPACITY.casefold()
        compact = " ".join(lowered.split())
        compact_without_thousands_separators = compact.replace(",", "")
        self.assertEqual(lowered.count("begin;"), 1)
        self.assertEqual(lowered.count("commit;"), 1)
        self.assertIn("max_rows integer default 750000", compact)
        self.assertIn("max_rows > 750000", compact)
        self.assertIn("for update of candidates skip locked", compact)
        self.assertIn("for update of observations skip locked", compact)
        self.assertIn("max_rows => 500000", compact)
        self.assertIn("max_rows => 750000", compact)
        cleanup_compact = compact.split(
            "create or replace function ingest.verify_nostr_release_v1()", 1
        )[0]
        self.assertNotIn("delete from ingest.nostr_relay_checkpoints", cleanup_compact)
        self.assertIn("648000", compact_without_thousands_separators)
        self.assertIn("750000", compact_without_thousands_separators)
        self.assertIn("length(definition) - length(replace(definition", compact)
        self.assertIn("finalize_cleanup_job", compact)
        attestation = lowered.split(
            "create or replace function ingest.verify_nostr_release_v1()", 1
        )[1].split(
            "alter function ingest.verify_nostr_release_v1()", 1
        )[0]
        self.assertIn("returns jsonb", attestation)
        self.assertIn("security definer", attestation)
        self.assertIn("set search_path = pg_catalog", attestation)
        self.assertIn("jsonb_build_object", attestation)
        for contract_key in (
            "ledger_060",
            "ledger_090",
            "request_gates_exact",
            "nostr_acl_exact",
            "public_v2_acl_exact",
            "attestor_role_exact",
        ):
            self.assertIn(f"'{contract_key}'", attestation)
        self.assertIn(
            "create role pokecrack_nostr_attestor nologin noinherit nosuperuser",
            compact,
        )
        self.assertIn(
            "grant execute on function ingest.verify_nostr_release_v1() to pokecrack_nostr_attestor",
            compact,
        )
        self.assertNotIn(
            "grant execute on function ingest.verify_nostr_release_v1() to service_role",
            compact,
        )
        self.assertIn("memberships.inherit_option", attestation)
        self.assertIn("memberships.set_option", attestation)
        self.assertIn("pokecrack_nostr_attestor_login", attestation)
        self.assertIn("relations.relkind in ('r', 'p', 'v', 'm', 's')", attestation)
        self.assertIn("grants.privilege_type = 'maintain'", attestation)
        self.assertIn("grants.grantee <> gates.relowner", attestation)
        self.assertIn("verify_nostr_release_v1:", DATABASE_TYPES)

    def test_nostr_worker_role_isolation_is_exact_and_forward_only(self) -> None:
        lowered = NOSTR_WORKER_ISOLATION.casefold()
        compact = " ".join(lowered.split())
        self.assertEqual(lowered.count("begin;"), 1)
        self.assertEqual(lowered.count("commit;"), 1)
        self.assertIn(
            "create role pokecrack_nostr_worker nologin noinherit nosuperuser",
            compact,
        )
        for function_name in (
            "enqueue_due_nostr_relay_jobs_v1",
            "claim_nostr_relay_jobs_v1",
            "heartbeat_nostr_relay_job_v1",
            "fail_nostr_relay_job_v1",
            "pause_nostr_relay_job_v1",
            "upsert_nostr_worker_heartbeat_v1",
            "nostr_worker_runtime_ready_v1",
            "get_nostr_worker_policy_snapshot_v1",
        ):
            self.assertEqual(
                lowered.count(f"create or replace function ingest.{function_name}"),
                1,
            )
            self.assertIn(function_name, DATABASE_TYPES)
        self.assertIn("verify_nostr_release_v2:", DATABASE_TYPES)
        self.assertIn("set search_path = pg_catalog", lowered)
        self.assertIn("worker_id !~ '^nostr-collector-", lowered)
        self.assertIn("where exhausted.job_type <> 'source.nostr.relay'", lowered)
        self.assertIn("where j.job_type <> 'source.nostr.relay'", lowered)
        self.assertIn("leased_job.job_type = 'source.nostr.relay'", lowered)
        self.assertIn("jobs.job_type <> 'source.nostr.relay'", lowered)
        self.assertIn(
            "revoke all on function ingest.begin_nostr_relay_job", compact
        )
        self.assertIn(
            "revoke all on function ingest.finalize_nostr_relay_job", compact
        )
        self.assertNotIn(
            "grant execute on function ingest.begin_nostr_relay_job(uuid, text, bigint, text) to service_role",
            compact,
        )
        self.assertNotIn(
            "grant execute on function ingest.finalize_nostr_relay_job(uuid, text, bigint, jsonb) to service_role",
            compact,
        )
        attestation = lowered.split(
            "create or replace function ingest.verify_nostr_release_v2()", 1
        )[1].split("alter function ingest.verify_nostr_release_v2()", 1)[0]
        for contract_key in (
            "ledger_100",
            "nostr_policies_exact",
            "nostr_acl_exact",
            "attestor_role_exact",
            "nostr_worker_role_exact",
        ):
            self.assertIn(f"'{contract_key}'", attestation)
        self.assertIn("pg_catalog.pg_db_role_setting", attestation)
        self.assertIn("owned_catalog_objects", attestation)
        self.assertIn("pg_catalog.pg_default_acl", attestation)
        self.assertIn("pg_catalog.pg_extension", attestation)
        self.assertIn("nostr_column_acl_grants", attestation)
        self.assertIn("ingest_column_acl_grants", attestation)
        self.assertIn("nostr_sequence_acl_grants", attestation)
        self.assertIn("worker_function_acl_grants", attestation)
        self.assertIn("attestor_function_acl_grants", attestation)
        self.assertIn("aclexplode", attestation)
        self.assertEqual(attestation.count("aclexplode(columns.attacl)"), 2)
        self.assertNotIn("'{}'::aclitem[]", attestation)
        self.assertIn("pg_has_role", attestation)
        self.assertIn("relations.relkind = 's'", attestation)
        self.assertIn("has_sequence_privilege", attestation)
        self.assertIn("has_any_column_privilege", attestation)
        self.assertIn("count(distinct grants.privilege_type) = 8", attestation)
        self.assertIn("count(distinct grants.privilege_type) = 3", attestation)
        self.assertIn("functions.prosecdef", attestation)
        self.assertIn("functions.proconfig", attestation)
        self.assertIn("grants.is_grantable", attestation)
        self.assertIn("bool_and(grants.grantee = grants.relowner)", attestation)
        self.assertIn("'maintain'", attestation)
        self.assertEqual(
            attestation.count("memberships.member = 'postgres'::regrole"), 2
        )
        self.assertIn("memberships.admin_option", attestation)
        self.assertIn("not memberships.set_option", attestation)
        self.assertIn("memberships.roleid <> roles.group_oid", attestation)
        self.assertIn(
            "grant execute on function ingest.verify_nostr_release_v2() to pokecrack_nostr_attestor",
            compact,
        )
        self.assertNotIn(
            "grant execute on function ingest.verify_nostr_release_v2() to service_role",
            compact,
        )

    def test_mastodon_public_hashtag_is_fixed_private_hashed_and_public_safe(self) -> None:
        historical = MASTODON_PUBLIC_HASHTAG
        hardening = MASTODON_COMPLIANCE_HARDENING
        migration = historical + "\n" + hardening
        lowered = migration.casefold()
        hardening_lowered = hardening.casefold()
        compact = " ".join(lowered.split())
        self.assertEqual(historical.casefold().count("begin;"), 1)
        self.assertEqual(historical.casefold().count("commit;"), 1)
        self.assertEqual(hardening_lowered.count("begin;"), 1)
        self.assertEqual(hardening_lowered.count("commit;"), 1)
        self.assertNotIn("record_mastodon_rate_limit", historical.casefold())
        self.assertEqual(
            hashlib.sha256(historical.encode("utf-8")).hexdigest(),
            "bdf39370988b0b7417b302aeeaa87ee4ec554a4cb2ea994ec03d2b74f6620e9e",
            "the historical Mastodon predecessor remains byte-identical",
        )
        self.assertIn("20260912010000_mastodon_compliance_hardening", hardening_lowered)
        self.assertIn("'source.mastodon.public_hashtag'", lowered)
        self.assertIn("'mastodon_social'", lowered)
        self.assertIn("'mastodon_rest'", lowered)
        self.assertIn("https://mastodon.social/", lowered)
        self.assertIn("https://mastodon.social/api/v2/instance", lowered)
        self.assertIn("https://mastodon.social/about", lowered)
        self.assertIn("https://mastodon.social/api/v1/instance/privacy_policy", lowered)
        self.assertIn("https://mastodon.social/robots.txt", lowered)
        self.assertIn("https://docs.joinmastodon.org/methods/timelines/", lowered)
        self.assertIn("terms_checked_at", lowered)
        self.assertIn("privacy_checked_at", lowered)
        self.assertIn("rules_checked_at", lowered)
        self.assertIn("robots_checked_at", lowered)
        self.assertIn("public_access_checked_at", lowered)
        self.assertIn("api_route_not_disallowed", lowered)
        self.assertIn("live_x_ratelimit_headers", lowered)
        self.assertIn('"rate_limit_default_per_5m":300', lowered)
        self.assertIn('"effective_max_requests_per_5m":150', lowered)
        self.assertIn("recommended_before_production", lowered)
        self.assertIn("opaque_cursor_persists_beyond_activity_ttl", lowered)
        self.assertIn(
            "PokecrackMetadataCollector/0.1 (+https://pokecrack.vercel.app)".casefold(),
            lowered,
        )
        self.assertIn("min_delay_seconds = 2", lowered)
        self.assertIn("interval '2 seconds'", lowered)
        self.assertIn("reserve the full bounded request window", lowered)
        self.assertIn('"max_pages_per_run":2', lowered)
        self.assertIn('"max_items_per_run":80', lowered)
        self.assertIn('"max_response_bytes":2097152', lowered)
        self.assertIn('"allow_redirects":false', lowered)
        self.assertIn('"pokemon_card_zh_hant":"寶可夢卡牌"', compact)
        for raw_tag in (
            "pokemontcg",
            "pokemoncards",
            "ポケカ",
            "ポケモンカード",
            "포켓몬카드",
            "宝可梦卡牌",
            "寶可夢卡牌",
        ):
            self.assertIn(raw_tag.casefold(), lowered)
        for table in (
            "mastodon_public_hashtag_candidates",
            "mastodon_public_hashtag_observations",
            "mastodon_public_hashtag_checkpoints",
            "mastodon_rate_cooldowns",
        ):
            self.assertIn(f"alter table ingest.{table} force row level security", compact)
        self.assertIn("grant select on table ingest.mastodon_public_hashtag_candidates to service_role", compact)
        self.assertIn("grant select on table ingest.mastodon_public_hashtag_observations to service_role", compact)
        self.assertNotIn("grant insert on table ingest.mastodon_public_hashtag_candidates", compact)
        self.assertNotIn("grant update on table ingest.mastodon_public_hashtag_observations", compact)
        self.assertNotIn("grant delete on table ingest.mastodon_public_hashtag_checkpoints", compact)

        candidate_table = lowered.split(
            "create table ingest.mastodon_public_hashtag_candidates", 1
        )[1].split("create index mastodon_candidates_active_idx", 1)[0]
        observation_table = lowered.split(
            "create table ingest.mastodon_public_hashtag_observations", 1
        )[1].split("create index mastodon_observations_expiry_idx", 1)[0]
        for table in (candidate_table, observation_table):
            self.assertIn("status_key_sha256", table)
            self.assertIn("activity_only", table)
            self.assertIn("statistics_eligible", table)
            self.assertNotIn("status_id", table)
            for forbidden in (
                "content",
                "account",
                "handle",
                "profile",
                "media",
                "url",
                "uri",
                "location",
                "raw_payload",
            ):
                self.assertNotIn(forbidden, table)
        checkpoint_table = lowered.split(
            "create table ingest.mastodon_public_hashtag_checkpoints", 1
        )[1].split("create index mastodon_checkpoints_collected_idx", 1)[0]
        self.assertIn("last_status_id text", checkpoint_table)
        self.assertNotIn("account", checkpoint_table)
        self.assertNotIn("raw_payload", checkpoint_table)
        self.assertIn("mastodon_tag_keys_v1", lowered)
        self.assertIn("array_position(value, null) is null", lowered)
        self.assertIn("order by approved.ordinal", lowered)

        begin = hardening_lowered.split(
            "create or replace function ingest.begin_mastodon_public_hashtag_job", 1
        )[1].split(
            "alter function ingest.begin_mastodon_public_hashtag_job", 1
        )[0]
        for fragment in (
            "security definer",
            "set search_path = pg_catalog",
            "for update of jobs",
            "for update of gates",
            "for update of checkpoints",
            "for update of cooldowns",
            "pg_advisory_xact_lock",
            "jobs.lease_generation = $3",
            "payload <> jsonb_build_object",
            "collector_type = 'mastodon_rest'",
            "policies.config = expected_config",
            "start_status_id text",
            "cooldown_until timestamptz",
        ):
            self.assertIn(fragment, begin)
        self.assertIn(
            "create or replace function ingest.record_mastodon_rate_limit",
            hardening_lowered,
        )
        self.assertIn("retry-after", lowered)
        rate_recorder = hardening_lowered.split(
            "create or replace function ingest.record_mastodon_rate_limit", 1
        )[1].split("alter function ingest.record_mastodon_rate_limit", 1)[0]
        for fragment in (
            "security definer",
            "set search_path = pg_catalog",
            "for update of jobs",
            "for update of gates",
            "for update of cooldowns",
            "cooldown_until = greatest",
            "owner_job_id = null",
            "active_until = null",
            "status = 'pending'",
            "attempts = greatest(0, jobs.attempts - 1)",
            "available_at = retry_at",
            "jobs.locked_by = record_mastodon_rate_limit.worker_id",
            "leased_job.payload - array['instance_key', 'tag_key'] <> '{}'::jsonb",
            "(leased_job.payload -> 'instance_key') is distinct from to_jsonb('mastodon_social'::text)",
            "jsonb_typeof(leased_job.payload -> 'instance_key') is distinct from 'string'",
            "jsonb_typeof(leased_job.payload -> 'tag_key') is distinct from 'string'",
            "not coalesce(leased_job.payload ->> 'tag_key' = any (array[",
            "mastodon rate-limit pause lost its fenced lease",
        ):
            self.assertIn(fragment, rate_recorder)
        finalizer = hardening_lowered.split(
            "create or replace function ingest.finalize_mastodon_public_hashtag_job", 1
        )[1].split(
            "alter function ingest.finalize_mastodon_public_hashtag_job", 1
        )[0]
        for fragment in (
            "security definer",
            "set search_path = pg_catalog",
            "for update of jobs",
            "result - array",
            "result ->> 'version' <> '1.0.0'",
            "result_requests_made > 2",
            "result_statuses_seen > 80",
            "result_bytes_seen > 2097152",
            "candidate_count > 80",
            "request_gate.acquired_at",
            "result_start_status_id is distinct from checkpoint_row.last_status_id",
            "checkpoints.last_status_id is not distinct from result_start_status_id",
            "extensions.digest",
            "convert_to(result_instance_key || e'\\n' || candidate_status_id, 'utf8')",
            "insert into ingest.mastodon_public_hashtag_observations",
            "insert into ingest.mastodon_public_hashtag_candidates",
            "on conflict (source_policy_id, tag_key, status_key_sha256) do nothing",
            "existing_observation.matched_tags <> candidate_tags",
            "existing_candidate.matched_tags <> candidate_tags",
            "update ingest.mastodon_public_hashtag_checkpoints",
            "result_rate_limit_remaining = 0",
            "jobs.lease_generation = finalize_mastodon_public_hashtag_job.lease_generation",
            "gates.owner_lease_generation = finalize_mastodon_public_hashtag_job.lease_generation",
        ):
            self.assertIn(fragment, finalizer)
        self.assertIn("prune_mastodon_public_hashtag_v1", migration.casefold())
        self.assertIn("prune_nostr_relay_v1", migration.casefold())
        self.assertNotIn("delete from ingest.mastodon_public_hashtag_checkpoints", migration.casefold())
        self.assertNotIn("delete from ingest.mastodon_rate_cooldowns", migration.casefold())
        self.assertIn("payload - array['instance_key', 'tag_key'] = '{}'::jsonb", compact)
        self.assertIn("if p_job_type = 'source.mastodon.public_hashtag'", lowered)

        scheduled_allowlist = hardening_lowered.split(
            "add constraint jobs_live_scheduled_enqueue_allowlist_check", 1
        )[1].split("do $migration$", 1)[0]
        self.assertIn("job_type = 'source.mastodon.public_hashtag'", scheduled_allowlist)
        self.assertIn("payload - array['instance_key', 'tag_key'] = '{}'::jsonb", scheduled_allowlist)
        self.assertIn("payload ->> 'instance_key' = 'mastodon_social'", scheduled_allowlist)
        self.assertNotIn("schedule_name", scheduled_allowlist)

        historical_scheduled_allowlist = historical.casefold().split(
            "add constraint jobs_live_scheduled_enqueue_allowlist_check", 1
        )[1].split("do $migration$", 1)[0]
        self.assertIn(
            "job_type = 'source.mastodon.public_hashtag'",
            historical_scheduled_allowlist,
        )
        self.assertNotIn("schedule_name", historical_scheduled_allowlist)

        scheduled_extension = historical.casefold().split(
            "select pg_get_functiondef(\n    'ingest.enqueue_scheduled_job_v1", 1
        )[1].split(
            "select pg_get_functiondef(\n    'ingest.enqueue_job_v1", 1
        )[0]
        self.assertIn(
            "schedule_name <> ((payload ->> 'instance_key') || '_' || (payload ->> 'tag_key'))",
            scheduled_extension,
        )
        self.assertIn(
            "mastodon jobs require one exact instance_key, tag_key, and canonical schedule name",
            scheduled_extension,
        )

        public_rpc = hardening_lowered.split(
            "create or replace function public.get_public_social_discovery_v3()", 1
        )[1].split("alter function public.get_public_social_discovery_v3()", 1)[0]
        self.assertIn("public.get_public_social_discovery_v2()", public_rpc)
        self.assertIn("'schemaversion', '3.0.0'", public_rpc)
        for safe_key in (
            "'id'",
            "'name'",
            "'kind'",
            "'access'",
            "'status'",
            "'lastcollectedat'",
            "'url'",
            "'note'",
        ):
            self.assertIn(safe_key, public_rpc)
        public_builder = public_rpc.split("mastodon_source as", 1)[1].split(
            "all_sources as", 1
        )[0]
        for forbidden in (
            "'instance_key'",
            "'tag_key'",
            "'status_id'",
            "'rate_limit_reset_at'",
            "'raw_payload'",
        ):
            self.assertNotIn(forbidden, public_builder)
        self.assertIn("coverage may be incomplete", public_rpc)
        self.assertIn("activity-only", public_rpc)
        self.assertIn("opening evidence", public_rpc)
        self.assertIn("a denominator", public_rpc)
        self.assertIn("rate evidence", public_rpc)
        self.assertIn(
            "revoke all on function public.get_public_social_discovery_v3() from public, anon, authenticated, service_role",
            compact,
        )
        self.assertIn(
            "grant execute on function public.get_public_social_discovery_v3() to anon, authenticated",
            compact,
        )
        self.assertNotIn(
            "grant execute on function public.get_public_social_discovery_v3() to service_role",
            compact,
        )
        for type_name in (
            "mastodon_public_hashtag_candidates:",
            "mastodon_public_hashtag_observations:",
            "mastodon_public_hashtag_checkpoints:",
            "mastodon_rate_cooldowns:",
            "begin_mastodon_public_hashtag_job:",
            "finalize_mastodon_public_hashtag_job:",
            "record_mastodon_rate_limit:",
            "prune_mastodon_public_hashtag_v1:",
            "get_public_social_discovery_v3:",
        ):
            self.assertIn(type_name, DATABASE_TYPES)

    def test_bluesky_runtime_bounds_are_forward_only_and_fail_closed(self) -> None:
        lowered = BLUESKY_RUNTIME_BOUNDS.casefold()
        compact = " ".join(lowered.split())
        self.assertEqual(lowered.count("begin;"), 1)
        self.assertEqual(lowered.count("commit;"), 1)
        self.assertIn('"stream_window_seconds":40', lowered)
        self.assertIn('"stream_window_seconds":10', lowered)
        self.assertIn('"max_stream_bytes":2097152', lowered)
        self.assertIn("pg_get_functiondef", lowered)
        self.assertIn("occurrence_count <> 1", lowered)
        self.assertIn("changed_rows <> 1", lowered)
        self.assertIn("get diagnostics changed_rows = row_count", compact)
        self.assertIn("did not match the reviewed 40-second predecessor", lowered)
        self.assertIn("function contract drifted before bounds update", lowered)
        self.assertIn(
            "grant execute on function ingest.begin_bluesky_jetstream_job(uuid, text, bigint) to service_role",
            compact,
        )
        self.assertIn(
            "grant execute on function ingest.finalize_bluesky_jetstream_job(uuid, text, bigint, jsonb) to service_role",
            compact,
        )
        self.assertIn(
            "grant execute on function public.get_public_social_discovery_v1() to anon, authenticated",
            compact,
        )
        self.assertNotIn("drop table", lowered)
        self.assertNotIn("truncate", lowered)

    def test_global_dashboard_is_a_separate_strict_v2_projection(self) -> None:
        lowered = GLOBAL_DASHBOARD.casefold()
        compact = " ".join(lowered.split())
        self.assertNotIn("alter table catalog.regions", lowered)
        self.assertNotIn("alter table public.region_summaries", lowered)
        self.assertNotIn("create or replace function public.get_public_dashboard_snapshot_v1", lowered)
        self.assertIn("create table catalog.iso_alpha2_codes", lowered)
        codes = re.search(
            r"select unnest\(array\[(.*?)\]::text\[\]\)",
            GLOBAL_DASHBOARD,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(codes)
        code_values = re.findall(r"'([A-Z]{2})'", codes.group(1) if codes else "")
        self.assertEqual(len(code_values), 249)
        self.assertEqual(len(set(code_values)), 249)
        self.assertIn("AU", code_values)
        self.assertIn("US", code_values)
        self.assertNotIn("UK", code_values)
        self.assertNotIn("ZZ", code_values)
        self.assertIn(
            "references catalog.iso_alpha2_codes(code)",
            compact,
        )
        self.assertIn("num_nonnulls(", lowered)
        self.assertIn("observed_packs >= 30", lowered)
        self.assertIn("independent_source_count >= 3", lowered)
        self.assertIn("or observed_packs >= 200", lowered)
        self.assertNotIn("hit_pack_count", lowered)

    def test_global_public_rpc_reads_only_its_three_public_projections(self) -> None:
        lowered = GLOBAL_DASHBOARD.casefold()
        snapshot = lowered.split(
            "create or replace function public.get_public_dashboard_snapshot_v2()", 1
        )[1].split("revoke all on function public.get_public_dashboard_snapshot_v2()", 1)[0]
        for relation in (
            "public.tcgdex_set_index",
            "public.tcgdex_catalog_status",
            "public.country_period_map_cells",
        ):
            self.assertIn(relation, snapshot)
        for forbidden in (
            "dashboard_overview",
            "get_public_dashboard_snapshot_v1",
            "catalog.sets",
            "catalog.sync_state",
            "ingest.",
            "analytics.",
            "218",
        ):
            self.assertNotIn(forbidden, snapshot)
        self.assertIn("security invoker", snapshot)
        self.assertIn("set search_path = pg_catalog, public", snapshot)
        self.assertIn("limit 1000", snapshot)
        self.assertIn("limit 249", snapshot)
        self.assertIn("join latest_period as period", snapshot)
        self.assertIn("'period', case", snapshot)
        self.assertIn("'mapcells', values.map_cells", snapshot)
        self.assertIn("get_public_dashboard_snapshot_v2:", DATABASE_TYPES)

    def test_public_pipeline_snapshot_is_bounded_and_redacted(self) -> None:
        lowered = PUBLIC_PIPELINE_SNAPSHOT.casefold()
        compact = " ".join(lowered.split())
        snapshot = lowered.split(
            "create or replace function public.get_public_dashboard_snapshot_v3()", 1
        )[1].split(
            "alter function public.get_public_dashboard_snapshot_v3() owner to postgres", 1
        )[0]
        self.assertIn("security definer", snapshot)
        self.assertIn("set search_path = pg_catalog", snapshot)
        self.assertIn("public.get_public_dashboard_snapshot_v2()", snapshot)
        for relation in (
            "ingest.source_policies",
            "ingest.youtube_discoveries",
            "ingest.public_study_observations",
            "ingest.worker_heartbeats",
            "catalog.sets",
        ):
            self.assertIn(relation, snapshot)
        for forbidden in (
            "discoveries.video_id",
            "discoveries.title",
            "source_items",
            "extraction_runs",
            "opening_hits",
            "qualifying_hit_pack_count",
            "jobs.payload",
            "last_error_message",
            "heartbeats.worker_id",
        ):
            self.assertNotIn(forbidden, snapshot)
        self.assertIn("limit 100", snapshot)
        self.assertIn("limit 249", GLOBAL_DASHBOARD.casefold())
        self.assertIn("reviewed_country_metrics", snapshot)
        self.assertIn("'pending'", snapshot)
        for policy_field in (
            "expected_display_name",
            "expected_source_kind",
            "expected_base_url",
            "expected_robots_policy",
            "expected_routes",
            "expected_include_subdomains",
            "expected_min_delay_seconds",
            "expected_max_pages_per_run",
            "expected_max_items_per_run",
            "expected_max_concurrency",
            "expected_browser_profile",
            "expected_statistics_eligible_default",
            "expected_retention_days",
            "expected_config_sha256",
        ):
            self.assertIn(policy_field, snapshot)
        self.assertIn("extensions.digest(policies.config::text, 'sha256')", snapshot)
        self.assertIn(
            "policies.browser_profile is not distinct from definitions.expected_browser_profile",
            snapshot,
        )
        self.assertIn("join policy_state as policies", snapshot)
        self.assertIn("and policies.policy_contract_valid", snapshot)
        self.assertEqual(lowered.count("'youtube_discovery'::text"), 2)
        self.assertIn("'public_study_comicbook_us_55'", snapshot)
        self.assertIn("'public_study_wargamer_gb_17'", snapshot)
        self.assertIn(
            "revoke all on function public.get_public_dashboard_snapshot_v3() from public, anon, authenticated, service_role",
            compact,
        )
        self.assertIn(
            "grant execute on function public.get_public_dashboard_snapshot_v3() to anon, authenticated",
            compact,
        )
        self.assertNotIn(
            "grant execute on function public.get_public_dashboard_snapshot_v3() to service_role",
            compact,
        )
        self.assertIn("get_public_dashboard_snapshot_v3:", DATABASE_TYPES)

    def test_global_catalog_projection_is_narrow_current_and_trigger_owned(self) -> None:
        lowered = GLOBAL_DASHBOARD.casefold()
        compact = " ".join(lowered.split())
        public_index = lowered.split("create table public.tcgdex_set_index", 1)[1].split(
            "create table public.tcgdex_catalog_status", 1
        )[0]
        for private_field in (
            "external_id",
            "metadata",
            "etag",
            "content_sha256",
            "last_job_id",
        ):
            self.assertNotIn(private_field, public_index)
        self.assertIn("pg_advisory_xact_lock", lowered)
        self.assertIn("sets_publish_tcgdex_set_index", lowered)
        self.assertIn("sync_state_publish_tcgdex_catalog_status", lowered)
        self.assertIn("published.refreshed_at < new.last_changed_at", compact)
        self.assertIn("checkpoint count does not match", lowered)
        self.assertIn("using (not is_demo and is_current)", compact)
        self.assertIn(
            "grant select on table public.tcgdex_set_index, public.tcgdex_catalog_status, public.country_period_map_cells to anon, authenticated, service_role",
            compact,
        )
        self.assertIn(
            "grant execute on function public.get_public_dashboard_snapshot_v2() to anon, authenticated",
            compact,
        )
        self.assertNotIn(
            "grant execute on function public.get_public_dashboard_snapshot_v2() to service_role",
            compact,
        )

    def test_public_study_pipeline_provisions_two_exact_private_sources(self) -> None:
        lowered = PUBLIC_STUDY_PIPELINE.casefold()
        compact = " ".join(lowered.split())
        self.assertGreaterEqual(lowered.count("'public_study_comicbook_us_55'"), 6)
        self.assertGreaterEqual(lowered.count("'public_study_wargamer_gb_17'"), 6)
        for identity in (
            "comicbook-perfect-order-us-55-v1",
            "wargamer-chaos-rising-gb-17-v1",
        ):
            self.assertIn(identity, lowered)
        self.assertIn("create table ingest.public_study_observations", lowered)
        self.assertIn(
            "alter table ingest.public_study_observations force row level security",
            lowered,
        )
        self.assertIn(
            "grant select on table ingest.public_study_observations to service_role",
            compact,
        )
        self.assertNotIn(
            "grant insert on table ingest.public_study_observations", lowered
        )
        self.assertNotIn(
            "grant update on table ingest.public_study_observations", lowered
        )
        self.assertNotIn(
            "grant delete on table ingest.public_study_observations", lowered
        )
        self.assertIn(
            "drop policy country_period_map_cells_public_read", lowered
        )
        self.assertIn(
            "period_end = (statement_timestamp() at time zone 'utc')::date",
            compact,
        )

    def test_public_study_finalizer_is_evidence_only_and_withholds_rates(self) -> None:
        lowered = PUBLIC_STUDY_PIPELINE.casefold()
        finalizer = lowered.split(
            "create or replace function ingest.finalize_public_study_job", 1
        )[1].split("alter function ingest.finalize_public_study_job", 1)[0]
        self.assertIn("security definer", finalizer)
        self.assertIn("set search_path = pg_catalog", finalizer)
        self.assertIn("for update of jobs", finalizer)
        self.assertIn("requested_study_key text", finalizer)
        self.assertNotIn("observations.study_key = study_key", finalizer)
        self.assertIn("extensions.digest", finalizer)
        self.assertIn("result_excerpt <> expected_evidence", finalizer)
        self.assertIn("result_evidence_sha256 <> expected_evidence_sha256", finalizer)
        self.assertIn("expected_config ->> 'country_code'", finalizer)
        self.assertIn("expected_config ->> 'pack_count'", finalizer)
        self.assertIn("pokecrack:public-study-country:", finalizer)
        self.assertIn(
            "(observations.source_observed_at at time zone 'utc')::date",
            finalizer,
        )
        self.assertIn("insert into ingest.source_items", finalizer)
        self.assertIn("insert into ingest.extraction_runs", finalizer)
        self.assertIn("insert into ingest.openings", finalizer)
        self.assertIn("insert into ingest.public_study_observations", finalizer)
        self.assertNotIn("insert into ingest.opening_hits", finalizer)
        self.assertNotIn("raw_html", finalizer.split("jsonb_build_object", 1)[0])
        self.assertIn("observed_rate = null", finalizer)
        self.assertIn("posterior_mean = null", finalizer)
        self.assertIn("credible_interval_low = null", finalizer)
        self.assertIn("credible_interval_high = null", finalizer)
        self.assertIn("signal_status = 'insufficient sample'", finalizer)
        self.assertIn(
            "where cells.methodology_version = excluded.methodology_version",
            finalizer,
        )
        self.assertIn("existing_source.text_excerpt is not null", finalizer)
        self.assertIn("set text_excerpt = result_excerpt", finalizer)
        self.assertEqual(
            finalizer.count("expires_at = completion_time + interval '730 days'"),
            3,
        )

    def test_public_study_jobs_are_exactly_allowlisted_and_typed(self) -> None:
        lowered = PUBLIC_STUDY_PIPELINE.casefold()
        compact = " ".join(lowered.split())
        self.assertIn("job_type = 'source.public_study.opening'", compact)
        self.assertIn("payload - array['study_key'] = '{}'::jsonb", compact)
        self.assertIn(
            "public-study schedule_name must match its exact study_key", lowered
        )
        self.assertIn(
            "typed live jobs require their dedicated fenced finalizer", lowered
        )
        for function_name in (
            "begin_public_study_job",
            "finalize_public_study_job",
        ):
            function = lowered.split(
                f"create or replace function ingest.{function_name}", 1
            )[1].split(f"alter function ingest.{function_name}", 1)[0]
            self.assertIn("security definer", function)
            self.assertIn("set search_path = pg_catalog", function)
            self.assertIn("lease_generation", function)
            self.assertIn(f"{function_name}:", DATABASE_TYPES)

    def test_reviewed_coverage_extension_is_denominator_only_and_fail_closed(self) -> None:
        lowered = REVIEWED_GLOBAL_EVIDENCE.casefold()
        compact = " ".join(lowered.split())
        self.assertEqual(lowered.count("begin;"), 1)
        self.assertEqual(lowered.count("commit;"), 1)
        for study_key in (
            "cardchill-ascended-heroes-gb-90-v1",
            "bleedingcool-phantasmal-flames-us-36-v1",
        ):
            self.assertGreaterEqual(lowered.count(study_key), 4)
        self.assertIn(
            "create table ingest.public_study_coverage_observations", lowered
        )
        coverage_table = lowered.split(
            "create table ingest.public_study_coverage_observations", 1
        )[1].split("create index public_study_coverage_country_time_idx", 1)[0]
        for private_metric in (
            "qualifying_hit_pack_count",
            "observed_rate",
            "posterior",
            "baseline",
            "evidence_excerpt",
        ):
            self.assertNotIn(private_metric, coverage_table)
        self.assertIn(
            "alter table ingest.public_study_coverage_observations force row level security",
            compact,
        )
        self.assertIn(
            "grant select on table ingest.public_study_coverage_observations to service_role",
            compact,
        )
        for mutation in ("insert", "update", "delete"):
            self.assertNotIn(
                f"grant {mutation} on table ingest.public_study_coverage_observations",
                compact,
            )

        finalizer = lowered.split(
            "create or replace function ingest.finalize_public_study_coverage_job_v1",
            1,
        )[1].split(
            "alter function ingest.finalize_public_study_coverage_job_v1", 1
        )[0]
        self.assertIn("security definer", finalizer)
        self.assertIn("set search_path = pg_catalog", finalizer)
        self.assertIn("for update of jobs", finalizer)
        self.assertIn("owner_lease_generation", finalizer)
        self.assertIn("result_excerpt <> reviewed.evidence_excerpt", finalizer)
        self.assertIn("extensions.digest", finalizer)
        self.assertIn(
            "insert into ingest.public_study_coverage_observations", finalizer
        )
        for forbidden_write in (
            "insert into ingest.source_items",
            "insert into ingest.extraction_runs",
            "insert into ingest.openings",
            "insert into ingest.public_study_observations",
            "insert into public.country_period_map_cells",
        ):
            self.assertNotIn(forbidden_write, finalizer)

        preflight = lowered.split(
            "create or replace function ingest.begin_public_study_job_v2", 1
        )[1].split("alter function ingest.begin_public_study_job_v2", 1)[0]
        self.assertIn("contracts.ordinal in (3, 4)", preflight)
        self.assertIn("p_schedule_name is null", lowered)

        public_rpc = lowered.split(
            "create or replace function public.get_public_study_coverage_v1", 1
        )[1].split(
            "alter function public.get_public_study_coverage_v1", 1
        )[0]
        self.assertIn("security definer", public_rpc)
        self.assertIn("btrim(catalog_sets.series_name) <> ''", public_rpc)
        for safe_key in (
            "'countries'",
            "'sets'",
            "'sources'",
            "'packsobserved'",
            "'independentsources'",
        ):
            self.assertIn(safe_key, public_rpc)
        for forbidden_json_key in (
            "'evidence_excerpt'",
            "'evidence_sha256'",
            "'qualifying_hit_pack_count'",
            "'job_id'",
            "'policy_id'",
        ):
            self.assertNotIn(forbidden_json_key, public_rpc)
        self.assertIn(
            "grant execute on function public.get_public_study_coverage_v1() to anon, authenticated",
            compact,
        )
        for generated_contract in (
            "public_study_coverage_observations:",
            "begin_public_study_job_v2:",
            "finalize_public_study_coverage_job_v1:",
            "enqueue_public_study_coverage_job_v1:",
            "enqueue_scheduled_public_study_coverage_job_v1:",
            "get_public_study_coverage_v1:",
        ):
            self.assertIn(generated_contract, DATABASE_TYPES)

    def test_generated_public_study_types_preserve_the_dedicated_ledger(self) -> None:
        observations = DATABASE_TYPES.split(
            "public_study_observations:", 1
        )[1].split("schedule_slots:", 1)[0]
        self.assertGreaterEqual(observations.count("qualifying_hit_pack_count"), 3)
        self.assertGreaterEqual(observations.count("geography_basis"), 3)
        openings = DATABASE_TYPES.split("openings:", 1)[1].split(
            "public_study_observations:", 1
        )[0]
        self.assertNotIn("qualifying_hit_pack_count", openings)

    def test_local_supabase_matches_the_postgresql_17_backup_contract(self) -> None:
        self.assertIn("major_version = 17", SUPABASE_CONFIG)
        self.assertNotIn("major_version = 15", SUPABASE_CONFIG)
        self.assertIn("server_version_num", MIGRATION_WORKFLOW)
        self.assertIn("server_version_num >= 170000", MIGRATION_WORKFLOW)
        self.assertIn("scripts/run_supabase_migrations.py", MIGRATION_WORKFLOW)
        self.assertIn("SUPABASE_ACCESS_TOKEN", MIGRATION_WORKFLOW)
        self.assertNotIn("SUPABASE_DB_URL", MIGRATION_WORKFLOW)
        self.assertNotIn("--db-url", MIGRATION_WORKFLOW)

    def test_seed_aggregate_rows_obey_count_and_practical_probability_contracts(self) -> None:
        source_fields = {
            "analytics.set_metrics_daily": "independent_source_count",
            "analytics.region_metrics_daily": "independent_source_count",
            "analytics.retailer_metrics_daily": "independent_source_count",
            "analytics.batch_metrics_daily": "independent_source_count",
            "public.dashboard_overview": "verified_sources",
            "public.set_summaries": "independent_source_count",
            "public.region_summaries": "independent_source_count",
            "public.retailer_summaries": "independent_source_count",
            "public.batch_summaries": "independent_source_count",
            "public.public_signals": "independent_source_count",
        }
        for table, source_field in source_fields.items():
            for row in _seed_rows(table):
                self.assertLessEqual(
                    int(row[source_field]),
                    int(row["complete_openings"]),
                    f"{table} seed sources exceed complete openings",
                )

        for table in ("analytics.signals", "public.public_signals"):
            for row in _seed_rows(table):
                status = _sql_text(row["status"])
                probability = row["probability_above_practical_uplift"]
                if status == "Watch":
                    self.assertGreaterEqual(Decimal(probability), Decimal("0.900"))
                elif status == "Possible anomaly":
                    self.assertGreaterEqual(Decimal(probability), Decimal("0.950"))

    def test_source_items_reserve_media_fingerprints(self) -> None:
        self.assertIn("video_fingerprint text", INGEST)
        self.assertIn("audio_fingerprint text", INGEST)


    def test_recent_activity_carries_explicit_statistics_eligibility(self) -> None:
        self.assertIn("statistics_eligible boolean not null default false", PUBLIC)
        self.assertIn("a.statistics_eligible", RPC)



    def test_generated_row_types_match_every_migration_table_column(self) -> None:
        migrations = "\n".join(
            path.read_text() for path in sorted((ROOT / "migrations").glob("*.sql"))
        )
        tables = re.findall(
            r"create table(?: if not exists)? ([a-z_]+)\.([a-z_]+) \((.*?)\n\);",
            migrations,
            flags=re.DOTALL,
        )
        added_columns: dict[tuple[str, str], set[str]] = {}
        for match in re.finditer(
            r"alter\s+table\s+([a-z_]+)\.([a-z_]+)\s+add\s+column(?:\s+if\s+not\s+exists)?\s+([a-z_][a-z0-9_]*)\s+",
            migrations,
            flags=re.IGNORECASE,
        ):
            added_columns.setdefault((match.group(1), match.group(2)), set()).add(
                match.group(3)
            )
        self.assertGreaterEqual(len(tables), 20)
        ignored = {"constraint", "primary", "unique", "check", "foreign", "exclude"}
        for schema, table, body in tables:
            columns = {
                match.group(1)
                for match in re.finditer(r"^  ([a-z_][a-z0-9_]*)\s+", body, flags=re.MULTILINE)
                if match.group(1) not in ignored
            }
            columns.update(added_columns.get((schema, table), set()))
            table_match = re.search(
                rf"^      {table}: \{{\n(.*?)^      \}};$",
                DATABASE_TYPES,
                flags=re.MULTILINE | re.DOTALL,
            )
            self.assertIsNotNone(table_match, f"missing generated type for {schema}.{table}")
            table_block = table_match.group(1) if table_match is not None else ""
            for contract_name in ("Row", "Insert", "Update"):
                contract_match = re.search(
                    rf"^        {contract_name}: \{{\n(.*?)^        \}};$",
                    table_block,
                    flags=re.MULTILINE | re.DOTALL,
                )
                self.assertIsNotNone(contract_match, f"missing generated {contract_name} for {schema}.{table}")
                contract_block = contract_match.group(1) if contract_match is not None else ""
                generated_columns = set(
                    re.findall(r"^          ([a-z_][a-z0-9_]*)(?:\?)?:", contract_block, re.MULTILINE)
                )
                self.assertEqual(
                    columns,
                    generated_columns,
                    f"generated {contract_name} drift for {schema}.{table}",
                )

    def test_claim_jobs_dead_letters_due_max_attempt_rows_before_claiming(self) -> None:
        lowered = FENCING.casefold()
        self.assertIn("create or replace function ingest.claim_jobs_v2", lowered)
        self.assertIn("update ingest.jobs as exhausted", lowered)
        self.assertIn("exhausted.attempts >= exhausted.max_attempts", lowered)
        self.assertIn("exhausted.status = 'running'", lowered)
        self.assertIn("exhausted.lock_expires_at <= sweep_time", lowered)
        self.assertIn("claim_time := clock_timestamp()", lowered)
        self.assertIn("'lease_expired_max_attempts'", lowered)
        self.assertIn("status = 'dead'", lowered)
        self.assertIn("and not exhausted.is_demo", lowered)
        self.assertIn("and not j.is_demo", lowered)

    def test_job_lease_fencing_uses_a_forward_only_generation_protocol(self) -> None:
        lowered = FENCING.casefold()
        self.assertIn("add column lease_generation bigint not null default 0", lowered)
        self.assertIn("check (lease_generation >= 0)", lowered)
        self.assertIn("create or replace function ingest.claim_jobs_v2", lowered)
        self.assertGreaterEqual(lowered.count("lease_generation + 1"), 3)
        self.assertIn("claim_jobs is disabled", lowered)
        self.assertIn("from public, anon, authenticated, service_role", lowered)
        self.assertIn("create or replace function ingest.finalize_cleanup_job", lowered)
        self.assertIn("for update of j", lowered)
        self.assertIn("perform ingest.prune_expired_ephemera_v2", lowered)
        self.assertIn("prune_expired_ephemera is disabled", lowered)
        self.assertIn("ingest.prune_expired_ephemera_v2(timestamptz, integer)", lowered)
        self.assertIn("finalize_cleanup_job:", DATABASE_TYPES)
        self.assertIn("lease_generation: number;", DATABASE_TYPES)

    def test_tcgdex_pipeline_provisions_only_the_exact_approved_live_policy(self) -> None:
        compact = " ".join(TCGDEX_PIPELINE.casefold().split())
        self.assertIn("'tcgdex_catalog'", compact)
        self.assertIn("'api.tcgdex.net'", compact)
        self.assertIn("'official_api'", compact)
        self.assertIn("'not_applicable'", compact)
        self.assertIn("array['official_api']::text[]", compact)
        self.assertIn("10, 1, 1000, 1, false", compact)
        self.assertIn("'tcgdex-sets-v1'", compact)
        self.assertNotIn("api_key", compact)
        self.assertNotIn("service_role_key", compact)

    def test_tcgdex_catalog_state_and_schedule_slots_are_private_and_mode_safe(self) -> None:
        lowered = TCGDEX_PIPELINE.casefold()
        compact = " ".join(lowered.split())
        self.assertIn("create table catalog.sync_state", lowered)
        self.assertIn("primary key (source, scope, language, is_demo)", compact)
        self.assertIn("revision bigint not null default 1", compact)
        self.assertIn("constraint sync_state_revision_check check (revision >= 1)", compact)
        self.assertIn("etag !~ '[[:cntrl:]]'", compact)
        self.assertIn("create table ingest.schedule_slots", lowered)
        self.assertIn("primary key (schedule_name, slot_at)", compact)
        self.assertIn("create table ingest.source_request_gates", lowered)
        self.assertIn("source_key text primary key", compact)
        self.assertIn("source_key = 'tcgdex_catalog'", compact)
        self.assertIn("owner_lease_generation >= 1", compact)
        self.assertIn("active_until > acquired_at", compact)
        self.assertIn("unique (slug, is_demo)", compact)
        self.assertIn(
            "unique (external_source, external_id, language, is_demo)",
            compact,
        )
        self.assertIn("alter table catalog.sync_state force row level security", lowered)
        self.assertIn("alter table ingest.schedule_slots force row level security", lowered)
        self.assertIn(
            "alter table ingest.source_request_gates force row level security", lowered
        )
        self.assertIn("grant select on table catalog.sync_state to service_role", lowered)
        self.assertIn("grant select on table ingest.schedule_slots to service_role", lowered)
        self.assertIn(
            "revoke all on table ingest.source_request_gates from public, anon, authenticated, service_role",
            compact,
        )
        self.assertNotIn(
            "grant select on table ingest.source_request_gates to service_role", lowered
        )

    def test_backup_can_lock_but_never_read_the_opaque_request_gate(self) -> None:
        backup_lock = " ".join(BACKUP_GATE_LOCK.casefold().split())
        youtube = " ".join(YOUTUBE_PIPELINE.casefold().split())
        self.assertIn("server_version_num", backup_lock)
        self.assertIn(
            "grant maintain on table ingest.source_request_gates to service_role",
            backup_lock,
        )
        self.assertNotIn("grant select", backup_lock)
        self.assertIn(
            "revoke all on table ingest.source_request_gates from service_role; grant maintain on table ingest.source_request_gates to service_role",
            youtube,
        )

    def test_scheduled_enqueue_reserves_a_durable_slot_before_one_live_job(self) -> None:
        lowered = TCGDEX_PIPELINE.casefold()
        function = lowered.split(
            "create or replace function ingest.enqueue_scheduled_job_v1", 1
        )[1].split("alter function ingest.enqueue_scheduled_job_v1", 1)[0]
        self.assertIn("security definer", function)
        self.assertIn("set search_path = pg_catalog", function)
        self.assertLess(
            function.index("insert into ingest.schedule_slots"),
            function.index("insert into ingest.jobs"),
        )
        self.assertIn("on conflict on constraint schedule_slots_pkey do nothing", function)
        self.assertIn("jobs.dedupe_key = schedule_dedupe_key", function)
        self.assertIn("order by jobs.created_at, jobs.id", function)
        self.assertIn("interval '36 hours'", function)
        self.assertIn("interval '5 minutes'", function)
        self.assertIn("false", function)

        self.assertIn(
            "^schedule:([a-z][a-z0-9_.-]{0,79}):([0-9]{8}t[0-9]{4}00z)$",
            lowered,
        )
        self.assertIn("make_timestamptz", lowered)
        self.assertIn("legacy_job.slot_token", lowered)
        self.assertLess(
            lowered.index("do $$"),
            lowered.index("create or replace function ingest.enqueue_scheduled_job_v1"),
        )

    def test_tcgdex_begin_and_finalize_recheck_fencing_and_policy(self) -> None:
        lowered = TCGDEX_PIPELINE.casefold()
        begin = lowered.split(
            "create or replace function ingest.begin_tcgdex_sets_job", 1
        )[1].split("alter function ingest.begin_tcgdex_sets_job", 1)[0]
        finalizer = lowered.split(
            "create or replace function ingest.finalize_tcgdex_sets_job", 1
        )[1].split("alter function ingest.finalize_tcgdex_sets_job", 1)[0]
        compact_begin = " ".join(begin.split())
        for function in (begin, finalizer):
            self.assertIn("security definer", function)
            self.assertIn("set search_path = pg_catalog", function)
            self.assertIn("for update of jobs", function)
            self.assertIn("lease_generation", function)
            self.assertIn("lock_expires_at <=", function)
            self.assertIn("'tcgdex_catalog'", function)
            self.assertIn("'api.tcgdex.net'", function)
            self.assertIn("policies.enabled", function)
            self.assertIn("not policies.is_demo", function)
            for exact_policy_fragment in (
                "policies.display_name = 'tcgdex catalog api'",
                "policies.base_url = 'https://api.tcgdex.net/v2'",
                "not policies.include_subdomains",
                "policies.min_delay_seconds = 10",
                "policies.max_pages_per_run = 1",
                "policies.max_items_per_run = 1000",
                "policies.max_concurrency = 1",
                "policies.browser_profile is null",
                "not policies.statistics_eligible_default",
                "policies.retention_days = 365",
                "policies.config = '{\"scope\":\"sets\",\"metadata_only\":true}'::jsonb",
                "policies.expected_interval_seconds = 86400",
            ):
                self.assertIn(exact_policy_fragment, function)
            self.assertIn("for update of policies", function)
            self.assertLess(
                function.index("for update of policies"),
                function.rindex("lease_checked_at := clock_timestamp()"),
            )
        self.assertIn("last_attempt_at", begin)
        self.assertIn(
            "returns table( acquired boolean, retry_at timestamptz, etag text, content_sha256 text, item_count integer, revision bigint )",
            compact_begin,
        )
        self.assertIn("pg_advisory_xact_lock", begin)
        self.assertIn("for update of gates", begin)
        self.assertIn("request_gate.active_until > lease_checked_at", begin)
        self.assertIn("return query select false", compact_begin)
        self.assertIn("lease_checked_at + interval '45 seconds'", begin)
        self.assertIn("owner_lease_generation = $3", begin)
        self.assertNotIn("earlier_jobs", begin)
        self.assertIn("policy_last_attempt_at + interval '10 seconds'", begin)
        self.assertIn("pg_advisory_xact_lock", finalizer)
        self.assertIn("for update of gates", finalizer)
        self.assertIn("request_gate.owner_job_id is distinct from $1", finalizer)
        self.assertIn("request_gate.owner_lease_generation is distinct from $3", finalizer)
        self.assertIn("insert into catalog.sets", finalizer)
        self.assertIn("insert into catalog.sync_state", finalizer)
        self.assertIn("last_success_at", finalizer)
        self.assertIn("changed tcgdex results require a new content hash", finalizer)
        self.assertIn("expected_revision", finalizer)
        self.assertIn("if result_expected_revision <> (", finalizer)
        self.assertIn("states.revision = result_expected_revision", finalizer)
        self.assertIn("states.revision + 1", finalizer)
        self.assertIn("stale checkpoint revision", finalizer)
        self.assertIn("result_etag ~ '[[:cntrl:]]'", finalizer)
        self.assertIn("result_etag !~ '^(w/)?\"[!#-~]*\"$'", finalizer)
        self.assertIn("set_external_id ~ '[[:cntrl:]]'", finalizer)
        self.assertIn("set_name ~ '[[:cntrl:]]'", finalizer)
        self.assertNotIn("(elements.value ->> 'card_count_total')::numeric", finalizer)
        self.assertIn("is_active = true", finalizer)
        self.assertIn("update ingest.jobs", finalizer)
        self.assertIn("jobs.locked_by = $2", finalizer)
        self.assertIn("jobs.lease_generation = $3", finalizer)
        self.assertIn("owner_job_id = null", finalizer)
        self.assertIn("owner_lease_generation = null", finalizer)
        self.assertIn("tcgdex completion lost its request gate ownership", finalizer)
        self.assertNotIn("delete from catalog.sets", finalizer)
        self.assertNotIn("is_active = false", finalizer)
        self.assertIn("revision: number;", DATABASE_TYPES)
        self.assertIn(
            "acquired: boolean; retry_at: string | null; etag: string | null; content_sha256: string | null; item_count: number; revision: number",
            DATABASE_TYPES,
        )

    def test_fenced_job_lifecycle_rpcs_own_request_gate_mutation(self) -> None:
        lowered = TCGDEX_PIPELINE.casefold()
        heartbeat = lowered.split(
            "create or replace function ingest.heartbeat_job_v2", 1
        )[1].split("alter function ingest.heartbeat_job_v2", 1)[0]
        failure = lowered.split(
            "create or replace function ingest.fail_job_v2", 1
        )[1].split("alter function ingest.fail_job_v2", 1)[0]
        for function in (heartbeat, failure):
            self.assertIn("security definer", function)
            self.assertIn("set search_path = pg_catalog", function)
            self.assertIn("for update of jobs", function)
            self.assertIn("jobs.lease_generation = $3", function)
            self.assertIn("and not jobs.is_demo", function)
            self.assertIn("ingest.source_request_gates", function)
        self.assertIn("set active_until = renewed_job.lock_expires_at", heartbeat)
        self.assertIn("lease_checked_at + make_interval(secs => $4)", heartbeat)
        self.assertIn("owner_job_id = null", failure)
        self.assertIn("owner_lease_generation = null", failure)
        self.assertIn("when not $6", failure)
        self.assertIn("heartbeat_job_v2:", DATABASE_TYPES)
        self.assertIn("fail_job_v2:", DATABASE_TYPES)

    def test_youtube_pipeline_is_exact_bounded_metadata_only_activity(self) -> None:
        lowered = YOUTUBE_PIPELINE.casefold()
        compact = " ".join(lowered.split())
        self.assertIn("'youtube_discovery'", compact)
        self.assertIn("'youtube global discovery api'", compact)
        self.assertIn("'youtube.googleapis.com'", compact)
        self.assertIn("'https://youtube.googleapis.com/youtube/v3'", compact)
        self.assertIn("2, 1, 25, 1, false, 28", compact)
        self.assertIn("'youtube-global-discovery-v1'", compact)
        self.assertIn(
            "'{\"metadata_only\":true,\"media_download\":false,"
            "\"max_response_bytes\":2097152,\"query_allowlist\":["
            "\"pokemon-tcg-booster-box-opening\",\"pokemon-tcg-etb-opening\","
            "\"pokemon-tcg-booster-bundle-opening\",\"pokemon-tcg-pack-opening\","
            "\"pokemon-tcg-opening-batch-code\"]}'::jsonb",
            compact,
        )
        for forbidden_contract_field in (
            "product_type_hints",
            "batch_code_hints",
            "youtube-metadata-v1",
            "discovery_scope",
            "geography_status",
            "evidence_tier",
            "channel_country_code",
        ):
            self.assertNotIn(forbidden_contract_field, lowered)
        self.assertNotIn("youtube_api_key", lowered)
        self.assertNotIn("service_role_key", lowered)
        self.assertNotIn("insert into ingest.openings", lowered)
        self.assertNotIn("insert into ingest.opening_hits", lowered)
        self.assertNotIn("insert into public.", lowered)

    def test_youtube_cache_is_unlogged_private_unlinked_and_mode_safe(self) -> None:
        lowered = YOUTUBE_PIPELINE.casefold()
        compact = " ".join(lowered.split())
        duplicate_cluster_fk = lowered.split(
            "add constraint source_items_duplicate_cluster_mode_fkey", 1
        )[1].split("create unique index source_items_normalized_url_uidx", 1)[0]
        self.assertIn("create unlogged table ingest.youtube_discoveries", lowered)
        self.assertIn(
            "alter table ingest.youtube_discoveries force row level security",
            lowered,
        )
        self.assertIn(
            "grant select on table ingest.youtube_discoveries to service_role",
            lowered,
        )
        self.assertNotIn(
            "grant insert on table ingest.youtube_discoveries to service_role",
            lowered,
        )
        self.assertNotIn(
            "grant update on table ingest.youtube_discoveries to service_role",
            lowered,
        )
        self.assertIn("youtube_discoveries_live_only_check check (not is_demo)", compact)
        self.assertIn("expires_at = last_seen_at + interval '28 days'", compact)
        self.assertNotIn("ingest.source_discoveries", lowered)
        self.assertNotIn("is_youtube_discovery_metadata_source", lowered)
        self.assertNotIn("reject_youtube_discovery", lowered)
        self.assertNotIn("enforce_youtube_discovery", lowered)
        self.assertNotIn("create constraint trigger", lowered)
        self.assertNotIn("jobs_id_mode_unique", lowered)
        self.assertNotIn("alter column content_hash drop not null", compact)
        self.assertNotIn("alter column language drop not null", compact)
        self.assertIn(
            "on ingest.source_items (normalized_url, is_demo)", compact
        )
        self.assertIn(
            "on ingest.source_items (platform, external_id, is_demo)", compact
        )
        self.assertIn("source_items_id_mode_unique unique (id, is_demo)", compact)
        self.assertIn("drop constraint source_items_duplicate_cluster_id_fkey", compact)
        self.assertIn("foreign key (duplicate_cluster_id, is_demo)", compact)
        self.assertIn("references ingest.source_items (id, is_demo)", compact)
        self.assertIn("on update restrict", duplicate_cluster_fk)
        self.assertIn("on delete set null (duplicate_cluster_id)", duplicate_cluster_fk)
        self.assertIn("source_items_duplicate_cluster_mode_fkey", DATABASE_TYPES)
        self.assertIn("columns: ['duplicate_cluster_id', 'is_demo']", DATABASE_TYPES)
        self.assertIn("referencedcolumns: ['id', 'is_demo']", DATABASE_TYPES.casefold())
        self.assertIn("youtube_discoveries:", DATABASE_TYPES)
        self.assertIn(
            "youtube_discoveries_source_policy_id_fkey",
            DATABASE_TYPES,
        )
        youtube_types = DATABASE_TYPES.split("youtube_discoveries:", 1)[1].split(
            "source_request_gates:", 1
        )[0]
        for forbidden in (
            "source_item_id",
            "query_name",
            "job_id",
            "result_rank",
            "channel_country_code",
            "geography_status",
            "geography_basis",
            "metadata:",
            "text_excerpt",
            "author_hash",
            "content_hash",
            "language:",
        ):
            self.assertNotIn(forbidden, youtube_types)

    def test_service_role_is_read_only_and_worker_writes_use_fenced_rpcs(self) -> None:
        lowered = YOUTUBE_PIPELINE.casefold()
        compact = " ".join(lowered.split())
        self.assertIn("jobs_live_scheduled_enqueue_allowlist_check", lowered)
        self.assertIn("dedupe_key !~ '^schedule:'", compact)
        self.assertIn(
            "job_type in ('catalog.tcgdex.sets.sync', 'maintenance.cleanup')",
            compact,
        )
        self.assertIn("job_type = 'source.youtube.discovery'", compact)
        self.assertIn("payload - array['query_name'] = '{}'::jsonb", compact)
        scheduled = lowered.rsplit(
            "create or replace function ingest.enqueue_scheduled_job_v1", 1
        )[1].split("alter function ingest.enqueue_scheduled_job_v1", 1)[0]
        self.assertIn("job_type is not approved for scheduled enqueue", scheduled)
        self.assertIn("youtube jobs require one exact approved query_name", scheduled)
        self.assertLess(
            scheduled.index("job_type is not approved for scheduled enqueue"),
            scheduled.index("from ingest.jobs as jobs"),
        )
        self.assertIn(
            "schedule slot request must match its original job type and payload",
            scheduled,
        )
        self.assertIn(
            "revoke all privileges "
            "on all tables in schema catalog, ingest, analytics, public "
            "from service_role",
            compact,
        )
        self.assertIn(
            "grant select on all tables in schema catalog, ingest, analytics, public "
            "to service_role",
            compact,
        )
        self.assertIn(
            "revoke all on table ingest.source_request_gates from service_role",
            compact,
        )
        self.assertEqual(lowered.count("_service_role_all on "), 23)
        self.assertEqual(lowered.count("_service_all on "), 9)
        self.assertEqual(lowered.count("_service_role_select on "), 23)
        self.assertEqual(lowered.count("_service_select on "), 9)
        for function_name in (
            "enqueue_job_v1",
            "complete_job_v2",
            "pause_job_for_budget_v2",
            "upsert_worker_heartbeat_v1",
        ):
            function = lowered.split(
                f"create or replace function ingest.{function_name}", 1
            )[1].split(f"alter function ingest.{function_name}", 1)[0]
            self.assertIn("security definer", function)
            self.assertIn("set search_path = pg_catalog", function)
            self.assertIn(f"{function_name}:", DATABASE_TYPES)
        self.assertIn("typed live jobs require their dedicated fenced finalizer", lowered)
        self.assertIn("p_lease_generation", lowered)
        self.assertIn("lock_expires_at >", lowered)

    def test_youtube_begin_and_finalize_are_exact_fenced_kill_switches(self) -> None:
        lowered = YOUTUBE_PIPELINE.casefold()
        begin = lowered.split(
            "create or replace function ingest.begin_youtube_discovery_job", 1
        )[1].split("alter function ingest.begin_youtube_discovery_job", 1)[0]
        finalizer = lowered.split(
            "create or replace function ingest.finalize_youtube_discovery_job", 1
        )[1].split("alter function ingest.finalize_youtube_discovery_job", 1)[0]
        for function in (begin, finalizer):
            self.assertIn("security definer", function)
            self.assertIn("set search_path = pg_catalog", function)
            self.assertIn("for update of jobs", function)
            self.assertIn("lease_generation", function)
            self.assertIn("lock_expires_at <=", function)
            self.assertIn("'source.youtube.discovery'", function)
            self.assertIn("'youtube_discovery'", function)
            self.assertIn("policies.enabled", function)
            self.assertIn("not policies.statistics_eligible_default", function)
            self.assertIn("policies.retention_days = 28", function)
            self.assertIn("policies.max_items_per_run = 25", function)
            self.assertIn("policies.max_pages_per_run = 1", function)
            self.assertIn("for update of policies", function)
            self.assertLess(
                function.index("for update of policies"),
                function.rindex("lease_checked_at := clock_timestamp()"),
            )
        self.assertIn(
            "returns table( acquired boolean, retry_at timestamptz )",
            " ".join(begin.split()),
        )
        self.assertIn("lease_checked_at + interval '75 seconds'", begin)
        self.assertIn("owner_lease_generation = $3", begin)
        self.assertIn("octet_length(result::text) > 2097152", finalizer)
        self.assertIn("jsonb_array_length(result -> 'items') > 25", finalizer)
        self.assertIn(
            "not (item_value ?& array[ 'external_id', 'source_url', 'title', "
            "'published_at', 'collector_version', 'source_policy_version' ])",
            " ".join(finalizer.split()),
        )
        for forbidden_item_field in (
            "'normalized_url'",
            "'text_excerpt'",
            "'author_hash'",
            "'content_hash'",
            "'language'",
            "'metadata'",
        ):
            self.assertNotIn(forbidden_item_field, finalizer)
        self.assertNotIn("with ordinality", finalizer)
        self.assertIn("youtube result identities must be unique", finalizer)
        self.assertIn("insert into ingest.youtube_discoveries", finalizer)
        persistence_loop = finalizer[finalizer.rindex("for item_record in") :]
        self.assertIn("discovery_seen_at := clock_timestamp()", persistence_loop)
        self.assertIn("discovery_seen_at + interval '28 days'", persistence_loop)
        self.assertNotIn(
            "lease_checked_at + interval '28 days'",
            persistence_loop,
        )
        self.assertIn("on conflict (video_id)", finalizer)
        self.assertIn("expires_at = excluded.expires_at", finalizer)
        self.assertNotIn("insert into ingest.source_items", finalizer)
        self.assertNotIn("update ingest.source_items", finalizer)
        self.assertNotIn("insert into ingest.source_discoveries", finalizer)
        self.assertNotIn("insert into ingest.extraction_runs", finalizer)
        self.assertNotIn("insert into ingest.openings", finalizer)
        self.assertNotIn("insert into ingest.batch_sightings", finalizer)
        self.assertIn("last_attempt_at = greatest", finalizer)
        self.assertIn("last_success_at = policy_attempt_time", finalizer)
        self.assertIn("owner_job_id = null", finalizer)
        self.assertIn("owner_lease_generation = null", finalizer)
        self.assertIn("begin_youtube_discovery_job:", DATABASE_TYPES)
        self.assertIn("finalize_youtube_discovery_job:", DATABASE_TYPES)

    def test_request_gate_lifecycle_is_source_agnostic_and_retention_deletes_safely(self) -> None:
        lowered = YOUTUBE_PIPELINE.casefold()
        heartbeat = lowered.split(
            "create or replace function ingest.heartbeat_job_v2", 1
        )[1].split("alter function ingest.heartbeat_job_v2", 1)[0]
        failure = lowered.split(
            "create or replace function ingest.fail_job_v2", 1
        )[1].split("alter function ingest.fail_job_v2", 1)[0]
        self.assertNotIn("gates.source_key = 'tcgdex_catalog'", heartbeat)
        self.assertNotIn("gates.source_key = 'tcgdex_catalog'", failure)
        self.assertIn("gates.owner_job_id = $1", heartbeat)
        self.assertIn("gates.owner_lease_generation = $3", heartbeat)
        self.assertIn("gates.owner_job_id = $1", failure)
        self.assertIn("gates.owner_lease_generation = $3", failure)
        self.assertIn("policies.source_key = gates.source_key", failure)
        self.assertIn("last_attempt_at = greatest", failure)
        self.assertIn("last_failure_at = cooldown_recorded_at", failure)
        self.assertLess(
            failure.index("last_failure_at = cooldown_recorded_at"),
            failure.index("set owner_job_id = null"),
        )
        cleanup = lowered.split(
            "create or replace function ingest.prune_expired_ephemera_v2", 1
        )[1].split("alter function ingest.prune_expired_ephemera_v2", 1)[0]
        youtube_candidates = cleanup.split(
            "delete from ingest.youtube_discoveries", 1
        )[0]
        self.assertIn("from ingest.youtube_discoveries", youtube_candidates)
        self.assertIn("discoveries.expires_at <= cutoff", youtube_candidates)
        self.assertIn(
            "order by discoveries.expires_at, discoveries.video_id",
            youtube_candidates,
        )
        self.assertIn("for update of discoveries skip locked", youtube_candidates)
        self.assertIn("limit max_rows", youtube_candidates)
        self.assertIn("delete from ingest.youtube_discoveries", cleanup)
        self.assertIn("youtube_discoveries_deleted", cleanup)
        self.assertNotIn("source_discoveries", cleanup)
        self.assertNotIn("source_policy_id", youtube_candidates)

    def test_admin_control_rpc_is_callable_only_by_service_role_with_explicit_actor(self) -> None:
        admin = (ROOT / "migrations/20260825000600_admin_control.sql").read_text().casefold()
        self.assertIn("p_actor_id uuid", admin)
        self.assertIn("p_actor_email text", admin)
        self.assertIn("service_role", admin)
        self.assertIn("revoke all on function public.admin_control_and_audit_v1", admin)
        self.assertIn("from public, anon, authenticated", admin)
        self.assertIn("to service_role", admin)
        self.assertNotIn("to authenticated", admin)

    def test_admin_wrappers_reject_direct_database_service_role_sessions(self) -> None:
        fence = " ".join(ADMIN_SESSION_FENCE.casefold().split())
        self.assertIn(
            "alter function public.get_admin_dashboard_snapshot_v1() set schema ingest",
            fence,
        )
        self.assertIn(
            "alter function public.admin_control_and_audit_v1(text, uuid, text, text, text) set schema ingest",
            fence,
        )
        self.assertEqual(fence.count("session_user <> 'authenticator'"), 2)
        self.assertEqual(fence.count("auth.jwt() ->> 'role'"), 2)
        self.assertIn(
            "revoke all on function ingest.admin_control_and_audit_v1",
            fence,
        )
        self.assertIn(
            "revoke all on function ingest.get_admin_dashboard_snapshot_v1",
            fence,
        )
        self.assertIn(
            "grant execute on function public.admin_control_and_audit_v1",
            fence,
        )
        self.assertIn(
            "grant execute on function public.get_admin_dashboard_snapshot_v1",
            fence,
        )
        self.assertEqual(DATABASE_TYPES.count("admin_control_and_audit_v1:"), 2)
        self.assertEqual(DATABASE_TYPES.count("get_admin_dashboard_snapshot_v1:"), 2)

    def test_admin_control_rpc_is_audited_and_matches_generated_types(self) -> None:
        migrations = "\n".join(
            path.read_text() for path in sorted((ROOT / "migrations").glob("*.sql"))
        )
        self.assertIn("function public.admin_control_and_audit_v1", migrations)
        self.assertIn("security definer", migrations.casefold())
        self.assertIn("p_actor_id uuid", migrations)
        self.assertIn("p_actor_email text", migrations)
        self.assertIn("insert into ingest.admin_audit_log", migrations)
        self.assertIn("grant execute on function public.admin_control_and_audit_v1", migrations)
        self.assertIn("revoke all on function public.admin_control_and_audit_v1", migrations)
        self.assertIn("admin_control_and_audit_v1:", DATABASE_TYPES)
        self.assertIn("get_admin_dashboard_snapshot_v1:", DATABASE_TYPES)
        self.assertIn("p_actor_id: string;", DATABASE_TYPES)
        self.assertIn("p_actor_email: string;", DATABASE_TYPES)

    def test_admin_snapshot_is_service_only_bounded_telemetry(self) -> None:
        admin = (ROOT / "migrations/20260825000600_admin_control.sql").read_text().casefold()
        snapshot = admin.split(
            "create or replace function public.get_admin_dashboard_snapshot_v1()", 1
        )[1].split("$$;", 1)[0]
        self.assertIn("security definer", snapshot)
        self.assertIn("service_role", snapshot)
        self.assertIn("limit 100", snapshot)
        self.assertIn("limit 50", snapshot)
        for private_field in (
            "j.payload",
            "last_error",
            "authenticated_sources",
            "provider",
            "model",
            "prompt",
            "source_excerpt",
            "ip_address",
            "cookie",
            "secret",
        ):
            self.assertNotIn(private_field, snapshot)

    def test_operational_telemetry_separates_live_and_demo_modes(self) -> None:
        compact_ingest = " ".join(INGEST.split()).casefold()
        for table in ("worker_heartbeats", "browser_sessions", "ai_usage_daily"):
            body = compact_ingest.split(f"create table ingest.{table} (", 1)[1].split(
                ");", 1
            )[0]
            self.assertIn("is_demo boolean not null default false", body)
        self.assertIn(
            "primary key (date, provider, model, stage, is_demo)",
            compact_ingest,
        )

        admin = " ".join(
            (ROOT / "migrations/20260825000600_admin_control.sql").read_text().split()
        ).casefold()
        snapshot = admin.split(
            "create or replace function public.get_admin_dashboard_snapshot_v1()", 1
        )[1].split("$$;", 1)[0]
        for predicate in (
            "where not h.is_demo",
            "where not s.is_demo",
            "where not u.is_demo",
        ):
            self.assertIn(predicate, snapshot)

        browser_seed = _seed_rows("ingest.browser_sessions")
        self.assertEqual(browser_seed[0]["is_demo"].casefold(), "true")

    def test_admin_controls_reject_demo_targets_and_create_only_live_jobs(self) -> None:
        admin = " ".join(
            (ROOT / "migrations/20260825000600_admin_control.sql").read_text().split()
        ).casefold()
        control = admin.split(
            "create or replace function public.admin_control_and_audit_v1", 1
        )[1]
        self.assertIn("where policy.enabled and not policy.is_demo", control)
        self.assertGreaterEqual(control.count("and not is_demo"), 3)
        self.assertIn("where not is_demo and (source_key = p_target_id", control)
        self.assertIn("from ingest.browser_sessions s where s.profile_name = p_target_id and not s.is_demo", control)
        self.assertIn("from ingest.worker_heartbeats h where h.worker_id = p_target_id and not h.is_demo", control)
        self.assertGreaterEqual(control.count("max_attempts, is_demo"), 3)
        self.assertGreaterEqual(control.count("on conflict (job_type, dedupe_key, is_demo)"), 3)

    def test_source_policy_denial_is_audited_without_transaction_rollback(self) -> None:
        admin = (ROOT / "migrations/20260825000600_admin_control.sql").read_text().casefold()
        enqueue = admin.split("when 'source.enqueue' then", 1)[1].split(
            "when 'job.retry' then", 1
        )[0]
        denial = enqueue.split("if v_policy_id is null then", 1)[1].split("end if;", 1)[0]
        self.assertIn("insert into ingest.admin_audit_log", denial)
        self.assertIn("'reason', 'source_policy_denied'", denial)
        self.assertIn("'audit_written', true", denial)
        self.assertIn("'ok', false", denial)
        self.assertNotIn("raise exception", denial)

    def test_record_exclusion_revokes_eligibility_and_invalidates_derived_data(self) -> None:
        admin = (ROOT / "migrations/20260825000600_admin_control.sql").read_text().casefold()
        exclusion = admin.split("when 'record.exclude' then", 1)[1].split(
            "when 'browser.refresh' then", 1
        )[0]
        self.assertIn("returning is_demo into v_record_is_demo", exclusion)
        self.assertIn("and not is_demo", exclusion)
        self.assertIn("update ingest.openings", exclusion)
        self.assertIn("eligible_for_statistics = false", exclusion)
        self.assertIn("validation_status = 'excluded'", exclusion)
        self.assertIn("public_status = 'rejected'", exclusion)
        self.assertIn(
            "where source_item_id = p_target_id::uuid and is_demo = v_record_is_demo",
            " ".join(exclusion.split()),
        )
        for table in (
            "analytics.dashboard_daily",
            "analytics.set_metrics_daily",
            "analytics.region_metrics_daily",
            "analytics.retailer_metrics_daily",
            "analytics.batch_metrics_daily",
            "analytics.signals",
            "public.dashboard_overview",
            "public.set_summaries",
            "public.region_summaries",
            "public.retailer_summaries",
            "public.batch_summaries",
            "public.recent_activity",
            "public.public_signals",
        ):
            self.assertIn(f"delete from {table}", exclusion)
        self.assertIn("'unavailable'", exclusion)
        self.assertIn("'admin-record-exclusion-demo'", exclusion)
        self.assertIn("'admin-record-exclusion-live'", exclusion)
        self.assertIn("is_demo = v_record_is_demo", exclusion)

    def test_generated_source_item_contract_includes_reserved_fingerprints(self) -> None:
        source_items = DATABASE_TYPES.split("source_items:", 1)[1].split("worker_heartbeats:", 1)[0]
        self.assertGreaterEqual(source_items.count("video_fingerprint"), 3)
        self.assertGreaterEqual(source_items.count("audio_fingerprint"), 3)

    def test_generated_public_activity_contract_tracks_statistics_eligibility(self) -> None:
        activity = DATABASE_TYPES.split("recent_activity:", 1)[1].split("region_summaries:", 1)[0]
        self.assertGreaterEqual(activity.count("statistics_eligible"), 3)
        self.assertIn("country_code: string;", activity)
        self.assertNotIn("country_code: string | null;", activity)

    def test_live_rpc_does_not_fabricate_an_empty_snapshot(self) -> None:
        self.assertIn("join dashboard_row d on true", RPC)
        self.assertNotIn("left join dashboard_row d on true", RPC)

    def test_public_rpc_selects_only_the_latest_non_demo_live_snapshot(self) -> None:
        compact = " ".join(RPC.split())
        dashboard_row = compact.split("with dashboard_row as (", 1)[1].split(
            "), relation_guard as (", 1
        )[0]
        self.assertIn("from public.dashboard_overview d where not d.is_demo", dashboard_row)
        self.assertLess(dashboard_row.index("where not d.is_demo"), dashboard_row.index("order by"))
        self.assertIn("and d.mode = 'live'", compact)
        self.assertNotIn("d.mode in ('demo', 'live')", compact)

    def test_unavailable_dashboard_sentinel_preserves_its_data_mode(self) -> None:
        compact = " ".join(PUBLIC.split())
        self.assertIn("(mode = 'demo' and is_demo)", compact)
        self.assertIn("(mode = 'live' and not is_demo)", compact)
        self.assertIn("or mode = 'unavailable'", compact)

    def test_public_inference_requires_three_independent_sources(self) -> None:
        compact = " ".join(PUBLIC.split())
        self.assertEqual(
            compact.count(
                "(signal_status = 'Insufficient sample' and (observed_packs < 30 or independent_source_count < 3))"
            ),
            4,
        )
        self.assertEqual(
            compact.count(
                "(signal_status = 'No significant signal' and observed_packs >= 30 and independent_source_count >= 3)"
            ),
            4,
        )
        self.assertIn(
            "(status = 'Insufficient sample' and (sample_size < 30 or independent_source_count < 3))",
            compact,
        )
        self.assertIn(
            "(status = 'No significant signal' and sample_size >= 30 and independent_source_count >= 3)",
            compact,
        )

    def test_private_signal_storage_matches_the_three_source_gate(self) -> None:
        compact = " ".join(ANALYTICS.split())
        self.assertIn(
            "(signal_status = 'Insufficient sample' and (observed_packs < 30 or independent_source_count < 3))",
            compact,
        )
        self.assertIn(
            "(signal_status = 'No significant signal' and observed_packs >= 30 and independent_source_count >= 3)",
            compact,
        )
        self.assertIn(
            "(status = 'Insufficient sample' and (sample_size < 30 or independent_source_count < 3))",
            compact,
        )
        self.assertIn(
            "(status = 'No significant signal' and sample_size >= 30 and independent_source_count >= 3)",
            compact,
        )

    def test_dashboard_baseline_is_withheld_below_pack_or_source_minimums(self) -> None:
        compact = " ".join(PUBLIC.split())
        self.assertIn(
            "baseline_hit_rate is null or (observed_packs >= 30 and verified_sources >= 3 and baseline_hit_rate between 0 and 1)",
            compact,
        )
        self.assertIn("'baselineHitRate', d.baseline_hit_rate", RPC)
        self.assertNotIn("'baselineHitRate', coalesce(d.baseline_hit_rate, 0)", RPC)

    def test_public_rpc_filters_every_collection_to_the_selected_available_mode(self) -> None:
        self.assertEqual(RPC.count("cross join dashboard_row mode_guard"), 6)
        self.assertEqual(RPC.count("is_demo = mode_guard.is_demo"), 6)
        self.assertIn("d.mode = 'live'", RPC)
        self.assertIn("'mode', d.mode", RPC)

    def test_public_data_tables_bound_independent_sources_to_openings(self) -> None:
        self.assertEqual(
            PUBLIC.count("independent_source_count <= complete_openings"),
            5,
        )

    def test_seed_metric_deltas_equal_observed_minus_baseline(self) -> None:
        for table in (
            "public.set_summaries",
            "public.region_summaries",
            "public.retailer_summaries",
            "public.batch_summaries",
        ):
            for row in _seed_rows(table):
                values = [row[field].strip().lower() for field in ("baseline_rate", "observed_rate", "delta_from_baseline")]
                if values == ["null", "null", "null"]:
                    continue
                self.assertNotIn("null", values, msg=f"{table} has a partially withheld metric tuple: {row}")
                baseline, observed, delta = (Decimal(value) for value in values)
                self.assertEqual(
                    delta,
                    observed - baseline,
                    msg=f"{table} delta must equal observed minus baseline: {row}",
                )

    def test_dashboard_daily_bounds_accepted_sources_to_complete_openings(self) -> None:
        self.assertIn("accepted_sources <= complete_openings", ANALYTICS)

    def test_private_metric_tables_bound_independent_sources_to_openings(self) -> None:
        self.assertEqual(
            ANALYTICS.count(
                "independent_source_count >= 0 and independent_source_count <= complete_openings"
            ),
            4,
        )

    def test_dashboard_and_public_signals_bound_sources_to_openings(self) -> None:
        self.assertIn("verified_sources <= complete_openings", PUBLIC)
        self.assertIn(
            "complete_openings <= sample_size and independent_source_count > 0 "
            "and independent_source_count <= complete_openings",
            PUBLIC,
        )

    def test_public_metric_tables_bind_delta_to_observed_and_baseline_rates(self) -> None:
        self.assertEqual(
            PUBLIC.count("abs(delta_from_baseline - (observed_rate - baseline_rate))"),
            4,
        )

    def test_public_metric_rpc_includes_baseline_posterior_and_source_context(self) -> None:
        self.assertEqual(RPC.count("'independentSources'"), 4)
        self.assertEqual(RPC.count("'baselineRate'"), 4)
        self.assertEqual(RPC.count("'posteriorMean'"), 4)

    def test_public_activity_and_regions_are_australia_only(self) -> None:
        self.assertIn("regions_country_code_check check (country_code = 'AU')", CATALOG)
        self.assertGreaterEqual(PUBLIC.count("country_code = 'AU'"), 3)
        self.assertIn("a.country_code = 'AU'", RPC)

    def test_catalog_openings_and_analytics_are_english_only(self) -> None:
        for name in ("sets", "products", "cards"):
            self.assertIn(f"constraint {name}_language_check check (language = 'en')", CATALOG)
        self.assertIn("constraint openings_language_check check (language = 'en')", INGEST)
        for name in ("dashboard", "set_metrics", "region_metrics", "retailer_metrics"):
            self.assertIn(f"constraint {name}_daily_language_check check (language = 'en')", ANALYTICS)

    def test_database_product_vocabulary_is_mvp_only(self) -> None:
        contracts = "\n".join((CATALOG, ANALYTICS, PUBLIC))
        checks = re.findall(
            r"constraint [a-z_]*(?:product_type|products_type)_check check \((.*?)\),?\n",
            contracts,
            flags=re.DOTALL,
        )
        self.assertGreaterEqual(len(checks), 5)
        vocabulary_contract = "\n".join(checks)
        for unsupported in ("blister", "collection", "tin", "other", "unknown", "elite_trainer_box"):
            self.assertNotIn(f"'{unsupported}'", vocabulary_contract)
        self.assertIn("('booster_box', 'etb', 'booster_bundle')", vocabulary_contract)

    def test_signal_tables_enforce_conservative_publication_gates(self) -> None:
        for sql in (PUBLIC, (ROOT / "migrations/20260825000300_analytics.sql").read_text()):
            self.assertIn("sample_size >= 200", sql)
            self.assertIn("independent_source_count >= 3", sql)
            self.assertIn("probability_above_practical_uplift >= 0.900", sql)
            self.assertIn("probability_above_practical_uplift >= 0.950", sql)
            self.assertNotIn("probability_above_baseline >= 0.900", sql)



if __name__ == "__main__":
    unittest.main()
