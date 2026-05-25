"""Champion regression gate.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.evaluation.schemas import GateResult
from typing import Any

import pandas as pd
from sklearn.metrics import roc_auc_score


def run_regression_gate(
    candidate_model: Any,
    champion_model: Any | None,
    benchmark: pd.DataFrame,
    feature_columns: list[str],
) -> GateResult:
    """Compare candidate performance against the current champion."""
    if champion_model is None:
        return GateResult(
            gate="regression",
            passed=True,
            metrics={"auc_delta": 0.0},
            failure_reason=None,
        )
    labels = benchmark["label"]
    candidate_auc = float(
        roc_auc_score(labels, candidate_model.predict_proba(benchmark[feature_columns])[:, 1])
    )
    champion_auc = float(
        roc_auc_score(labels, champion_model.predict_proba(benchmark[feature_columns])[:, 1])
    )
    delta = candidate_auc - champion_auc
    return GateResult(
        gate="regression",
        passed=delta >= -0.02,
        metrics={"candidate_auc": candidate_auc, "champion_auc": champion_auc, "auc_delta": delta},
        failure_reason=None if delta >= -0.02 else "candidate regressed more than 0.02 AUC",
    )
