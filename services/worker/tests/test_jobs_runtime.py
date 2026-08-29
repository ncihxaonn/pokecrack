from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from pokecrack_worker.db import PsycopgQueryExecutor
from pokecrack_worker.deduplication.fingerprints import content_sha256
from pokecrack_worker.jobs import (
    CompletionEffect,
    InMemoryJobRepository,
    JobStatus,
    LeaseLostError,
    PostgresJobRepository,
    PublicStudyCompletion,
    TCGdexSetsSyncCompletion,
    TCGdexSetWrite,
    TCGdexSyncOutcome,
    YouTubeDiscoveryCompletion,
    YouTubeSourceItemWrite,
)

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)


def test_lease_claims_one_due_job_by_priority_without_double_claim() -> None:
    repository = InMemoryJobRepository()
    low = repository.enqueue("collect.url", {"url": "https://example.com/low"}, priority=1, now=NOW)
    high = repository.enqueue(
        "collect.url", {"url": "https://example.com/high"}, priority=10, now=NOW
    )

    claimed = repository.lease("worker-a", now=NOW, lease_for=timedelta(minutes=5))
    second = repository.lease("worker-b", now=NOW, lease_for=timedelta(minutes=5))

    assert claimed is not None
    assert claimed.id == high.id
    assert claimed.status is JobStatus.RUNNING
    assert claimed.attempts == 1
    assert claimed.lease_generation == 1
    assert second is not None
    assert second.id == low.id
    assert second.id != claimed.id


def test_in_memory_repository_reclaims_an_expired_lease_for_the_next_attempt() -> None:
    repository = InMemoryJobRepository()
    queued = repository.enqueue("extract", {}, max_attempts=2, now=NOW)
    first = repository.lease("worker-a", now=NOW, lease_for=timedelta(seconds=1))
    assert first is not None

    reclaimed = repository.lease(
        "worker-b",
        now=NOW + timedelta(seconds=2),
        lease_for=timedelta(seconds=1),
    )

    assert reclaimed is not None
    assert reclaimed.id == queued.id
    assert reclaimed.leased_by == "worker-b"
    assert reclaimed.attempts == 2
    assert reclaimed.lease_generation == 2


def test_reclaim_rotates_generation_when_worker_id_is_reused() -> None:
    repository = InMemoryJobRepository()
    queued = repository.enqueue("extract", {}, now=NOW)
    first = repository.lease("worker-a", now=NOW, lease_for=timedelta(seconds=1))
    assert first is not None

    reclaimed = repository.lease(
        "worker-a",
        now=NOW + timedelta(seconds=2),
        lease_for=timedelta(minutes=1),
    )
    assert reclaimed is not None
    assert reclaimed.id == queued.id
    assert reclaimed.lease_generation == first.lease_generation + 1

    stale_mutations = (
        lambda: repository.heartbeat(
            first.id,
            worker_id="worker-a",
            lease_generation=first.lease_generation,
            now=NOW + timedelta(seconds=2),
            lease_for=timedelta(minutes=1),
        ),
        lambda: repository.complete(
            first.id,
            worker_id="worker-a",
            lease_generation=first.lease_generation,
            now=NOW + timedelta(seconds=2),
        ),
        lambda: repository.fail(
            first.id,
            "stale failure",
            worker_id="worker-a",
            lease_generation=first.lease_generation,
            now=NOW + timedelta(seconds=2),
        ),
        lambda: repository.pause_for_budget(
            first.id,
            worker_id="worker-a",
            lease_generation=first.lease_generation,
            now=NOW + timedelta(seconds=2),
            retry_at=NOW + timedelta(hours=1),
        ),
    )

    for mutate in stale_mutations:
        with pytest.raises(LeaseLostError):
            mutate()

    active = repository.get(queued.id)
    assert active is not None
    assert active.status is JobStatus.RUNNING
    assert active.attempts == 2
    assert active.lease_generation == reclaimed.lease_generation


def test_in_memory_repository_dead_letters_an_expired_final_attempt() -> None:
    repository = InMemoryJobRepository()
    queued = repository.enqueue("extract", {}, max_attempts=1, now=NOW)
    assert repository.lease("worker-a", now=NOW, lease_for=timedelta(seconds=1)) is not None

    assert (
        repository.lease(
            "worker-b",
            now=NOW + timedelta(seconds=2),
            lease_for=timedelta(seconds=1),
        )
        is None
    )
    terminal = repository.get(queued.id)
    assert terminal is not None
    assert terminal.status is JobStatus.DEAD
    assert terminal.lease_generation == 2
    assert terminal.finished_at == NOW + timedelta(seconds=2)
    assert terminal.last_error == "lease_expired_max_attempts"


