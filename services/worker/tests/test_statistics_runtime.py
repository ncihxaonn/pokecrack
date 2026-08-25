from __future__ import annotations

import pytest

from pokecrack_worker.statistics import (
    Baseline,
    BaselineCatalog,
    BaselineLevel,
    SignalStatus,
    SignalThresholds,
    analyze_signal,
    beta_quantile,
    classify_signal_status,
    empirical_bayes_posterior,
    regularized_beta_cdf,
)


@pytest.mark.parametrize(
    ("x", "alpha", "beta", "expected"),
    [
        (0.25, 1.0, 1.0, 0.25),
        (0.4, 2.0, 1.0, 0.16),
        (0.4, 1.0, 2.0, 0.64),
        (0.5, 2.0, 2.0, 0.5),
    ],
)
def test_regularized_beta_cdf_matches_simple_closed_forms(
    x: float, alpha: float, beta: float, expected: float
) -> None:
    assert regularized_beta_cdf(x, alpha, beta) == pytest.approx(expected, abs=1e-12)


def test_beta_quantile_inverts_cdf_including_known_closed_form() -> None:
    assert beta_quantile(0.9, 1.0, 1.0) == pytest.approx(0.9, abs=1e-10)
    assert beta_quantile(0.25, 2.0, 1.0) == pytest.approx(0.5, abs=1e-10)
    for alpha, beta, probability in ((0.5, 0.5, 0.05), (25.0, 80.0, 0.95)):
        quantile = beta_quantile(probability, alpha, beta)
        assert regularized_beta_cdf(quantile, alpha, beta) == pytest.approx(probability, abs=1e-10)


def test_empirical_bayes_posterior_reports_mean_interval_and_both_probabilities() -> None:
    result = empirical_bayes_posterior(
        hits=1,
        packs=2,
        baseline_rate=0.5,
        prior_strength=2.0,
        practical_uplift=0.2,
    )

    assert result.alpha == pytest.approx(2.0)
    assert result.beta == pytest.approx(2.0)
    assert result.mean == pytest.approx(0.5)
    assert result.credible_interval.level == 0.9
    assert result.credible_interval.low == pytest.approx(0.1353503622, abs=1e-9)
    assert result.credible_interval.high == pytest.approx(0.8646496378, abs=1e-9)
    assert result.probability_above_baseline == pytest.approx(0.5, abs=1e-12)
    assert result.practical_threshold == pytest.approx(0.6)
    assert result.probability_above_practical == pytest.approx(0.352, abs=1e-12)


def test_baseline_fallback_is_exactly_specific_then_language_then_set() -> None:
    catalog = BaselineCatalog(
        [
            Baseline("set-en-box", "set-a", 0.10, language="en", product_type="box"),
            Baseline("set-en", "set-a", 0.08, language="en"),
            Baseline("set", "set-a", 0.06),
        ]
    )

    exact = catalog.resolve("set-a", language="en", product_type="box")
    language = catalog.resolve("set-a", language="en", product_type="bundle")
    broad = catalog.resolve("set-a", language="fr", product_type="box")

    assert exact.baseline.id == "set-en-box"
    assert exact.level is BaselineLevel.SET_LANGUAGE_PRODUCT_TYPE
    assert language.baseline.id == "set-en"
    assert language.level is BaselineLevel.SET_LANGUAGE
    assert broad.baseline.id == "set"
    assert broad.level is BaselineLevel.SET
    with pytest.raises(LookupError):
        catalog.resolve("unknown", language="en", product_type="box")


def test_baseline_catalog_requires_explicit_version_when_scopes_repeat() -> None:
    catalog = BaselineCatalog(
        [
            Baseline("set-v1", "set-a", 0.1, version="v1"),
            Baseline("set-v2", "set-a", 0.2, version="v2"),
        ]
    )

    assert (
        catalog.resolve(
            "set-a", language="en", product_type="booster_box", version="v2"
        ).baseline.rate
        == 0.2
    )
    with pytest.raises(LookupError, match="version"):
        catalog.resolve("set-a", language="en", product_type="booster_box")


