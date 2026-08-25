"""Conservative sample and posterior-probability signal thresholds."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, Self

from .empirical import CredibleInterval, PosteriorEstimate, empirical_bayes_posterior


class SignalStatus(StrEnum):
    INSUFFICIENT_SAMPLE = "Insufficient sample"
    NO_SIGNIFICANT_SIGNAL = "No significant signal"
    WATCH = "Watch"
    POSSIBLE_ANOMALY = "Possible anomaly"

    @property
    def slug(self) -> str:
        return self.value.casefold().replace(" ", "_")


class ThresholdSettings(Protocol):
    bayes_prior_strength: float
    min_rate_display_packs: int
    min_signal_packs: int
    min_signal_sources: int
    min_watch_probability: float
    min_anomaly_probability: float
    min_practical_uplift: float


@dataclass(frozen=True, slots=True)
class SignalThresholds:
    prior_strength: float = 50.0
    min_rate_display_packs: int = 30
    min_signal_packs: int = 200
    min_signal_sources: int = 3
    min_watch_probability: float = 0.90
    min_anomaly_probability: float = 0.95
    min_practical_uplift: float = 0.20

    def __post_init__(self) -> None:
        if not math.isfinite(self.prior_strength) or self.prior_strength <= 0:
            raise ValueError("prior_strength must be positive")
        if (
            min(
                self.min_rate_display_packs,
                self.min_signal_packs,
                self.min_signal_sources,
            )
            < 1
        ):
            raise ValueError("sample thresholds must be positive")
        if not 0.0 <= self.min_watch_probability <= self.min_anomaly_probability <= 1.0:
            raise ValueError("probability thresholds must be ordered within [0, 1]")
        if not math.isfinite(self.min_practical_uplift) or self.min_practical_uplift < 0:
            raise ValueError("min_practical_uplift must be finite and non-negative")

    @classmethod
    def from_settings(cls, settings: ThresholdSettings) -> Self:
        return cls(
            prior_strength=settings.bayes_prior_strength,
            min_rate_display_packs=settings.min_rate_display_packs,
            min_signal_packs=settings.min_signal_packs,
            min_signal_sources=settings.min_signal_sources,
            min_watch_probability=settings.min_watch_probability,
            min_anomaly_probability=settings.min_anomaly_probability,
            min_practical_uplift=settings.min_practical_uplift,
        )


@dataclass(frozen=True, slots=True)
class SignalAnalysis:
    hits: int
    packs: int
    source_count: int
    posterior: PosteriorEstimate
    posterior_mean: float
    status: SignalStatus
    published_rate: float | None
    published_interval: CredibleInterval | None
    delta_from_baseline: float | None


def classify_signal_status(
    packs: int,
    source_count: int,
    probability_above_baseline: float,
    probability_above_practical_uplift: float,
    thresholds: SignalThresholds | None = None,
) -> SignalStatus:
    configured = thresholds or SignalThresholds()
    if packs < configured.min_rate_display_packs or source_count < configured.min_signal_sources:
        return SignalStatus.INSUFFICIENT_SAMPLE
    if packs < configured.min_signal_packs:
        return SignalStatus.NO_SIGNIFICANT_SIGNAL
    if not all(
        math.isfinite(value)
        for value in (
            probability_above_baseline,
            probability_above_practical_uplift,
        )
    ):
        raise ValueError("posterior probabilities must be finite")
    if probability_above_practical_uplift >= configured.min_anomaly_probability:
        return SignalStatus.POSSIBLE_ANOMALY
    if probability_above_practical_uplift >= configured.min_watch_probability:
        return SignalStatus.WATCH
    return SignalStatus.NO_SIGNIFICANT_SIGNAL


def analyze_signal(
    *,
    hits: int,
    packs: int,
    source_count: int,
    baseline_rate: float,
    thresholds: SignalThresholds | None = None,
) -> SignalAnalysis:
    configured = thresholds or SignalThresholds()
    posterior = empirical_bayes_posterior(
        hits=hits,
        packs=packs,
        baseline_rate=baseline_rate,
        prior_strength=configured.prior_strength,
        practical_uplift=configured.min_practical_uplift,
    )
    status = classify_signal_status(
        packs,
        source_count,
        posterior.probability_above_baseline,
        posterior.probability_above_practical,
        configured,
    )
    publish = (
        packs >= configured.min_rate_display_packs and source_count >= configured.min_signal_sources
    )
    observed_rate = hits / packs if publish else None
    return SignalAnalysis(
        hits=hits,
        packs=packs,
        source_count=source_count,
        posterior=posterior,
        posterior_mean=posterior.mean,
        status=status,
        published_rate=observed_rate,
        published_interval=posterior.credible_interval if publish else None,
        delta_from_baseline=(observed_rate - baseline_rate if observed_rate is not None else None),
    )