def test_failed_job_requeues_with_backoff_then_becomes_dead_at_max_attempts() -> None:
    repository = InMemoryJobRepository()
    queued = repository.enqueue("extract", {}, max_attempts=2, now=NOW)
    first = repository.lease("worker-a", now=NOW, lease_for=timedelta(minutes=1))
    assert first is not None

    retrying = repository.fail(
        first.id,
        "provider timeout",
        worker_id="worker-a",
        lease_generation=first.lease_generation,
        now=NOW,
    )
    assert retrying.status is JobStatus.PENDING
    assert retrying.last_error == "provider timeout"
    assert retrying.available_at == NOW + timedelta(seconds=30)
    assert repository.lease("worker-b", now=NOW, lease_for=timedelta(minutes=1)) is None

    second = repository.lease(
        "worker-b", now=NOW + timedelta(seconds=30), lease_for=timedelta(minutes=1)
    )
    assert second is not None
    assert second.id == queued.id
    assert second.attempts == 2
    dead = repository.fail(
        second.id,
        "still unavailable",
        worker_id="worker-b",
        lease_generation=second.lease_generation,
        now=NOW + timedelta(seconds=30),
    )

    assert dead.status is JobStatus.DEAD
    assert (
        repository.lease("worker-c", now=NOW + timedelta(days=1), lease_for=timedelta(minutes=1))
        is None
    )


def test_expired_in_memory_lease_cannot_complete_a_job() -> None:
    repository = InMemoryJobRepository()
    repository.enqueue("extract", {}, now=NOW)
    leased = repository.lease("worker-a", now=NOW, lease_for=timedelta(seconds=1))
    assert leased is not None

    with pytest.raises(LeaseLostError):
        repository.complete(
            leased.id,
            worker_id="worker-a",
            lease_generation=leased.lease_generation,
            now=NOW + timedelta(seconds=2),
        )


def test_expired_in_memory_lease_cannot_fail_a_job() -> None:
    repository = InMemoryJobRepository()
    repository.enqueue("extract", {}, now=NOW)
    leased = repository.lease("worker-a", now=NOW, lease_for=timedelta(seconds=1))
    assert leased is not None

    with pytest.raises(LeaseLostError):
        repository.fail(
            leased.id,
            worker_id="worker-a",
            lease_generation=leased.lease_generation,
            error="late",
            now=NOW + timedelta(seconds=2),
        )


def test_expired_in_memory_lease_cannot_pause_a_job() -> None:
    repository = InMemoryJobRepository()
    repository.enqueue("extract", {}, now=NOW)
    leased = repository.lease("worker-a", now=NOW, lease_for=timedelta(seconds=1))
    assert leased is not None

    with pytest.raises(LeaseLostError):
        repository.pause_for_budget(
            leased.id,
            worker_id="worker-a",
            lease_generation=leased.lease_generation,
            now=NOW + timedelta(seconds=2),
            retry_at=NOW + timedelta(hours=1),
        )


def test_heartbeat_requires_lease_owner_and_extends_lease() -> None:
    repository = InMemoryJobRepository()
    repository.enqueue("extract", {}, now=NOW)
    leased = repository.lease("worker-a", now=NOW, lease_for=timedelta(seconds=30))
    assert leased is not None

    with pytest.raises(LeaseLostError):
        repository.heartbeat(
            leased.id,
            worker_id="worker-b",
            lease_generation=leased.lease_generation,
            now=NOW + timedelta(seconds=10),
            lease_for=timedelta(seconds=30),
        )

    heartbeat = repository.heartbeat(
        leased.id,
        worker_id="worker-a",
        lease_generation=leased.lease_generation,
        now=NOW + timedelta(seconds=10),
        lease_for=timedelta(seconds=30),
    )
    assert heartbeat.heartbeat_at == NOW + timedelta(seconds=10)
    assert heartbeat.lease_expires_at == NOW + timedelta(seconds=40)


def test_budget_pause_requeues_without_counting_failure_or_attempt() -> None:
    repository = InMemoryJobRepository()
    queued = repository.enqueue("ai.extract", {}, now=NOW)
    leased = repository.lease("worker-a", now=NOW, lease_for=timedelta(minutes=1))
    assert leased is not None

    paused = repository.pause_for_budget(
        leased.id,
        worker_id="worker-a",
        lease_generation=leased.lease_generation,
        now=NOW,
        retry_at=NOW + timedelta(hours=1),
    )

    assert paused.id == queued.id
    assert paused.status is JobStatus.PENDING
    assert paused.attempts == 0
    assert paused.lease_generation == 1
    assert paused.last_error is None
    assert (
        repository.lease(
            "worker-b", now=NOW + timedelta(minutes=30), lease_for=timedelta(minutes=1)
        )
        is None
    )
    resumed = repository.lease(
        "worker-b", now=NOW + timedelta(hours=1), lease_for=timedelta(minutes=1)
    )
    assert resumed is not None
    assert resumed.attempts == 1
    assert resumed.lease_generation == 2


def test_postgres_lease_uses_canonical_claim_rpc_that_terminalizes_exhausted_jobs() -> None:
    class Executor:
        def __init__(self) -> None:
            self.sql = ""
            self.params: dict[str, object] = {}

        def query(self, sql: str, params: dict[str, object]) -> list[dict[str, object]]:
            self.sql = sql
            self.params = params
            return []

    executor = Executor()
    repository = PostgresJobRepository(executor)

    assert (
        repository.lease(
            "worker-a",
            now=NOW,
            lease_for=timedelta(minutes=5),
            kinds={"extract"},
        )
        is None
    )
    assert "ingest.claim_jobs_v2" in executor.sql
    assert executor.params["lease_seconds"] == 300
    assert executor.params["kinds"] == ["extract"]


