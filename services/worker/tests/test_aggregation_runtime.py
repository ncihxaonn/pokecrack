from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from pokecrack_worker.aggregation import (
    AggregateScope,
    AggregationService,
    InMemoryAggregateRepository,
    OpeningObservation,
    build_public_summary,
    is_statistics_eligible,
)
from pokecrack_worker.statistics import Baseline, BaselineCatalog

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)


def _opening(**changes: object) -> OpeningObservation:
    base: dict[str, object] = {
        "id": "opening-1",
        "source_id": "source-1",
        "set_id": "set-a",
        "pack_count": 10,
        "country_code": "AU",
        "hit_count": 2,
        "source_status": "accepted",
        "validation_status": "accepted",
        "complete_opening": True,
        "eligible_for_statistics": True,
        "evidence_tier": "A",
        "duplicate_of": None,
        "duplicate_suspected": False,
        "catalog_mapped": True,
        "language": "en",
        "product_type": "booster_box",
        "observed_at": NOW,
    }
    base.update(changes)
    return OpeningObservation(**base)


def test_eligibility_requires_every_primary_rate_gate() -> None:
    valid = _opening()
    assert is_statistics_eligible(valid)
    for excluded in (
        replace(valid, source_status="activity_only"),
        replace(valid, validation_status="activity_only"),
        replace(valid, complete_opening=False),
        replace(valid, eligible_for_statistics=False),
        replace(valid, evidence_tier="C"),
        replace(valid, duplicate_of="opening-0"),
        replace(valid, duplicate_suspected=True),
        replace(valid, pack_count=None),
        replace(valid, catalog_mapped=False),
        replace(valid, language="fr"),
        replace(valid, country_code=None),
        replace(valid, product_type="other"),
    ):
        assert not is_statistics_eligible(excluded)


@pytest.mark.parametrize("country_code", ["US", "JP", "GB"])
def test_non_australian_openings_remain_private(country_code: str) -> None:
    opening = _opening(country_code=country_code)
    service = AggregationService(InMemoryAggregateRepository(), baseline_rate=0.1)

    assert not is_statistics_eligible(opening)
    assert service.aggregate_sets([opening], now=NOW, version="method-v1").records == ()


def test_unresolved_country_is_neither_rate_eligible_nor_public() -> None:
    opening = _opening(country_code=None)
    service = AggregationService(InMemoryAggregateRepository(), baseline_rate=0.1)

    assert not is_statistics_eligible(opening)
    assert service.aggregate_sets([opening], now=NOW, version="method-v1").records == ()


@pytest.mark.parametrize("country_code", ["USA", "au"])
def test_opening_observation_rejects_malformed_country_codes(country_code: str) -> None:
    with pytest.raises(ValueError, match="country_code"):
        _opening(country_code=country_code)


def test_aggregate_all_is_idempotent_for_every_scope_and_excludes_activity_rates() -> None:
    eligible_a = _opening(
        id="opening-a",
        source_id="source-a",
        pack_count=10,
        hit_count=2,
        region_id="region-au",
        retailer_id="retailer-1",
        batch_code="BATCH-1",
    )
    eligible_b = _opening(
        id="opening-b",
        source_id="source-b",
        pack_count=20,
        hit_count=1,
        evidence_tier="B",
        region_id="region-au",
        retailer_id="retailer-1",
        batch_code="BATCH-1",
    )
    activity = _opening(
        id="activity",
        source_id="source-c",
        pack_count=100,
        hit_count=100,
        source_status="activity_only",
        validation_status="activity_only",
        complete_opening=False,
        eligible_for_statistics=False,
        evidence_tier="D",
        region_id="region-au",
        retailer_id="retailer-1",
        batch_code="BATCH-1",
    )
    duplicate = _opening(
        id="duplicate",
        source_id="source-d",
        pack_count=500,
        hit_count=500,
        duplicate_of="opening-a",
        region_id="region-au",
        retailer_id="retailer-1",
        batch_code="BATCH-1",
    )
    repository = InMemoryAggregateRepository()
    service = AggregationService(repository, baseline_rate=0.1)

    first = service.aggregate_all(
        [eligible_a, eligible_b, activity, duplicate], now=NOW, version="method-v1"
    )
    second = service.aggregate_all(
        [eligible_a, eligible_b, activity, duplicate], now=NOW, version="method-v1"
    )

    assert first.upserted == second.upserted == 5
    assert repository.count == 5
    assert repository.public_count == 5
    for scope, key in (
        (AggregateScope.DASHBOARD, "all"),
        (AggregateScope.SET, "set-a"),
        (AggregateScope.REGION, "region-au"),
        (AggregateScope.RETAILER, "retailer-1"),
        (AggregateScope.BATCH, "BATCH-1"),
    ):
        record = repository.get(scope, key, version="method-v1")
        assert record is not None
        assert record.packs_observed == 30
        assert record.hit_count == 3
        assert record.opening_count == 2
        assert record.source_count == 2
        assert record.activity_observations == 1
        summary = repository.get_public(scope, key, version="method-v1")
        assert summary is not None
        assert summary.packs_observed == 30
        assert summary.openings == 2
        assert summary.hit_rate is None
        assert summary.posterior_mean is None
        assert summary.credible_interval is None
        assert summary.delta_from_baseline is None
        assert summary.baseline_rate is None
        assert summary.signal_label == "Insufficient sample"


