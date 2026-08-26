from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from pokecrack_worker.jobs import InMemoryJobRepository, JobStatus
from pokecrack_worker.scheduler import CronExpression, ScheduleEntry, Scheduler

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)


def test_scheduler_uses_deterministic_interval_slots_and_repository_deduplication() -> None:
    repository = InMemoryJobRepository()
    entry = ScheduleEntry(
        name="aggregate",
        job_type="aggregate.all",
        interval=timedelta(hours=1),
    )

    first = Scheduler(repository, [entry]).run_due(now=NOW)
    same_slot_from_another_process = Scheduler(repository, [entry]).run_due(
        now=NOW + timedelta(minutes=30)
    )
    dry = Scheduler(repository, [entry]).run_due(now=NOW + timedelta(hours=1), dry_run=True)
    actual = Scheduler(repository, [entry]).run_due(now=NOW + timedelta(hours=1))

    assert first.created == 1
    assert same_slot_from_another_process.planned == 1
    assert dry.planned == 1
    assert dry.created == 0
    assert actual.created == 1
    assert repository.counts()[JobStatus.PENDING] == 2
    assert {job.kind for job in repository.list_jobs()} == {"aggregate.all"}
    assert {job.dedupe_key for job in repository.list_jobs()} == {
        "schedule:aggregate:20260825T120000Z",
        "schedule:aggregate:20260825T130000Z",
    }


def test_scheduler_uses_the_same_cron_slot_key_across_instances() -> None:
    repository = InMemoryJobRepository()
    entry = ScheduleEntry(name="cleanup", job_type="maintenance.cleanup", cron="* * * * *")

    Scheduler(repository, [entry]).run_due(now=NOW + timedelta(seconds=2))
    Scheduler(repository, [entry]).run_due(now=NOW + timedelta(seconds=58))

    jobs = repository.list_jobs()
    assert len(jobs) == 1
    assert jobs[0].dedupe_key == "schedule:cleanup:20260825T120000Z"


def test_five_field_cron_supports_ranges_lists_steps_and_utc_conversion() -> None:
    weekdays = CronExpression.parse("0,30 9-17/2 * * 1-5")
    local_time = datetime(2026, 8, 24, 19, 30, tzinfo=timezone(timedelta(hours=10)))

    assert weekdays.matches(local_time)
    assert not weekdays.matches(local_time + timedelta(minutes=1))
    assert not weekdays.matches(datetime(2026, 8, 23, 9, 30, tzinfo=UTC))


def test_cron_accepts_zero_and_seven_for_sunday() -> None:
    sunday = datetime(2026, 8, 23, 0, 0, tzinfo=UTC)

    assert CronExpression.parse("0 0 * * 0").matches(sunday)
    assert CronExpression.parse("0 0 * * 7").matches(sunday)


def test_cron_uses_traditional_day_of_month_or_day_of_week_semantics() -> None:
    expression = CronExpression.parse("0 0 25 * 0")

    assert expression.matches(datetime(2026, 8, 25, 0, 0, tzinfo=UTC))
    assert expression.matches(datetime(2026, 8, 23, 0, 0, tzinfo=UTC))
    assert not expression.matches(datetime(2026, 8, 24, 0, 0, tzinfo=UTC))

    wildcard_step = CronExpression.parse("0 0 */1 * 0")
    assert not wildcard_step.matches(datetime(2026, 8, 24, 0, 0, tzinfo=UTC))


@pytest.mark.parametrize(
    "expression",
    (
        "* * * *",
        "* * * * * *",
        "60 * * * *",
        "* 24 * * *",
        "* * 32 * *",
        "* * * 13 *",
        "* * * * 8",
        "* * * * MON",
        "* 5-2 * * *",
        "* 1/2 * * *",
        "*/0 * * * *",
        "1,,2 * * * *",
    ),
)
def test_cron_rejects_unsupported_or_out_of_range_syntax(expression: str) -> None:
    with pytest.raises(ValueError):
        CronExpression.parse(expression)


def test_scheduler_rejects_naive_timestamps_and_dry_run_never_enqueues() -> None:
    repository = InMemoryJobRepository()
    scheduler = Scheduler(
        repository,
        [ScheduleEntry(name="cleanup", job_type="maintenance.cleanup", cron="* * * * *")],
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        scheduler.run_due(now=NOW.replace(tzinfo=None))

    result = scheduler.run_due(now=NOW, dry_run=True)
    assert result.planned == 1
    assert result.created == 0
    assert repository.list_jobs() == ()
