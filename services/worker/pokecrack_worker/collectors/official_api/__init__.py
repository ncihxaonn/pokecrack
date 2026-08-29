"""Official, metadata-only API collectors."""

from .postgres import (
    PostgresPublicStudyGate,
    PostgresTCGdexCheckpointRepository,
    PostgresYouTubeDiscoveryGate,
    PublicStudyRequestDeferred,
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
    MatonYouTubeTransport,
    YouTubeDataClient,
    YouTubeTransport,
)

__all__ = [
    "HTTPXTCGdexTransport",
    "HTTPXYouTubeTransport",
    "InMemoryTCGdexSetsCache",
    "MatonYouTubeTransport",
    "PostgresTCGdexCheckpointRepository",
    "PostgresPublicStudyGate",
    "PostgresYouTubeDiscoveryGate",
    "TCGdexRequestDeferred",
    "PublicStudyRequestDeferred",
    "TCGdexSetBrief",
    "TCGdexSetsClient",
    "TCGdexSetsCheckpoint",
    "TCGdexSetsSyncAttempt",
    "TCGdexSetsSyncOutcome",
    "TCGdexSetsSyncResult",
    "YouTubeDataClient",
    "YouTubeRequestDeferred",
    "YouTubeTransport",
]
