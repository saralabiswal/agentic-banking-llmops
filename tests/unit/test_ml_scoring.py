"""Unit tests for classical ML scoring.

Author: Sarala Biswal
"""

from __future__ import annotations

import pickle
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from platform.core.schemas import (
    BankingProfile,
    BehavioralProfile,
    CardProfile,
    Channel,
    CRMProfile,
    CustomerProfile,
    ModelSignals,
    Segment,
)
from platform.ml import train_models
from platform.ml.generate_training_data import (
    generate_benchmark_set,
    generate_churn_data,
    generate_payment_risk_data,
)
from platform.ml.scoring_service import MLScoringService

import numpy as np
import pytest


class ProbabilityModel:
    """Small pickleable sklearn-like model for scoring tests."""

    def __init__(self, positive_probability: float) -> None:
        """Create a model that always returns one positive probability."""
        self.positive_probability = positive_probability

    def predict_proba(self, rows: np.ndarray) -> np.ndarray:
        """Return fixed binary probabilities with sklearn-compatible shape."""
        return np.array(
            [
                [1.0 - self.positive_probability, self.positive_probability]
                for _ in range(rows.shape[0])
            ]
        )


@pytest.mark.asyncio
async def test_scoring_service_loads_artifacts_and_scores_profile(tmp_path: Path) -> None:
    """MLScoringService should load .pkl artifacts and return bounded scores."""
    _write_model(tmp_path / "payment_risk_model.pkl", ProbabilityModel(0.73))
    _write_model(tmp_path / "churn_propensity_model.pkl", ProbabilityModel(0.41))
    service = MLScoringService(artifact_dir=tmp_path)

    score = await service.score(_profile(), trace_id="trace_ml_test")

    assert score.risk_score == 0.73
    assert score.churn_probability == 0.41
    assert score.model_versions["risk_score"] == "payment_risk_model:v1"
    assert score.model_versions["churn_probability"] == "churn_propensity_model:v1"


@pytest.mark.asyncio
async def test_scoring_service_raises_when_artifact_missing(tmp_path: Path) -> None:
    """Missing artifacts should raise so Layer 1 can degrade explicitly."""
    service = MLScoringService(artifact_dir=tmp_path)

    with pytest.raises(FileNotFoundError):
        await service.score(_profile(), trace_id="trace_missing_model")


def test_feature_extraction_matches_customer_profile_fields(tmp_path: Path) -> None:
    """Feature extraction should map canonical profile fields into model inputs."""
    service = MLScoringService(artifact_dir=tmp_path)
    profile = _profile()

    risk_features = service.extract_payment_risk_features(profile)
    churn_features = service.extract_churn_features(profile)

    assert risk_features["card_utilization"] == 0.76
    assert risk_features["card_missed_payments_90d"] == 2.0
    assert risk_features["banking_overdraft_count_30d"] == 1.0
    assert risk_features["checking_to_credit_limit_ratio"] == pytest.approx(312.4 / 5000)
    assert churn_features["crm_open_tickets"] == 2.0
    assert churn_features["intervention_count_7d"] == 1.0
    assert churn_features["days_since_last_contact"] == 14.0


def test_synthetic_training_data_has_expected_shape_and_rates() -> None:
    """Synthetic data should be reproducible, realistic, and labeled."""
    risk = generate_payment_risk_data(n_samples=2000, seed=42)
    churn = generate_churn_data(n_samples=2000, seed=42)
    benchmark = generate_benchmark_set(n_samples=20, seed=4242)

    assert len(risk) == 2000
    assert len(churn) == 2000
    assert set(benchmark) == {"payment_risk_model", "churn_propensity_model"}
    assert 0.08 <= float(risk["label"].mean()) <= 0.22
    assert 0.06 <= float(churn["label"].mean()) <= 0.18
    assert {"segment", "label"}.issubset(risk.columns)
    assert {"segment", "label"}.issubset(churn.columns)


