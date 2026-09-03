from __future__ import annotations

import re
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MIGRATION = REPOSITORY_ROOT / "supabase" / "migrations" / "20260923000000_runtime_release_evidence.sql"
HARDENING_MIGRATION = (
    REPOSITORY_ROOT
    / "supabase"
    / "migrations"
    / "20260924000000_runtime_release_evidence_hardening.sql"
)
BLUESKY_RUNTIME_MIGRATION = (
    REPOSITORY_ROOT
    / "supabase"
    / "migrations"
    / "20260929000000_runtime_release_evidence_bluesky.sql"
)
ACL_NORMALIZATION_MIGRATION = (
    REPOSITORY_ROOT
    / "supabase"
    / "migrations"
    / "20260930000000_runtime_release_evidence_acl_normalization.sql"
)
PYTHON_ROOT = REPOSITORY_ROOT / "services" / "worker" / "pokecrack_worker"


class RuntimeReleaseEvidenceMigrationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")
        cls.function_body = cls.sql.split("as $function$", 1)[1].split("$function$", 1)[0]

    def test_migration_is_forward_only_and_uses_exact_capability_acl(self) -> None:
        self.assertEqual(self.sql.lower().count("begin;"), 1)
        self.assertEqual(self.sql.lower().count("commit;"), 1)
        self.assertIn("create role pokecrack_runtime_monitor", self.sql)
        self.assertIn("nologin noinherit nosuperuser", self.sql)
        self.assertIn("grant usage on schema ingest to pokecrack_runtime_monitor", self.sql)
        self.assertIn(
            "revoke all on function ingest.get_runtime_release_evidence_v1(timestamptz, integer, integer)",
            self.sql,
        )
        self.assertIn(
            "from public, anon, authenticated, service_role",
            self.sql,
        )
        self.assertRegex(
            self.sql,
            r"grant execute on function ingest\.get_runtime_release_evidence_v1\(timestamptz, integer, integer\)\s+to pokecrack_runtime_monitor",
        )
        self.assertNotRegex(
            self.sql,
            r"grant\s+(?:all|execute)[^;]*\b(?:public|anon|authenticated|service_role)\b",
        )

    def test_result_keys_are_aggregate_only_and_never_raw_data(self) -> None:
        returned_keys = set(
            re.findall(r"^\s+'([a-z0-9][a-z0-9_]*)',", self.function_body, flags=re.MULTILINE)
        )
        self.assertEqual(
            returned_keys,
            {
                "schema_version",
                "status",
                "release_age_seconds",
                "grace_seconds",
                "workers",
                "sources",
                "schedule",
                "queue",
                "checkpoints",
                "cleanup",
                "expected_count",
                "observed_count",
                "healthy_count",
                "stale_count",
                "missing_count",
                "future_count",
                "max_age_seconds",
                "configured_count",
                "enabled_count",
                "disabled_count",
                "fresh_count",
                "never_succeeded_count",
                "advanced_since_release_count",
                "slot_count",
                "slots_with_job_count",
                "orphan_slot_count",
                "latest_slot_age_seconds",
                "latest_job_age_seconds",
                "latest_job_status",
                "live_job_count",
                "pending_count",
                "running_count",
                "completed_count",
                "failed_count",
                "dead_count",
                "cancelled_count",
                "future_created_count",
                "pending_age_bands",
                "under_5m",
                "5m_to_1h",
                "1h_to_6h",
                "over_6h",
                "never_collected_count",
                "scheduled_count",
                "latest_status",
                "latest_age_seconds",
            },
        )
        for forbidden in (
            "'payload'",
            "'url'",
            "'cursor'",
            "'policy_id'",
            "'gate_id'",
            "'worker_id'",
            "'job_id'",
            "'credential'",
            "'identity'",
        ):
            self.assertNotIn(forbidden, self.function_body)
        for source in (
            "ingest.worker_heartbeats",
            "ingest.source_policies",
            "ingest.schedule_slots",
            "ingest.jobs",
            "catalog.sync_state",
            "ingest.bluesky_jetstream_checkpoints",
            "ingest.nostr_relay_checkpoints",
            "ingest.mastodon_public_hashtag_checkpoints",
        ):
            self.assertIn(source, self.function_body)

    def test_function_is_fail_closed_for_context_and_grants_no_direct_table_access(self) -> None:
        self.assertIn("set search_path = pg_catalog", self.sql)
        self.assertIn("p_release_started_at > observed_at + make_interval(mins => 5)", self.sql)
        self.assertIn("raise exception 'invalid runtime evidence grace window'", self.sql)
        self.assertIn("raise exception 'invalid runtime evidence heartbeat window'", self.sql)
        self.assertIn("revoke all on all tables in schema ingest from pokecrack_runtime_monitor", self.sql)
        self.assertNotIn("grant select on", self.sql.lower())


class RuntimeReleaseEvidenceHardeningContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = HARDENING_MIGRATION.read_text(encoding="utf-8")

    def test_service_sets_are_exact_scoped_and_exclude_demo_data(self) -> None:
        self.assertEqual(self.sql.lower().count("begin;"), 1)
        self.assertEqual(self.sql.lower().count("commit;"), 1)
        self.assertIn("when 'tcgdex' then", self.sql)
        self.assertIn("when 'tcgdex-nostr' then", self.sql)
        self.assertIn("raise exception 'invalid runtime evidence service set'", self.sql)
        self.assertIn("'nostr-collector'", self.sql)
        for source_key in (
            "tcgdex_catalog",
            "nostr_relay_primal",
            "nostr_relay_nos_lol",
            "nostr_relay_nostr_net",
        ):
            self.assertIn(f"'{source_key}'", self.sql)
        self.assertIn("and policies.is_demo = false", self.sql)
        self.assertIn("heartbeats.is_demo = false", self.sql)
        self.assertIn("jobs.is_demo = false", self.sql)

    def test_healthy_requires_current_release_progress_not_just_old_state(self) -> None:
        self.assertIn("worker_advanced_count <> expected_worker_count", self.sql)
        self.assertIn("source_advanced_count <> expected_source_count", self.sql)
        self.assertIn("checkpoint_advanced_count <> expected_source_count", self.sql)
        self.assertIn("freshness_at >= p_release_started_at", self.sql)
        self.assertIn("jobs.created_at >= p_release_started_at", self.sql)
        self.assertIn("slots.slot_at >= p_release_started_at", self.sql)
        self.assertIn("schedule_stale_count > 0", self.sql)
        self.assertIn("schedule_future_count > 0", self.sql)
        self.assertIn("cleanup_latest_age_seconds > 129600", self.sql)

    def test_monitor_capability_is_runtime_attested_and_old_overload_is_not_a_bypass(self) -> None:
        self.assertIn("set search_path = pg_catalog, pg_temp", self.sql)
        self.assertIn("if session_user <> 'postgres' then", self.sql)
        self.assertIn("memberships.set_option", self.sql)
        self.assertIn("not memberships.inherit_option", self.sql)
        self.assertIn("not memberships.admin_option", self.sql)
        self.assertIn("runtime evidence monitor capability has drifted", self.sql)
        self.assertIn("pg_catalog.pg_db_role_setting", self.sql)
        self.assertIn("relations.relowner = monitor_oid", self.sql)
        self.assertIn("relations.relowner = caller_oid", self.sql)
        self.assertIn("coalesce(roles.rolconfig, '{}'::text[]) = '{}'::text[]", self.sql)
        self.assertIn("runtime evidence monitor login has direct application grants", self.sql)
        self.assertIn(
            "revoke execute on function ingest.get_runtime_release_evidence_v1(timestamptz, integer, integer)",
            self.sql,
        )
        self.assertRegex(
            self.sql,
            r"grant execute on function ingest\.get_runtime_release_evidence_v1\(timestamptz, integer, integer, text\)\s+to pokecrack_runtime_monitor",
        )


class RuntimeReleaseEvidenceBlueskyContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = BLUESKY_RUNTIME_MIGRATION.read_text(encoding="utf-8")

    def test_forward_patch_requires_the_reviewed_bluesky_prerequisites(self) -> None:
        self.assertEqual(self.sql.lower().count("begin;"), 1)
        self.assertEqual(self.sql.lower().count("commit;"), 1)
        self.assertIn(
            "to_regprocedure('ingest.verify_bluesky_release_v1()')", self.sql
        )
        self.assertIn(
            "to_regclass('ingest.bluesky_jetstream_checkpoints')", self.sql
        )
        self.assertIn(
            "runtime evidence Bluesky capability is unavailable or drifted", self.sql
        )
        self.assertIn(
            "runtime release evidence Bluesky integration did not match exactly", self.sql
        )
        self.assertIn(
            "runtime release evidence no longer has the reviewed security header",
            self.sql,
        )
        self.assertIn("functions.prosecdef", self.sql)
        self.assertIn("functions.provolatile = 's'", self.sql)
        self.assertIn("functions.proparallel = 'r'", self.sql)
        self.assertIn(
            "array['search_path=pg_catalog, pg_temp']::text[]", self.sql
        )
        self.assertIn("pg_get_functiondef(", self.sql)
        self.assertIn("execute updated_definition;", self.sql)

    def test_bluesky_service_set_is_exact_and_uses_its_own_checkpoint(self) -> None:
        for expected in (
            "when 'tcgdex-bluesky' then",
            "'collector', 'scheduler', 'watchdog', 'bluesky-collector'",
            "'tcgdex_catalog'",
            "'bluesky_jetstream'",
            "'catalog.tcgdex.sets.sync'",
            "'maintenance.cleanup'",
            "'source.bluesky.jetstream'",
            "'catalog_sync', 'cleanup', 'bluesky_jetstream'",
            "expected_schedule_count := 3;",
            "bluesky_checkpoints.last_collected_at",
            "ingest.bluesky_jetstream_checkpoints",
        ):
            self.assertIn(expected, self.sql)
        self.assertIn(
            "expected.source_key <> 'bluesky_jetstream'\n      and nostr_checkpoints.source_policy_id",
            self.sql,
        )

    def test_forward_patch_replaces_rather_than_retains_reviewed_fragments(self) -> None:
        hardened_sql = HARDENING_MIGRATION.read_text(encoding="utf-8")
        baseline_body = hardened_sql.split("as $function$", 1)[1].split("$function$", 1)[0]
        updated_body = baseline_body
        fragments: list[tuple[str, str]] = []

        for fragment_name in (
            "service_sets",
            "declaration",
            "monitor_transition",
            "checkpoint_rows",
        ):
            old_match = re.search(
                rf"old_{fragment_name} constant text := \$old\$(.*?)\$old\$;",
                self.sql,
                flags=re.DOTALL,
            )
            new_match = re.search(
                rf"new_{fragment_name} constant text := \$new\$(.*?)\$new\$;",
                self.sql,
                flags=re.DOTALL,
            )
            self.assertIsNotNone(old_match)
            self.assertIsNotNone(new_match)
            assert old_match is not None
            assert new_match is not None
            old_fragment = old_match.group(1)
            new_fragment = new_match.group(1)
            self.assertEqual(updated_body.count(old_fragment), 1, fragment_name)
            updated_body = updated_body.replace(old_fragment, new_fragment)
            fragments.append((old_fragment, new_fragment))

        for old_fragment, new_fragment in fragments:
            self.assertNotIn(old_fragment, updated_body)
            self.assertEqual(updated_body.count(new_fragment), 1)

    def test_reissued_private_rpc_preserves_exact_owner_and_acl(self) -> None:
        self.assertIn(
            "alter function ingest.get_runtime_release_evidence_v1(timestamptz, integer, integer, text)\n  owner to postgres;",
            self.sql,
        )
        self.assertIn(
            "revoke all on function ingest.get_runtime_release_evidence_v1(timestamptz, integer, integer, text)\n  from public, anon, authenticated, service_role;",
            self.sql,
        )
        self.assertRegex(
            self.sql,
            r"grant execute on function ingest\.get_runtime_release_evidence_v1\(timestamptz, integer, integer, text\)\s+to pokecrack_runtime_monitor",
        )


class RuntimeReleaseEvidenceAclNormalizationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = ACL_NORMALIZATION_MIGRATION.read_text(encoding="utf-8")

    def test_forward_patch_normalizes_null_catalog_acls_without_relaxing_header(self) -> None:
        self.assertEqual(self.sql.lower().count("begin;"), 1)
        self.assertEqual(self.sql.lower().count("commit;"), 1)
        self.assertIn("pg_get_functiondef(", self.sql)
        self.assertIn("functions.prosecdef", self.sql)
        self.assertIn("functions.provolatile = 's'", self.sql)
        self.assertIn("functions.proparallel = 'r'", self.sql)
        self.assertIn(
            "array['search_path=pg_catalog, pg_temp']::text[]",
            self.sql,
        )
        self.assertEqual(self.sql.count("'{}'::aclitem[]"), 3)
        for expected in (
            "acldefault('n', namespaces.nspowner)",
            "acldefault('r', relations.relowner)",
            "acldefault('f', procedures.proowner)",
            "runtime release evidence ACL normalization did not match exactly",
        ):
            self.assertIn(expected, self.sql)

    def test_forward_patch_replaces_each_acl_fragment_twice(self) -> None:
        hardened_sql = HARDENING_MIGRATION.read_text(encoding="utf-8")
        updated_body = hardened_sql.split("as $function$", 1)[1].split("$function$", 1)[0]
        bluesky_sql = BLUESKY_RUNTIME_MIGRATION.read_text(encoding="utf-8")

        for fragment_name in (
            "service_sets",
            "declaration",
            "monitor_transition",
            "checkpoint_rows",
        ):
            old_match = re.search(
                rf"old_{fragment_name} constant text := \$old\$(.*?)\$old\$;",
                bluesky_sql,
                flags=re.DOTALL,
            )
            new_match = re.search(
                rf"new_{fragment_name} constant text := \$new\$(.*?)\$new\$;",
                bluesky_sql,
                flags=re.DOTALL,
            )
            self.assertIsNotNone(old_match)
            self.assertIsNotNone(new_match)
            assert old_match is not None
            assert new_match is not None
            updated_body = updated_body.replace(old_match.group(1), new_match.group(1))

        for fragment_name in ("namespace_acl", "relation_acl", "procedure_acl"):
            old_match = re.search(
                rf"old_{fragment_name} constant text := \$old\$(.*?)\$old\$;",
                self.sql,
                flags=re.DOTALL,
            )
            new_match = re.search(
                rf"new_{fragment_name} constant text := \$new\$(.*?)\$new\$;",
                self.sql,
                flags=re.DOTALL,
            )
            self.assertIsNotNone(old_match)
            self.assertIsNotNone(new_match)
            assert old_match is not None
            assert new_match is not None
            old_fragment = old_match.group(1)
            new_fragment = new_match.group(1)
            self.assertEqual(updated_body.count(old_fragment), 2, fragment_name)
            self.assertNotIn(new_fragment, updated_body)
            updated_body = updated_body.replace(old_fragment, new_fragment)
            self.assertNotIn(old_fragment, updated_body)
            self.assertEqual(updated_body.count(new_fragment), 2, fragment_name)


