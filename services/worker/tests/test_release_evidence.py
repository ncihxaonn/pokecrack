from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pokecrack_worker.release_evidence import (
    RuntimeEvidenceUnavailable,
    exit_code_for_status,
    parse_release_started_at,
    query_runtime_release_evidence,
    read_backup_marker,
    validate_runtime_evidence,
    with_backup_marker,
)


def evidence(status: str = "healthy") -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "status": status,
        "release_age_seconds": 120,
        "grace_seconds": 21600,
        "workers": {"status": "healthy"},
        "sources": {"status": "healthy"},
        "schedule": {"status": "advancing"},
        "queue": {"status": "healthy", "pending_age_bands": {}},
        "checkpoints": {"status": "healthy"},
        "cleanup": {"status": "healthy"},
    }


class FakeExecutor:
    def __init__(self, value: object) -> None:
        self.value = value
        self.sql = ""
        self.params: dict[str, object] = {}

    def query(self, sql: str, params: dict[str, object]) -> tuple[dict[str, object], ...]:
        self.sql = sql
        self.params = params
        return ({"evidence": self.value},)


def test_query_validates_schema_and_does_not_widen_output() -> None:
    executor = FakeExecutor(json.dumps(evidence()))
    result = query_runtime_release_evidence(
        executor,
        release_started_at=datetime(2026, 9, 3, tzinfo=UTC),
        grace_seconds=21600,
        heartbeat_stale_seconds=180,
    )

    assert result["schema_version"] == "1.0.0"
    assert "payload" not in json.dumps(result)
    assert "release_started_at" in executor.params
    assert "get_runtime_release_evidence_v1" in executor.sql


@pytest.mark.parametrize("value", [{"schema_version": "0.9.0"}, {"schema_version": "1.0.0", "status": "unknown"}])
def test_old_or_unknown_rpc_shape_is_inconclusive(value: dict[str, object]) -> None:
    with pytest.raises(RuntimeEvidenceUnavailable):
        validate_runtime_evidence(value)


def test_forbidden_rpc_key_is_rejected_even_when_nested() -> None:
    value = evidence()
    value["queue"]["job_id"] = "private"
    with pytest.raises(RuntimeEvidenceUnavailable):
        validate_runtime_evidence(value)


def test_parse_release_timestamp_requires_timezone() -> None:
    assert parse_release_started_at("2026-09-03T00:00:00Z") == datetime(
        2026, 9, 3, tzinfo=UTC
    )
    with pytest.raises(ValueError):
        parse_release_started_at("2026-09-03T00:00:00")


def test_backup_marker_reports_only_safe_age_and_status(tmp_path: Path) -> None:
    marker = tmp_path / ".last-successful-backup"
    marker.write_text(
        "pokecrack-20260903T020000Z.sql.gz\ncompleted_at=20260903T020000Z\n",
        encoding="utf-8",
    )
    result = read_backup_marker(marker, now=datetime(2026, 9, 3, 3, tzinfo=UTC))
    assert result == {"status": "fresh", "age_seconds": 3600}
    assert "pokecrack-" not in json.dumps(result)


def test_backup_marker_stale_missing_and_unsupported_are_explicit(tmp_path: Path) -> None:
    marker = tmp_path / ".last-successful-backup"
    marker.write_text(
        "pokecrack-20260901T020000Z.sql.gz\ncompleted_at=20260901T020000Z\n",
        encoding="utf-8",
    )
    assert read_backup_marker(marker, now=datetime(2026, 9, 3, 3, tzinfo=UTC))["status"] == "stale"
    assert read_backup_marker(tmp_path / "missing", now=datetime.now(UTC))["status"] == "missing"
    assert read_backup_marker(None) == {"status": "unsupported"}


def test_backup_marker_changes_release_status_conservatively() -> None:
    assert with_backup_marker(evidence(), {"status": "fresh"})["status"] == "healthy"
    assert with_backup_marker(evidence(), {"status": "missing"})["status"] == "warming_up"
    old = evidence()
    old["release_age_seconds"] = 21601
    assert with_backup_marker(old, {"status": "missing"})["status"] == "failed"
    assert with_backup_marker(evidence(), {"status": "inconclusive"})["status"] == "inconclusive"


@pytest.mark.parametrize(
    ("status", "expected"),
    (("healthy", 0), ("warming_up", 0), ("failed", 1), ("inconclusive", 2), ("other", 2)),
)
def test_exit_codes_are_stable(status: str, expected: int) -> None:
    assert exit_code_for_status(status) == expected
