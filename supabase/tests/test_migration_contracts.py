import re
from decimal import Decimal
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CATALOG = (ROOT / "migrations/20260825000100_catalog.sql").read_text()
INGEST = (ROOT / "migrations/20260825000200_ingest.sql").read_text()
ANALYTICS = (ROOT / "migrations/20260825000300_analytics.sql").read_text()
PUBLIC = (ROOT / "migrations/20260825000400_public_tables.sql").read_text()
RPC = (ROOT / "migrations/20260825000500_public_rpc_security.sql").read_text()
FENCING = (ROOT / "migrations/20260827000000_job_lease_fencing.sql").read_text()
TCGDEX_PIPELINE = (ROOT / "migrations/20260828000000_tcgdex_sets_pipeline.sql").read_text()
YOUTUBE_PIPELINE = (ROOT / "migrations/20260829000000_youtube_global_discovery.sql").read_text()
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
        self.assertIn("2, 2, 50, 1, false, 30", compact)
        self.assertIn("'youtube-global-discovery-v1'", compact)
        self.assertIn('"youtube-metadata-v1"', compact)
        self.assertIn('"discovery_scope":"global"', compact)
        self.assertIn("'activity_only'", compact)
        self.assertIn("'evidence_tier'", compact)
        self.assertIn("'statistics_eligible'", compact)
        self.assertNotIn("youtube_api_key", lowered)
        self.assertNotIn("service_role_key", lowered)
        self.assertNotIn("insert into ingest.openings", lowered)
        self.assertNotIn("insert into ingest.opening_hits", lowered)
        self.assertNotIn("insert into public.", lowered)

    def test_youtube_source_identity_and_provenance_are_private_and_mode_safe(self) -> None:
        lowered = YOUTUBE_PIPELINE.casefold()
        compact = " ".join(lowered.split())
        self.assertIn("alter column content_hash drop not null", compact)
        self.assertIn(
            "on ingest.source_items (normalized_url, is_demo)", compact
        )
        self.assertIn(
            "on ingest.source_items (platform, external_id, is_demo)", compact
        )
        self.assertIn("create table ingest.source_discoveries", lowered)
        self.assertIn(
            "unique (source_item_id, query_name, is_demo)", compact
        )
        self.assertIn("source_items_id_mode_unique unique (id, is_demo)", compact)
        self.assertIn("jobs_id_mode_unique unique (id, is_demo)", compact)
        self.assertIn("source_discoveries_source_item_mode_fkey", compact)
        self.assertIn("foreign key (source_item_id, is_demo)", compact)
        self.assertIn("references ingest.source_items (id, is_demo)", compact)
        self.assertIn("source_discoveries_job_mode_fkey", compact)
        self.assertIn("foreign key (job_id, is_demo)", compact)
        self.assertIn("references ingest.jobs (id, is_demo)", compact)
        self.assertGreaterEqual(compact.count("on update restrict"), 2)
        self.assertIn("channel_country_proxy", lowered)
        self.assertIn("youtube_channel_country", lowered)
        self.assertIn("alter table ingest.source_discoveries force row level security", lowered)
        self.assertIn("grant select on table ingest.source_discoveries to service_role", lowered)
        self.assertNotIn(
            "grant insert on table ingest.source_discoveries to service_role", lowered
        )
        self.assertNotIn(
            "grant update on table ingest.source_discoveries to service_role", lowered
        )
        self.assertIn("source_discoveries_source_item_mode_fkey", DATABASE_TYPES)
        self.assertIn("source_discoveries_job_mode_fkey", DATABASE_TYPES)

    def test_youtube_metadata_cannot_be_promoted_or_clustered_after_policy_rebind(self) -> None:
        lowered = YOUTUBE_PIPELINE.casefold()
        classifier = lowered.split(
            "create or replace function ingest.is_youtube_discovery_metadata_source", 1
        )[1].split(
            "alter function ingest.is_youtube_discovery_metadata_source", 1
        )[0]
        evidence_guard = lowered.split(
            "create or replace function ingest.reject_youtube_discovery_evidence_reference", 1
        )[1].split(
            "alter function ingest.reject_youtube_discovery_evidence_reference", 1
        )[0]
        duplicate_guard = lowered.split(
            "create or replace function ingest.reject_youtube_discovery_duplicate_cluster", 1
        )[1].split(
            "alter function ingest.reject_youtube_discovery_duplicate_cluster", 1
        )[0]
        policy_rebind_guard = lowered.split(
            "create or replace function ingest.reject_youtube_discovery_policy_rebind", 1
        )[1].split(
            "alter function ingest.reject_youtube_discovery_policy_rebind", 1
        )[0]
        end_state_guard = lowered.split(
            "create or replace function ingest.enforce_youtube_discovery_metadata_end_state", 1
        )[1].split(
            "alter function ingest.enforce_youtube_discovery_metadata_end_state", 1
        )[0]
        self.assertIn("security definer", classifier)
        self.assertIn("ingest.source_discoveries", classifier)
        self.assertIn("policies.source_key = 'youtube_discovery'", classifier)
        self.assertIn("is_youtube_discovery_metadata_source(new.source_item_id)", evidence_guard)
        self.assertIn("new.duplicate_cluster_id is not null", duplicate_guard)
        self.assertIn("new.id, new.source_policy_id", duplicate_guard)
        self.assertIn("new.duplicate_cluster_id", duplicate_guard)
        self.assertEqual(lowered.count("reject_youtube_discovery_evidence_reference();"), 3)
        self.assertIn("before insert or update of duplicate_cluster_id", lowered)
        self.assertIn("errcode = '23514'", evidence_guard)
        self.assertIn("errcode = '23514'", duplicate_guard)
        self.assertIn("new.id, new.source_policy_id", policy_rebind_guard)
        self.assertIn("tg_op = 'update'", policy_rebind_guard)
        self.assertIn("old.id", policy_rebind_guard)
        self.assertIn("old.source_policy_id", policy_rebind_guard)
        self.assertIn(
            "and not ingest.is_youtube_discovery_metadata_source",
            policy_rebind_guard,
        )
        self.assertIn("source_items.duplicate_cluster_id = new.id", policy_rebind_guard)
        self.assertIn("ingest.extraction_runs", policy_rebind_guard)
        self.assertIn("ingest.openings", policy_rebind_guard)
        self.assertIn("ingest.batch_sightings", policy_rebind_guard)
        self.assertIn("before insert or update of source_policy_id", lowered)
        self.assertIn("errcode = '23514'", policy_rebind_guard)
        self.assertIn("ingest.source_discoveries", end_state_guard)
        self.assertIn("ingest.extraction_runs", end_state_guard)
        self.assertIn("ingest.openings", end_state_guard)
        self.assertIn("ingest.batch_sightings", end_state_guard)
        self.assertIn("current_source.duplicate_cluster_id", end_state_guard)
        self.assertEqual(
            lowered.count("enforce_youtube_discovery_metadata_end_state();"),
            5,
        )
        self.assertEqual(lowered.count("create constraint trigger"), 5)
        self.assertEqual(lowered.count("deferrable initially deferred"), 5)
        self.assertIn(
            "revoke all on function ingest.enforce_youtube_discovery_metadata_end_state()",
            lowered,
        )

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
            self.assertIn("policies.retention_days = 30", function)
            self.assertIn("policies.max_items_per_run = 50", function)
            self.assertIn("policies.max_pages_per_run = 2", function)
            self.assertIn("for update of policies", function)
            self.assertLess(
                function.index("for update of policies"),
                function.rindex("lease_checked_at := clock_timestamp()"),
            )
        self.assertIn("returns table( acquired boolean, retry_at timestamptz )", " ".join(begin.split()))
        self.assertIn("lease_checked_at + interval '75 seconds'", begin)
        self.assertIn("owner_lease_generation = $3", begin)
        self.assertIn("octet_length(result::text) > 2097152", finalizer)
        self.assertIn("jsonb_array_length(result -> 'items') > 50", finalizer)
        self.assertIn("youtube result identities must be unique", finalizer)
        self.assertIn("youtube discovery identity conflicts", finalizer)
        self.assertIn("'activity_only'", finalizer)
        self.assertNotIn("usage_classification = 'activity_only'", finalizer)
        self.assertNotIn("status = 'activity_only'", finalizer)
        self.assertIn("insert into ingest.source_discoveries", finalizer)
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
        youtube_candidates = cleanup.split("delete from ingest.source_items", 1)[0]
        self.assertIn("policies.source_key = 'youtube_discovery'", cleanup)
        self.assertIn("source_items.expires_at <= cutoff", cleanup)
        self.assertIn("ingest.source_discoveries", youtube_candidates)
        self.assertIn(
            "max(discoveries.last_seen_at) + interval '30 days' as effective_expiry",
            youtube_candidates,
        )
        self.assertIn("marker_expiry.effective_expiry <= cutoff", youtube_candidates)
        self.assertIn("marker_expiry.effective_expiry is null", youtube_candidates)
        self.assertIn(
            "order by coalesce( marker_expiry.effective_expiry, source_items.expires_at )",
            " ".join(youtube_candidates.split()),
        )
        self.assertNotIn("ingest.extraction_runs", youtube_candidates)
        self.assertNotIn("ingest.openings", youtube_candidates)
        self.assertNotIn("ingest.batch_sightings", youtube_candidates)
        self.assertIn("limit max_rows", cleanup)
        self.assertIn("delete from ingest.source_items", cleanup)
        self.assertIn("youtube_source_items_deleted", cleanup)

    def test_admin_control_rpc_is_callable_only_by_service_role_with_explicit_actor(self) -> None:
        admin = (ROOT / "migrations/20260825000600_admin_control.sql").read_text().casefold()
        self.assertIn("p_actor_id uuid", admin)
        self.assertIn("p_actor_email text", admin)
        self.assertIn("service_role", admin)
        self.assertIn("revoke all on function public.admin_control_and_audit_v1", admin)
        self.assertIn("from public, anon, authenticated", admin)
        self.assertIn("to service_role", admin)
        self.assertNotIn("to authenticated", admin)

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