def test_train_models_writes_artifacts_and_logs_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Training should persist both artifacts and call the MLflow logging surface."""
    fake_mlflow = FakeMLflow()
    monkeypatch.setattr(train_models, "mlflow", fake_mlflow)
    monkeypatch.setattr(
        train_models,
        "generate_payment_risk_data",
        lambda: generate_payment_risk_data(n_samples=240, seed=42),
    )
    monkeypatch.setattr(
        train_models,
        "generate_churn_data",
        lambda: generate_churn_data(n_samples=240, seed=42),
    )

    reports = train_models.train_all(output_dir=tmp_path)

    assert (tmp_path / "payment_risk_model.pkl").exists()
    assert (tmp_path / "churn_propensity_model.pkl").exists()
    assert set(reports) == {"payment_risk_model", "churn_propensity_model"}
    assert fake_mlflow.run_names == [
        "payment_risk_model-training",
        "churn_propensity_model-training",
    ]
    assert "auc_roc" in fake_mlflow.logged_metrics


def test_training_air_score_handles_empty_or_zero_rates() -> None:
    """AIR helper should avoid divide-by-zero when no segment has approvals."""
    data = generate_payment_risk_data(n_samples=20, seed=42)
    model = ProbabilityModel(0.95)

    assert train_models._air_score(data, train_models.RISK_FEATURES, model) == 1.0  # noqa: SLF001


class FakeRun:
    """Context manager returned by fake MLflow start_run."""

    def __init__(self, fake_mlflow: FakeMLflow, run_name: str) -> None:
        self._fake_mlflow = fake_mlflow
        self._run_name = run_name

    def __enter__(self) -> FakeRun:
        self._fake_mlflow.run_names.append(self._run_name)
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        del exc_type, exc, traceback


class FakeMLflow:
    """Small MLflow test double that records logging calls."""

    def __init__(self) -> None:
        self.run_names: list[str] = []
        self.logged_metrics: set[str] = set()

    def set_tracking_uri(self, uri: str) -> None:
        self.tracking_uri = uri

    def start_run(self, run_name: str) -> FakeRun:
        return FakeRun(self, run_name)

    def set_tag(self, key: str, value: str) -> None:
        del key, value

    def log_params(self, params: dict[str, object]) -> None:
        del params

    def log_metric(self, metric_name: str, value: float) -> None:
        del value
        self.logged_metrics.add(metric_name)

    def log_artifact(self, path: str) -> None:
        assert path.endswith(".pkl")


def _write_model(path: Path, model: ProbabilityModel) -> None:
    with path.open("wb") as artifact:
        pickle.dump(model, artifact)


def _profile() -> CustomerProfile:
    assembled_at = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
    return CustomerProfile(
        customer_id="C002",
        name="Marcus Webb",
        segment=Segment.STANDARD,
        card=CardProfile(
            balance=Decimal("3800"),
            credit_limit=Decimal("5000"),
            utilization=0.76,
            missed_pmts=2,
            past_due=Decimal("420"),
            days_since_last_payment=41,
        ),
        banking=BankingProfile(
            checking_balance=Decimal("312.40"),
            savings_balance=Decimal("0"),
            last_deposit_at=assembled_at - timedelta(days=4),
            overdrafts_30d=1,
            direct_deposit=False,
        ),
        crm=CRMProfile(
            tenure_months=24,
            nps_score=-12,
            open_tickets=2,
            last_contact_at=assembled_at - timedelta(days=14),
        ),
        behavioral=BehavioralProfile(
            app_logins_30d=14,
            preferred_channel=Channel.MOBILE,
            sms_ok=True,
            push_enabled=True,
        ),
        signals=ModelSignals(
            risk_score=0.71,
            churn_probability=0.58,
            clv_estimate=Decimal("1240"),
            last_intervention=assembled_at - timedelta(days=20),
            intervention_7d=1,
            payment_propensity=0.31,
            model_versions={
                "risk_score": "risk-v4.2.1",
                "churn_probability": "churn-v3.0.8",
            },
        ),
        assembled_at=assembled_at,
        assembly_latency_ms=120,
        sources_available=["card", "banking", "crm", "behavioral", "feature_store"],
    )
