"""Build dashboard, set, region, retailer, and batch summaries."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import datetime

from pokecrack_worker.statistics import BaselineCatalog, SignalThresholds, analyze_signal

from .eligibility import SUPPORTED_MVP_PRODUCT_TYPES, is_statistics_eligible
from .models import (
    AggregateRecord,
    AggregateScope,
    AggregationRun,
    OpeningObservation,
    PublicAggregateSummary,
)
from .repository import InMemoryAggregateRepository

_SCOPE_ATTRIBUTE = {
    AggregateScope.SET: "set_id",
    AggregateScope.REGION: "region_id",
    AggregateScope.RETAILER: "retailer_id",
    AggregateScope.BATCH: "batch_code",
}


def _is_public_observation(opening: OpeningObservation) -> bool:
    in_scope = (
        opening.language.strip().casefold() == "en"
        and opening.country_code == "AU"
        and opening.product_type in SUPPORTED_MVP_PRODUCT_TYPES
    )
    if not in_scope:
        return False
    if is_statistics_eligible(opening):
        return True
    return (
        opening.source_status in {"accepted", "activity_only"}
        and opening.validation_status in {"accepted", "activity_only"}
        and (
            opening.source_status == "activity_only" or opening.validation_status == "activity_only"
        )
        and opening.duplicate_of is None
        and not opening.duplicate_suspected
    )


def _unique_openings(openings: Iterable[OpeningObservation]) -> tuple[OpeningObservation, ...]:
    by_id: dict[str, OpeningObservation] = {}
    conflicting_ids: set[str] = set()
    for opening in openings:
        existing = by_id.get(opening.id)
        if existing is None:
            by_id[opening.id] = opening
        elif existing != opening:
            conflicting_ids.add(opening.id)
    return tuple(
        opening for opening_id, opening in by_id.items() if opening_id not in conflicting_ids
    )


def build_public_summary(record: AggregateRecord) -> PublicAggregateSummary:
    analysis = record.analysis
    return PublicAggregateSummary(
        scope=record.scope,
        id=record.key,
        version=record.version,
        packs_observed=record.packs_observed,
        openings=record.opening_count,
        independent_sources=record.source_count,
        hit_rate=analysis.published_rate,
        posterior_mean=(analysis.posterior_mean if analysis.published_rate is not None else None),
        credible_interval=analysis.published_interval,
        delta_from_baseline=analysis.delta_from_baseline,
        baseline_rate=(
            analysis.posterior.baseline_rate if analysis.published_rate is not None else None
        ),
        signal_label=analysis.status.value,
        activity_observations=record.activity_observations,
        first_observed_at=record.first_observed_at,
        last_observed_at=record.last_observed_at,
        updated_at=record.updated_at,
        is_fixture=record.is_fixture,
    )


class AggregationService:
    def __init__(
        self,
        repository: InMemoryAggregateRepository,
        *,
        baseline_rate: float,
        baseline_catalog: BaselineCatalog | None = None,
        baseline_version: str | None = None,
        thresholds: SignalThresholds | None = None,
    ) -> None:
        self.repository = repository
        self.baseline_rate = baseline_rate
        self.baseline_catalog = baseline_catalog
        self.baseline_version = baseline_version
        self.thresholds = thresholds or SignalThresholds()

    def aggregate_all(
        self,
        openings: Iterable[OpeningObservation],
        *,
        now: datetime,
        version: str,
        dry_run: bool = False,
    ) -> AggregationRun:
        materialized = _unique_openings(openings)
        records: list[AggregateRecord] = []
        for scope in AggregateScope:
            records.extend(self._build_scope(materialized, scope=scope, now=now, version=version))
        if not dry_run:
            for record in records:
                self.repository.upsert(record)
                self.repository.upsert_public(build_public_summary(record))
        return AggregationRun(
            records=tuple(records),
            upserted=len(records),
            public_upserted=len(records),
            dry_run=dry_run,
        )

    def aggregate_dashboard(
        self,
        openings: Iterable[OpeningObservation],
        *,
        now: datetime,
        version: str,
        dry_run: bool = False,
    ) -> AggregationRun:
        return self._aggregate_one_scope(
            openings,
            scope=AggregateScope.DASHBOARD,
            now=now,
            version=version,
            dry_run=dry_run,
        )

    def aggregate_sets(
        self,
        openings: Iterable[OpeningObservation],
        *,
        now: datetime,
        version: str,
        dry_run: bool = False,
    ) -> AggregationRun:
        return self._aggregate_one_scope(
            openings,
            scope=AggregateScope.SET,
            now=now,
            version=version,
            dry_run=dry_run,
        )

    def aggregate_regions(
        self,
        openings: Iterable[OpeningObservation],
        *,
        now: datetime,
        version: str,
        dry_run: bool = False,
    ) -> AggregationRun:
        return self._aggregate_one_scope(
            openings,
            scope=AggregateScope.REGION,
            now=now,
            version=version,
            dry_run=dry_run,
        )

    def aggregate_retailers(
        self,
        openings: Iterable[OpeningObservation],
        *,
        now: datetime,
        version: str,
        dry_run: bool = False,
    ) -> AggregationRun:
        return self._aggregate_one_scope(
            openings,
            scope=AggregateScope.RETAILER,
            now=now,
            version=version,
            dry_run=dry_run,
        )

    def aggregate_batches(
        self,
        openings: Iterable[OpeningObservation],
        *,
        now: datetime,
        version: str,
        dry_run: bool = False,
    ) -> AggregationRun:
        return self._aggregate_one_scope(
            openings,
            scope=AggregateScope.BATCH,
            now=now,
            version=version,
            dry_run=dry_run,
        )

    def _aggregate_one_scope(
        self,
        openings: Iterable[OpeningObservation],
        *,
        scope: AggregateScope,
        now: datetime,
        version: str,
        dry_run: bool,
    ) -> AggregationRun:
        records = self._build_scope(
            _unique_openings(openings), scope=scope, now=now, version=version
        )
        if not dry_run:
            for record in records:
                self.repository.upsert(record)
                self.repository.upsert_public(build_public_summary(record))
        return AggregationRun(
            records=records,
            upserted=len(records),
            public_upserted=len(records),
            dry_run=dry_run,
        )

    def _build_scope(
        self,
        openings: Sequence[OpeningObservation],
        *,
        scope: AggregateScope,
        now: datetime,
        version: str,
    ) -> tuple[AggregateRecord, ...]:
        groups: dict[str, list[OpeningObservation]] = defaultdict(list)
        public_openings = tuple(opening for opening in openings if _is_public_observation(opening))
        if scope is AggregateScope.DASHBOARD:
            if public_openings:
                groups["all"].extend(public_openings)
        else:
            attribute = _SCOPE_ATTRIBUTE[scope]
            for opening in public_openings:
                key = getattr(opening, attribute)
                if key is not None and str(key).strip():
                    groups[str(key)].append(opening)
        return tuple(
            self._build_record(scope, key, group, now=now, version=version)
            for key, group in sorted(groups.items())
        )

    def _build_record(
        self,
        scope: AggregateScope,
        key: str,
        group: Sequence[OpeningObservation],
        *,
        now: datetime,
        version: str,
    ) -> AggregateRecord:
        eligible = tuple(opening for opening in group if is_statistics_eligible(opening))
        packs = sum(opening.pack_count or 0 for opening in eligible)
        hits = sum(opening.hit_count for opening in eligible)
        sources = len({opening.source_id for opening in eligible})
        activity = sum(
            opening.source_status == "activity_only" or opening.validation_status == "activity_only"
            for opening in group
        )
        baseline_rate = self.baseline_rate
        if self.baseline_catalog is not None and packs > 0:
            weighted_baseline = 0.0
            for opening in eligible:
                selection = self.baseline_catalog.resolve(
                    opening.set_id or "",
                    language=opening.language,
                    product_type=opening.product_type,
                    version=self.baseline_version,
                )
                weighted_baseline += selection.baseline.rate * (opening.pack_count or 0)
            baseline_rate = weighted_baseline / packs
        analysis = analyze_signal(
            hits=hits,
            packs=packs,
            source_count=sources,
            baseline_rate=baseline_rate,
            thresholds=self.thresholds,
        )
        observed = [opening.observed_at for opening in group]
        return AggregateRecord(
            scope=scope,
            key=key,
            version=version,
            packs_observed=packs,
            opening_count=len(eligible),
            hit_count=hits,
            source_count=sources,
            activity_observations=activity,
            first_observed_at=min(observed),
            last_observed_at=max(observed),
            analysis=analysis,
            updated_at=now,
            is_fixture=any(opening.is_fixture for opening in group),
        )
