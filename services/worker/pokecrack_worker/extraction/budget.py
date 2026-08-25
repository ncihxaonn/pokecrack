from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from threading import RLock
from typing import Any, TypeVar
from uuid import uuid4

from .providers import AICompletion, AIProvider, AIRequest, AIRunMetadata, TokenUsage

ZERO_AUD = Decimal("0")
T = TypeVar("T")


def _aud(value: Decimal | int | str) -> Decimal:
    amount = value if isinstance(value, Decimal) else Decimal(str(value))
    if not amount.is_finite() or amount < ZERO_AUD:
        raise ValueError("AUD amounts must be finite and non-negative")
    return amount


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("budget timestamps must be timezone-aware")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class BudgetLimits:
    daily_aud: Decimal
    monthly_aud: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "daily_aud", _aud(self.daily_aud))
        object.__setattr__(self, "monthly_aud", _aud(self.monthly_aud))


@dataclass(frozen=True, slots=True)
class BudgetSnapshot:
    at: datetime
    daily_spend_aud: Decimal
    monthly_spend_aud: Decimal
    daily_remaining_aud: Decimal
    monthly_remaining_aud: Decimal


class BudgetStatus(StrEnum):
    AVAILABLE = "available"
    BUDGET_PAUSED = "budget_paused"


@dataclass(frozen=True, slots=True)
class BudgetCheck:
    status: BudgetStatus
    estimated_cost_aud: Decimal
    snapshot: BudgetSnapshot
    reason: str | None = None

    @property
    def allowed(self) -> bool:
        return self.status is BudgetStatus.AVAILABLE


