"""Benchmark performance gate.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.evaluation.schemas import GateResult
from typing import Any

import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score


def run_benchmark_gate(
    model: Any,
    benchmark: pd.DataFrame,
    feature_columns: list[str],
) -> GateResult:
    """Evaluate candidate model performance on a held-out benchmark set."""
    probabilities = model.predict_proba(benchmark[feature_columns])[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    labels = benchmark["label"]
    metrics = {
        "auc_roc": float(roc_auc_score(labels, probabilities)),
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "f1": float(f1_score(labels, predictions, zero_division=0)),
    }
    failures = []
    if metrics["auc_roc"] < 0.72:
        failures.append("AUC-ROC below 0.72")
    if metrics["precision"] < 0.60:
        failures.append("precision below 0.60")
    if metrics["recall"] < 0.55:
        failures.append("recall below 0.55")
    return GateResult(
        gate="benchmark",
        passed=not failures,
        metrics=metrics,
        failure_reason="; ".join(failures) if failures else None,
    )
