"""Train classical propensity models and write local artifacts.

Author: Sarala Biswal
"""

from __future__ import annotations

import pickle
from pathlib import Path
from platform.core.config import settings
from platform.ml.generate_training_data import (
    CHURN_FEATURES,
    DATA_DIR,
    RISK_FEATURES,
    generate_churn_data,
    generate_payment_risk_data,
)
from platform.ml.scoring_service import ARTIFACT_DIR
from typing import Any

import mlflow
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split


def train_all(output_dir: Path = ARTIFACT_DIR) -> dict[str, dict[str, float]]:
    """Train both propensity models, persist artifacts, and log MLflow metrics."""
    output_dir.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
    reports = {
        "payment_risk_model": _train_one(
            model_name="payment_risk_model",
            data=generate_payment_risk_data(),
            feature_columns=RISK_FEATURES,
            artifact_path=output_dir / "payment_risk_model.pkl",
        ),
        "churn_propensity_model": _train_one(
            model_name="churn_propensity_model",
            data=generate_churn_data(),
            feature_columns=CHURN_FEATURES,
            artifact_path=output_dir / "churn_propensity_model.pkl",
        ),
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    generate_payment_risk_data().to_csv(DATA_DIR / "payment_risk_training.csv", index=False)
    generate_churn_data().to_csv(DATA_DIR / "churn_training.csv", index=False)
    return reports


def _train_one(
    model_name: str,
    data: pd.DataFrame,
    feature_columns: list[str],
    artifact_path: Path,
) -> dict[str, float]:
    x_train, x_test, y_train, y_test = train_test_split(
        data[feature_columns],
        data["label"],
        test_size=0.2,
        random_state=42,
        stratify=data["label"],
    )
    model = GradientBoostingClassifier(random_state=42)
    model.fit(x_train, y_train)
    probabilities = model.predict_proba(x_test)[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    metrics = {
        "auc_roc": float(roc_auc_score(y_test, probabilities)),
        "precision": float(precision_score(y_test, predictions, zero_division=0)),
        "recall": float(recall_score(y_test, predictions, zero_division=0)),
        "f1": float(f1_score(y_test, predictions, zero_division=0)),
        "air": _air_score(data, feature_columns, model),
    }
    with artifact_path.open("wb") as artifact:
        pickle.dump(model, artifact)
    with mlflow.start_run(run_name=f"{model_name}-training"):
        mlflow.set_tag("model_name", model_name)
        mlflow.set_tag("stage", "Production")
        mlflow.log_params(
            {
                "algorithm": "GradientBoostingClassifier",
                "features": ",".join(feature_columns),
                "train_rows": len(x_train),
                "test_rows": len(x_test),
            }
        )
        for metric_name, value in metrics.items():
            mlflow.log_metric(metric_name, value)
        mlflow.log_artifact(str(artifact_path))
    return metrics


def _air_score(data: pd.DataFrame, feature_columns: list[str], model: Any) -> float:
    probabilities = model.predict_proba(data[feature_columns])[:, 1]
    approved = probabilities < 0.5
    rates = []
    for segment in sorted(data["segment"].unique()):
        mask = np.array(data["segment"] == segment)
        if mask.any():
            rates.append(float(np.mean(approved[mask])))
    if not rates or max(rates) == 0:
        return 1.0
    return min(rates) / max(rates)


def main() -> None:
    """CLI entry point for `make train-models`."""
    reports = train_all()
    for model_name, metrics in reports.items():
        print(f"{model_name}: {metrics}")


if __name__ == "__main__":
    main()
