"""Numerically stable Beta distribution primitives without SciPy."""

from __future__ import annotations

import math

_EPSILON = 3e-14
_MIN_FLOAT = 1e-300
_MAX_ITERATIONS = 300


def _continued_fraction(alpha: float, beta: float, x: float) -> float:
    total = alpha + beta
    alpha_plus = alpha + 1.0
    alpha_minus = alpha - 1.0
    c = 1.0
    d = 1.0 - total * x / alpha_plus
    if abs(d) < _MIN_FLOAT:
        d = _MIN_FLOAT
    d = 1.0 / d
    result = d
    for iteration in range(1, _MAX_ITERATIONS + 1):
        twice = 2 * iteration
        coefficient = iteration * (beta - iteration) * x / ((alpha_minus + twice) * (alpha + twice))
        d = 1.0 + coefficient * d
        if abs(d) < _MIN_FLOAT:
            d = _MIN_FLOAT
        c = 1.0 + coefficient / c
        if abs(c) < _MIN_FLOAT:
            c = _MIN_FLOAT
        d = 1.0 / d
        result *= d * c

        coefficient = -(
            (alpha + iteration) * (total + iteration) * x / ((alpha + twice) * (alpha_plus + twice))
        )
        d = 1.0 + coefficient * d
        if abs(d) < _MIN_FLOAT:
            d = _MIN_FLOAT
        c = 1.0 + coefficient / c
        if abs(c) < _MIN_FLOAT:
            c = _MIN_FLOAT
        d = 1.0 / d
        delta = d * c
        result *= delta
        if abs(delta - 1.0) <= _EPSILON:
            return result
    raise ArithmeticError("regularized beta continued fraction did not converge")


def regularized_beta_cdf(x: float, alpha: float, beta: float) -> float:
    """Return I_x(alpha, beta), including stable tail evaluation."""

    if not all(math.isfinite(value) for value in (x, alpha, beta)):
        raise ValueError("beta CDF arguments must be finite")
    if alpha <= 0.0 or beta <= 0.0:
        raise ValueError("beta shape parameters must be positive")
    if not 0.0 <= x <= 1.0:
        raise ValueError("x must be between zero and one")
    if x == 0.0:
        return 0.0
    if x == 1.0:
        return 1.0

    log_front = (
        math.lgamma(alpha + beta)
        - math.lgamma(alpha)
        - math.lgamma(beta)
        + alpha * math.log(x)
        + beta * math.log1p(-x)
    )
    front = math.exp(log_front)
    if x < (alpha + 1.0) / (alpha + beta + 2.0):
        value = front * _continued_fraction(alpha, beta, x) / alpha
    else:
        value = 1.0 - front * _continued_fraction(beta, alpha, 1.0 - x) / beta
    return min(1.0, max(0.0, value))


def beta_quantile(probability: float, alpha: float, beta: float) -> float:
    """Invert the Beta CDF by monotone bisection."""

    if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be between zero and one")
    if probability == 0.0:
        return 0.0
    if probability == 1.0:
        return 1.0
    low = 0.0
    high = 1.0
    for _ in range(200):
        midpoint = (low + high) / 2.0
        value = regularized_beta_cdf(midpoint, alpha, beta)
        if abs(value - probability) <= 1e-13 or high - low <= 1e-14:
            return midpoint
        if value < probability:
            low = midpoint
        else:
            high = midpoint
    return (low + high) / 2.0
