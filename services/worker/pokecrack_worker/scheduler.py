"""Deterministic UTC scheduler backed by active-job database deduplication."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from pokecrack_worker.jobs import Job


class SchedulerRepository(Protocol):
    def enqueue(
        self,
        kind: str,
        payload: Mapping[str, Any] | None = None,
        *,
        priority: int,
        now: datetime,
        max_attempts: int,
        dedupe_key: str | None,
        available_at: datetime | None = None,
    ) -> Job: ...


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
    _parsed_cron: CronExpression | None = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.name or not self.job_type:
            raise ValueError("schedule name and job_type are required")
        if (self.interval is None) == (self.cron is None):
            raise ValueError("schedule requires exactly one of interval or cron")
        if self.interval is not None and self.interval <= timedelta():
            raise ValueError("schedule interval must be positive")
        parsed = CronExpression.parse(self.cron) if self.cron is not None else None
        object.__setattr__(self, "_parsed_cron", parsed)

    def slot(self, now: datetime) -> datetime | None:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("scheduler timestamps must be timezone-aware")
        moment = now.astimezone(UTC)
        if self._parsed_cron is not None:
            if not self._parsed_cron.matches(moment):
                return None
            return moment.replace(second=0, microsecond=0)
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
        if not dry_run:
            for entry, slot in due:
                self.repository.enqueue(
                    entry.job_type,
                    entry.payload,
                    priority=entry.priority,
                    max_attempts=entry.max_attempts,
                    dedupe_key=f"schedule:{entry.name}:{slot.strftime('%Y%m%dT%H%M%SZ')}",
                    now=now,
                )
        return SchedulerResult(
            due_names=tuple(entry.name for entry, _slot in due),
            planned=len(due),
            created=0 if dry_run else len(due),
            dry_run=dry_run,
        )
