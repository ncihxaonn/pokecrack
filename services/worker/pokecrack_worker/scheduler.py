"""Deterministic PostgreSQL/in-memory job scheduler without Redis."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
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


@dataclass(frozen=True, slots=True)
class ScheduleEntry:
    name: str
    job_type: str
    interval: timedelta | None = None
    cron: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    priority: int = 0
    max_attempts: int = 5

    def __post_init__(self) -> None:
        if not self.name or not self.job_type:
            raise ValueError("schedule name and job_type are required")
        if (self.interval is None) == (self.cron is None):
            raise ValueError("schedule requires exactly one of interval or cron")
        if self.interval is not None and self.interval <= timedelta():
            raise ValueError("schedule interval must be positive")


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
        self._last_created: dict[str, datetime] = {}

    def run_due(self, *, now: datetime, dry_run: bool = False) -> SchedulerResult:
        due = tuple(entry for entry in self.entries if self._is_due(entry, now))
        if not dry_run:
            for entry in due:
                self.repository.enqueue(
                    entry.job_type,
                    entry.payload,
                    priority=entry.priority,
                    max_attempts=entry.max_attempts,
                    dedupe_key=f"schedule:{entry.name}:{now.isoformat()}",
                    now=now,
                )
                self._last_created[entry.name] = now
        return SchedulerResult(
            due_names=tuple(entry.name for entry in due),
            planned=len(due),
            created=0 if dry_run else len(due),
            dry_run=dry_run,
        )

    def _is_due(self, entry: ScheduleEntry, now: datetime) -> bool:
        previous = self._last_created.get(entry.name)
        if entry.interval is not None:
            return previous is None or now - previous >= entry.interval
        raise NotImplementedError("cron schedules are not yet implemented")
