from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from pokecrack_worker.cli import app

runner = CliRunner()


@pytest.mark.parametrize(
    "args",
    [
        ["--help"],
        ["health", "--help"],
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
        ["worker", "--forever"],
        ["scheduler"],
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
def test_fixture_only_service_commands_refuse_live_mode(args: list[str]) -> None:
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
