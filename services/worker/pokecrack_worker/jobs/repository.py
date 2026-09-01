"""Thread-safe fixture queue with production-equivalent leasing semantics."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime, timedelta
from threading import RLock
from typing import Any
from uuid import uuid4

from .models import (
    BlueskyJetstreamCompletion,
    CompletionEffect,
    Job,
    JobStatus,
    MastodonPublicHashtagCompletion,
    NostrRelayCompletion,
    PublicStudyCompletion,
    TCGdexSetsSyncCompletion,
    YouTubeDiscoveryCompletion,
)


class JobRepositoryError(RuntimeError):
    """Base queue state-transition error."""


class JobNotFoundError(JobRepositoryError):
    """The requested job does not exist."""


class LeaseLostError(JobRepositoryError):
    """The job is no longer running under the expected worker lease."""


class InMemoryJobRepository:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._scheduled_slots: dict[tuple[str, datetime], str] = {}
        self._lock = RLock()

    def enqueue(
        self,
        kind: str,
        payload: Mapping[str, Any] | None = None,
        *,
        priority: int = 0,
        now: datetime,
        max_attempts: int = 5,
        dedupe_key: str | None = None,
        available_at: datetime | None = None,
    ) -> Job:
        with self._lock:
            if dedupe_key is not None:
                for existing in self._jobs.values():
                    if (
                        existing.kind == kind
                        and existing.dedupe_key == dedupe_key
                        and existing.status in {JobStatus.PENDING, JobStatus.RUNNING}
                    ):
                        return existing
            job = Job(
                id=str(uuid4()),
                kind=kind,
                payload=dict(payload or {}),
                priority=priority,
                available_at=available_at or now,
                max_attempts=max_attempts,
                dedupe_key=dedupe_key,
                created_at=now,
                updated_at=now,
            )
            self._jobs[job.id] = job
            return job

    def enqueue_scheduled(
        self,
        kind: str,
        payload: Mapping[str, Any] | None = None,
        *,
        schedule_name: str,
        scheduled_for: datetime,
        priority: int = 0,
        now: datetime,
        max_attempts: int = 5,
    ) -> Job:
        """Reserve one durable logical slot even after its job becomes terminal."""

        with self._lock:
            slot_key = (schedule_name, scheduled_for)
            existing_id = self._scheduled_slots.get(slot_key)
            if existing_id is not None:
                return self._jobs[existing_id]
            dedupe_key = f"schedule:{schedule_name}:{scheduled_for.strftime('%Y%m%dT%H%M%SZ')}"
            job = self.enqueue(
                kind,
                payload,
                priority=priority,
                now=now,
                max_attempts=max_attempts,
                dedupe_key=dedupe_key,
            )
            self._scheduled_slots[slot_key] = job.id
            return job

    def lease(
        self,
        worker_id: str,
        *,
        now: datetime,
        lease_for: timedelta,
        kinds: set[str] | None = None,
    ) -> Job | None:
        with self._lock:
            for job_id, job in tuple(self._jobs.items()):
                pending_due = job.status is JobStatus.PENDING and job.available_at <= now
                lease_expired = (
                    job.status is JobStatus.RUNNING
                    and job.lease_expires_at is not None
                    and job.lease_expires_at <= now
                )
                if (pending_due or lease_expired) and job.attempts >= job.max_attempts:
                    self._jobs[job_id] = replace(
                        job,
                        status=JobStatus.DEAD,
                        lease_generation=(
                            job.lease_generation + 1 if lease_expired else job.lease_generation
                        ),
                        leased_by=None,
                        leased_at=None,
                        lease_expires_at=None,
                        heartbeat_at=None,
                        last_error=(
                            "lease_expired_max_attempts"
                            if lease_expired
                            else "max_attempts_exhausted"
                        ),
                        finished_at=now,
                        updated_at=now,
                    )
            due = [
                job
                for job in self._jobs.values()
                if (
                    (job.status is JobStatus.PENDING and job.available_at <= now)
                    or (
                        job.status is JobStatus.RUNNING
                        and job.lease_expires_at is not None
                        and job.lease_expires_at <= now
                    )
                )
                and job.attempts < job.max_attempts
                and (kinds is None or job.kind in kinds)
            ]
            if not due:
                return None
            selected = min(
                due,
                key=lambda job: (
                    -job.priority,
                    job.available_at,
                    job.created_at,
                    job.id,
                ),
            )
            leased = replace(
                selected,
                status=JobStatus.RUNNING,
                attempts=selected.attempts + 1,
                lease_generation=selected.lease_generation + 1,
                leased_by=worker_id,
                leased_at=now,
                lease_expires_at=now + lease_for,
                heartbeat_at=now,
                updated_at=now,
            )
            self._jobs[leased.id] = leased
            return leased

    def heartbeat(
        self,
        job_id: str,
        *,
        worker_id: str,
        lease_generation: int,
        now: datetime,
        lease_for: timedelta,
    ) -> Job:
        with self._lock:
            job = self._active_lease(
                job_id,
                worker_id,
                lease_generation=lease_generation,
                now=now,
            )
            heartbeat = replace(
                job,
                heartbeat_at=now,
                lease_expires_at=now + lease_for,
                updated_at=now,
            )
            self._jobs[job_id] = heartbeat
            return heartbeat

    def pause_for_budget(
        self,
        job_id: str,
        *,
        worker_id: str,
        lease_generation: int,
        now: datetime,
        retry_at: datetime,
    ) -> Job:
        with self._lock:
            job = self._active_lease(
                job_id,
                worker_id,
                lease_generation=lease_generation,
                now=now,
            )
            paused = replace(
                job,
                status=JobStatus.PENDING,
                attempts=max(0, job.attempts - 1),
                available_at=retry_at,
                leased_by=None,
                leased_at=None,
                lease_expires_at=None,
                heartbeat_at=None,
                last_error=None,
                finished_at=None,
                updated_at=now,
            )
            self._jobs[job_id] = paused
            return paused

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
        | BlueskyJetstreamCompletion
        | NostrRelayCompletion
        | MastodonPublicHashtagCompletion
        | None = None,
    ) -> Job:
        with self._lock:
            if effect is not None:
                raise JobRepositoryError(
                    "the in-memory repository cannot commit database completion effects"
                )
            job = self._active_lease(
                job_id,
                worker_id,
                lease_generation=lease_generation,
                now=now,
            )
            completed = replace(
                job,
                status=JobStatus.COMPLETED,
                leased_by=None,
                leased_at=None,
                lease_expires_at=None,
                heartbeat_at=None,
                last_error=None,
                finished_at=now,
                updated_at=now,
            )
            self._jobs[job_id] = completed
            return completed

    def cancel(self, job_id: str, *, now: datetime) -> Job:
        with self._lock:
            try:
                job = self._jobs[job_id]
            except KeyError as error:
                raise JobNotFoundError(job_id) from error
            if job.status in {JobStatus.COMPLETED, JobStatus.DEAD, JobStatus.CANCELLED}:
                raise JobRepositoryError(f"job cannot be cancelled from {job.status.value}")
            cancelled = replace(
                job,
                status=JobStatus.CANCELLED,
                leased_by=None,
                leased_at=None,
                lease_expires_at=None,
                heartbeat_at=None,
                finished_at=now,
                updated_at=now,
            )
            self._jobs[job_id] = cancelled
            return cancelled

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self, *, statuses: set[JobStatus] | None = None) -> tuple[Job, ...]:
        with self._lock:
            return tuple(
                job for job in self._jobs.values() if statuses is None or job.status in statuses
            )

    def counts(self) -> dict[JobStatus, int]:
        with self._lock:
            return {
                status: sum(job.status is status for job in self._jobs.values())
                for status in JobStatus
            }

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
    ) -> Job:
        del error_code
        with self._lock:
            job = self._active_lease(
                job_id,
                worker_id,
                lease_generation=lease_generation,
                now=now,
            )
            exhausted = not retryable or job.attempts >= job.max_attempts
            status = JobStatus.DEAD if exhausted else JobStatus.PENDING
            backoff_seconds = min(3_600, 30 * (2 ** max(0, job.attempts - 1)))
            failed = replace(
                job,
                status=status,
                available_at=(
                    job.available_at if exhausted else now + timedelta(seconds=backoff_seconds)
                ),
                leased_by=None,
                leased_at=None,
                lease_expires_at=None,
                heartbeat_at=None,
                last_error=error[:8_000],
                finished_at=now if exhausted else None,
                updated_at=now,
            )
            self._jobs[job_id] = failed
            return failed

    def retry_failed(self, *, now: datetime, delay: timedelta = timedelta()) -> int:
        retried = 0
        with self._lock:
            for job_id, job in tuple(self._jobs.items()):
                if job.status is not JobStatus.FAILED:
                    continue
                if job.attempts >= job.max_attempts:
                    self._jobs[job_id] = replace(
                        job,
                        status=JobStatus.DEAD,
                        updated_at=now,
                    )
                    continue
                self._jobs[job_id] = replace(
                    job,
                    status=JobStatus.PENDING,
                    available_at=now + delay,
                    finished_at=None,
                    updated_at=now,
                )
                retried += 1
        return retried

    def _active_lease(
        self,
        job_id: str,
        worker_id: str,
        *,
        lease_generation: int,
        now: datetime,
    ) -> Job:
        job = self._leased(job_id, worker_id, lease_generation=lease_generation)
        if job.lease_expires_at is None or job.lease_expires_at <= now:
            raise LeaseLostError(job_id)
        return job

    def _leased(self, job_id: str, worker_id: str, *, lease_generation: int) -> Job:
        try:
            job = self._jobs[job_id]
        except KeyError as error:
            raise JobNotFoundError(job_id) from error
        if (
            job.status is not JobStatus.RUNNING
            or job.leased_by != worker_id
            or job.lease_generation != lease_generation
        ):
            raise LeaseLostError(job_id)
        return job