def test_postgres_lease_maps_one_row_from_the_canonical_claim_rpc() -> None:
    class FakeExecutor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        def query(self, sql: str, params: dict[str, object]) -> list[dict[str, object]]:
            self.calls.append((sql, params))
            return [
                {
                    "id": "job-1",
                    "job_type": "extract",
                    "payload": {},
                    "status": "running",
                    "priority": 2,
                    "available_at": NOW,
                    "attempts": 1,
                    "max_attempts": 5,
                    "lease_generation": 1,
                    "locked_by": "worker-a",
                    "locked_at": NOW,
                    "lock_expires_at": NOW + timedelta(minutes=5),
                    "last_error_code": None,
                    "last_error_message": None,
                    "completed_at": None,
                    "dedupe_key": None,
                    "created_at": NOW,
                    "updated_at": NOW,
                }
            ]

    executor = FakeExecutor()
    repository = PostgresJobRepository(executor)

    job = repository.lease("worker-a", now=NOW, lease_for=timedelta(minutes=5), kinds={"extract"})

    assert job is not None
    assert job.status is JobStatus.RUNNING
    assert job.attempts == 1
    assert job.lease_generation == 1
    assert len(executor.calls) == 1
    sql, params = executor.calls[0]
    assert "ingest.claim_jobs_v2" in sql
    assert params["worker_id"] == "worker-a"
    assert params["kinds"] == ["extract"]
    assert params["lease_seconds"] == 300


def test_enqueue_deduplicates_only_active_jobs_and_lifecycle_is_queryable() -> None:
    repository = InMemoryJobRepository()
    first = repository.enqueue("collect.url", {}, dedupe_key="url:example", now=NOW)
    duplicate = repository.enqueue(
        "collect.url", {"ignored": True}, dedupe_key="url:example", now=NOW
    )
    assert duplicate.id == first.id
    assert repository.counts()[JobStatus.PENDING] == 1

    leased = repository.lease("worker-a", now=NOW, lease_for=timedelta(minutes=1))
    assert leased is not None
    completed = repository.complete(
        leased.id,
        worker_id="worker-a",
        lease_generation=leased.lease_generation,
        now=NOW,
    )
    assert completed.status is JobStatus.COMPLETED

    replacement = repository.enqueue("collect.url", {}, dedupe_key="url:example", now=NOW)
    cancelled = repository.cancel(replacement.id, now=NOW)
    assert cancelled.status is JobStatus.CANCELLED
    assert [job.status for job in repository.list_jobs()] == [
        JobStatus.COMPLETED,
        JobStatus.CANCELLED,
    ]


def test_postgres_lease_mutations_use_one_database_clock_for_ownership() -> None:
    class Executor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        def query(self, sql: str, params: dict[str, object]) -> list[dict[str, object]]:
            self.calls.append((sql, params))
            return []

    executor = Executor()
    repository = PostgresJobRepository(executor)
    operations = (
        lambda: repository.heartbeat(
            "job-1",
            worker_id="worker-a",
            lease_generation=1,
            now=NOW,
            lease_for=timedelta(seconds=30),
        ),
        lambda: repository.complete("job-1", worker_id="worker-a", lease_generation=1, now=NOW),
        lambda: repository.fail("job-1", "late", worker_id="worker-a", lease_generation=1, now=NOW),
        lambda: repository.pause_for_budget(
            "job-1",
            worker_id="worker-a",
            lease_generation=1,
            now=NOW,
            retry_at=NOW + timedelta(hours=1),
        ),
    )

    for operation in operations:
        with pytest.raises(LeaseLostError):
            operation()

    assert len(executor.calls) == 4
    heartbeat_sql, heartbeat_params = executor.calls[0]
    complete_sql, complete_params = executor.calls[1]
    fail_sql, fail_params = executor.calls[2]
    pause_sql, pause_params = executor.calls[3]
    assert "ingest.heartbeat_job_v2" in heartbeat_sql
    assert "ingest.fail_job_v2" in fail_sql
    assert "ingest.complete_job_v2" in complete_sql
    assert "ingest.pause_job_for_budget_v2" in pause_sql
    for sql in (complete_sql, pause_sql):
        assert "UPDATE ingest.jobs" not in sql
    for sql, params in executor.calls:
        assert "%(lease_generation)s" in sql
        assert "%(now)s" not in sql
        assert "now" not in params
        assert params["lease_generation"] == 1
    assert heartbeat_params["lease_seconds"] == 30
    assert complete_params["lease_generation"] == 1
    assert fail_params["lease_generation"] == 1
    assert pause_params["lease_generation"] == 1


