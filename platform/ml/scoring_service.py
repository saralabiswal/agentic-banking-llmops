"""Model serving service for classical banking propensity models.

Author: Sarala Biswal
"""

from __future__ import annotations

import asyncio
import math
import pickle
import time
from datetime import UTC, datetime
from pathlib import Path
from platform.core.schemas import CustomerProfile
from platform.ml.generate_training_data import CHURN_FEATURES, RISK_FEATURES
from platform.ml.schemas import ModelScore
from typing import Any

import numpy as np
import structlog
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

logger = structlog.get_logger()
ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"


class MLScoringService:
    """Loads trained sklearn models from disk and scores CustomerProfile objects."""

    def __init__(
        self,
        artifact_dir: Path | str = ARTIFACT_DIR,
        payment_model_name: str = "payment_risk_model.pkl",
        churn_model_name: str = "churn_propensity_model.pkl",
    ) -> None:
        """Create a scoring service with lazy artifact loading."""
        self._artifact_dir = Path(artifact_dir)
        self._payment_model_name = payment_model_name
        self._churn_model_name = churn_model_name
        self._payment_model: Any | None = None
        self._churn_model: Any | None = None

    async def score(self, profile: CustomerProfile, trace_id: str) -> ModelScore:
        """Score payment risk and churn propensity for a customer profile."""
        started = time.perf_counter()
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("ml.score") as span:
            span.set_attribute("trace_id", trace_id)
            span.set_attribute("customer_id", profile.customer_id)
            try:
                score = await asyncio.to_thread(self._score_sync, profile)
                latency_ms = int((time.perf_counter() - started) * 1000)
                span.set_attribute("latency_ms", latency_ms)
                span.set_attribute("risk_score", score.risk_score)
                span.set_attribute("churn_probability", score.churn_probability)
                logger.info(
                    "ml.scoring.complete",
                    trace_id=trace_id,
                    customer_id=profile.customer_id,
                    latency_ms=latency_ms,
                    model_versions=score.model_versions,
                )
                return score
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                logger.warning(
                    "ml.scoring_failed",
                    trace_id=trace_id,
                    customer_id=profile.customer_id,
                    reason=str(exc),
                )
                raise

    def extract_payment_risk_features(self, profile: CustomerProfile) -> dict[str, float]:
        """Extract ordered payment-risk model features from a CustomerProfile."""
        credit_limit = float(profile.card.credit_limit or 1)
        checking_balance = float(profile.banking.checking_balance)
        balance = float(profile.card.balance)
        crm = profile.crm
        return {
            "card_utilization": float(profile.card.utilization),
            "card_missed_payments_90d": float(profile.card.missed_pmts),
            "banking_overdraft_count_30d": float(profile.banking.overdrafts_30d),
            "checking_to_credit_limit_ratio": checking_balance / max(credit_limit, 1.0),
            "crm_tenure_months": float(crm.tenure_months if crm is not None else 0),
            "crm_nps_score": _nps_score(crm),
            "card_balance_to_limit_ratio": balance / max(credit_limit, 1.0),
        }

    def extract_churn_features(self, profile: CustomerProfile) -> dict[str, float]:
        """Extract ordered churn-propensity model features from a CustomerProfile."""
        crm = profile.crm
        checking_balance = max(float(profile.banking.checking_balance), 0.0)
        days_since_last_contact = 180.0
        if crm is not None and crm.last_contact_at is not None:
            days_since_last_contact = max(
                (profile.assembled_at - crm.last_contact_at).total_seconds() / 86400,
                0.0,
            )
        return {
            "crm_tenure_months": float(crm.tenure_months if crm is not None else 0),
            "crm_nps_score": _nps_score(crm),
            "crm_open_tickets": float(crm.open_tickets if crm is not None else 0),
            "intervention_count_7d": float(profile.signals.intervention_7d),
            "card_utilization": float(profile.card.utilization),
            "log_checking_balance": math.log1p(checking_balance),
            "days_since_last_contact": days_since_last_contact,
        }

    def _score_sync(self, profile: CustomerProfile) -> ModelScore:
        """Run sklearn predict_proba using loaded model artifacts."""
        payment_model = self._payment_model or self._load_model(self._payment_model_name)
        churn_model = self._churn_model or self._load_model(self._churn_model_name)
        self._payment_model = payment_model
        self._churn_model = churn_model
        risk_features = self.extract_payment_risk_features(profile)
        churn_features = self.extract_churn_features(profile)
        risk_score = _positive_probability(payment_model, _row(risk_features, RISK_FEATURES))
        churn_probability = _positive_probability(churn_model, _row(churn_features, CHURN_FEATURES))
        return ModelScore(
            risk_score=risk_score,
            churn_probability=churn_probability,
            model_versions={
                "risk_score": "payment_risk_model:v1",
                "churn_probability": "churn_propensity_model:v1",
            },
            scored_at=datetime.now(UTC),
        )

    def _load_model(self, filename: str) -> Any:
        """Load a pickle model artifact or raise a clear file error."""
        artifact_path = self._artifact_dir / filename
        if not artifact_path.exists():
            raise FileNotFoundError(f"Missing ML model artifact: {artifact_path}")
        with artifact_path.open("rb") as artifact:
            return pickle.load(artifact)


def _row(features: dict[str, float], columns: list[str]) -> np.ndarray:
    return np.array([[features[column] for column in columns]], dtype=float)


def _positive_probability(model: Any, row: np.ndarray) -> float:
    probability = model.predict_proba(row)
    return float(np.clip(probability[0][1], 0.0, 1.0))


def _nps_score(crm: Any | None) -> float:
    if crm is None or crm.nps_score is None:
        return -1.0
    return float(crm.nps_score)
