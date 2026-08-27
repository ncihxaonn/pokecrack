"""Official, metadata-only API collectors."""

from .postgres import (
    PostgresTCGdexCheckpointRepository,
    TCGdexRequestDeferred,
    TCGdexSetsCheckpoint,
)
from .tcgdex import (
    HTTPXTCGdexTransport,
    InMemoryTCGdexSetsCache,
    TCGdexSetBrief,
    TCGdexSetsClient,
    TCGdexSetsSyncAttempt,
    TCGdexSetsSyncOutcome,
    TCGdexSetsSyncResult,
)
from .youtube import YouTubeDataClient, YouTubeDiscoveryResult

__all__ = [
    "HTTPXTCGdexTransport",
    "InMemoryTCGdexSetsCache",
    "PostgresTCGdexCheckpointRepository",
    "TCGdexRequestDeferred",
    "TCGdexSetBrief",
    "TCGdexSetsClient",
    "TCGdexSetsCheckpoint",
    "TCGdexSetsSyncAttempt",
    "TCGdexSetsSyncOutcome",
    "TCGdexSetsSyncResult",
    "YouTubeDataClient",
    "YouTubeDiscoveryResult",
]