def test_postgres_completion_requires_an_unexpired_lease() -> None:
    class Executor:
        def __init__(self) -> None:
            self.sql = ""

        def query(self, sql: str, params: dict[str, object]) -> list[dict[str, object]]:
            self.sql = sql
            return []

    executor = Executor()
    repository = PostgresJobRepository(executor)

    with pytest.raises(LeaseLostError):
        repository.complete("job-1", worker_id="worker-a", lease_generation=1, now=NOW)

    assert "ingest.complete_job_v2" in executor.sql
    assert "UPDATE ingest.jobs" not in executor.sql
    assert "%(lease_generation)s::bigint" in executor.sql


def test_postgres_cleanup_completion_uses_only_the_controlled_atomic_rpc() -> None:
    completed_row: dict[str, object] = {
        "id": "job-1",
        "job_type": "maintenance.cleanup",
        "payload": {},
        "status": "completed",
        "priority": 0,
        "available_at": NOW,
        "attempts": 1,
        "max_attempts": 5,
        "lease_generation": 7,
        "locked_by": None,
        "locked_at": None,
        "lock_expires_at": None,
        "last_error_code": None,
        "last_error_message": None,
        "completed_at": NOW,
        "dedupe_key": None,
        "created_at": NOW,
        "updated_at": NOW,
    }

    class Executor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        def query(self, sql: str, params: dict[str, object]) -> list[dict[str, object]]:
            self.calls.append((sql, params))
            return [completed_row]

    executor = Executor()
    completed = PostgresJobRepository(executor).complete(
        "job-1",
        worker_id="worker-a",
        lease_generation=7,
        now=NOW,
        effect=CompletionEffect.PRUNE_EXPIRED_EPHEMERA,
    )

    assert completed.status is JobStatus.COMPLETED
    assert completed.lease_generation == 7
    assert len(executor.calls) == 1
    sql, params = executor.calls[0]
    assert "SELECT *" in sql
    assert "ingest.finalize_cleanup_job" in sql
    assert "ingest.prune_expired_ephemera()" not in sql
    assert "UPDATE ingest.jobs" not in sql
    assert params == {
        "job_id": "job-1",
        "worker_id": "worker-a",
        "lease_generation": 7,
    }


def test_postgres_failure_requires_an_unexpired_lease() -> None:
    class Executor:
        def __init__(self) -> None:
            self.sql = ""

        def query(self, sql: str, params: dict[str, object]) -> list[dict[str, object]]:
            self.sql = sql
            return []

    executor = Executor()
    repository = PostgresJobRepository(executor)

    with pytest.raises(LeaseLostError):
        repository.fail("job-1", "late", worker_id="worker-a", lease_generation=1, now=NOW)

    assert "ingest.fail_job_v2" in executor.sql
    assert "lease_generation => %(lease_generation)s::bigint" in executor.sql


def test_postgres_budget_pause_requires_an_unexpired_lease() -> None:
    class Executor:
        def __init__(self) -> None:
            self.sql = ""

        def query(self, sql: str, params: dict[str, object]) -> list[dict[str, object]]:
            self.sql = sql
            return []

    executor = Executor()
    repository = PostgresJobRepository(executor)

    with pytest.raises(LeaseLostError):
        repository.pause_for_budget(
            "job-1",
            worker_id="worker-a",
            lease_generation=1,
            now=NOW,
            retry_at=NOW + timedelta(hours=1),
        )

    assert "ingest.pause_job_for_budget_v2" in executor.sql
    assert "UPDATE ingest.jobs" not in executor.sql
    assert "%(lease_generation)s::bigint" in executor.sql


def test_postgres_failure_atomically_requeues_with_exponential_backoff() -> None:
    row: dict[str, object] = {
        "id": "job-1",
        "job_type": "extract",
        "payload": {},
        "status": "pending",
        "priority": 0,
        "available_at": NOW + timedelta(seconds=30),
        "attempts": 1,
        "max_attempts": 5,
        "lease_generation": 1,
        "locked_by": None,
        "locked_at": None,
        "lock_expires_at": None,
        "last_error_code": "job_failed",
        "last_error_message": "timeout",
        "completed_at": None,
        "dedupe_key": None,
        "created_at": NOW,
        "updated_at": NOW,
    }

    class Executor:
        def __init__(self) -> None:
            self.sql = ""
            self.params: dict[str, object] = {}

        def query(self, sql: str, params: dict[str, object]) -> list[dict[str, object]]:
            self.sql = sql
            self.params = params
            return [row]

    executor = Executor()
    repository = PostgresJobRepository(executor)
    retrying = repository.fail(
        "job-1", "timeout", worker_id="worker-a", lease_generation=1, now=NOW
    )

    assert retrying.status is JobStatus.PENDING
    assert retrying.available_at == NOW + timedelta(seconds=30)
    assert "ingest.fail_job_v2" in executor.sql
    assert "UPDATE ingest.jobs" not in executor.sql
    assert executor.params["retryable"] is True


