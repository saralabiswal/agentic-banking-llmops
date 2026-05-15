"""Unit tests for Layer 5 A/B evaluation and model governance.

Author: Sarala Biswal
"""

from __future__ import annotations

from pathlib import Path
from platform.layer5_ab.drift_monitor import FeatureDriftMonitor
from platform.layer5_ab.experiment_service import ExperimentService, assignment_bucket
from platform.layer5_ab.model_registry import ModelRegistry
from platform.layer5_ab.statistics import calculate_air, calculate_psi
from random import Random

import numpy as np


def test_c002_hash_bucket_selects_variant_a():
    service = ExperimentService()

    bucket = assignment_bucket("C002", "exp_payment_message_v3")
    variant = service.select_variant(
        customer_id="C002",
        scenario="payment_risk_intervention",
        action_type="SEND_PUSH_NOTIFICATION",
    )

    assert bucket == 34
    assert variant.variant_id == "A"


def test_same_customer_always_gets_same_variant_for_random_ids():
    service = ExperimentService()
    rng = Random(42)
    customer_ids = [f"C{rng.randrange(100000):05d}" for _ in range(50)]

    for customer_id in customer_ids:
        first = service.select_variant(
            customer_id=customer_id,
            scenario="payment_risk_intervention",
            action_type="SEND_PUSH_NOTIFICATION",
        )
        second = service.select_variant(
            customer_id=customer_id,
            scenario="payment_risk_intervention",
            action_type="SEND_PUSH_NOTIFICATION",
        )
        assert first.variant_id == second.variant_id


def test_psi_known_distribution_shift_exceeds_alert_threshold():
    expected = np.concatenate([np.zeros(500), np.ones(500)])
    actual = np.concatenate([np.zeros(100), np.ones(900)])

    psi = calculate_psi(expected, actual, bins=2)

    assert psi > 0.25


def test_air_equal_rates_and_disparity():
    assert calculate_air(0.8, 0.8) == 1.0
    assert calculate_air(0.3, 0.5) == 0.6


def test_mlflow_model_registration_and_champion_promotion(tmp_path):
    registry = ModelRegistry(tracking_uri=f"file://{tmp_path / 'mlruns'}")

    run_id = registry.register_model(
        model_id="risk_model",
        version="risk-v4.2.1",
        metrics={"recall": 0.84, "precision": 0.80},
    )
    registry.promote_to_champion("risk_model", "risk-v4.2.1")

    assert run_id
    assert registry.get_current_champion("risk_model") == "risk-v4.2.1"


def test_evidently_style_drift_report_generated(tmp_path):
    monitor = FeatureDriftMonitor(reports_dir=tmp_path)

    result = monitor.check(
        model_id="risk_model",
        feature_name="checking_balance",
        reference=np.linspace(0.0, 1.0, 100),
        current=np.linspace(0.2, 1.2, 100),
    )

    assert result.report_path is not None
    assert Path(result.report_path).exists()
    assert "Feature drift" in Path(result.report_path).read_text(encoding="utf-8")


def test_experiment_concludes_when_confidence_and_sample_size_met():
    service = ExperimentService()

    result = service.record_outcome("exp_payment_message_v3", "A", "payment_made_7d")
    experiment = service.get_experiment("exp_payment_message_v3")

    assert result.confidence >= 0.95
    assert result.sample_count >= 5000
    assert experiment.status == "CONCLUDED"
    assert experiment.winner == "A"
