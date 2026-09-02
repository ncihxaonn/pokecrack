from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from pokecrack_worker.release_evidence import (
    RuntimeEvidenceUnavailable,
    bound_release_started_at,
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
        "workers": {
            "expected_count": 3,
            "observed_count": 3,
            "healthy_count": 3,
            "stale_count": 0,
            "missing_count": 0,
            "future_count": 0,
            "max_age_seconds": 30,
            "status": "healthy",
        },
        "sources": {
            "configured_count": 2,
            "enabled_count": 1,
            "disabled_count": 1,
            "fresh_count": 1,
            "stale_count": 0,
            "never_succeeded_count": 0,
            "future_count": 0,
            "advanced_since_release_count": 1,
            "status": "healthy",
        },
        "schedule": {
            "slot_count": 1,
            "slots_with_job_count": 1,
            "orphan_slot_count": 0,
            "latest_slot_age_seconds": 60,
            "latest_job_age_seconds": 30,
            "latest_job_status": "completed",
            "status": "advancing",
        },
        "queue": {
            "live_job_count": 1,
            "pending_count": 0,
            "running_count": 0,
            "completed_count": 1,
            "failed_count": 0,
            "dead_count": 0,
            "cancelled_count": 0,
            "future_created_count": 0,
            "pending_age_bands": {
                "under_5m": 0,
                "5m_to_1h": 0,
                "1h_to_6h": 0,
                "over_6h": 0,
            },
            "status": "healthy",
        },
        "checkpoints": {
            "expected_count": 1,
            "observed_count": 1,
            "fresh_count": 1,
            "stale_count": 0,
            "never_collected_count": 0,
            "future_count": 0,
            "status": "healthy",
        },
        "cleanup": {
            "scheduled_count": 1,
            "completed_count": 1,
            "latest_status": "completed",
            "latest_age_seconds": 60,
            "status": "healthy",
        },
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
        release_started_at=datetime.now(UTC) - timedelta(minutes=5),
        grace_seconds=21600,
        heartbeat_stale_seconds=180,
    )

    assert result["schema_version"] == "1.0.0"
    assert "payload" not in json.dumps(result)
    assert "release_started_at" in executor.params
    assert executor.params["service_set"] == "tcgdex"
    assert "get_runtime_release_evidence_v1" in executor.sql


@pytest.mark.parametrize(
    "value", [{"schema_version": "0.9.0"}, {"schema_version": "1.0.0", "status": "unknown"}]
)
def test_old_or_unknown_rpc_shape_is_inconclusive(value: dict[str, object]) -> None:
    with pytest.raises(RuntimeEvidenceUnavailable):
        validate_runtime_evidence(value)


def test_forbidden_rpc_key_is_rejected_even_when_nested() -> None:
    value = evidence()
    value["queue"]["job_id"] = "private"
    with pytest.raises(RuntimeEvidenceUnavailable):
        validate_runtime_evidence(value)


def test_missing_runtime_evidence_field_is_rejected() -> None:
    value = evidence()
    del value["workers"]["max_age_seconds"]

    with pytest.raises(RuntimeEvidenceUnavailable):
        validate_runtime_evidence(value)


def test_parse_release_timestamp_requires_timezone() -> None:
    assert parse_release_started_at("2026-09-03T00:00:00Z") == datetime(2026, 9, 3, tzinfo=UTC)
    with pytest.raises(ValueError):
        parse_release_started_at("2026-09-03T00:00:00")
    with pytest.raises(ValueError):
        parse_release_started_at(123)  # type: ignore[arg-type]


def test_release_timestamp_is_bounded_and_normalized() -> None:
    now = datetime(2026, 9, 3, 3, tzinfo=UTC)
    assert bound_release_started_at(datetime(2026, 9, 3, 2, tzinfo=UTC), now=now) == datetime(
        2026, 9, 3, 2, tzinfo=UTC
    )
    with pytest.raises(ValueError):
        bound_release_started_at(datetime(2026, 8, 1, tzinfo=UTC), now=now)
    with pytest.raises(ValueError):
        bound_release_started_at(datetime(2026, 9, 3, 3, 6, tzinfo=UTC), now=now)


def test_query_rejects_unknown_service_set_without_querying() -> None:
    executor = FakeExecutor(json.dumps(evidence()))
    with pytest.raises(RuntimeEvidenceUnavailable):
        query_runtime_release_evidence(
            executor,
            release_started_at=datetime(2026, 9, 3, tzinfo=UTC),
            grace_seconds=21600,
            heartbeat_stale_seconds=180,
            service_set="tcgdex-nostr-extra",
        )
    assert executor.sql == ""


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


def test_backup_marker_with_invalid_encoding_is_malformed(tmp_path: Path) -> None:
    marker = tmp_path / ".last-successful-backup"
    marker.write_bytes(b"\xff\ncompleted_at=20260903T020000Z\n")
    assert read_backup_marker(marker)["status"] == "invalid"


def test_backup_marker_changes_release_status_conservatively() -> None:
    assert (
        with_backup_marker(evidence(), {"status": "fresh", "age_seconds": 60})["status"]
        == "healthy"
    )
    assert with_backup_marker(evidence(), {"status": "missing"})["status"] == "inconclusive"
    old = evidence()
    old["release_age_seconds"] = 21601
    assert with_backup_marker(old, {"status": "missing"})["status"] == "inconclusive"
    assert with_backup_marker(evidence(), {"status": "unsupported"})["status"] == "inconclusive"
    assert with_backup_marker(evidence(), {"status": "inconclusive"})["status"] == "inconclusive"


@pytest.mark.parametrize(
    ("path", "replacement"),
    (
        (("status",), True),
        (("grace_seconds",), "21600"),
        (("workers", "expected_count"), False),
        (("queue", "pending_age_bands", "under_5m"), 1.0),
        (("release_age_seconds",), "120"),
        (("workers", "status"), "secret-like-value"),
    ),
)
def test_rpc_rejects_unsafe_scalar_types_and_values(
    path: tuple[str, ...], replacement: object
) -> None:
    value = evidence()
    target: dict[str, Any] = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement
    with pytest.raises(RuntimeEvidenceUnavailable):
        validate_runtime_evidence(value)


def test_rpc_rejects_duplicate_keys_and_nonfinite_json() -> None:
    raw = json.dumps(evidence(), separators=(",", ":"))
    duplicate = raw.replace(
        '"schema_version":"1.0.0"',
        '"schema_version":"1.0.0","schema_version":"1.0.0"',
        1,
    )
    with pytest.raises(RuntimeEvidenceUnavailable):
        validate_runtime_evidence(duplicate)
    nonfinite = raw.replace('"release_age_seconds":120', '"release_age_seconds":NaN', 1)
    with pytest.raises(RuntimeEvidenceUnavailable):
        validate_runtime_evidence(nonfinite)


@pytest.mark.parametrize(
    ("status", "expected"),
    (("healthy", 0), ("warming_up", 0), ("failed", 1), ("inconclusive", 2), ("other", 2)),
)
def test_exit_codes_are_stable(status: str, expected: int) -> None:
    assert exit_code_for_status(status) == expected
