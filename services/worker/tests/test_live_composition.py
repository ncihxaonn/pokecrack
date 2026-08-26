from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from pokecrack_worker.composition import (
    CLEANUP_JOB_TYPE,
    LiveCompositionError,
    build_live_scheduler,
    build_live_worker_runtime,
    live_schedule_entries,
    require_worker_job_types,
    write_health_heartbeat,
)
from pokecrack_worker.config.settings import Settings
from pokecrack_worker.runtime import RuntimeStatus

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)


class RecordingExecutor:
    def __init__(self, responses: Sequence[Sequence[Mapping[str, Any]]] = ()) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, Mapping[str, object]]] = []

    def query(self, sql: str, params: Mapping[str, object]) -> Sequence[Mapping[str, Any]]:
        self.calls.append((sql, dict(params)))
        return self.responses.pop(0) if self.responses else ()


def _settings(role: str | None, **values: object) -> Settings:
    return Settings(
        _env_file=None,
        data_mode="live",
        supabase_db_url="postgresql://db.example.invalid/pokecrack",
        ai_provider="fixture",
        worker_id="worker-1",
        worker_role=role,
        worker_max_concurrency=1,
        **values,
    )


def _job_row(
    *,
    status: str,
    payload: Mapping[str, object] | None = None,
    locked: bool = True,
) -> dict[str, object]:
    return {
        "id": "00000000-0000-0000-0000-000000000001",
        "job_type": CLEANUP_JOB_TYPE,
        "payload": dict(payload or {}),
        "status": status,
        "priority": 10,
        "available_at": NOW,
        "attempts": 1,
        "max_attempts": 5,
        "lease_generation": 1,
        "locked_by": "worker-1" if locked else None,
        "locked_at": NOW if locked else None,
        "lock_expires_at": NOW + timedelta(minutes=5) if locked else None,
        "last_error_code": None,
        "last_error_message": None,
        "completed_at": NOW if status == "completed" else None,
        "dedupe_key": "schedule:cleanup:20260825T120000Z",
        "created_at": NOW,
        "updated_at": NOW,
    }


def test_live_health_probes_postgres_and_upserts_a_role_heartbeat() -> None:
    executor = RecordingExecutor([[{"last_seen_at": NOW}]])

    heartbeat = write_health_heartbeat(_settings("watchdog"), executor=executor)

    assert heartbeat.worker_id == "worker-1"
    assert heartbeat.worker_role.value == "watchdog"
    assert heartbeat.last_seen_at == NOW
    assert len(executor.calls) == 1
    sql, params = executor.calls[0]
    assert "SELECT 1 AS reachable" in sql
    assert "INSERT INTO ingest.worker_heartbeats" in sql
    assert "ON CONFLICT (worker_id) DO UPDATE" in sql
    assert "metadata, is_demo" in sql
    assert "WHERE not heartbeats.is_demo" in sql
    assert params["worker_id"] == "worker-1"
    assert params["worker_type"] == "watchdog"
    assert json.loads(str(params["metadata"])) == {
        "command": "health",
        "data_mode": "live",
        "max_concurrency": 1,
        "role_ready": True,
    }
    assert "postgresql://" not in repr(executor.calls)


def test_live_health_refuses_unready_roles_before_writing_a_heartbeat() -> None:
    executor = RecordingExecutor([[{"last_seen_at": NOW}]])

    with pytest.raises(LiveCompositionError) as raised:
        write_health_heartbeat(_settings("collector"), executor=executor)

    assert raised.value.code == "worker_role_not_ready"
    assert executor.calls == []


@pytest.mark.parametrize("role", (None, "unknown", "collector", "ai-worker", "aggregator"))
def test_live_worker_roles_without_safe_handlers_fail_closed(role: str | None) -> None:
    expected = "worker_role_not_ready" if role in {"collector", "ai-worker", "aggregator"} else None

    with pytest.raises(LiveCompositionError) as raised:
        require_worker_job_types(_settings(role))

    if expected is not None:
        assert raised.value.code == expected
    else:
        assert raised.value.code in {"worker_role_missing", "unsupported_worker_role"}