def test_signal_thresholds_and_status_boundaries_are_exact() -> None:
    thresholds = SignalThresholds()
    assert thresholds.prior_strength == 50.0
    assert thresholds.min_rate_display_packs == 30
    assert thresholds.min_signal_packs == 200
    assert thresholds.min_signal_sources == 3
    assert thresholds.min_watch_probability == 0.90
    assert thresholds.min_anomaly_probability == 0.95
    assert thresholds.min_practical_uplift == 0.20
    assert [status.value for status in SignalStatus] == [
        "Insufficient sample",
        "No significant signal",
        "Watch",
        "Possible anomaly",
    ]

    assert classify_signal_status(29, 3, 1.0, 1.0, thresholds) is SignalStatus.INSUFFICIENT_SAMPLE
    assert classify_signal_status(30, 3, 1.0, 1.0, thresholds) is SignalStatus.NO_SIGNIFICANT_SIGNAL
    assert (
        classify_signal_status(199, 3, 1.0, 1.0, thresholds) is SignalStatus.NO_SIGNIFICANT_SIGNAL
    )
    assert classify_signal_status(200, 2, 1.0, 1.0, thresholds) is SignalStatus.INSUFFICIENT_SAMPLE
    assert (
        classify_signal_status(200, 3, 0.899999, 0.899999, thresholds)
        is SignalStatus.NO_SIGNIFICANT_SIGNAL
    )
    assert (
        classify_signal_status(200, 3, 1.0, 0.899999, thresholds)
        is SignalStatus.NO_SIGNIFICANT_SIGNAL
    )
    assert classify_signal_status(200, 3, 0.5, 0.90, thresholds) is SignalStatus.WATCH
    assert classify_signal_status(200, 3, 0.99, 0.95, thresholds) is SignalStatus.POSSIBLE_ANOMALY


def test_analyze_signal_withholds_inference_until_three_independent_sources() -> None:
    analysis = analyze_signal(
        hits=50,
        packs=200,
        source_count=2,
        baseline_rate=0.1,
        thresholds=SignalThresholds(),
    )

    assert analysis.status is SignalStatus.INSUFFICIENT_SAMPLE
    assert analysis.published_rate is None
    assert analysis.published_interval is None
    assert analysis.delta_from_baseline is None


def test_analyze_signal_hides_tiny_rates_and_uses_practical_posterior_probability() -> None:
    hidden = analyze_signal(
        hits=2,
        packs=29,
        source_count=1,
        baseline_rate=0.1,
        thresholds=SignalThresholds(),
    )
    anomaly = analyze_signal(
        hits=50,
        packs=200,
        source_count=3,
        baseline_rate=0.1,
        thresholds=SignalThresholds(),
    )

    assert hidden.published_rate is None
    assert hidden.published_interval is None
    assert hidden.status is SignalStatus.INSUFFICIENT_SAMPLE
    assert anomaly.published_rate == pytest.approx(50 / 200)
    assert anomaly.posterior_mean == pytest.approx(anomaly.posterior.mean)
    assert anomaly.posterior_mean != pytest.approx(anomaly.published_rate)
    assert anomaly.posterior.probability_above_practical >= 0.95
    assert anomaly.status is SignalStatus.POSSIBLE_ANOMALY


def test_signal_boundary_matrix_is_conservative() -> None:
    thresholds = SignalThresholds()
    assert (
        classify_signal_status(
            packs=29,
            source_count=3,
            probability_above_baseline=1.0,
            probability_above_practical_uplift=1.0,
            thresholds=thresholds,
        )
        is SignalStatus.INSUFFICIENT_SAMPLE
    )
    assert (
        classify_signal_status(
            packs=30,
            source_count=3,
            probability_above_baseline=1.0,
            probability_above_practical_uplift=1.0,
            thresholds=thresholds,
        )
        is SignalStatus.NO_SIGNIFICANT_SIGNAL
    )
    assert (
        classify_signal_status(
            packs=199,
            source_count=3,
            probability_above_baseline=1.0,
            probability_above_practical_uplift=1.0,
            thresholds=thresholds,
        )
        is SignalStatus.NO_SIGNIFICANT_SIGNAL
    )
    assert (
        classify_signal_status(
            packs=200,
            source_count=2,
            probability_above_baseline=1.0,
            probability_above_practical_uplift=1.0,
            thresholds=thresholds,
        )
        is SignalStatus.INSUFFICIENT_SAMPLE
    )
    assert (
        classify_signal_status(
            packs=200,
            source_count=3,
            probability_above_baseline=0.90,
            probability_above_practical_uplift=0.94,
            thresholds=thresholds,
        )
        is SignalStatus.WATCH
    )
    assert (
        classify_signal_status(
            packs=200,
            source_count=3,
            probability_above_baseline=0.90,
            probability_above_practical_uplift=0.95,
            thresholds=thresholds,
        )
        is SignalStatus.POSSIBLE_ANOMALY
    )
