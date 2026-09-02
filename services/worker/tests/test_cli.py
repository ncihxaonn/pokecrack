from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from pokecrack_worker import cli, composition
from pokecrack_worker.cli import app
from pokecrack_worker.config.settings import DataMode
from pokecrack_worker.runtime import CycleResult, RuntimeStatus, WorkerRunResult
from pokecrack_worker.scheduler import SchedulerResult

runner = CliRunner()


@pytest.mark.parametrize(
    "args",
    [
        ["--help"],
        ["health", "--help"],
        ["verify-release", "--help"],
        ["worker", "--help"],
        ["scheduler", "--help"],
        ["aggregate", "all", "--help"],
        ["collect", "youtube", "--help"],
        ["collect-source", "--help"],
        ["enqueue-url", "--help"],
        ["import-csv", "--help"],
        ["import-jsonl", "--help"],
        ["import-opencli", "--help"],
        ["sync-catalog", "tcgdex", "--help"],
        ["retry-failed", "--help"],
        ["cleanup", "--help"],
        ["show-budget", "--help"],
        ["show-queue", "--help"],
        ["show-storage-usage", "--help"],
    ],
)
def test_every_requested_cli_command_has_help(args: list[str]) -> None:
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert "Usage:" in result.output


def test_health_is_structured_and_uses_fixture_boundaries_by_default() -> None:
    result = runner.invoke(app, ["health"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["data_mode"] == "demo"
    assert payload["ai_provider"] == "fixture"
    assert payload["database"] == "in_memory_fixture"


def test_verify_release_is_inconclusive_in_fixture_mode() -> None:
    result = runner.invoke(app, ["verify-release"])

    assert result.exit_code == 2, result.output
    assert json.loads(result.stdout) == {
        "reason": "live_mode_required",
        "status": "inconclusive",
    }


def test_verify_release_requires_bounded_start_in_live_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        cli,
        "_settings",
        lambda: SimpleNamespace(data_mode=DataMode.LIVE, backup_dir=tmp_path),
    )

    def unexpected_executor(_settings: object) -> object:
        raise AssertionError("release verifier must reject a missing timestamp before querying")

    monkeypatch.setattr(cli.composition, "runtime_release_evidence_executor", unexpected_executor)

    result = runner.invoke(app, ["verify-release"])

    assert result.exit_code == 2, result.output
    assert json.loads(result.stdout) == {
        "reason": "invalid_release_timestamp",
        "status": "inconclusive",
    }


@pytest.mark.parametrize(
    "args",
    [
        ["worker", "--dry-run"],
        ["scheduler", "--dry-run"],
        ["aggregate", "all", "--dry-run"],
        ["collect", "youtube", "--dry-run"],
        ["collect-source", "example.com", "--dry-run"],
        ["enqueue-url", "https://example.com/", "--dry-run"],
        ["import-csv", "--dry-run"],
        ["import-jsonl", "--dry-run"],
        ["import-opencli", "--dry-run"],
        ["sync-catalog", "tcgdex", "--dry-run"],
        ["retry-failed", "--dry-run"],
        ["cleanup", "--dry-run"],
    ],
)
def test_mutating_cli_commands_support_dry_run(args: list[str]) -> None:
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["mutated"] is False


@pytest.mark.parametrize(
    "args",
    [
        ["worker", "--forever"],
        ["scheduler"],
        ["aggregate", "all"],
    ],
)
def test_fixture_only_commands_never_claim_a_real_mutation(args: list[str]) -> None:
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["fixture"] is True
    assert payload["mutated"] is False


def test_policy_denial_returns_nonzero_structured_redacted_error() -> None:
    result = runner.invoke(
        app,
        [
            "enqueue-url",
            "https://unknown.example/item?api_key=do-not-log",
            "--dry-run",
        ],
    )

    assert result.exit_code != 0
    assert "do-not-log" not in result.output
    payload = json.loads(result.stderr)
    assert payload["error"] == "source_policy_denied"
    assert payload["reason"] == "unknown_domain"


def test_import_csv_dry_run_parses_fixture() -> None:
    result = runner.invoke(
        app, ["import-csv", "../../data/examples/openings.example.csv", "--dry-run"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["validated"] > 0


def test_import_jsonl_dry_run_rejects_invalid_payload(tmp_path) -> None:
    invalid = tmp_path / "invalid.jsonl"
    invalid.write_text("not-json\n", encoding="utf-8")
    result = runner.invoke(app, ["import-jsonl", str(invalid), "--dry-run"])
    assert result.exit_code == 2
    assert json.loads(result.output)["error"] == "invalid_import"


def test_enqueue_url_rejects_embedded_credentials_without_leaking_them() -> None:
    result = runner.invoke(
        app, ["enqueue-url", "https://user:password@example-public-store.com/item", "--dry-run"]
    )
    assert result.exit_code == 2
    assert "password" not in result.output
    assert "user" not in result.output


def test_default_import_commands_use_canonical_fixture_names() -> None:
    expected = {
        "import-csv": "openings.example.csv",
        "import-jsonl": "sources.example.jsonl",
        "import-opencli": "opencli.example.json",
    }
    for command, filename in expected.items():
        result = runner.invoke(app, [command, "--dry-run"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["path"].endswith(filename)


@pytest.mark.parametrize(
    "args",
    (
        ["aggregate", "all"],
        ["collect", "youtube"],
        ["collect-source", "sources.pokecrack.invalid"],
        ["enqueue-url", "https://sources.pokecrack.invalid/item"],
        ["import-csv"],
        ["import-jsonl"],
        ["import-opencli"],
        ["sync-catalog", "tcgdex"],
        ["retry-failed"],
        ["cleanup"],
        ["show-budget"],
        ["show-queue"],
        ["show-storage-usage"],
    ),
)
def test_unwired_service_commands_refuse_live_mode(args: list[str]) -> None:
    result = runner.invoke(
        app,
        args,
        env={
            "DATA_MODE": "live",
            "SUPABASE_DB_URL": "postgresql://db.example.com/pokecrack",
            "AI_PROVIDER": "fixture",
        },
    )

    assert result.exit_code != 0
    assert "production database-backed worker role wiring is not implemented" in result.output


def test_live_health_uses_database_heartbeat_and_reports_ready_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)

    def heartbeat(_settings: object) -> composition.HeartbeatResult:
        return composition.HeartbeatResult(
            worker_id="watchdog-1",
            worker_role=composition.WorkerRole.WATCHDOG,
            last_seen_at=now,
        )

    monkeypatch.setattr(cli.composition, "write_health_heartbeat", heartbeat)
    result = runner.invoke(
        app,
        ["health"],
        env={
            "DATA_MODE": "live",
            "SUPABASE_DB_URL": "postgresql://db.example.invalid/pokecrack",
            "WORKER_ID": "watchdog-1",
            "WORKER_ROLE": "watchdog",
            "WORKER_MAX_CONCURRENCY": "1",
            "AI_PROVIDER": "fixture",
        },
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["database"] == "postgres_reachable"
    assert payload["worker_role"] == "watchdog"
    assert payload["heartbeat_at"] == now.isoformat()


def test_live_health_database_failures_are_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(_settings: object) -> None:
        raise RuntimeError("postgresql://user:do-not-log@db.example.invalid/pokecrack")

    monkeypatch.setattr(cli.composition, "write_health_heartbeat", fail)
    result = runner.invoke(
        app,
        ["health"],
        env={
            "DATA_MODE": "live",
            "SUPABASE_DB_URL": "postgresql://user:do-not-log@db.example.invalid/pokecrack",
            "WORKER_ROLE": "watchdog",
            "WORKER_MAX_CONCURRENCY": "1",
            "AI_PROVIDER": "fixture",
        },
    )

    assert result.exit_code == 1
    assert "do-not-log" not in result.output
    assert "Traceback" not in result.output
    assert json.loads(result.output)["error"] == "database_unavailable"


def test_live_worker_dry_run_validates_role_without_building_or_touching_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(_settings: object) -> None:
        raise AssertionError("dry-run built the database runtime")

    monkeypatch.setattr(cli.composition, "build_live_worker_runtime", forbidden)
    result = runner.invoke(
        app,
        ["worker", "--forever", "--dry-run"],
        env={
            "DATA_MODE": "live",
            "SUPABASE_DB_URL": "postgresql://db.example.invalid/pokecrack",
            "WORKER_ROLE": "watchdog",
            "WORKER_MAX_CONCURRENCY": "1",
            "AI_PROVIDER": "fixture",
        },
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["mutated"] is False
    assert payload["once"] is False
    assert payload["registered_job_types"] == [composition.CLEANUP_JOB_TYPE]


@pytest.mark.parametrize(("option", "expected_once"), (("--once", True), ("--forever", False)))
def test_live_worker_passes_once_or_forever_to_the_composed_runtime(
    option: str,
    expected_once: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []

    class Runtime:
        def run(self, *, once: bool) -> WorkerRunResult:
            calls.append(once)
            return WorkerRunResult((CycleResult(status=RuntimeStatus.IDLE),))

    monkeypatch.setattr(cli.composition, "build_live_worker_runtime", lambda _settings: Runtime())
    result = runner.invoke(
        app,
        ["worker", option],
        env={
            "DATA_MODE": "live",
            "SUPABASE_DB_URL": "postgresql://db.example.invalid/pokecrack",
            "WORKER_ROLE": "watchdog",
            "WORKER_MAX_CONCURRENCY": "1",
            "AI_PROVIDER": "fixture",
        },
    )

    assert result.exit_code == 0, result.output
    assert calls == [expected_once]
    assert json.loads(result.stdout)["registered_job_types"] == [composition.CLEANUP_JOB_TYPE]


def test_live_worker_rejects_unknown_or_unimplemented_roles_without_database_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(_settings: object) -> None:
        raise AssertionError("an unsupported role reached the database runtime")

    monkeypatch.setattr(cli.composition, "build_live_worker_runtime", forbidden)
    for role, expected_error in (
        ("unknown", "unsupported_worker_role"),
        ("ai-worker", "worker_role_not_ready"),
        ("aggregator", "worker_role_not_ready"),
    ):
        result = runner.invoke(
            app,
            ["worker", "--once"],
            env={
                "DATA_MODE": "live",
                "SUPABASE_DB_URL": "postgresql://db.example.invalid/pokecrack",
                "WORKER_ROLE": role,
                "WORKER_MAX_CONCURRENCY": "1",
                "AI_PROVIDER": "fixture",
            },
        )

        assert result.exit_code == 78
        assert json.loads(result.output)["error"] == expected_error


def test_live_collector_dry_run_registers_only_tcgdex_sets_without_database_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(_settings: object) -> None:
        raise AssertionError("collector dry-run built the database runtime")

    monkeypatch.setattr(cli.composition, "build_live_worker_runtime", forbidden)
    result = runner.invoke(
        app,
        ["worker", "--forever", "--dry-run"],
        env={
            "DATA_MODE": "live",
            "SUPABASE_DB_URL": "postgresql://db.example.invalid/pokecrack",
            "WORKER_ROLE": "collector",
            "WORKER_MAX_CONCURRENCY": "1",
            "AI_PROVIDER": "fixture",
        },
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["registered_job_types"] == [composition.TCGDEX_SETS_JOB_TYPE]
    assert payload["worker_role"] == "collector"
    assert payload["dry_run"] is True
    assert payload["mutated"] is False


def test_live_scheduler_dry_run_does_not_build_a_database_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(_settings: object) -> None:
        raise AssertionError("dry-run built the database scheduler")

    monkeypatch.setattr(cli.composition, "build_live_scheduler", forbidden)
    result = runner.invoke(
        app,
        ["scheduler", "--dry-run"],
        env={
            "DATA_MODE": "live",
            "SUPABASE_DB_URL": "postgresql://db.example.invalid/pokecrack",
            "WORKER_ROLE": "scheduler",
            "WORKER_MAX_CONCURRENCY": "1",
            "SCHEDULE_CLEANUP": "* * * * *",
            "SCHEDULE_CATALOG_SYNC": "0 0 31 2 *",
            "AI_PROVIDER": "fixture",
        },
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["mutated"] is False
    assert payload["planned"] == 1
    assert payload["registered_job_types"] == [
        composition.TCGDEX_SETS_JOB_TYPE,
        composition.CLEANUP_JOB_TYPE,
    ]
    assert "official_api" not in payload["unwired_schedules"]
    assert "bluesky_collection" not in payload["unwired_schedules"]
    assert "catalog_sync" not in payload["unwired_schedules"]


def test_live_scheduler_runs_the_composed_postgres_scheduler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class LiveScheduler:
        def run_due(self, *, now: datetime, dry_run: bool) -> SchedulerResult:
            assert now.tzinfo is not None
            assert dry_run is False
            return SchedulerResult(("cleanup",), planned=1, created=1, dry_run=False)

    monkeypatch.setattr(
        cli.composition,
        "build_live_scheduler",
        lambda _settings: LiveScheduler(),
    )
    result = runner.invoke(
        app,
        ["scheduler"],
        env={
            "DATA_MODE": "live",
            "SUPABASE_DB_URL": "postgresql://db.example.invalid/pokecrack",
            "WORKER_ROLE": "scheduler",
            "WORKER_MAX_CONCURRENCY": "1",
            "AI_PROVIDER": "fixture",
        },
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["mutated"] is True
    assert payload["enqueue_attempts"] == 1


def test_invalid_live_configuration_returns_redacted_json_without_traceback() -> None:
    result = runner.invoke(
        app,
        ["worker", "--once", "--dry-run"],
        env={
            "DATA_MODE": "live",
            "SUPABASE_DB_URL": "",
            "AI_PROVIDER": "fixture",
        },
    )

    assert result.exit_code == 78
    assert "Traceback" not in result.output
    payload = json.loads(result.output)
    assert payload == {
        "error": "invalid_configuration",
        "message": "validated runtime configuration is unavailable",
    }
