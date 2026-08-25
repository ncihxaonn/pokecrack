"""Private aggregation inputs and public-safe result contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from pokecrack_worker.statistics import CredibleInterval, SignalAnalysis


class AggregateScope(StrEnum):
    DASHBOARD = "dashboard"
    SET = "set"
    REGION = "region"
    RETAILER = "retailer"
    BATCH = "batch"


@dataclass(frozen=True, slots=True)
class OpeningObservation:
    id: str
    source_id: str
    set_id: str | None
    pack_count: int | None
    hit_count: int = 0
    source_status: str = "accepted"
    validation_status: str = "accepted"
    complete_opening: bool = False
    eligible_for_statistics: bool = False
    evidence_tier: str = "D"
    duplicate_of: str | None = None
    duplicate_suspected: bool = False
    catalog_mapped: bool = True
    language: str = "en"
    product_type: str = "unknown"
    country_code: str = "AU"
    region_id: str | None = None
    retailer_id: str | None = None
    batch_code: str | None = None
    observed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    opened_at: datetime | None = None
    is_fixture: bool = False

    def __post_init__(self) -> None:
        if not self.id or not self.source_id:
            raise ValueError("opening and source ids are required")
        if self.pack_count is not None and self.pack_count < 1:
            raise ValueError("pack_count must be positive when present")
        if self.hit_count < 0:
            raise ValueError("hit_count must be non-negative")
        if self.pack_count is not None and self.hit_count > self.pack_count:
            raise ValueError("hit_count must not exceed pack_count")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class AggregateRecord:
    scope: AggregateScope
    key: str
    version: str
    packs_observed: int
    opening_count: int
    hit_count: int
    source_count: int
    activity_observations: int
    first_observed_at: datetime
    last_observed_at: datetime
    analysis: SignalAnalysis
    updated_at: datetime
    is_fixture: bool = False


@dataclass(frozen=True, slots=True)
class PublicAggregateSummary:
    scope: AggregateScope
    id: str
    version: str
    packs_observed: int
    openings: int
    independent_sources: int
    hit_rate: float | None
    posterior_mean: float | None
    credible_interval: CredibleInterval | None
    delta_from_baseline: float | None
    baseline_rate: float | None
    signal_label: str
    activity_observations: int
    first_observed_at: datetime
    last_observed_at: datetime
    updated_at: datetime
    is_fixture: bool

    def to_dict(self) -> dict[str, object]:
        interval = self.credible_interval
        return {
            "scope": self.scope.value,
            "id": self.id,
            "version": self.version,
            "packsObserved": self.packs_observed,
            "openings": self.openings,
            "independentSources": self.independent_sources,
            "hitRate": self.hit_rate,
            "posteriorMean": self.posterior_mean,
            "credibleInterval": (
                {"low": interval.low, "high": interval.high, "level": interval.level}
                if interval is not None
                else None
            ),
            "deltaFromBaseline": self.delta_from_baseline,
            "baselineRate": self.baseline_rate,
            "signalLabel": self.signal_label,
            "activityObservations": self.activity_observations,
            "firstObservedAt": self.first_observed_at.isoformat(),
            "lastObservedAt": self.last_observed_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "isFixture": self.is_fixture,
        }


@dataclass(frozen=True, slots=True)
class AggregationRun:
    records: tuple[AggregateRecord, ...]
    upserted: int
    public_upserted: int
    dry_run: bool
