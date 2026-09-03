from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event

from pokecrack_worker.composition import (
    BLUESKY_JETSTREAM_JOB_TYPE,
    MASTODON_PUBLIC_HASHTAG_JOB_TYPE,
)
from pokecrack_worker.jobs import InMemoryJobRepository, Job, JobStatus
from pokecrack_worker.runtime import RuntimeStatus, WorkerRuntime

NOW = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)


def test_bluesky_lane_advances_while_mastodon_handler_is_saturated() -> None:
    """A slow public-source handler cannot starve the source-scoped lane."""

    repository = InMemoryJobRepository()
    mastodon_job = repository.enqueue(
        MASTODON_PUBLIC_HASHTAG_JOB_TYPE,
        now=NOW,
        priority=100,
    )
    bluesky_job = repository.enqueue(
        BLUESKY_JETSTREAM_JOB_TYPE,
        now=NOW,
        priority=-50,
    )
    mastodon_started = Event()
    release_mastodon = Event()
    bluesky_claimed = Event()

    def slow_mastodon(_job: Job) -> None:
        mastodon_started.set()
        assert release_mastodon.wait(timeout=5), "Mastodon fixture did not release"

    def fast_bluesky(_job: Job) -> None:
        bluesky_claimed.set()

    mastodon_runtime = WorkerRuntime(
        repository,
        handlers={MASTODON_PUBLIC_HASHTAG_JOB_TYPE: slow_mastodon},
        worker_id="collector-mastodon-1",
        lease_for=timedelta(minutes=5),
        clock=lambda: NOW,
    )
    bluesky_runtime = WorkerRuntime(
        repository,
        handlers={BLUESKY_JETSTREAM_JOB_TYPE: fast_bluesky},
        worker_id="bluesky-collector-1",
        lease_for=timedelta(minutes=5),
        clock=lambda: NOW,
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        mastodon_future = executor.submit(mastodon_runtime.run_once)
        assert mastodon_started.wait(timeout=5), "Mastodon job was not claimed"

        bluesky_result = bluesky_runtime.run_once()
        assert bluesky_result.status is RuntimeStatus.COMPLETED
        assert bluesky_result.job_id == bluesky_job.id
        assert bluesky_claimed.is_set()
        assert repository.get(bluesky_job.id).status is JobStatus.COMPLETED  # type: ignore[union-attr]
        assert repository.get(mastodon_job.id).status is JobStatus.RUNNING  # type: ignore[union-attr]

        release_mastodon.set()
        assert mastodon_future.result(timeout=5).status is RuntimeStatus.COMPLETED

    assert repository.get(mastodon_job.id).status is JobStatus.COMPLETED  # type: ignore[union-attr]