def test_postgres_nonretryable_failure_dead_letters_under_the_same_fence() -> None:
    row: dict[str, object] = {
        "id": "job-1",
        "job_type": "catalog.tcgdex.sets.sync",
        "payload": {},
        "status": "dead",
        "priority": 0,
        "available_at": NOW,
        "attempts": 1,
        "max_attempts": 5,
        "lease_generation": 1,
        "locked_by": None,
        "locked_at": None,
        "lock_expires_at": None,
        "last_error_code": "invalid_response",
        "last_error_message": "invalid_response",
        "completed_at": NOW,
        "dedupe_key": None,
        "created_at": NOW,
        "updated_at": NOW,
    }

    class Executor:
        def __init__(self) -> None:
            self.params: dict[str, object] = {}

        def query(self, sql: str, params: dict[str, object]) -> list[dict[str, object]]:
            assert "ingest.fail_job_v2" in sql
            self.params = params
            return [row]

    executor = Executor()
    failed = PostgresJobRepository(executor).fail(
        "job-1",
        "invalid_response",
        worker_id="worker-a",
        lease_generation=1,
        now=NOW,
        error_code="invalid_response",
        retryable=False,
    )

    assert failed.status is JobStatus.DEAD
    assert executor.params["retryable"] is False
    assert executor.params["error_code"] == "invalid_response"


def test_postgres_heartbeat_and_failure_use_owner_guard_and_dead_mapping() -> None:
    base_row: dict[str, object] = {
        "id": "job-1",
        "job_type": "extract",
        "payload": {},
        "status": "running",
        "priority": 0,
        "available_at": NOW,
        "attempts": 5,
        "max_attempts": 5,
        "lease_generation": 1,
        "locked_by": "worker-a",
        "locked_at": NOW,
        "lock_expires_at": NOW + timedelta(minutes=5),
        "last_error_code": None,
        "last_error_message": None,
        "completed_at": None,
        "dedupe_key": None,
        "created_at": NOW,
        "updated_at": NOW,
    }

    class ScriptedExecutor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        def query(self, sql: str, params: dict[str, object]) -> list[dict[str, object]]:
            self.calls.append((sql, params))
            if "ingest.fail_job_v2" in sql:
                return [
                    {
                        **base_row,
                        "status": "dead",
                        "last_error_code": "job_failed",
                        "last_error_message": "timeout",
                    }
                ]
            return [base_row]

    executor = ScriptedExecutor()
    repository = PostgresJobRepository(executor)
    heartbeat = repository.heartbeat(
        "job-1",
        worker_id="worker-a",
        lease_generation=1,
        now=NOW,
        lease_for=timedelta(minutes=5),
    )
    dead = repository.fail("job-1", "timeout", worker_id="worker-a", lease_generation=1, now=NOW)

    assert heartbeat.status is JobStatus.RUNNING
    assert dead.status is JobStatus.DEAD
    assert "ingest.heartbeat_job_v2" in executor.calls[0][0]
    assert "ingest.fail_job_v2" in executor.calls[1][0]
    assert all(params["worker_id"] == "worker-a" for _, params in executor.calls)
    assert all("%(lease_generation)s" in sql for sql, _ in executor.calls)


def test_psycopg_query_executor_commits_and_returns_mapping_rows() -> None:
    events: list[object] = []

    class Cursor:
        description = object()

        def __enter__(self) -> Cursor:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def execute(self, sql: str, params: object) -> None:
            events.append((sql, params))

        def fetchall(self) -> list[dict[str, object]]:
            return [{"id": "job-1"}]

    class Connection:
        def __enter__(self) -> Connection:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def cursor(self, *, row_factory: object = None) -> Cursor:
            events.append(("row_factory", row_factory))
            return Cursor()

        def commit(self) -> None:
            events.append("commit")

    executor = PsycopgQueryExecutor(lambda: Connection())
    rows = executor.query("SELECT %(value)s", {"value": 1})

    assert rows == ({"id": "job-1"},)
    assert "commit" in events


def test_postgres_enqueue_is_atomic_and_respects_active_dedupe_constraint() -> None:
    row: dict[str, object] = {
        "id": "job-1",
        "job_type": "catalog.tcgdex.sets.sync",
        "payload": {},
        "status": "pending",
        "priority": 3,
        "available_at": NOW,
        "attempts": 0,
        "max_attempts": 4,
        "lease_generation": 0,
        "locked_by": None,
        "locked_at": None,
        "lock_expires_at": None,
        "last_error_code": None,
        "last_error_message": None,
        "completed_at": None,
        "dedupe_key": "manual:catalog",
        "created_at": NOW,
        "updated_at": NOW,
    }

    class Executor:
        def __init__(self) -> None:
            self.sql = ""
            self.params: dict[str, object] = {}

        def query(self, sql: str, params: dict[str, object]) -> list[dict[str, object]]:
            self.sql = sql
            self.params = params
            return [row]

    executor = Executor()
    repository = PostgresJobRepository(executor)
    job = repository.enqueue(
        "catalog.tcgdex.sets.sync",
        {},
        priority=3,
        max_attempts=4,
        dedupe_key="manual:catalog",
        now=NOW,
    )

    assert job.status is JobStatus.PENDING
    assert "ingest.enqueue_job_v1" in executor.sql
    assert "INSERT INTO ingest.jobs" not in executor.sql
    assert "%(now)s" not in executor.sql
    assert "now" not in executor.params
    assert executor.params["dedupe_key"] == "manual:catalog"


