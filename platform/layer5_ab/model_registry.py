"""MLflow-backed model registry wrapper for Layer 5.

Author: Sarala Biswal
"""

from __future__ import annotations

from dataclasses import dataclass
from platform.core.config import Settings, settings
from platform.observability.metrics import metered
from platform.observability.tracing import traced
from typing import cast

import mlflow
from mlflow.tracking import MlflowClient


@dataclass
class RegisteredModelVersion:
    """Tracked model version metadata."""

    model_id: str
    version: str
    metrics: dict[str, float]
    run_id: str
    champion: bool = False


class ModelRegistry:
    """Thin MLflow wrapper with champion/challenger metadata."""

    def __init__(
        self,
        tracking_uri: str | None = None,
        config: Settings = settings,
    ) -> None:
        """Create a model registry wrapper."""
        self._tracking_uri = tracking_uri or config.MLFLOW_TRACKING_URI
        self._models: dict[str, dict[str, RegisteredModelVersion]] = {}
        mlflow.set_tracking_uri(self._tracking_uri)
        self._client = MlflowClient(tracking_uri=self._tracking_uri)

    @traced(layer="L5", operation="model_register")
    @metered(layer="L5")
    def register_model(self, model_id: str, version: str, metrics: dict[str, float]) -> str:
        """Register a model version as a challenger and return the MLflow run ID."""
        with mlflow.start_run(run_name=f"{model_id}-{version}") as run:
            mlflow.set_tag("model_id", model_id)
            mlflow.set_tag("model_version", version)
            mlflow.set_tag("role", "challenger")
            for metric_name, metric_value in metrics.items():
                mlflow.log_metric(metric_name, metric_value)
            run_id = cast("str", run.info.run_id)
        self._models.setdefault(model_id, {})[version] = RegisteredModelVersion(
            model_id=model_id,
            version=version,
            metrics=metrics,
            run_id=run_id,
            champion=False,
        )
        return run_id

    @traced(layer="L5", operation="model_promote")
    @metered(layer="L5")
    def promote_to_champion(self, model_id: str, version: str) -> None:
        """Promote a registered version to champion and demote prior champions."""
        versions = self._models.setdefault(model_id, {})
        if version not in versions:
            self.register_model(model_id, version, metrics={})
        for registered in versions.values():
            registered.champion = False
            self._client.set_tag(registered.run_id, "role", "challenger")
        versions[version].champion = True
        self._client.set_tag(versions[version].run_id, "role", "champion")
        self._client.set_tag(versions[version].run_id, "champion_model", f"{model_id}:{version}")

    @traced(layer="L5", operation="model_get_champion")
    @metered(layer="L5")
    def get_current_champion(self, model_id: str) -> str | None:
        """Return the current champion version for a model."""
        for version, registered in self._models.get(model_id, {}).items():
            if registered.champion:
                return version
        return None

    @traced(layer="L5", operation="model_seed")
    @metered(layer="L5")
    def seed_initial_models(self) -> None:
        """Seed risk, churn, and payment propensity model champions."""
        seeds = {
            "risk_model": ("risk-v3.2.1", {"recall": 0.831, "precision": 0.794}),
            "churn_model": ("churn-v2.4.0", {"recall": 0.781, "precision": 0.742}),
            "payment_propensity_model": (
                "payprop-v1.9.2",
                {"recall": 0.804, "precision": 0.768},
            ),
        }
        for model_id, (version, metrics) in seeds.items():
            self.register_model(model_id, version, metrics)
            self.promote_to_champion(model_id, version)