def test_watchdog_runtime_claims_only_the_cleanup_job_type() -> None:
    executor = RecordingExecutor()
    runtime = build_live_worker_runtime(_settings("watchdog"), executor=executor, clock=lambda: NOW)

    result = runtime.run_once()

    assert result.status is RuntimeStatus.IDLE
    assert len(executor.calls) == 1
    sql, params = executor.calls[0]
    assert "ingest.claim_jobs_v2" in sql
    assert params["kinds"] == [CLEANUP_JOB_TYPE]


def test_live_worker_dry_run_never_touches_the_database() -> None:
    executor = RecordingExecutor()
    runtime = build_live_worker_runtime(_settings("watchdog"), executor=executor, clock=lambda: NOW)

    result = runtime.run(once=False, dry_run=True)

    assert result.results[0].status is RuntimeStatus.DRY_RUN
    assert executor.calls == []


def test_watchdog_cleanup_handler_uses_one_fenced_atomic_finalizer() -> None:
    executor = RecordingExecutor(
        [
            [_job_row(status="running")],
            [_job_row(status="completed", locked=False)],
        ]
    )
    runtime = build_live_worker_runtime(_settings("watchdog"), executor=executor, clock=lambda: NOW)

    result = runtime.run_once()

    assert result.status is RuntimeStatus.COMPLETED
    assert result.job_type == CLEANUP_JOB_TYPE
    assert len(executor.calls) == 2
    assert "ingest.claim_jobs_v2" in executor.calls[0][0]
    finalizer_sql, finalizer_params = executor.calls[1]
    assert "ingest.finalize_cleanup_job" in finalizer_sql
    assert "ingest.prune_expired_ephemera()" not in finalizer_sql
    assert "SET status = 'completed'" not in finalizer_sql
    assert finalizer_params == {
        "job_id": "00000000-0000-0000-0000-000000000001",
        "worker_id": "worker-1",
        "lease_generation": 1,
    }


def test_stale_cleanup_finalizer_returns_lease_lost_without_an_unfenced_effect() -> None:
    executor = RecordingExecutor(
        [
            [_job_row(status="running")],
            [],
        ]
    )
    runtime = build_live_worker_runtime(_settings("watchdog"), executor=executor, clock=lambda: NOW)

    result = runtime.run_once()

    assert result.status is RuntimeStatus.LEASE_LOST
    assert len(executor.calls) == 2
    assert "ingest.finalize_cleanup_job" in executor.calls[1][0]
    assert all("ingest.prune_expired_ephemera()" not in sql for sql, _ in executor.calls)


def test_cleanup_handler_rejects_payloads_instead_of_expanding_its_authority() -> None:
    executor = RecordingExecutor(
        [
            [_job_row(status="running", payload={"cutoff": "tomorrow"})],
            [_job_row(status="pending", payload={"cutoff": "tomorrow"}, locked=False)],
        ]
    )
    runtime = build_live_worker_runtime(_settings("watchdog"), executor=executor, clock=lambda: NOW)

    result = runtime.run_once()

    assert result.status is RuntimeStatus.FAILED
    assert result.error_code == "ValueError"
    assert len(executor.calls) == 2
    assert "ingest.prune_expired_ephemera" not in executor.calls[1][0]
    assert "ingest.finalize_cleanup_job" not in executor.calls[1][0]
    assert "last_error_code" in executor.calls[1][0]


def test_live_scheduler_registers_only_cleanup_and_uses_the_slot_dedupe_key() -> None:
    executor = RecordingExecutor([[_job_row(status="pending", locked=False)]])
    settings = _settings("scheduler", schedule_cleanup="* * * * *")

    result = build_live_scheduler(settings, executor=executor).run_due(now=NOW)

    assert result.due_names == ("cleanup",)
    assert result.created == 1
    assert len(executor.calls) == 1
    sql, params = executor.calls[0]
    assert "INSERT INTO ingest.jobs" in sql
    assert params["kind"] == CLEANUP_JOB_TYPE
    assert params["dedupe_key"] == "schedule:cleanup:20260825T120000Z"


def test_live_scheduler_validates_even_unwired_cron_configuration() -> None:
    settings = _settings("scheduler", schedule_public_collection="not-a-cron")

    with pytest.raises(ValueError, match="five fields"):
        live_schedule_entries(settings)
