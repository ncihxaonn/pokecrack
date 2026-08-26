from __future__ import annotations

from datetime import UTC, datetime, timedelta
from threading import Event

from pokecrack_worker.jobs import InMemoryJobRepository, Job, JobStatus, LeaseLostError
from pokecrack_worker.jobs.models import CompletionEffect
from pokecrack_worker.runtime import BudgetPaused, RuntimeStatus, WorkerRuntime

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)


def test_worker_once_completes_one_job_and_dry_run_never_claims() -> None:
    repository = InMemoryJobRepository()
    first = repository.enqueue("fixture.echo", {"value": 1}, now=NOW)
    second = repository.enqueue("fixture.echo", {"value": 2}, now=NOW)
    handled: list[int] = []
    runtime = WorkerRuntime(
        repository,
        handlers={"fixture.echo": lambda job: handled.append(int(job.payload["value"]))},
        worker_id="worker-a",
        lease_for=timedelta(minutes=5),
        clock=lambda: NOW,
    )

    result = runtime.run(once=True)
    dry_result = runtime.run(once=False, dry_run=True)

    assert result.cycles == 1
    assert result.results[0].status is RuntimeStatus.COMPLETED
    statuses = {repository.get(first.id).status, repository.get(second.id).status}  # type: ignore[union-attr]
    assert statuses == {JobStatus.COMPLETED, JobStatus.PENDING}
    assert handled in ([1], [2])
    assert dry_result.cycles == 1
    assert dry_result.results[0].status is RuntimeStatus.DRY_RUN
    assert repository.counts()[JobStatus.PENDING] == 1


def test_budget_pause_is_requeued_without_becoming_a_failure() -> None:
    repository = InMemoryJobRepository()
    job = repository.enqueue("ai.extract", {}, now=NOW)

    def paused_handler(_job: object) -> None:
        raise BudgetPaused(retry_at=NOW + timedelta(hours=1), reason="daily_limit")

    runtime = WorkerRuntime(
        repository,
        handlers={"ai.extract": paused_handler},
        worker_id="worker-a",
        clock=lambda: NOW,
    )
    result = runtime.run_once()
    requeued = repository.get(job.id)

    assert result.status is RuntimeStatus.BUDGET_PAUSED
    assert result.error_code == "budget_paused"
    assert requeued is not None
    assert requeued.status is JobStatus.PENDING
    assert requeued.attempts == 0
    assert requeued.last_error is None
    assert requeued.available_at == NOW + timedelta(hours=1)


def test_worker_heartbeats_lease_while_handler_is_running() -> None:
    heartbeat_observed = Event()

    class RecordingRepository(InMemoryJobRepository):
        def heartbeat(
            self,
            job_id: str,
            *,
            worker_id: str,
            lease_generation: int,
            now: datetime,
            lease_for: timedelta,
        ) -> Job:
            result = super().heartbeat(
                job_id,
                worker_id=worker_id,
                lease_generation=lease_generation,
                now=now,
                lease_for=lease_for,
            )
            heartbeat_observed.set()
            return result

    repository = RecordingRepository()
    repository.enqueue("slow", {}, now=NOW)
    handler_observations: list[bool] = []

    runtime = WorkerRuntime(
        repository,
        handlers={"slow": lambda _job: handler_observations.append(heartbeat_observed.wait(0.2))},
        worker_id="worker-a",
        lease_for=timedelta(milliseconds=60),
    )
    result = runtime.run_once()

    assert result.status is RuntimeStatus.COMPLETED
    assert handler_observations == [True]
    assert heartbeat_observed.is_set()


def test_handler_timeout_exception_is_recorded_instead_of_mistaken_for_heartbeat_wait() -> None:
    class GuardedRepository(InMemoryJobRepository):
        def heartbeat(
            self,
            job_id: str,
            *,
            worker_id: str,
            lease_generation: int,
            now: datetime,
            lease_for: timedelta,
        ) -> Job:
            raise AssertionError("completed handler must not be heartbeated")

    repository = GuardedRepository()
    repository.enqueue("timeout", {}, now=NOW)

    def timeout_handler(_job: Job) -> None:
        raise TimeoutError("provider timeout")

    result = WorkerRuntime(
        repository,
        handlers={"timeout": timeout_handler},
        worker_id="worker-a",
        clock=lambda: NOW,
    ).run_once()

    assert result.status is RuntimeStatus.FAILED
    assert result.error_code == "TimeoutError"


def test_lease_lost_during_heartbeat_is_not_recorded_with_a_stale_fail() -> None:
    class LeaseLosingRepository(InMemoryJobRepository):
        def __init__(self) -> None:
            super().__init__()
            self.fail_calls = 0

        def heartbeat(
            self,
            job_id: str,
            *,
            worker_id: str,
            lease_generation: int,
            now: datetime,
            lease_for: timedelta,
        ) -> Job:
            raise LeaseLostError(job_id)

        def fail(
            self,
            job_id: str,
            error: str,
            *,
            worker_id: str,
            lease_generation: int,
            now: datetime,
        ) -> Job:
            self.fail_calls += 1
            return super().fail(
                job_id,
                error,
                worker_id=worker_id,
                lease_generation=lease_generation,
                now=now,
            )

    repository = LeaseLosingRepository()
    repository.enqueue("slow", {}, now=NOW)
    handler_release = Event()

    def slow_handler(_job: Job) -> None:
        handler_release.wait(0.05)

    runtime = WorkerRuntime(
        repository,
        handlers={"slow": slow_handler},
        worker_id="worker-a",
        lease_for=timedelta(milliseconds=30),
    )

    result = runtime.run_once()

    assert result.status is RuntimeStatus.LEASE_LOST
    assert result.error_code == "lease_lost"
    assert repository.fail_calls == 0


def test_lease_lost_during_atomic_completion_is_not_retried_as_a_failure() -> None:
    class LeaseLosingRepository(InMemoryJobRepository):
        def __init__(self) -> None:
            super().__init__()
            self.fail_calls = 0

        def complete(
            self,
            job_id: str,
            *,
            worker_id: str,
            lease_generation: int,
            now: datetime,
            effect: CompletionEffect | None = None,
        ) -> Job:
            raise LeaseLostError(job_id)

        def fail(
            self,
            job_id: str,
            error: str,
            *,
            worker_id: str,
            lease_generation: int,
            now: datetime,
        ) -> Job:
            self.fail_calls += 1
            return super().fail(
                job_id,
                error,
                worker_id=worker_id,
                lease_generation=lease_generation,
                now=now,
            )

    repository = LeaseLosingRepository()
    repository.enqueue("fixture.echo", {}, now=NOW)
    result = WorkerRuntime(
        repository,
        handlers={"fixture.echo": lambda _job: None},
        worker_id="worker-a",
        clock=lambda: NOW,
    ).run_once()

    assert result.status is RuntimeStatus.LEASE_LOST
    assert repository.fail_calls == 0


def test_runtime_can_require_a_typed_atomic_completion_effect() -> None:
    repository = InMemoryJobRepository()
    queued = repository.enqueue("live.unwired", {}, now=NOW)
    result = WorkerRuntime(
        repository,
        handlers={"live.unwired": lambda _job: None},
        worker_id="worker-a",
        clock=lambda: NOW,
        require_completion_effect=True,
    ).run_once()

    failed = repository.get(queued.id)
    assert result.status is RuntimeStatus.FAILED
    assert result.error_code == "CompletionEffectRequiredError"
    assert failed is not None
    assert failed.status is JobStatus.PENDING
    assert failed.last_error == "CompletionEffectRequiredError"
