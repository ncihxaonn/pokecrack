from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from pokecrack_worker import cli
from pokecrack_worker.config.settings import DataMode
from pokecrack_worker.research_intake import (
    IMPORT_SQL,
    MAX_BYTES,
    SCHEMA_VERSION,
    import_manifest,
    reference_url,
    validate_manifest,
)


def manifest() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "snapshot_sha256": "a" * 64,
        "references": [
            {
                "url": "https://example.com/study",
                "report_group_sha256": "b" * 64,
                "conflicting": False,
            }
        ],
    }


def encoded(value: object) -> bytes:
    return json.dumps(value).encode()


def outcome(**changes: object) -> dict:
    return {
        "status": "accepted",
        "snapshot_sha256": "a" * 64,
        "references_received": 1,
        "references_inserted": 1,
        "reference_count": 1,
        "conflicting_count": 0,
        "family_queued": 0,
        **changes,
    }


def test_intake_accepts_only_private_references_and_uses_one_parameterized_query() -> None:
    executor = Mock()
    executor.query.return_value = ({"result": outcome()},)
    assert import_manifest(executor, encoded(manifest())) == outcome()
    executor.query.assert_called_once_with(
        IMPORT_SQL, {"manifest": json.dumps(manifest(), sort_keys=True)}
    )
    assert "http" not in IMPORT_SQL and "public." not in IMPORT_SQL


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        {},
        {**manifest(), "packs": 30},
        {**manifest(), "schema_version": None},
        {**manifest(), "schema_version": "self-approved"},
        {**manifest(), "snapshot_sha256": "A" * 64},
        {**manifest(), "references": None},
        {**manifest(), "references": [manifest()["references"][0]] * 10001},
    ],
)
def test_invalid_manifest_never_queries(value: object) -> None:
    executor = Mock()
    with pytest.raises(ValueError):
        import_manifest(executor, encoded(value))
    executor.query.assert_not_called()


@pytest.mark.parametrize(
    "update",
    [
        {"packs": 1000},
        {"country": "JP"},
        {"approved": True},
        {"html": "private body"},
        {"conflicting": 0},
        {"conflicting": None},
        {"report_group_sha256": None},
        {"url": "http://example.com/study"},
        {"url": "https://127.0.0.1/study"},
        {"url": "https://user:secret@example.com/study"},
        {"url": "https://example.com/study?secret=value"},
        {"url": "https://example.com/study#fragment"},
        {"url": "https://example.local/study"},
        {"url": "https://example.com:443/study"},
        {"url": "https://example.com:bad/study"},
        {"url": "https://EXAMPLE.com/study"},
        {"url": "https://example.com/study/"},
        {"url": "https://example.com/a\nb"},
        {"url": "https://example.com/`x`"},
        {"url": "https://example.com/<x>"},
        {"url": "https://example.com/a\\b"},
    ],
)
def test_reference_cannot_carry_claims_or_unsafe_identity(update: dict) -> None:
    value = manifest()
    value["references"][0].update(update)
    with pytest.raises(ValueError):
        validate_manifest(encoded(value))


def test_empty_manifest_and_non_latin_paths_are_reference_only() -> None:
    empty = {**manifest(), "references": []}
    assert validate_manifest(encoded(empty)) == empty
    value = manifest()
    value["references"][0]["url"] = "https://example.com/開封"
    assert validate_manifest(encoded(value)) == value
    assert reference_url("https://EXAMPLE.com/開封/") == "https://example.com/開封"


def test_duplicate_order_and_size_boundaries() -> None:
    value = manifest()
    value["references"] *= 2
    with pytest.raises(ValueError, match="duplicate"):
        validate_manifest(encoded(value))
    value["references"] = [
        {**manifest()["references"][0], "url": "https://example.com/z"},
        manifest()["references"][0],
    ]
    with pytest.raises(ValueError, match="unsorted"):
        validate_manifest(encoded(value))
    with pytest.raises(ValueError, match="too_large"):
        validate_manifest(b" " * (MAX_BYTES + 1))


@pytest.mark.parametrize(
    "result",
    [
        None,
        {**outcome(), "url": "https://example.com/private"},
        outcome(status="approved"),
        outcome(snapshot_sha256="c" * 64),
        outcome(references_received=2),
        outcome(references_inserted=2),
        outcome(reference_count=0),
        outcome(conflicting_count=2),
        outcome(family_queued=2),
        outcome(references_inserted=True),
        outcome(status="paused"),
        outcome(reference_count=10001),
    ],
)
def test_unexpected_database_result_is_not_exposed(result: object) -> None:
    executor = Mock()
    executor.query.return_value = ({"result": result},)
    with pytest.raises(ValueError, match="invalid_intake_result"):
        import_manifest(executor, encoded(manifest()))


def test_paused_result_does_not_claim_mutation() -> None:
    executor = Mock()
    executor.query.return_value = ({"result": outcome(status="paused", references_inserted=0)},)
    assert import_manifest(executor, encoded(manifest()))["status"] == "paused"


def test_cli_dry_run_has_no_settings_or_database_access(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Mock(side_effect=AssertionError("not needed"))
    monkeypatch.setattr(cli, "_settings", settings)
    result = CliRunner().invoke(
        cli.app, ["intake-research", "--dry-run"], input=encoded(manifest())
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"dry_run": True, "mutated": False, "references": 1}
    settings.assert_not_called()


@pytest.mark.parametrize(
    "mode,role",
    [
        (DataMode.DEMO, "collector"),
        (DataMode.LIVE, "scheduler"),
        (DataMode.LIVE, None),
        (DataMode.LIVE, "nostr-collector"),
    ],
)
def test_cli_rejects_non_live_collector(
    monkeypatch: pytest.MonkeyPatch, mode: DataMode, role: str | None
) -> None:
    monkeypatch.setattr(cli, "_settings", lambda: SimpleNamespace(data_mode=mode, worker_role=role))
    executor = Mock(side_effect=AssertionError("must not query"))
    monkeypatch.setattr(cli.composition, "executor_from_settings", executor)
    result = CliRunner().invoke(cli.app, ["intake-research"], input=encoded(manifest()))
    assert result.exit_code == 2
    assert json.loads(result.stdout)["reason"] == "live_collector_required"
    executor.assert_not_called()


def test_cli_redacts_database_failure_and_handles_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli, "_settings", lambda: SimpleNamespace(data_mode=DataMode.LIVE, worker_role="collector")
    )
    executor = Mock()
    monkeypatch.setattr(cli.composition, "executor_from_settings", lambda _: executor)
    executor.query.side_effect = RuntimeError("postgres://secret/private body")
    result = CliRunner().invoke(cli.app, ["intake-research"], input=encoded(manifest()))
    assert result.exit_code == 2
    assert "secret" not in result.output and "private body" not in result.output
    executor.query.side_effect = None
    executor.query.return_value = ({"result": outcome()},)
    result = CliRunner().invoke(cli.app, ["intake-research"], input=encoded(manifest()))
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == outcome()
