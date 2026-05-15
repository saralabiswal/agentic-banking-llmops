"""Statistical helpers for Layer 5 experiments and drift monitoring.

Author: Sarala Biswal
"""

from __future__ import annotations

import math

import numpy as np
from scipy import stats


def z_test_proportions(n_a: int, conv_a: int, n_b: int, conv_b: int) -> tuple[float, float]:
    """Return (z_score, p_value) for a two-proportion z-test."""
    if n_a <= 0 or n_b <= 0:
        return 0.0, 1.0
    p_a = conv_a / n_a
    p_b = conv_b / n_b
    pooled = (conv_a + conv_b) / (n_a + n_b)
    standard_error = math.sqrt(pooled * (1.0 - pooled) * ((1.0 / n_a) + (1.0 / n_b)))
    if standard_error == 0.0:
        return 0.0, 1.0
    z_score = (p_a - p_b) / standard_error
    p_value = float(2.0 * stats.norm.sf(abs(z_score)))
    return float(z_score), p_value


def calculate_psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """Return the Population Stability Index for two distributions."""
    if expected.size == 0 or actual.size == 0:
        return 0.0
    quantiles = np.linspace(0.0, 1.0, bins + 1)
    breakpoints = np.unique(np.quantile(expected, quantiles))
    if breakpoints.size < 2:
        breakpoints = np.linspace(float(expected.min()), float(expected.max()) + 1.0, bins + 1)
    expected_counts, _ = np.histogram(expected, bins=breakpoints)
    actual_counts, _ = np.histogram(actual, bins=breakpoints)
    epsilon = 1e-6
    expected_pct = np.maximum(expected_counts / max(expected_counts.sum(), 1), epsilon)
    actual_pct = np.maximum(actual_counts / max(actual_counts.sum(), 1), epsilon)
    psi_values = (actual_pct - expected_pct) * np.log(actual_pct / expected_pct)
    return float(np.sum(psi_values))


def calculate_air(rate_protected: float, rate_reference: float) -> float:
    """Return the Adverse Impact Ratio for protected/reference rates."""
    if rate_reference == 0.0:
        return 1.0 if rate_protected == 0.0 else 0.0
    return rate_protected / rate_reference


def ks_test(reference: np.ndarray, current: np.ndarray) -> tuple[float, float]:
    """Return (statistic, p_value) for a two-sample Kolmogorov-Smirnov test."""
    if reference.size == 0 or current.size == 0:
        return 0.0, 1.0
    result = stats.ks_2samp(reference, current)
    return float(result.statistic), float(result.pvalue)
