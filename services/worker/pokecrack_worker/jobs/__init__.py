"""PostgreSQL-backed and fixture-safe background job queue."""

from .models import (
    CompletionEffect,
    Job,
    JobStatus,
    PublicStudyCompletion,
    TCGdexSetsSyncCompletion,
    TCGdexSetWrite,
    TCGdexSyncOutcome,
    YouTubeDiscoveryCompletion,
    YouTubeSourceItemWrite,
)
from .postgres import CLAIM_SQL, PostgresJobRepository, QueryExecutor
from .repository import (
    InMemoryJobRepository,
    JobNotFoundError,
    JobRepositoryError,
    LeaseLostError,
)

__all__ = [
    "CLAIM_SQL",
    "CompletionEffect",
    "InMemoryJobRepository",
    "Job",
    "JobNotFoundError",
    "JobRepositoryError",
    "JobStatus",
    "LeaseLostError",
    "PostgresJobRepository",
    "PublicStudyCompletion",
    "QueryExecutor",
    "TCGdexSetsSyncCompletion",
    "TCGdexSetWrite",
    "TCGdexSyncOutcome",
    "YouTubeDiscoveryCompletion",
    "YouTubeSourceItemWrite",
]
