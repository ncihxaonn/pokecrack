"""Deterministic UTC scheduler backed by active-job database deduplication."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from pokecrack_worker.jobs import Job


class SchedulerRepository(Protocol):
    def enqueue_scheduled(
        self,
        kind: str,
        payload: Mapping[str, Any] | None = None,
        *,
        schedule_name: str,
        scheduled_for: datetime,
        priority: int,
        now: datetime,
        max_attempts: int,
    ) -> Job | None: ...


_FIELD_RANGES = (
    (0, 59),  # minute
    (0, 23),  # hour
    (1, 31),  # day of month
    (1, 12),  # month
    (0, 7),  # day of week; both 0 and 7 are Sunday
)


def _parse_number(value: str, *, minimum: int, maximum: int) -> int:
    if not value.isascii() or not value.isdigit():
        raise ValueError(f"cron value must be an integer: {value!r}")
    parsed = int(value)
    if not minimum <= parsed <= maximum:
        raise ValueError(f"cron value must be between {minimum} and {maximum}: {value!r}")
    return parsed


@dataclass(frozen=True, slots=True)
class CronField:
    values: frozenset[int]
    unrestricted: bool

    @classmethod
    def parse(cls, expression: str, *, minimum: int, maximum: int) -> CronField:
        if not expression or any(character.isspace() for character in expression):
            raise ValueError("cron fields must be non-empty and contain no whitespace")
        values: set[int] = set()
        for component in expression.split(","):
            if not component:
                raise ValueError("cron lists cannot contain empty components")
            base, separator, step_value = component.partition("/")
            if separator:
                if "/" in step_value:
                    raise ValueError("cron components may contain at most one step")
                step = _parse_number(step_value, minimum=1, maximum=maximum - minimum + 1)
            else:
                step = 1
            if base == "*":
                start, end = minimum, maximum
            elif "-" in base:
                start_value, range_separator, end_value = base.partition("-")
                if not range_separator or "-" in end_value:
                    raise ValueError("cron ranges must contain exactly one hyphen")
                start = _parse_number(start_value, minimum=minimum, maximum=maximum)
                end = _parse_number(end_value, minimum=minimum, maximum=maximum)
                if start > end:
                    raise ValueError("cron ranges must be ascending")
            else:
                if separator:
                    raise ValueError("cron steps require '*' or an explicit range")
                start = end = _parse_number(base, minimum=minimum, maximum=maximum)
            values.update(range(start, end + 1, step))
        if not values:
            raise ValueError("cron field selects no values")
        # Seven is only an alias for Sunday in the day-of-week field. Store a
        # canonical zero so semantic wildcard detection also handles */1.
        if minimum == 0 and maximum == 7 and 7 in values:
            values.remove(7)
            values.add(0)
            domain = set(range(0, 7))
        else:
            domain = set(range(minimum, maximum + 1))
        unrestricted = values == domain
        return cls(values=frozenset(values), unrestricted=unrestricted)


@dataclass(frozen=True, slots=True)
class CronExpression:
    """A strict five-field cron expression evaluated only in UTC.

    The day-of-month/day-of-week relationship follows traditional cron rules:
    when both fields are restricted either may match; otherwise the restricted
    field must match. Names, macros and seconds are intentionally unsupported.
    """

    minute: CronField
    hour: CronField
    day_of_month: CronField
    month: CronField
    day_of_week: CronField

    @classmethod
    def parse(cls, expression: str) -> CronExpression:
        parts = expression.split()
        if len(parts) != 5:
            raise ValueError("cron expression must contain exactly five fields")
        fields = tuple(
            CronField.parse(part, minimum=minimum, maximum=maximum)
            for part, (minimum, maximum) in zip(parts, _FIELD_RANGES, strict=True)
        )
        return cls(*fields)

    def matches(self, value: datetime) -> bool:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("scheduler timestamps must be timezone-aware")
        moment = value.astimezone(UTC)
        # Python Monday=0; cron Sunday=0 and accepts 7 as the same day.
        cron_weekday = (moment.weekday() + 1) % 7
        weekday_matches = cron_weekday in self.day_of_week.values
        day_matches = moment.day in self.day_of_month.values
        if self.day_of_month.unrestricted or self.day_of_week.unrestricted:
            calendar_day_matches = day_matches and weekday_matches
        else:
            calendar_day_matches = day_matches or weekday_matches
        return (
            moment.minute in self.minute.values
            and moment.hour in self.hour.values
            and moment.month in self.month.values
            and calendar_day_matches
        )


@dataclass(frozen=True, slots=True)
class ScheduleEntry:
    name: str
    job_type: str
    interval: timedelta | None = None
    cron: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    priority: int = 0
    max_attempts: int = 5
    catch_up_within: timedelta | None = None
    catch_up_check_interval: timedelta | None = None
    _parsed_cron: CronExpression | None = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.name or not self.job_type:
            raise ValueError("schedule name and job_type are required")
        if (self.interval is None) == (self.cron is None):
            raise ValueError("schedule requires exactly one of interval or cron")
        if self.interval is not None and self.interval <= timedelta():
            raise ValueError("schedule interval must be positive")
        if (self.catch_up_within is None) != (self.catch_up_check_interval is None):
            raise ValueError("cron catch-up requires both a window and check interval")
        if self.catch_up_within is not None:
            if self.cron is None:
                raise ValueError("catch-up is supported only for cron schedules")
            assert self.catch_up_check_interval is not None
            for value in (self.catch_up_within, self.catch_up_check_interval):
                if value <= timedelta() or value.total_seconds() % 60 != 0:
                    raise ValueError("cron catch-up durations must use whole positive minutes")
            if self.catch_up_check_interval > self.catch_up_within:
                raise ValueError("cron catch-up check interval cannot exceed its window")
            if self.catch_up_within > timedelta(hours=36):
                raise ValueError("cron catch-up window cannot exceed 36 hours")
        parsed = CronExpression.parse(self.cron) if self.cron is not None else None
        object.__setattr__(self, "_parsed_cron", parsed)

    def slot(self, now: datetime) -> datetime | None:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("scheduler timestamps must be timezone-aware")
        moment = now.astimezone(UTC)
        if self._parsed_cron is not None:
            current_slot = moment.replace(second=0, microsecond=0)
            if self._parsed_cron.matches(current_slot):
                return current_slot
            if self.catch_up_within is None:
                return None
            assert self.catch_up_check_interval is not None
            check_seconds = int(self.catch_up_check_interval.total_seconds())
            check_slot_seconds = int(current_slot.timestamp()) // check_seconds * check_seconds
            check_slot = datetime.fromtimestamp(check_slot_seconds, tz=UTC)
            window_minutes = int(self.catch_up_within.total_seconds() // 60)
            for missed_minutes in range(window_minutes + 1):
                candidate = check_slot - timedelta(minutes=missed_minutes)
                if current_slot - candidate > self.catch_up_within:
                    break
                if self._parsed_cron.matches(candidate):
                    return candidate
            return None
        assert self.interval is not None
        interval_seconds = self.interval.total_seconds()
        if not interval_seconds.is_integer() or interval_seconds < 1:
            raise ValueError("schedule intervals must contain whole positive seconds")
        slot_seconds = int(moment.timestamp()) // int(interval_seconds) * int(interval_seconds)
        return datetime.fromtimestamp(slot_seconds, tz=UTC)


@dataclass(frozen=True, slots=True)
class SchedulerResult:
    due_names: tuple[str, ...]
    planned: int
    created: int
    dry_run: bool


class Scheduler:
    def __init__(
        self,
        repository: SchedulerRepository,
        entries: Iterable[ScheduleEntry],
    ) -> None:
        materialized = tuple(entries)
        names = [entry.name for entry in materialized]
        if len(names) != len(set(names)):
            raise ValueError("schedule names must be unique")
        self.repository = repository
        self.entries = materialized

    def run_due(self, *, now: datetime, dry_run: bool = False) -> SchedulerResult:
        due = tuple(
            (entry, slot) for entry in self.entries if (slot := entry.slot(now)) is not None
        )
        created = 0
        if not dry_run:
            for entry, slot in due:
                job = self.repository.enqueue_scheduled(
                    entry.job_type,
                    entry.payload,
                    schedule_name=entry.name,
                    scheduled_for=slot,
                    priority=entry.priority,
                    max_attempts=entry.max_attempts,
                    now=now,
                )
                if job is not None:
                    created += 1
        return SchedulerResult(
            due_names=tuple(entry.name for entry, _slot in due),
            planned=len(due),
            created=created,
            dry_run=dry_run,
        )
