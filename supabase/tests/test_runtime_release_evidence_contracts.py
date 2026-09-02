from __future__ import annotations

import re
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MIGRATION = REPOSITORY_ROOT / "supabase" / "migrations" / "20260923000000_runtime_release_evidence.sql"
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
        self.assertNotIn("migrate-database", wrapper)
        self.assertNotIn("docker compose up", wrapper)

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
