"""Empirical-Bayes posterior construction for binomial pull-rate metrics."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .beta import beta_quantile, regularized_beta_cdf


@dataclass(frozen=True, slots=True)
class BetaParameters:
    alpha: float
    beta: float

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)


@dataclass(frozen=True, slots=True)
class CredibleInterval:
    low: float
    high: float
    level: float = 0.9


@dataclass(frozen=True, slots=True)
class PosteriorEstimate:
    alpha: float
    beta: float
    mean: float
    credible_interval: CredibleInterval
    baseline_rate: float
    practical_threshold: float
    probability_above_baseline: float
    probability_above_practical: float


def beta_prior(baseline_rate: float, strength: float) -> BetaParameters:
    if not math.isfinite(baseline_rate) or not 0.0 < baseline_rate < 1.0:
        raise ValueError("baseline_rate must be strictly between zero and one")
    if not math.isfinite(strength) or strength <= 0.0:
        raise ValueError("prior strength must be positive")
    return BetaParameters(
        alpha=baseline_rate * strength,
        beta=(1.0 - baseline_rate) * strength,
    )


def beta_posterior(prior: BetaParameters, *, hits: int, packs: int) -> BetaParameters:
    if isinstance(hits, bool) or isinstance(packs, bool):
        raise ValueError("hits and packs must be integers")
    if hits < 0 or packs < 0 or hits > packs:
        raise ValueError("hits must satisfy 0 <= hits <= packs")
    return BetaParameters(
        alpha=prior.alpha + hits,
        beta=prior.beta + packs - hits,
    )


def empirical_bayes_posterior(
    *,
    hits: int,
    packs: int,
    baseline_rate: float,
    prior_strength: float,
    practical_uplift: float = 0.2,
    interval_level: float = 0.9,
) -> PosteriorEstimate:
    """Build a posterior and equal-tail credible interval.

    ``practical_uplift`` is relative: 20% over a 0.10 baseline tests 0.12.
    """

    if not math.isfinite(practical_uplift) or practical_uplift < 0.0:
        raise ValueError("practical_uplift must be finite and non-negative")
    if not math.isfinite(interval_level) or not 0.0 < interval_level < 1.0:
        raise ValueError("interval_level must be strictly between zero and one")
    prior = beta_prior(baseline_rate, prior_strength)
    posterior = beta_posterior(prior, hits=hits, packs=packs)
    tail = (1.0 - interval_level) / 2.0
    interval = CredibleInterval(
        low=beta_quantile(tail, posterior.alpha, posterior.beta),
        high=beta_quantile(1.0 - tail, posterior.alpha, posterior.beta),
        level=interval_level,
    )
    practical_threshold = min(1.0, baseline_rate * (1.0 + practical_uplift))
    return PosteriorEstimate(
        alpha=posterior.alpha,
        beta=posterior.beta,
        mean=posterior.mean,
        credible_interval=interval,
        baseline_rate=baseline_rate,
        practical_threshold=practical_threshold,
        probability_above_baseline=1.0
        - regularized_beta_cdf(baseline_rate, posterior.alpha, posterior.beta),
        probability_above_practical=1.0
        - regularized_beta_cdf(practical_threshold, posterior.alpha, posterior.beta),
    )
