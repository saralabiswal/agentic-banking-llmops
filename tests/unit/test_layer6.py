"""Unit tests for Layer 6 SDK surface and execution.

Author: Sarala Biswal
"""

from __future__ import annotations

from datetime import UTC, datetime
from platform.core.schemas import OutcomeEvent
from platform.layer6_sdk import (
    BILLING_DISPUTE_RESOLUTION,
    BLUEPRINTS,
    CHURN_PREVENTION,
    FRAUD_ALERT,
    PAYMENT_RISK_INTERVENTION,
    BlueprintRunner,
)
from platform.layer6_sdk.blueprint_runner import InMemoryAuditWriter
from platform.layer6_sdk.outcome_router import OutcomeRouter


def test_blueprint_catalog_contains_four_owned_compositions():
    assert set(BLUEPRINTS) == {
        "PAYMENT_RISK_INTERVENTION",
        "BILLING_DISPUTE_RESOLUTION",
        "CHURN_PREVENTION",
        "FRAUD_ALERT",
    }
    assert PAYMENT_RISK_INTERVENTION.scenario == "payment_risk_intervention"
    assert BILLING_DISPUTE_RESOLUTION.agents == ["DisputeTriageAgent", "ResolutionAgent"]
    assert CHURN_PREVENTION.channels == ["MOBILE_PUSH", "EMAIL", "ASSOCIATE_QUEUE"]
    assert FRAUD_ALERT.description


async def test_blueprint_runner_executes_c002_payment_risk_through_all_six_layers():
    runner = BlueprintRunner()

    result = await runner.run(
        blueprint=PAYMENT_RISK_INTERVENTION,
        customer_id="C002",
        trigger="payment_risk_scheduler",
        caller_id="mobile_app_team",
    )

    completed_layers = [
        event.payload["layer"]
        for event in runner.event_bus.events_for(result.trace_id)
        if event.event_type == "layer_completed"
    ]
    assert completed_layers == ["L1", "L2", "L3", "L4", "L5", "L6"]
    assert result.action_executed is True
    assert result.action_id == "ACT-001"
    assert result.status == "EXECUTED"
    assert result.outcome_tracking_id is not None
    assert len(result.pending_actions) == 1
    assert result.pending_actions[0].action.action_id == "ACT-002"
    assert runner.status_by_trace[result.trace_id]["status"] == "completed"


async def test_outcome_router_updates_experiment_model_governance_and_audit():
    runner = BlueprintRunner()
    audit_writer = runner.audit_writer
    assert isinstance(audit_writer, InMemoryAuditWriter)
    experiment = runner.experiment_service.get_experiment("exp_payment_message_v3")
    before = experiment.variants["A"].conversion_count
    router = OutcomeRouter(
        experiment_service=runner.experiment_service,
        audit_writer=audit_writer,
    )
    outcome = OutcomeEvent(
        outcome_id="out_test_layer6",
        trace_id="trace_test_layer6",
        action_id="ACT-001",
        customer_id="C002",
        outcome_type="ENROLLED",
        outcome_ts=datetime.now(UTC),
        metadata={
            "session_id": "sess_test_layer6",
            "experiment_id": "exp_payment_message_v3",
            "variant_id": "A",
        },
    )

    await router.route(outcome)

    after = experiment.variants["A"].conversion_count
    assert after == before + 1
    assert router.model_governance_events == [outcome]
    assert any(record.event_type == "OUTCOME_CAPTURED" for record in audit_writer.records)