class JobState(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"


class ExecutionStatus(StrEnum):
    COMPLETED = "completed"
    BUDGET_PAUSED = "budget_paused"


@dataclass(frozen=True, slots=True)
class PendingAIJob:
    job_id: str
    state: JobState = JobState.PENDING


@dataclass(frozen=True, slots=True)
class BudgetExecution[T]:
    status: ExecutionStatus
    job: PendingAIJob
    check: BudgetCheck
    value: T | None = None


class BudgetPausedError(RuntimeError):
    """Control signal: leave the owning job pending; this is not a job failure."""

    def __init__(self, check: BudgetCheck) -> None:
        self.check = check
        super().__init__(f"AI budget paused: {check.reason}")


@dataclass(frozen=True, slots=True)
class BudgetReservation:
    reservation_id: str
    at: datetime
    estimated_cost_aud: Decimal


class BudgetLedger:
    """Thread-safe, idempotent in-memory ledger keyed by AI run id.

    Persisted applications can replay stored ``AIRunMetadata`` rows at startup;
    duplicate run ids are ignored, so replay is safe.
    """

    def __init__(self, limits: BudgetLimits, *, runs: Iterable[AIRunMetadata] = ()) -> None:
        self.limits = limits
        self._runs: dict[str, AIRunMetadata] = {}
        self._reservations: dict[str, BudgetReservation] = {}
        self._lock = RLock()
        for run in runs:
            self.record_run(run)

    def record_run(self, run: AIRunMetadata) -> bool:
        _utc(run.started_at)
        _utc(run.completed_at)
        _aud(run.cost_aud)
        with self._lock:
            if run.run_id in self._runs:
                return False
            self._runs[run.run_id] = run
            return True

    def snapshot(self, at: datetime) -> BudgetSnapshot:
        moment = _utc(at)
        day = moment.date()
        month = (moment.year, moment.month)
        with self._lock:
            daily = sum(
                (run.cost_aud for run in self._runs.values() if _utc(run.started_at).date() == day),
                start=ZERO_AUD,
            )
            monthly = sum(
                (
                    run.cost_aud
                    for run in self._runs.values()
                    if (_utc(run.started_at).year, _utc(run.started_at).month) == month
                ),
                start=ZERO_AUD,
            )
            daily += sum(
                (
                    reservation.estimated_cost_aud
                    for reservation in self._reservations.values()
                    if _utc(reservation.at).date() == day
                ),
                start=ZERO_AUD,
            )
            monthly += sum(
                (
                    reservation.estimated_cost_aud
                    for reservation in self._reservations.values()
                    if (_utc(reservation.at).year, _utc(reservation.at).month) == month
                ),
                start=ZERO_AUD,
            )
        return BudgetSnapshot(
            at=moment,
            daily_spend_aud=daily,
            monthly_spend_aud=monthly,
            daily_remaining_aud=max(ZERO_AUD, self.limits.daily_aud - daily),
            monthly_remaining_aud=max(ZERO_AUD, self.limits.monthly_aud - monthly),
        )

    def check(self, estimated_cost_aud: Decimal, *, at: datetime) -> BudgetCheck:
        estimate = _aud(estimated_cost_aud)
        snapshot = self.snapshot(at)
        if snapshot.daily_spend_aud + estimate > self.limits.daily_aud:
            return BudgetCheck(
                status=BudgetStatus.BUDGET_PAUSED,
                estimated_cost_aud=estimate,
                snapshot=snapshot,
                reason="daily_limit",
            )
        if snapshot.monthly_spend_aud + estimate > self.limits.monthly_aud:
            return BudgetCheck(
                status=BudgetStatus.BUDGET_PAUSED,
                estimated_cost_aud=estimate,
                snapshot=snapshot,
                reason="monthly_limit",
            )
        return BudgetCheck(
            status=BudgetStatus.AVAILABLE,
            estimated_cost_aud=estimate,
            snapshot=snapshot,
        )

    def reserve(self, estimated_cost_aud: Decimal, *, at: datetime) -> BudgetReservation:
        with self._lock:
            check = self.check(estimated_cost_aud, at=at)
            if not check.allowed:
                raise BudgetPausedError(check)
            reservation = BudgetReservation(
                reservation_id=uuid4().hex,
                at=_utc(at),
                estimated_cost_aud=_aud(estimated_cost_aud),
            )
            self._reservations[reservation.reservation_id] = reservation
            return reservation

    def release(self, reservation: BudgetReservation) -> None:
        with self._lock:
            self._reservations.pop(reservation.reservation_id, None)

    def commit(self, reservation: BudgetReservation, run: AIRunMetadata) -> bool:
        _utc(run.completed_at)
        _aud(run.cost_aud)
        with self._lock:
            if self._reservations.pop(reservation.reservation_id, None) is None:
                raise RuntimeError("budget reservation is no longer active")
            if run.run_id in self._runs:
                return False
            self._runs[run.run_id] = replace(run, started_at=reservation.at)
            return True

    @property
    def run_count(self) -> int:
        with self._lock:
            return len(self._runs)


@dataclass(slots=True)
class BudgetedAIProvider:
    """Check projected spend before every request and record actual run usage."""

    provider: AIProvider
    ledger: BudgetLedger
    estimated_cost_aud: Decimal | Callable[[AIRequest[Any]], Decimal]
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)

    def __post_init__(self) -> None:
        if getattr(self.provider, "max_retries", 0) != 0:
            raise ValueError("budgeted AI providers require internal retries to be disabled")

    def complete(self, request: AIRequest[T]) -> AICompletion[T]:
        estimated_cost = (
            self.estimated_cost_aud(request)
            if callable(self.estimated_cost_aud)
            else self.estimated_cost_aud
        )
        reservation = self.ledger.reserve(estimated_cost, at=self.clock())
        try:
            completion = self.provider.complete(request)
        except BaseException:
            completed_at = self.clock()
            estimated_run = AIRunMetadata(
                run_id=f"estimated:{reservation.reservation_id}",
                operation=request.operation,
                provider=str(getattr(self.provider, "provider_name", "unknown")),
                model=str(getattr(self.provider, "model", "unknown")),
                schema_name=request.schema_name,
                started_at=reservation.at,
                completed_at=completed_at,
                attempts=1,
                usage=TokenUsage(0, 0),
                cost_aud=reservation.estimated_cost_aud,
                prompt_version=request.prompt_version,
                cost_is_estimate=True,
            )
            self.ledger.commit(reservation, estimated_run)
            raise
        self.ledger.commit(reservation, completion.run)
        return completion

    async def extract(self, request: AIRequest[T]) -> AICompletion[T]:
        return self.complete(request)

    async def validate(self, request: AIRequest[T]) -> AICompletion[T]:
        return self.complete(request)

    async def escalate(self, request: AIRequest[T]) -> AICompletion[T]:
        return self.complete(request)


@dataclass(slots=True)
class BudgetGate:
    ledger: BudgetLedger

    def execute(
        self,
        job: PendingAIJob,
        estimated_cost_aud: Decimal,
        work: Callable[[], T],
        *,
        at: datetime,
    ) -> BudgetExecution[T]:
        if job.state is not JobState.PENDING:
            raise ValueError("budget gate only accepts pending jobs")
        check = self.ledger.check(estimated_cost_aud, at=at)
        if not check.allowed:
            return BudgetExecution(
                status=ExecutionStatus.BUDGET_PAUSED,
                job=job,
                check=check,
            )
        value = work()
        return BudgetExecution(
            status=ExecutionStatus.COMPLETED,
            job=replace(job, state=JobState.COMPLETED),
            check=check,
            value=value,
        )