def test_postgres_scheduled_enqueue_uses_the_durable_slot_rpc() -> None:
    row: dict[str, object] = {
        "id": "job-1",
        "job_type": "catalog.tcgdex.sets.sync",
        "payload": {},
        "status": "pending",
        "priority": 20,
        "available_at": NOW,
        "attempts": 0,
        "max_attempts": 3,
        "lease_generation": 0,
        "locked_by": None,
        "locked_at": None,
        "lock_expires_at": None,
        "last_error_code": None,
        "last_error_message": None,
        "completed_at": None,
        "dedupe_key": "schedule:catalog_sync:20260825T120000Z",
        "created_at": NOW,
        "updated_at": NOW,
    }

    class Executor:
        def __init__(self) -> None:
            self.sql = ""
            self.params: dict[str, object] = {}

        def query(self, sql: str, params: dict[str, object]) -> list[dict[str, object]]:
            self.sql = sql
            self.params = params
            return [row]

    executor = Executor()
    job = PostgresJobRepository(executor).enqueue_scheduled(
        "catalog.tcgdex.sets.sync",
        {},
        schedule_name="catalog_sync",
        scheduled_for=NOW,
        priority=20,
        now=NOW,
        max_attempts=3,
    )

    assert job.id == "job-1"
    assert "ingest.enqueue_scheduled_job_v1" in executor.sql
    assert "INSERT INTO ingest.jobs" not in executor.sql
    assert executor.params == {
        "schedule_name": "catalog_sync",
        "scheduled_for": NOW,
        "kind": "catalog.tcgdex.sets.sync",
        "payload": "{}",
        "priority": 20,
        "max_attempts": 3,
    }


def test_postgres_tcgdex_completion_uses_one_data_bearing_atomic_rpc() -> None:
    completed_row: dict[str, object] = {
        "id": "job-1",
        "job_type": "catalog.tcgdex.sets.sync",
        "payload": {},
        "status": "completed",
        "priority": 20,
        "available_at": NOW,
        "attempts": 1,
        "max_attempts": 3,
        "lease_generation": 4,
        "locked_by": None,
        "locked_at": None,
        "lock_expires_at": None,
        "last_error_code": None,
        "last_error_message": None,
        "completed_at": NOW,
        "dedupe_key": "schedule:catalog_sync:20260825T120000Z",
        "created_at": NOW,
        "updated_at": NOW,
    }

    class Executor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        def query(self, sql: str, params: dict[str, object]) -> list[dict[str, object]]:
            self.calls.append((sql, params))
            return [completed_row]

    executor = Executor()
    completed = PostgresJobRepository(executor).complete(
        "job-1",
        worker_id="collector-1",
        lease_generation=4,
        now=NOW,
        effect=TCGdexSetsSyncCompletion(
            outcome=TCGdexSyncOutcome.CHANGED,
            expected_revision=0,
            etag='"v1"',
            content_sha256="a" * 64,
            sets=(
                TCGdexSetWrite(
                    external_id="sv1",
                    name="Scarlet & Violet",
                    card_count_total=258,
                    card_count_official=198,
                ),
            ),
        ),
    )

    assert completed.status is JobStatus.COMPLETED
    assert len(executor.calls) == 1
    sql, params = executor.calls[0]
    assert "ingest.finalize_tcgdex_sets_job" in sql
    assert "INSERT INTO catalog.sets" not in sql
    assert "UPDATE ingest.jobs" not in sql
    assert params["job_id"] == "job-1"
    assert params["worker_id"] == "collector-1"
    assert params["lease_generation"] == 4
    assert '"outcome":"changed"' in str(params["result"])


def test_tcgdex_completion_effect_rejects_unbounded_or_mismatched_data() -> None:
    one_set = TCGdexSetWrite(
        external_id="sv1",
        name="Scarlet & Violet",
        card_count_total=258,
        card_count_official=198,
    )

    with pytest.raises(ValueError, match="1 to 1000"):
        TCGdexSetsSyncCompletion(
            outcome=TCGdexSyncOutcome.CHANGED,
            expected_revision=0,
            etag='"v1"',
            content_sha256="a" * 64,
        )
    with pytest.raises(ValueError, match="must not carry"):
        TCGdexSetsSyncCompletion(
            outcome=TCGdexSyncOutcome.NOT_MODIFIED,
            expected_revision=1,
            etag='"v1"',
            content_sha256="a" * 64,
            sets=(one_set,),
        )
    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        TCGdexSetsSyncCompletion(
            outcome=TCGdexSyncOutcome.NOT_MODIFIED,
            expected_revision=1,
            etag='"v1"',
            content_sha256="A" * 64,
        )
    with pytest.raises(ValueError, match="bounded HTTP field value"):
        TCGdexSetsSyncCompletion(
            outcome=TCGdexSyncOutcome.NOT_MODIFIED,
            expected_revision=1,
            etag='"ÿ"',
            content_sha256="a" * 64,
        )


def _youtube_write() -> YouTubeSourceItemWrite:
    return YouTubeSourceItemWrite(
        external_id="dQw4w9WgXcQ",
        source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        title="Pokemon booster box opening",
        published_at=NOW,
        collector_version="youtube-global-discovery-v1",
        source_policy_version="youtube-global-discovery-v1",
    )


