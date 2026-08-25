from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pokecrack_worker.jobs import InMemoryJobRepository, JobStatus
from pokecrack_worker.scheduler import ScheduleEntry, Scheduler

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)


def test_scheduler_creates_interval_jobs_once_and_dry_run_does_not_advance_state() -> None:
    repository = InMemoryJobRepository()
    scheduler = Scheduler(
        repository,
        [
            ScheduleEntry(
                name="aggregate",
                job_type="aggregate.all",
                interval=timedelta(hours=1),
            )
        ],
    )

    first = scheduler.run_due(now=NOW)
    too_soon = scheduler.run_due(now=NOW + timedelta(minutes=30))
    dry = scheduler.run_due(now=NOW + timedelta(hours=1), dry_run=True)
    actual = scheduler.run_due(now=NOW + timedelta(hours=1))

    assert first.created == 1
    assert too_soon.created == 0
    assert dry.planned == 1
    assert dry.created == 0
    assert actual.created == 1
    assert repository.counts()[JobStatus.PENDING] == 2
    assert {job.kind for job in repository.list_jobs()} == {"aggregate.all"}
