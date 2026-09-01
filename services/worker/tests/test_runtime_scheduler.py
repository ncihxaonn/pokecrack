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


def test_scheduler_slot_remains_reserved_after_the_job_completes() -> None:
    repository = InMemoryJobRepository()
    entry = ScheduleEntry(name="cleanup", job_type="maintenance.cleanup", cron="* * * * *")
    scheduler = Scheduler(repository, [entry])

    scheduler.run_due(now=NOW)
    claimed = repository.lease("watchdog", now=NOW, lease_for=timedelta(minutes=5))
    assert claimed is not None
    repository.complete(
        claimed.id,
        worker_id="watchdog",
        lease_generation=claimed.lease_generation,
        now=NOW,
    )

    scheduler.run_due(now=NOW + timedelta(seconds=30))

    jobs = repository.list_jobs()
    assert len(jobs) == 1
    assert jobs[0].status is JobStatus.COMPLETED


def test_cron_catch_up_uses_the_latest_bounded_slot_without_wall_clock_phase() -> None:
    entry = ScheduleEntry(
        name="catalog_sync",
        job_type="catalog.tcgdex.sets.sync",
        cron="0 2,14 * * *",
        catch_up_within=timedelta(hours=36),
        catch_up_check_interval=timedelta(hours=1),
    )

    assert entry.slot(NOW.replace(hour=3)) == NOW.replace(hour=2)
    assert entry.slot(NOW.replace(hour=3, minute=30, second=17)) == NOW.replace(hour=2)
    assert entry.slot(NOW.replace(hour=3, minute=31, second=17)) == NOW.replace(hour=2)
    assert entry.slot(NOW.replace(hour=2)) == NOW.replace(hour=2)
    assert entry.slot(NOW.replace(hour=14)) == NOW.replace(hour=14)
    assert entry.slot(NOW.replace(hour=22, minute=41)) == NOW.replace(hour=14)
    assert entry.slot(NOW.replace(hour=1)) == NOW.replace(hour=14) - timedelta(days=1)
    assert entry.slot(NOW.replace(hour=2) + timedelta(days=2, hours=13)) == NOW.replace(
        hour=14
    ) + timedelta(days=2)


def test_catalog_recovery_window_creates_one_durable_job_per_slot() -> None:
    repository = InMemoryJobRepository()
    entry = ScheduleEntry(
        name="catalog_sync",
        job_type="catalog.tcgdex.sets.sync",
        cron="0 2,14 * * *",
        catch_up_within=timedelta(hours=36),
        catch_up_check_interval=timedelta(hours=1),
    )
    scheduler = Scheduler(repository, [entry])

    first = scheduler.run_due(now=NOW.replace(hour=2))
    same_slot = scheduler.run_due(now=NOW.replace(hour=2, second=30))
    recovery = scheduler.run_due(now=NOW.replace(hour=14))

    assert first.due_names == ("catalog_sync",)
    assert same_slot.due_names == ("catalog_sync",)
    assert recovery.due_names == ("catalog_sync",)
    jobs = repository.list_jobs()
    assert len(jobs) == 2
    assert len({job.id for job in jobs}) == 2
    assert {job.dedupe_key for job in jobs} == {
        "schedule:catalog_sync:20260825T020000Z",
        "schedule:catalog_sync:20260825T140000Z",
    }


def test_cron_catch_up_configuration_is_strict_and_bounded() -> None:
    with pytest.raises(ValueError, match="both"):
        ScheduleEntry(
            name="catalog_sync",
            job_type="catalog.tcgdex.sets.sync",
            cron="0 2 * * *",
            catch_up_within=timedelta(hours=36),
        )
    with pytest.raises(ValueError, match="cannot exceed"):
        ScheduleEntry(
            name="catalog_sync",
            job_type="catalog.tcgdex.sets.sync",
            cron="0 2 * * *",
            catch_up_within=timedelta(minutes=30),
            catch_up_check_interval=timedelta(hours=1),
        )
    with pytest.raises(ValueError, match="36 hours"):
        ScheduleEntry(
            name="catalog_sync",
            job_type="catalog.tcgdex.sets.sync",
            cron="0 2 * * *",
            catch_up_within=timedelta(hours=37),
            catch_up_check_interval=timedelta(hours=1),
        )


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
