"""Full end-to-end integration tests for all demo customers and scenarios.

Author: Sarala Biswal
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from platform.core.schemas import AuditRecord, OutcomeEvent
from platform.layer6_sdk import BlueprintRunner, blueprint_for_scenario
from platform.layer6_sdk.blueprint_runner import InMemoryAuditWriter
from platform.layer6_sdk.outcome_router import OutcomeRouter
from typing import Any

import pytest

PIPELINE_CASES = [
    ("C001", "payment_risk_intervention"),
    ("C001", "billing_dispute_resolution"),
    ("C001", "churn_prevention"),
    ("C002", "payment_risk_intervention"),
    ("C002", "billing_dispute_resolution"),
    ("C002", "churn_prevention"),
    ("C003", "payment_risk_intervention"),
    ("C003", "billing_dispute_resolution"),
    ("C003", "churn_prevention"),
]


@pytest.mark.parametrize(("customer_id", "scenario"), PIPELINE_CASES)
async def test_full_pipeline(customer_id: str, scenario: str) -> None:
    """Run every customer/scenario pair through all six layers."""
    runner = BlueprintRunner()
    audit_writer = runner.audit_writer
    assert isinstance(audit_writer, InMemoryAuditWriter)

    started = time.perf_counter()
    result = await runner.run(
        blueprint=blueprint_for_scenario(scenario),
        customer_id=customer_id,
        trigger="integration_test",
        caller_id="integration_test",
    )
    await _record_demo_outcomes(
        runner=runner,
        trace_id=result.trace_id,
        action_id=result.action_id,
        customer_id=customer_id,
    )
    total_latency_ms = int((time.perf_counter() - started) * 1000)

    records = [record for record in audit_writer.records if record.trace_id == result.trace_id]
    assert len(records) == 8
    assert all(record.trace_id == result.trace_id for record in records)
    assert all(record.session_id for record in records)
    assert all(record.customer_id == customer_id for record in records)
    assert total_latency_ms < 500

    event_types = [record.event_type for record in records]
    assert event_types.count("CONTEXT_ASSEMBLY") == 1
    assert event_types.count("VECTOR_RETRIEVAL") == 1
    assert event_types.count("ORCHESTRATION_COMPLETE") == 1
    assert event_types.count("GUARDRAILS_EVALUATION") == 1
    assert event_types.count("AB_ASSIGNMENT") == 1
    assert event_types.count("ACTION_EXECUTED") == 1
    assert event_types.count("OUTCOME_CAPTURED") == 2

    orchestration = _record(records, "ORCHESTRATION_COMPLETE")
    guardrails = _record(records, "GUARDRAILS_EVALUATION")
    _assert_guardrails_covered_proposed_actions(orchestration, guardrails)
    _assert_variant_assignment_consistent(runner, customer_id, scenario, records)

    if customer_id == "C002" and scenario == "payment_risk_intervention":
        risk_output = _agent_output(orchestration, "RiskScoringAgent")
        assert risk_output["risk_level"] == "CRITICAL"


async def _record_demo_outcomes(
    *,
    runner: BlueprintRunner,
    trace_id: str,
    action_id: str,
    customer_id: str,
) -> None:
    audit_writer = runner.audit_writer
    assert isinstance(audit_writer, InMemoryAuditWriter)
    status = runner.status_by_trace[trace_id]
    session_id = str(status["session_id"])
    assignment = _first_assignment(audit_writer.records, trace_id)
    metadata: dict[str, object] = {"session_id": session_id}
    if assignment is not None:
        experiment_id = assignment.get("experiment_id")
        variant_id = assignment.get("variant_id")
        if isinstance(experiment_id, str) and isinstance(variant_id, str):
            metadata.update({"experiment_id": experiment_id, "variant_id": variant_id})

    router = OutcomeRouter(
        experiment_service=runner.experiment_service,
        audit_writer=audit_writer,
    )
    for index, outcome_type in enumerate(("PUSH_OPENED", "ENROLLED"), start=1):
        await router.route(
            OutcomeEvent(
                outcome_id=f"out_{trace_id}_{index}",
                trace_id=trace_id,
                action_id=action_id,
                customer_id=customer_id,
                outcome_type=outcome_type,
                outcome_ts=datetime.now(UTC),
                metadata=metadata,
            )
        )


def _assert_guardrails_covered_proposed_actions(
    orchestration: AuditRecord,
    guardrails: AuditRecord,
) -> None:
    proposed = {
        str(action["action_id"])
        for action in _list_of_dicts(orchestration.payload.get("proposed_actions"))
    }
    evaluated = {
        str(action["action_id"])
        for action in _list_of_dicts(guardrails.payload.get("actions_evaluated"))
    }
    assert proposed <= evaluated


def _assert_variant_assignment_consistent(
    runner: BlueprintRunner,
    customer_id: str,
    scenario: str,
    records: list[AuditRecord],
) -> None:
    assignment = _first_assignment(records, records[0].trace_id)
    if assignment is None:
        return
    experiment_id = assignment.get("experiment_id")
    variant_id = assignment.get("variant_id")
    action_type = assignment.get("action_type")
    if not isinstance(experiment_id, str) or not isinstance(variant_id, str):
        return
    assert isinstance(action_type, str)
    first = runner.experiment_service.select_variant(customer_id, scenario, action_type)
    second = runner.experiment_service.select_variant(customer_id, scenario, action_type)
    assert first.variant_id == variant_id
    assert second.variant_id == variant_id


def _first_assignment(records: list[AuditRecord], trace_id: str) -> dict[str, Any] | None:
    assignment_record = next(
        (
            record
            for record in records
            if record.trace_id == trace_id and record.event_type == "AB_ASSIGNMENT"
        ),
        None,
    )
    if assignment_record is None:
        return None
    assignments = _list_of_dicts(assignment_record.payload.get("assignments"))
    return assignments[0] if assignments else None


def _agent_output(record: AuditRecord, agent_name: str) -> dict[str, Any]:
    for output in _list_of_dicts(record.payload.get("agent_outputs")):
        if output.get("agent_name") == agent_name:
            nested = output.get("output")
            assert isinstance(nested, dict)
            return nested
    raise AssertionError(f"missing agent output: {agent_name}")


def _record(records: list[AuditRecord], event_type: str) -> AuditRecord:
    return next(record for record in records if record.event_type == event_type)


def _list_of_dicts(value: object | None) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
