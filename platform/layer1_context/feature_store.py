"""Feature store pull helper for Layer 1.

Author: Sarala Biswal
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from platform.core.interfaces import FeatureStore
from platform.core.schemas import ModelSignals

SIGNAL_FIXTURES: dict[str, ModelSignals] = {
    "C001": ModelSignals(
        risk_score=0.08,
        churn_probability=0.04,
        clv_estimate=Decimal("6400"),
        last_intervention=datetime(2026, 4, 20, tzinfo=UTC),
        intervention_7d=0,
        payment_propensity=0.82,
        model_versions={
            "risk_score": "risk-v4.2.1",
            "churn_probability": "churn-v3.0.8",
            "clv_estimate": "clv-v2.1.4",
            "payment_propensity": "pay-v2.0.3",
        },
    ),
    "C002": ModelSignals(
        risk_score=0.71,
        churn_probability=0.58,
        clv_estimate=Decimal("1240"),
        last_intervention=datetime(2026, 4, 28, tzinfo=UTC),
        intervention_7d=0,
        payment_propensity=0.31,
        model_versions={
            "risk_score": "risk-v4.2.1",
            "churn_probability": "churn-v3.0.8",
            "clv_estimate": "clv-v2.1.4",
            "payment_propensity": "pay-v2.0.3",
        },
    ),
    "C003": ModelSignals(
        risk_score=0.03,
        churn_probability=0.02,
        clv_estimate=Decimal("14800"),
        last_intervention=datetime(2026, 3, 1, tzinfo=UTC),
        intervention_7d=0,
        payment_propensity=0.91,
        model_versions={
            "risk_score": "risk-v4.2.1",
            "churn_probability": "churn-v3.0.8",
            "clv_estimate": "clv-v2.1.4",
            "payment_propensity": "pay-v2.0.3",
        },
    ),
}


async def pull_signals(customer_id: str, feature_store: FeatureStore | None = None) -> ModelSignals:
    """Pull model signals from a feature store, falling back to deterministic fixtures."""
    await asyncio.sleep(0.007)
    if feature_store is not None:
        try:
            return await feature_store.get_signals(customer_id)
        except (KeyError, LookupError):
            return SIGNAL_FIXTURES[customer_id]
    return SIGNAL_FIXTURES[customer_id]
