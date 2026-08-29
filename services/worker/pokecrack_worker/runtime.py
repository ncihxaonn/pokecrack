"""Bounded worker execution loop shared by fixture and PostgreSQL queues."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from time import sleep
from typing import Protocol

from pokecrack_worker.jobs import (
    CompletionEffect,
    Job,
    LeaseLostError,
    PublicStudyCompletion,
    TCGdexSetsSyncCompletion,
    YouTubeDiscoveryCompletion,
)


class RuntimeRepository(Protocol):
    def lease(
        self,
        worker_id: str,
        *,
        now: datetime,
        lease_for: timedelta,
        kinds: set[str] | None = None,
    ) -> Job | None: ...

    def heartbeat(
        self,
        job_id: str,
        *,
        worker_id: str,
        lease_generation: int,
        now: datetime,
        lease_for: timedelta,
    ) -> Job: ...

    def complete(
        self,
        job_id: str,
        *,
        worker_id: str,
        lease_generation: int,
        now: datetime,
        effect: CompletionEffect
        | PublicStudyCompletion
        | TCGdexSetsSyncCompletion
        | YouTubeDiscoveryCompletion
        | None = None,
    ) -> Job: ...

    def fail(
        self,
        job_id: str,
        error: str,
        *,
        worker_id: str,
        lease_generation: int,
        now: datetime,
        error_code: str = "job_failed",
        retryable: bool = True,
    ) -> Job: ...

    def pause_for_budget(
        self,
        job_id: str,
        *,
        worker_id: str,
        lease_generation: int,
        now: datetime,
        retry_at: datetime,
    ) -> Job: ...


Completion = (
    CompletionEffect | PublicStudyCompletion | TCGdexSetsSyncCompletion | YouTubeDiscoveryCompletion
)
JobHandler = Callable[[Job], Completion | None]


class BudgetPaused(RuntimeError):
    def __init__(self, *, retry_at: datetime, reason: str) -> None:
        self.retry_at = retry_at
        self.reason = reason
        super().__init__("AI budget paused")


class JobDeferred(RuntimeError):
    """Retry a contended job later without consuming its claimed attempt."""

    def __init__(self, *, retry_at: datetime, code: str) -> None:
        if retry_at.tzinfo is None or retry_at.utcoffset() is None:
            raise ValueError("deferred job retry timestamp must be timezone-aware")
        if not code or len(code) > 160:
            raise ValueError("deferred job code must contain 1 to 160 characters")
        self.retry_at = retry_at
        self.code = code
        super().__init__(code)


class CompletionEffectRequiredError(RuntimeError):
    """A live handler returned without an atomic database completion effect."""


class JobExecutionError(RuntimeError):
    """Safe, typed handler failure with an explicit retry disposition."""

    def __init__(self, *, code: str, retryable: bool) -> None:
        if not code or len(code) > 160:
            raise ValueError("job execution error code must contain 1 to 160 characters")
        self.code = code
        self.retryable = retryable
        super().__init__(code)


class RuntimeStatus(StrEnum):
    DRY_RUN = "dry_run"
    IDLE = "idle"
    COMPLETED = "completed"
    FAILED = "failed"
    BUDGET_PAUSED = "budget_paused"
    DEFERRED = "deferred"
    LEASE_LOST = "lease_lost"


@dataclass(frozen=True, slots=True)
class CycleResult:
    status: RuntimeStatus
    job_id: str | None = None
    job_type: str | None = None
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class WorkerRunResult:
    results: tuple[CycleResult, ...]

    @property
    def cycles(self) -> int:
        return len(self.results)

    @property
    def processed(self) -> int:
        return sum(result.status is RuntimeStatus.COMPLETED for result in self.results)


class WorkerRuntime:
    def __init__(
        self,
        repository: RuntimeRepository,
        *,
        handlers: Mapping[str, JobHandler],
        worker_id: str,
        lease_for: timedelta = timedelta(minutes=5),
        poll_seconds: float = 10.0,
        clock: Callable[[], datetime] | None = None,
        sleeper: Callable[[float], None] = sleep,
        require_completion_effect: bool = False,
    ) -> None:
        self.repository = repository
        self.handlers = dict(handlers)
        self.worker_id = worker_id
        self.lease_for = lease_for
        self.poll_seconds = poll_seconds
        self.clock = clock or (lambda: datetime.now(UTC))
        self.sleeper = sleeper
        self.require_completion_effect = require_completion_effect

    def _run_handler_with_heartbeats(
        self,
        handler: JobHandler,
        job: Job,
    ) -> Completion | None:
        interval_seconds = max(0.01, min(30.0, self.lease_for.total_seconds() / 3))
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="pokecrack-job") as executor:
            future = executor.submit(handler, job)
            while True:
                try:
                    effect = future.result(timeout=interval_seconds)
                    if effect is not None and not isinstance(
                        effect,
                        (
                            CompletionEffect,
                            PublicStudyCompletion,
                            TCGdexSetsSyncCompletion,
                            YouTubeDiscoveryCompletion,
                        ),
                    ):
                        raise TypeError(
                            "job handlers must return a typed completion effect or None"
                        )
                    return effect
                except FutureTimeoutError:
                    if future.done():
                        future.result()
                    self.repository.heartbeat(
                        job.id,
                        worker_id=self.worker_id,
                        lease_generation=job.lease_generation,
                        now=self.clock(),
                        lease_for=self.lease_for,
                    )

    @staticmethod
    def _lease_lost(job: Job) -> CycleResult:
        return CycleResult(
            status=RuntimeStatus.LEASE_LOST,
            job_id=job.id,
            job_type=job.kind,
            error_code="lease_lost",
        )

    def run_once(self, *, dry_run: bool = False) -> CycleResult:
        if dry_run:
            return CycleResult(status=RuntimeStatus.DRY_RUN)
        job = self.repository.lease(
            self.worker_id,
            now=self.clock(),
            lease_for=self.lease_for,
            kinds=set(self.handlers),
        )
        if job is None:
            return CycleResult(status=RuntimeStatus.IDLE)
        handler = self.handlers.get(job.kind)
        if handler is None:
            try:
                self.repository.fail(
                    job.id,
                    "handler_unavailable",
                    worker_id=self.worker_id,
                    lease_generation=job.lease_generation,
                    now=self.clock(),
                )
            except LeaseLostError:
                return self._lease_lost(job)
            return CycleResult(
                status=RuntimeStatus.FAILED,
                job_id=job.id,
                job_type=job.kind,
                error_code="handler_unavailable",
            )
        try:
            effect = self._run_handler_with_heartbeats(handler, job)
            if self.require_completion_effect and effect is None:
                raise CompletionEffectRequiredError(
                    "live job handlers must return an atomic completion effect"
                )
        except LeaseLostError:
            return self._lease_lost(job)
        except BudgetPaused as paused:
            try:
                self.repository.pause_for_budget(
                    job.id,
                    worker_id=self.worker_id,
                    lease_generation=job.lease_generation,
                    now=self.clock(),
                    retry_at=paused.retry_at,
                )
            except LeaseLostError:
                return self._lease_lost(job)
            return CycleResult(
                status=RuntimeStatus.BUDGET_PAUSED,
                job_id=job.id,
                job_type=job.kind,
                error_code="budget_paused",
            )
        except JobDeferred as deferred:
            try:
                self.repository.pause_for_budget(
                    job.id,
                    worker_id=self.worker_id,
                    lease_generation=job.lease_generation,
                    now=self.clock(),
                    retry_at=deferred.retry_at,
                )
            except LeaseLostError:
                return self._lease_lost(job)
            return CycleResult(
                status=RuntimeStatus.DEFERRED,
                job_id=job.id,
                job_type=job.kind,
                error_code=deferred.code,
            )
        except JobExecutionError as error:
            try:
                self.repository.fail(
                    job.id,
                    error.code,
                    worker_id=self.worker_id,
                    lease_generation=job.lease_generation,
                    now=self.clock(),
                    error_code=error.code,
                    retryable=error.retryable,
                )
            except LeaseLostError:
                return self._lease_lost(job)
            return CycleResult(
                status=RuntimeStatus.FAILED,
                job_id=job.id,
                job_type=job.kind,
                error_code=error.code,
            )
        except Exception as error:  # queue boundary must retain failure state
            error_code = type(error).__name__[:160]
            try:
                self.repository.fail(
                    job.id,
                    error_code,
                    worker_id=self.worker_id,
                    lease_generation=job.lease_generation,
                    now=self.clock(),
                )
            except LeaseLostError:
                return self._lease_lost(job)
            return CycleResult(
                status=RuntimeStatus.FAILED,
                job_id=job.id,
                job_type=job.kind,
                error_code=error_code,
            )
        try:
            self.repository.complete(
                job.id,
                worker_id=self.worker_id,
                lease_generation=job.lease_generation,
                now=self.clock(),
                effect=effect,
            )
        except LeaseLostError:
            return self._lease_lost(job)
        except Exception as error:
            # A transactional finalizer error leaves no partial effect. If the
            # commit actually succeeded but its response was lost, this fenced
            # failure update returns no row and is reported as an ambiguous
            # lease loss instead of mutating the completed job.
            error_code = type(error).__name__[:160]
            try:
                self.repository.fail(
                    job.id,
                    error_code,
                    worker_id=self.worker_id,
                    lease_generation=job.lease_generation,
                    now=self.clock(),
                    error_code=error_code,
                )
            except LeaseLostError:
                return self._lease_lost(job)
            return CycleResult(
                status=RuntimeStatus.FAILED,
                job_id=job.id,
                job_type=job.kind,
                error_code=error_code,
            )
        return CycleResult(
            status=RuntimeStatus.COMPLETED,
            job_id=job.id,
            job_type=job.kind,
        )

    def run(
        self,
        *,
        once: bool = False,
        dry_run: bool = False,
        max_cycles: int | None = None,
    ) -> WorkerRunResult:
        if max_cycles is not None and max_cycles < 1:
            raise ValueError("max_cycles must be positive")
        bounded_cycles = 1 if once or dry_run else max_cycles
        results: list[CycleResult] = []
        while bounded_cycles is None or len(results) < bounded_cycles:
            result = self.run_once(dry_run=dry_run)
            results.append(result)
            if once or dry_run:
                break
            if result.status is RuntimeStatus.IDLE:
                self.sleeper(self.poll_seconds)
        return WorkerRunResult(results=tuple(results))
