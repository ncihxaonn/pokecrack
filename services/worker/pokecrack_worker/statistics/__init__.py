"""Empirical-Bayes statistics and conservative signal labels."""

from .baselines import (
    Baseline,
    BaselineCatalog,
    BaselineLevel,
    BaselineSelection,
    select_baseline,
)
from .beta import beta_quantile, regularized_beta_cdf
from .empirical import (
    BetaParameters,
    CredibleInterval,
    PosteriorEstimate,
    beta_posterior,
    beta_prior,
    empirical_bayes_posterior,
)
from .signals import (
    SignalAnalysis,
    SignalStatus,
    SignalThresholds,
    analyze_signal,
    classify_signal_status,
)

__all__ = [
    "Baseline",
    "BaselineCatalog",
    "BaselineLevel",
    "BaselineSelection",
    "BetaParameters",
    "CredibleInterval",
    "PosteriorEstimate",
    "SignalAnalysis",
    "SignalStatus",
    "SignalThresholds",
    "analyze_signal",
    "beta_posterior",
    "beta_prior",
    "beta_quantile",
    "classify_signal_status",
    "empirical_bayes_posterior",
    "regularized_beta_cdf",
    "select_baseline",
]
