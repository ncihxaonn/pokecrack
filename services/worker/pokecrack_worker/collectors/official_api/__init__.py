"""Official, metadata-only API collectors."""

from .postgres import (
    PostgresTCGdexCheckpointRepository,
    PostgresYouTubeDiscoveryGate,
    TCGdexRequestDeferred,
    TCGdexSetsCheckpoint,
    YouTubeRequestDeferred,
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
from .youtube import (
    HTTPXYouTubeTransport,
    YouTubeDataClient,
    YouTubeDiscoveryResult,
    YouTubeTransport,
)

__all__ = [
    "HTTPXTCGdexTransport",
    "HTTPXYouTubeTransport",
    "InMemoryTCGdexSetsCache",
    "PostgresTCGdexCheckpointRepository",
    "PostgresYouTubeDiscoveryGate",
    "TCGdexRequestDeferred",
    "TCGdexSetBrief",
    "TCGdexSetsClient",
    "TCGdexSetsCheckpoint",
    "TCGdexSetsSyncAttempt",
    "TCGdexSetsSyncOutcome",
    "TCGdexSetsSyncResult",
    "YouTubeDataClient",
    "YouTubeDiscoveryResult",
    "YouTubeRequestDeferred",
    "YouTubeTransport",
]