def test_postgres_youtube_completion_uses_one_exact_activity_only_finalizer() -> None:
    completed_row: dict[str, object] = {
        "id": "job-1",
        "job_type": "source.youtube.discovery",
        "payload": {"query_name": "pokemon-tcg-booster-box-opening"},
        "status": "completed",
        "priority": 15,
        "available_at": NOW,
        "attempts": 1,
        "max_attempts": 3,
        "lease_generation": 2,
        "locked_by": None,
        "locked_at": None,
        "lock_expires_at": None,
        "last_error_code": None,
        "last_error_message": None,
        "completed_at": NOW,
        "dedupe_key": "schedule:youtube:20260825T120000Z",
        "created_at": NOW,
        "updated_at": NOW,
    }

    class Executor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        def query(self, sql: str, params: dict[str, object]) -> list[dict[str, object]]:
            self.calls.append((sql, params))
            return [completed_row]

    executor = Executor()
    completion = YouTubeDiscoveryCompletion(
        query_name="pokemon-tcg-booster-box-opening",
        items=(_youtube_write(),),
    )
    completed = PostgresJobRepository(executor).complete(
        "job-1",
        worker_id="collector-1",
        lease_generation=2,
        now=NOW,
        effect=completion,
    )

    assert completed.status is JobStatus.COMPLETED
    sql, params = executor.calls[0]
    assert "ingest.finalize_youtube_discovery_job" in sql
    persisted = json.loads(str(params["result"]))
    assert set(persisted) == {"version", "query_name", "items"}
    assert persisted["query_name"] == "pokemon-tcg-booster-box-opening"
    assert len(persisted["items"]) == 1
    item = persisted["items"][0]
    assert set(item) == {
        "external_id",
        "source_url",
        "title",
        "published_at",
        "collector_version",
        "source_policy_version",
    }
    assert item["collector_version"] == "youtube-global-discovery-v1"
    assert item["source_policy_version"] == "youtube-global-discovery-v1"
    assert item["title"] == "Pokemon booster box opening"
    assert item["published_at"] == "2026-08-25T12:00:00Z"
    serialized = json.dumps(persisted)
    for forbidden in (
        "normalized_url",
        "text_excerpt",
        "author_hash",
        "content_hash",
        "language",
        "metadata",
        "media_urls",
        "channel_id",
        "description",
        "result_rank",
    ):
        assert forbidden not in serialized


def test_postgres_public_study_completion_uses_evidence_only_finalizer() -> None:
    completed_row: dict[str, object] = {
        "id": "job-1",
        "job_type": "source.public_study.opening",
        "payload": {"study_key": "comicbook-perfect-order-us-55-v1"},
        "status": "completed",
        "priority": 14,
        "available_at": NOW,
        "attempts": 1,
        "max_attempts": 3,
        "lease_generation": 2,
        "locked_by": None,
        "locked_at": None,
        "lock_expires_at": None,
        "last_error_code": None,
        "last_error_message": None,
        "completed_at": NOW,
        "dedupe_key": "schedule:public-study:20260825T120000Z",
        "created_at": NOW,
        "updated_at": NOW,
    }

    class Executor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        def query(self, sql: str, params: dict[str, object]) -> list[dict[str, object]]:
            self.calls.append((sql, params))
            return [completed_row]

    executor = Executor()
    completion = PublicStudyCompletion(
        study_key="comicbook-perfect-order-us-55-v1",
        source_url=(
            "https://comicbook.com/gaming/feature/"
            "pokemon-tcg-perfect-order-pull-rates-ex-illustration-rares-estimates"
        ),
        title="I Opened 55 Packs from Pokémon TCG's Perfect Order — Pull Rates",
        evidence_excerpt=(
            "In total, I opened 55 boosters from the upcoming Perfect Order lineup.\n"
            "1 Special Illustration Rare"
        ),
        evidence_sha256=content_sha256(
            "In total, I opened 55 boosters from the upcoming Perfect Order lineup.\n"
            "1 Special Illustration Rare"
        ),
        collector_version="public-study-comicbook-perfect-order-v1",
        parser_version="comicbook-perfect-order-evidence-v1",
        source_policy_version="public-study-comicbook-perfect-order-v1",
    )

    completed = PostgresJobRepository(executor).complete(
        "job-1",
        worker_id="collector-1",
        lease_generation=2,
        now=NOW,
        effect=completion,
    )

    assert completed.status is JobStatus.COMPLETED
    sql, params = executor.calls[0]
    assert "ingest.finalize_public_study_job" in sql
    persisted = json.loads(str(params["result"]))
    assert set(persisted) == {
        "version",
        "study_key",
        "source_url",
        "title",
        "evidence_excerpt",
        "evidence_sha256",
        "collector_version",
        "parser_version",
        "source_policy_version",
    }
    serialized = json.dumps(persisted)
    for forbidden in (
        "country_code",
        "country_name",
        "pack_count",
        "qualifying_hit_pack_count",
        "observed_rate",
        "set_external_id",
        "product_scope",
    ):
        assert forbidden not in serialized