def test_aggregation_counts_the_same_opening_identifier_only_once() -> None:
    opening = _opening()
    repository = InMemoryAggregateRepository()
    service = AggregationService(repository, baseline_rate=0.1)

    run = service.aggregate_sets([opening, opening], now=NOW, version="method-v1")

    assert len(run.records) == 1
    assert run.records[0].packs_observed == 10
    assert run.records[0].opening_count == 1


def test_aggregation_excludes_conflicting_records_with_the_same_identifier() -> None:
    first = _opening(pack_count=10, hit_count=2)
    conflicting = _opening(pack_count=20, hit_count=20)
    service = AggregationService(InMemoryAggregateRepository(), baseline_rate=0.1)

    run = service.aggregate_sets([first, conflicting], now=NOW, version="method-v1")

    assert run.records == ()


def test_out_of_scope_activity_does_not_create_public_observations() -> None:
    activity = _opening(
        source_status="activity_only",
        validation_status="activity_only",
        complete_opening=False,
        eligible_for_statistics=False,
        evidence_tier="D",
        country_code="US",
    )
    service = AggregationService(InMemoryAggregateRepository(), baseline_rate=0.1)

    run = service.aggregate_sets([activity], now=NOW, version="method-v1")

    assert run.records == ()


def test_rejected_records_do_not_create_public_aggregate_observations() -> None:
    rejected = _opening(
        source_status="rejected",
        validation_status="rejected",
        complete_opening=False,
        eligible_for_statistics=False,
        evidence_tier="D",
    )
    repository = InMemoryAggregateRepository()
    service = AggregationService(repository, baseline_rate=0.1)

    run = service.aggregate_sets([rejected], now=NOW, version="method-v1")

    assert run.records == ()
    assert repository.count == 0
    assert repository.public_count == 0


def test_aggregation_uses_the_versioned_baseline_fallback_catalog() -> None:
    opening = _opening(language="en", product_type="booster_box")
    catalog = BaselineCatalog(
        [
            Baseline(
                "specific",
                "set-a",
                0.2,
                language="en",
                product_type="booster_box",
                version="baseline-v1",
            ),
            Baseline("set", "set-a", 0.05, version="baseline-v1"),
        ]
    )
    service = AggregationService(
        InMemoryAggregateRepository(),
        baseline_rate=0.9,
        baseline_catalog=catalog,
    )

    run = service.aggregate_sets([opening], now=NOW, version="method-v1")

    assert run.records[0].analysis.posterior.baseline_rate == 0.2


def test_aggregation_selects_an_explicit_baseline_version() -> None:
    catalog = BaselineCatalog(
        [
            Baseline("set-v1", "set-a", 0.1, version="v1"),
            Baseline("set-v2", "set-a", 0.2, version="v2"),
        ]
    )
    service = AggregationService(
        InMemoryAggregateRepository(),
        baseline_rate=0.9,
        baseline_catalog=catalog,
        baseline_version="v2",
    )

    run = service.aggregate_sets([_opening()], now=NOW, version="method-v1")

    assert run.records[0].analysis.posterior.baseline_rate == 0.2


def test_public_summary_publishes_the_baseline_used_for_the_signal() -> None:
    service = AggregationService(InMemoryAggregateRepository(), baseline_rate=0.1)
    record = service.aggregate_sets(
        [
            _opening(
                id=f"opening-{index}",
                source_id=f"source-{index}",
                pack_count=10,
                hit_count=2,
            )
            for index in range(3)
        ],
        now=NOW,
        version="method-v1",
    ).records[0]

    payload = build_public_summary(record).to_dict()

    assert payload["baselineRate"] == 0.1


def test_public_summary_distinguishes_posterior_mean_from_observed_rate() -> None:
    service = AggregationService(InMemoryAggregateRepository(), baseline_rate=0.1)
    record = service.aggregate_sets(
        [
            _opening(
                id=f"opening-{index}",
                source_id=f"source-{index}",
                pack_count=10,
                hit_count=2,
            )
            for index in range(3)
        ],
        now=NOW,
        version="method-v1",
    ).records[0]

    payload = build_public_summary(record).to_dict()

    assert payload["posteriorMean"] == record.analysis.posterior_mean
    assert payload["posteriorMean"] != payload["hitRate"]


def test_public_summary_includes_the_independent_source_count() -> None:
    service = AggregationService(InMemoryAggregateRepository(), baseline_rate=0.1)
    record = service.aggregate_sets([_opening()], now=NOW, version="method-v1").records[0]

    payload = build_public_summary(record).to_dict()

    assert payload["independentSources"] == 1


def test_scope_dry_run_builds_public_safe_activity_summary_without_writes() -> None:
    activity = _opening(
        source_status="activity_only",
        validation_status="activity_only",
        eligible_for_statistics=False,
        complete_opening=False,
        evidence_tier="D",
        pack_count=None,
        hit_count=0,
        is_fixture=True,
    )
    repository = InMemoryAggregateRepository()
    service = AggregationService(repository, baseline_rate=0.1)

    run = service.aggregate_sets([activity], now=NOW, version="method-v1", dry_run=True)

    assert run.dry_run
    assert repository.count == repository.public_count == 0
    assert len(run.records) == 1
    record = run.records[0]
    assert record.packs_observed == 0
    assert record.activity_observations == 1
    service.repository.upsert(record)
    summary = build_public_summary(record)
    payload = summary.to_dict()
    assert payload["hitRate"] is None
    assert payload["baselineRate"] is None
    assert payload["posteriorMean"] is None
    assert payload["credibleInterval"] is None
    assert payload["deltaFromBaseline"] is None
    assert payload["signalLabel"] == "Insufficient sample"
    assert payload["isFixture"] is True