class RuntimeReleaseEvidenceIntegrationContractTests(unittest.TestCase):
    def test_cli_and_settings_use_the_dedicated_monitor_path(self) -> None:
        cli = (PYTHON_ROOT / "cli.py").read_text(encoding="utf-8")
        settings = (PYTHON_ROOT / "config" / "settings.py").read_text(encoding="utf-8")
        composition = (PYTHON_ROOT / "composition.py").read_text(encoding="utf-8")
        self.assertIn('@app.command("verify-release")', cli)
        self.assertIn('inconclusive_result("live_mode_required")', cli)
        self.assertIn('raise typer.Exit(code=2)', cli)
        self.assertIn("runtime_release_evidence_db_url", settings)
        self.assertIn("runtime_release_evidence_executor", composition)
        self.assertIn("_RUNTIME_EVIDENCE_DATABASE_ROLE", composition)
        self.assertIn("_RUNTIME_EVIDENCE_DATABASE_LOGIN", composition)
        self.assertIn("connect_timeout_seconds=", composition)
        self.assertIn("statement_timeout_seconds=", composition)
        self.assertIn('service_set: str = typer.Option(', cli)
        self.assertIn('require_healthy: bool = typer.Option(', cli)
        self.assertIn('require_healthy=require_healthy', cli)
        self.assertIn("bound_release_started_at", cli)
        evidence = (PYTHON_ROOT / "release_evidence.py").read_text(encoding="utf-8")
        self.assertIn("object_pairs_hook=_reject_duplicate_pairs", evidence)
        self.assertIn("parse_constant=_reject_json_constant", evidence)
        self.assertIn("%(service_set)s", evidence)
        self.assertIn('"tcgdex-bluesky"', evidence)

    def test_watchdog_only_receives_the_monitor_url_and_wrapper_is_read_only(self) -> None:
        compose = (REPOSITORY_ROOT / "deploy" / "compose.prod.yml").read_text(encoding="utf-8")
        wrapper = (REPOSITORY_ROOT / "deploy" / "scripts" / "verify-runtime-release.sh").read_text(
            encoding="utf-8"
        )
        worker_environment = compose.split("x-worker-environment:", 1)[1].split("x-service-logging:", 1)[0]
        self.assertNotIn("RUNTIME_RELEASE_EVIDENCE_DB_URL", worker_environment)
        watchdog = compose.split("watchdog:", 1)[1]
        self.assertIn("RUNTIME_RELEASE_EVIDENCE_DB_URL", watchdog)
        self.assertIn("exec -T watchdog pokecrack-worker verify-release", wrapper)
        self.assertIn("--release-started-at", wrapper)
        self.assertIn("--service-set", wrapper)
        self.assertIn("org.opencontainers.image.revision", wrapper)
        self.assertIn("timeout --foreground --kill-after=5", wrapper)
        self.assertIn("--bluesky-env-file", wrapper)
        self.assertIn("--require-healthy", wrapper)
        self.assertIn(
            "SERVICES=(collector scheduler watchdog bluesky-collector)", wrapper
        )
        self.assertIn("Bluesky environment file must have exact mode 0600", wrapper)
        self.assertNotIn("migrate-database", wrapper)
        self.assertNotIn("docker compose up", wrapper)

        deploy = (REPOSITORY_ROOT / "deploy" / "scripts" / "deploy.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("VERIFY_RUNTIME=true", deploy)
        self.assertIn(
            'runtime_verify_args+=(--bluesky-env-file "$BLUESKY_ENV_FILE" --require-healthy)', deploy
        )

    def test_type_and_docs_name_the_new_contract(self) -> None:
        database_types = (REPOSITORY_ROOT / "supabase" / "types" / "database.ts").read_text(
            encoding="utf-8"
        )
        self.assertIn("get_runtime_release_evidence_v1", database_types)
        for path in (
            REPOSITORY_ROOT / "deploy" / "README.md",
            REPOSITORY_ROOT / "docs" / "DEPLOYMENT.md",
            REPOSITORY_ROOT / "docs" / "OPERATIONS.md",
            REPOSITORY_ROOT / "docs" / "BACKUP_AND_RESTORE.md",
        ):
            self.assertIn("verify-runtime-release", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