def test_public_study_completion_rejects_identity_or_version_drift() -> None:
    common = {
        "study_key": "comicbook-perfect-order-us-55-v1",
        "source_url": (
            "https://comicbook.com/gaming/feature/"
            "pokemon-tcg-perfect-order-pull-rates-ex-illustration-rares-estimates"
        ),
        "title": "Reviewed opening",
        "evidence_excerpt": "55 packs\n1 Special Illustration Rare",
        "evidence_sha256": content_sha256("55 packs\n1 Special Illustration Rare"),
        "collector_version": "public-study-comicbook-perfect-order-v1",
        "parser_version": "comicbook-perfect-order-evidence-v1",
        "source_policy_version": "public-study-comicbook-perfect-order-v1",
    }

    with pytest.raises(ValueError, match="identity"):
        PublicStudyCompletion(**{**common, "source_url": "https://comicbook.com/wrong"})
    with pytest.raises(ValueError, match="parser version"):
        PublicStudyCompletion(**{**common, "parser_version": "drifted"})
    with pytest.raises(ValueError, match="does not match"):
        PublicStudyCompletion(**{**common, "evidence_sha256": "b" * 64})


def test_youtube_completion_rejects_noncanonical_watch_url() -> None:
    with pytest.raises(ValueError, match="canonical watch form"):
        replace(_youtube_write(), source_url="https://youtube.com/watch?v=dQw4w9WgXcQ")


@pytest.mark.parametrize(
    "forbidden_field",
    (
        "normalized_url",
        "text_excerpt",
        "author_hash",
        "content_hash",
        "language",
        "metadata",
        "query_name",
        "result_rank",
        "channel_id",
        "description",
        "product_type_hints",
        "batch_code_hints",
    ),
)
def test_youtube_write_contract_has_no_derived_or_placeholder_fields(
    forbidden_field: str,
) -> None:
    with pytest.raises(TypeError, match="unexpected keyword"):
        replace(_youtube_write(), **{forbidden_field: "forbidden"})


@pytest.mark.parametrize("control", ("\x00", "\t", "\n", "\r", "\x7f", "\u0085"))
def test_youtube_title_rejects_every_control_character(control: str) -> None:
    with pytest.raises(ValueError, match="title is invalid"):
        replace(_youtube_write(), title=f"Pokemon{control}opening")


def test_youtube_payload_matches_sql_primitive_and_range_boundaries() -> None:
    minimum = datetime(2005, 1, 1, tzinfo=UTC)
    write = replace(
        _youtube_write(),
        title="Pokemon opening",
        published_at=minimum,
    )

    payload = write.as_payload()

    assert set(payload) == {
        "external_id",
        "source_url",
        "title",
        "published_at",
        "collector_version",
        "source_policy_version",
    }
    assert payload["published_at"] == "2005-01-01T00:00:00Z"
    assert "\t" not in str(payload["title"])

    with pytest.raises(ValueError, match="approved range"):
        replace(write, published_at=minimum - timedelta(microseconds=1))
    with pytest.raises(ValueError, match="approved range"):
        replace(write, published_at=datetime.now(UTC) + timedelta(minutes=1))


def test_youtube_completion_rejects_more_than_one_search_page() -> None:
    with pytest.raises(ValueError, match="0 to 25"):
        YouTubeDiscoveryCompletion(
            query_name="pokemon-tcg-booster-box-opening",
            items=tuple(_youtube_write() for _ in range(26)),
        )


def test_postgres_budget_pause_and_completion_clear_canonical_locks() -> None:
    base: dict[str, object] = {
        "id": "job-1",
        "job_type": "ai.extract",
        "payload": {},
        "priority": 0,
        "available_at": NOW,
        "attempts": 0,
        "max_attempts": 5,
        "lease_generation": 1,
        "locked_by": None,
        "locked_at": None,
        "lock_expires_at": None,
        "last_error_code": None,
        "last_error_message": None,
        "completed_at": None,
        "dedupe_key": None,
        "created_at": NOW,
        "updated_at": NOW,
    }

    class Executor:
        def __init__(self) -> None:
            self.sql: list[str] = []

        def query(self, sql: str, params: dict[str, object]) -> list[dict[str, object]]:
            self.sql.append(sql)
            status = "pending" if "ingest.pause_job_for_budget_v2" in sql else "completed"
            return [{**base, "status": status}]

    executor = Executor()
    repository = PostgresJobRepository(executor)
    paused = repository.pause_for_budget(
        "job-1",
        worker_id="worker-a",
        lease_generation=1,
        now=NOW,
        retry_at=NOW + timedelta(hours=1),
    )
    completed = repository.complete("job-1", worker_id="worker-a", lease_generation=1, now=NOW)

    assert paused.status is JobStatus.PENDING
    assert completed.status is JobStatus.COMPLETED
    assert "ingest.pause_job_for_budget_v2" in executor.sql[0]
    assert "ingest.complete_job_v2" in executor.sql[1]
    assert all("UPDATE ingest.jobs" not in sql for sql in executor.sql)
