"""Fairness evaluation gate.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.evaluation.schemas import GateResult
from typing import Any

import pandas as pd


def run_fairness_gate(
    model: Any,
    benchmark: pd.DataFrame,
    feature_columns: list[str],
) -> GateResult:
    """Compute adverse impact ratio across synthetic balance segments."""
    probabilities = model.predict_proba(benchmark[feature_columns])[:, 1]
    approved = probabilities < 0.5
    rates: list[float] = []
    for segment in sorted(benchmark["segment"].unique()):
        mask = benchmark["segment"] == segment
        if mask.any():
            rates.append(float(approved[mask].mean()))
    air = 1.0 if not rates or max(rates) == 0 else min(rates) / max(rates)
    return GateResult(
        gate="fairness",
        passed=air >= 0.80,
        metrics={"air": air},
        failure_reason=None if air >= 0.80 else "AIR below 0.80",
    )
