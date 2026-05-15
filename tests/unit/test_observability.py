"""Unit tests for observability decorators and metric names.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.layer6_sdk import PAYMENT_RISK_INTERVENTION, BlueprintRunner

from prometheus_client import generate_latest


async def test_pipeline_records_layer_metrics_for_all_six_layers():
    runner = BlueprintRunner()

    await runner.run(
        blueprint=PAYMENT_RISK_INTERVENTION,
        customer_id="C002",
        trigger="payment_risk_scheduler",
        caller_id="test",
    )

    metrics_text = generate_latest().decode("utf-8")
    assert "platform_layer_latency_seconds_bucket" in metrics_text
    for layer in ("L1", "L2", "L3", "L4", "L5", "L6"):
        assert f'layer="{layer}"' in metrics_text
    assert "platform_adapter_latency_seconds_bucket" in metrics_text
    assert "platform_guardrail_checks_total" in metrics_text
    assert "platform_experiment_assignments_total" in metrics_text
