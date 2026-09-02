"""Redacted runtime release evidence and backup-marker verification.

The database function is the only source of release evidence.  This module
validates its small public shape before printing it so a schema drift or an
accidentally widened RPC cannot turn a deployment check into a data export.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pokecrack_worker.jobs import QueryExecutor

RUNTIME_RELEASE_EVIDENCE_SQL = """
SELECT ingest.get_runtime_release_evidence_v1(
    %(release_started_at)s::timestamptz,
    %(grace_seconds)s,
    %(heartbeat_stale_seconds)s
) AS evidence
""".strip()

RUNTIME_EVIDENCE_SCHEMA_VERSION = "1.0.0"
RUNTIME_EVIDENCE_SUCCESS_STATUSES = frozenset({"healthy", "warming_up"})
RUNTIME_EVIDENCE_STATUSES = frozenset({"healthy", "warming_up", "failed"})

# These names are rejected even if a future function version otherwise appears
# to have a valid shape. The verifier must never become a raw-data side channel.
_FORBIDDEN_KEYS = frozenset(
    {
        "payload",
        "payloads",
        "url",
        "urls",
        "source_text",
        "raw_text",
        "raw",
        "cursor",
        "cursor_value",
        "last_status_id",
        "relay_key",
        "instance_key",
        "endpoint",
        "policy_id",
        "gate_id",
        "worker_id",
        "job_id",
        "current_job_id",
        "credential",
        "credentials",
        "identity",
        "username",
        "password",
        "secret",
        "token",
    }
)

_ROOT_KEYS = frozenset(
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
    }
)
_NESTED_KEYS = {
    "workers": frozenset(
        {
            "expected_count",
            "observed_count",
            "healthy_count",
            "stale_count",
            "missing_count",
            "future_count",
            "max_age_seconds",
            "status",
        }
    ),
    "sources": frozenset(
        {
            "configured_count",
            "enabled_count",
            "disabled_count",
            "fresh_count",
            "stale_count",
            "never_succeeded_count",
            "future_count",
            "advanced_since_release_count",
            "status",
        }
    ),
    "schedule": frozenset(
        {
            "slot_count",
            "slots_with_job_count",
            "orphan_slot_count",
            "latest_slot_age_seconds",
            "latest_job_age_seconds",
            "latest_job_status",
            "status",
        }
    ),
    "queue": frozenset(
        {
            "live_job_count",
            "pending_count",
            "running_count",
            "completed_count",
            "failed_count",
            "dead_count",
            "cancelled_count",
            "future_created_count",
            "pending_age_bands",
            "status",
        }
    ),
    "pending_age_bands": frozenset({"under_5m", "5m_to_1h", "1h_to_6h", "over_6h"}),
    "checkpoints": frozenset(
        {
            "expected_count",
            "observed_count",
            "fresh_count",
            "stale_count",
            "never_collected_count",
            "future_count",
            "status",
        }
    ),
    "cleanup": frozenset(
        {
            "scheduled_count",
            "completed_count",
            "latest_status",
            "latest_age_seconds",
            "status",
        }
    ),
}

_MARKER_FILENAME = re.compile(r"^pokecrack-[0-9]{8}T[0-9]{6}Z\.sql\.gz$")
_MARKER_TIMESTAMP = re.compile(r"^completed_at=([0-9]{8}T[0-9]{6}Z)$")
_MARKER_MAX_AGE_SECONDS = 172800


class RuntimeEvidenceUnavailable(RuntimeError):
    """Raised when the private RPC is absent, inaccessible, or out of contract."""


def parse_release_started_at(value: str | None) -> datetime | None:
    """Parse a strict ISO-8601 release start without echoing user input."""

    if value is None or not value.strip():
        return None
    candidate = value.strip()
    if len(candidate) > 64:
        raise ValueError("release timestamp is too long")
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("release timestamp is invalid") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("release timestamp must include a timezone")
    return parsed.astimezone(UTC)


def _assert_safe_json(value: object, *, parent: str = "root") -> None:
    if isinstance(value, Mapping):
        allowed = _ROOT_KEYS if parent == "root" else _NESTED_KEYS.get(parent)
        if allowed is None:
            raise RuntimeEvidenceUnavailable("runtime evidence shape is unsupported")
        for key, nested in value.items():
            if not isinstance(key, str):
                raise RuntimeEvidenceUnavailable("runtime evidence shape is unsupported")
            if key.casefold() in _FORBIDDEN_KEYS:
                raise RuntimeEvidenceUnavailable("runtime evidence contains restricted data")
            if key not in allowed:
                raise RuntimeEvidenceUnavailable("runtime evidence schema is newer than this verifier")
            _assert_safe_json(nested, parent=key)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _assert_safe_json(item, parent=parent)
        return
    if value is None or isinstance(value, (bool, int, float, str)):
        return
    raise RuntimeEvidenceUnavailable("runtime evidence contains an unsupported value")


def _as_mapping(value: object) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError) as error:
            raise RuntimeEvidenceUnavailable("runtime evidence is not valid JSON") from error
    if not isinstance(value, Mapping):
        raise RuntimeEvidenceUnavailable("runtime evidence is not an object")
    payload = dict(value)
    _assert_safe_json(payload)
    return payload


def validate_runtime_evidence(value: object) -> dict[str, Any]:
    """Validate the exact aggregate-only RPC contract and return a safe object."""

    payload = _as_mapping(value)
    if payload.get("schema_version") != RUNTIME_EVIDENCE_SCHEMA_VERSION:
        raise RuntimeEvidenceUnavailable("runtime evidence schema is unavailable")
    if payload.get("status") not in RUNTIME_EVIDENCE_STATUSES:
        raise RuntimeEvidenceUnavailable("runtime evidence status is unsupported")
    for section in ("workers", "sources", "schedule", "queue", "checkpoints", "cleanup"):
        if not isinstance(payload.get(section), Mapping):
            raise RuntimeEvidenceUnavailable("runtime evidence section is unavailable")
    queue = payload["queue"]
    if not isinstance(queue.get("pending_age_bands"), Mapping):
        raise RuntimeEvidenceUnavailable("runtime evidence queue bands are unavailable")
    return payload


def query_runtime_release_evidence(
    executor: QueryExecutor,
    *,
    release_started_at: datetime | None,
    grace_seconds: int,
    heartbeat_stale_seconds: int,
) -> dict[str, Any]:
    """Call the private RPC and fail closed on missing/old/widened schemas."""

    rows: Sequence[Mapping[str, Any]]
    try:
        rows = executor.query(
            RUNTIME_RELEASE_EVIDENCE_SQL,
            {
                "release_started_at": release_started_at,
                "grace_seconds": grace_seconds,
                "heartbeat_stale_seconds": heartbeat_stale_seconds,
            },
        )
    except Exception as error:
        raise RuntimeEvidenceUnavailable("runtime evidence query failed") from error
    if len(rows) != 1 or "evidence" not in rows[0]:
        raise RuntimeEvidenceUnavailable("runtime evidence query returned no result")
    return validate_runtime_evidence(rows[0]["evidence"])


def _marker_result(status: str, *, age_seconds: int | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"status": status}
    if age_seconds is not None:
        result["age_seconds"] = max(0, age_seconds)
    return result


def read_backup_marker(
    path: Path | None,
    *,
    now: datetime | None = None,
    max_age_seconds: int = _MARKER_MAX_AGE_SECONDS,
) -> dict[str, Any]:
    """Read only the timestamp in the host backup marker, never its filename."""

    if path is None:
        return _marker_result("unsupported")
    now = now or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("marker comparison time must include a timezone")
    if max_age_seconds < 0 or max_age_seconds > 2_592_000:
        raise ValueError("backup marker age bound is invalid")
    try:
        if path.is_symlink():
            return _marker_result("invalid")
        if not path.exists():
            return _marker_result("missing")
        if not path.is_file():
            return _marker_result("invalid")
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return _marker_result("inconclusive")
    if len(lines) != 2 or _MARKER_FILENAME.fullmatch(lines[0]) is None:
        return _marker_result("invalid")
    match = _MARKER_TIMESTAMP.fullmatch(lines[1])
    if match is None:
        return _marker_result("invalid")
    try:
        completed_at = datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    except ValueError:
        return _marker_result("invalid")
    age_seconds = int((now.astimezone(UTC) - completed_at).total_seconds())
    if age_seconds < 0:
        return _marker_result("invalid")
    if age_seconds > max_age_seconds:
        return _marker_result("stale", age_seconds=age_seconds)
    return _marker_result("fresh", age_seconds=age_seconds)


def with_backup_marker(
    evidence: Mapping[str, Any],
    marker: Mapping[str, Any],
) -> dict[str, Any]:
    """Attach safe marker age and apply conservative release exit semantics."""

    result = dict(evidence)
    marker_result = dict(marker)
    if set(marker_result) - {"status", "age_seconds"}:
        raise RuntimeEvidenceUnavailable("backup marker shape is unsupported")
    if marker_result.get("status") not in {
        "fresh",
        "stale",
        "missing",
        "invalid",
        "unsupported",
        "inconclusive",
    }:
        raise RuntimeEvidenceUnavailable("backup marker status is unsupported")
    result["backup_marker"] = marker_result

    current_status = result.get("status")
    release_age = result.get("release_age_seconds")
    grace_seconds = result.get("grace_seconds")
    within_grace = (
        release_age is None
        or not isinstance(release_age, (int, float))
        or not isinstance(grace_seconds, (int, float))
        or release_age <= grace_seconds
    )
    marker_status = marker_result["status"]
    if marker_status == "inconclusive":
        result["status"] = "inconclusive"
        result["reason"] = "backup_marker_unavailable"
    elif marker_status in {"stale", "invalid"} and current_status != "failed":
        result["status"] = "failed"
    elif marker_status == "missing" and current_status not in {"failed", "inconclusive"}:
        result["status"] = "warming_up" if within_grace else "failed"
    return result


def exit_code_for_status(status: str) -> int:
    """Return 0 for healthy/warming, 1 for observed failure, 2 for inconclusive."""

    return {"healthy": 0, "warming_up": 0, "failed": 1, "inconclusive": 2}.get(status, 2)


def inconclusive_result(reason: str = "runtime_evidence_unavailable") -> dict[str, str]:
    """Create a stable redacted failure object for CLI output."""

    allowed_reasons = {
        "runtime_evidence_unavailable",
        "backup_marker_unavailable",
        "live_mode_required",
        "invalid_release_timestamp",
        "invalid_runtime_options",
    }
    return {
        "status": "inconclusive",
        "reason": reason if reason in allowed_reasons else "runtime_evidence_unavailable",
    }
