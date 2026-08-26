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
        self.assertGreaterEqual(len(tables), 20)
        ignored = {"constraint", "primary", "unique", "check", "foreign", "exclude"}
        for schema, table, body in tables:
            columns = {
                match.group(1)
                for match in re.finditer(r"^  ([a-z_][a-z0-9_]*)\s+", body, flags=re.MULTILINE)
                if match.group(1) not in ignored
            }
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
        lowered = INGEST.casefold()
        self.assertIn("update ingest.jobs as exhausted", lowered)
        self.assertIn("exhausted.attempts >= exhausted.max_attempts", lowered)
        self.assertIn("exhausted.status = 'running'", lowered)
        self.assertIn("exhausted.lock_expires_at <= claim_time", lowered)
        self.assertIn("'lease_expired_max_attempts'", lowered)
        self.assertIn("status = 'dead'", lowered)
        self.assertIn("and not exhausted.is_demo", lowered)
        self.assertIn("and not j.is_demo", lowered)

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
