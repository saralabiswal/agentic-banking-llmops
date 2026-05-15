"""Drift monitoring for Layer 5 model governance.

Author: Sarala Biswal
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from platform.core.config import Settings, settings
from platform.layer5_ab.statistics import calculate_psi, ks_test
from platform.observability.metrics import metered
from platform.observability.tracing import traced

import numpy as np


@dataclass(frozen=True)
class DriftCheckResult:
    """Result of a model drift check."""

    model_id: str
    check_name: str
    status: str
    metric_value: float
    report_path: Path | None = None


class FeatureDriftMonitor:
    """Checks input feature drift and writes an HTML report."""

    def __init__(
        self,
        reports_dir: str | Path = "reports",
        config: Settings = settings,
    ) -> None:
        """Create a feature drift monitor."""
        self._reports_dir = Path(reports_dir)
        self._config = config

    @traced(layer="L5", operation="feature_drift_check")
    @metered(layer="L5")
    def check(
        self,
        model_id: str,
        feature_name: str,
        reference: np.ndarray | None = None,
        current: np.ndarray | None = None,
    ) -> DriftCheckResult:
        """Run a KS drift check and generate an HTML report."""
        reference_data = reference if reference is not None else np.linspace(0.0, 1.0, 100)
        current_data = current if current is not None else np.linspace(0.0, 1.0, 100)
        statistic, p_value = ks_test(reference_data, current_data)
        status = "ALERT" if p_value < 0.01 else "OK"
        report_path = self._write_report(
            model_id=model_id,
            title=f"Feature drift: {feature_name}",
            metric_name="ks_statistic",
            metric_value=statistic,
            status=status,
        )
        return DriftCheckResult(model_id, "FEATURE_DRIFT", status, statistic, report_path)

    def _write_report(
        self,
        *,
        model_id: str,
        title: str,
        metric_name: str,
        metric_value: float,
        status: str,
    ) -> Path:
        self._reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = self._reports_dir / f"{model_id}_{datetime.now(UTC).date().isoformat()}.html"
        report_path.write_text(
            (
                "<html><body>"
                f"<h1>{title}</h1>"
                f"<p>Status: {status}</p>"
                f"<p>{metric_name}: {metric_value:.6f}</p>"
                "</body></html>"
            ),
            encoding="utf-8",
        )
        return report_path


class PredictionDriftMonitor:
    """Checks prediction-score drift using PSI."""

    def __init__(self, config: Settings = settings) -> None:
        """Create a prediction drift monitor."""
        self._config = config

    @traced(layer="L5", operation="prediction_drift_check")
    @metered(layer="L5")
    def check(
        self,
        model_id: str,
        reference: np.ndarray,
        current: np.ndarray,
    ) -> DriftCheckResult:
        """Return a PSI-based prediction drift result."""
        psi = calculate_psi(reference, current)
        status = "ALERT" if psi > self._config.PSI_ALERT_THRESHOLD else "OK"
        return DriftCheckResult(model_id, "PREDICTION_DRIFT", status, psi)


class PerformanceDriftMonitor:
    """Checks rolling model recall for performance degradation."""

    def __init__(self, config: Settings = settings) -> None:
        """Create a performance drift monitor."""
        self._config = config

    @traced(layer="L5", operation="performance_drift_check")
    @metered(layer="L5")
    def check(self, model_id: str, true_positive: int, false_negative: int) -> DriftCheckResult:
        """Return a recall-based performance drift result."""
        denominator = true_positive + false_negative
        recall = 1.0 if denominator == 0 else true_positive / denominator
        status = "ALERT" if recall < self._config.RECALL_ALERT_THRESHOLD else "OK"
        return DriftCheckResult(model_id, "PERFORMANCE_DRIFT", status, recall)
