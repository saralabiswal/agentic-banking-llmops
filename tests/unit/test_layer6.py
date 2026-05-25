"""Unit tests for Layer 6 SDK surface and execution.

Author: Sarala Biswal
"""

from __future__ import annotations

from datetime import UTC, datetime
from platform.core.schemas import ExecutionResult, OutcomeEvent
from platform.layer6_sdk import (
    BILLING_DISPUTE_RESOLUTION,
    BLUEPRINTS,
    CHURN_PREVENTION,
    FRAUD_ALERT,
    PAYMENT_RISK_INTERVENTION,
    BlueprintRunner,
)
from platform.layer6_sdk.blueprint_runner import InMemoryAuditWriter
from platform.layer6_sdk.client import BankingAgenticAIClient
from platform.layer6_sdk.outcome_router import OutcomeRouter
from platform.memory.schemas import CustomerMemory, MemoryType
from platform.memory.writer import MemoryWriter


class MemoryStoreStub:
    """In-memory MemoryStore test double."""

    def __init__(self) -> None:
        """Create an empty memory store stub."""
        self.memories: list[CustomerMemory] = []

    async def store(self, memory: CustomerMemory) -> str:
        """Store a memory and return its ID."""
        self.memories.append(memory)
        return memory.memory_id

    async def retrieve(
        self,
        customer_id: str,
        scenario: str,
        top_k: int = 5,
        memory_types: list[MemoryType] | None = None,
    ) -> list[CustomerMemory]:
        """Return memories matching the customer and scenario."""
        del top_k, memory_types
        return [
            memory
            for memory in self.memories
            if memory.customer_id == customer_id and memory.scenario == scenario
        ]

    async def get_recent(self, customer_id: str, limit: int = 10) -> list[CustomerMemory]:
        """Return recent memories for a customer."""
        return [memory for memory in self.memories if memory.customer_id == customer_id][:limit]


class OutcomeRouterStub:
    """Outcome router test double for SDK client tests."""

    def __init__(self) -> None:
        self.events: list[OutcomeEvent] = []

    async def route(self, outcome: OutcomeEvent) -> None:
        self.events.append(outcome)


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


async def test_outcome_router_writes_long_term_memory_and_audit():
    """Layer 6 should store customer outcomes in long-term memory when configured."""
    runner = BlueprintRunner()
    audit_writer = runner.audit_writer
    assert isinstance(audit_writer, InMemoryAuditWriter)
    memory_store = MemoryStoreStub()
    router = OutcomeRouter(
        experiment_service=runner.experiment_service,
        audit_writer=audit_writer,
        memory_writer=MemoryWriter(memory_store, audit_writer),
    )
    outcome = OutcomeEvent(
        outcome_id="out_test_memory",
        trace_id="trace_test_memory",
        action_id="ACT-001",
        customer_id="C002",
        outcome_type="ENROLLED",
        outcome_ts=datetime.now(UTC),
        metadata={
            "session_id": "sess_test_memory",
            "scenario": "payment_risk_intervention",
            "experiment_id": "exp_payment_message_v3",
            "variant_id": "A",
        },
    )

    await router.route(outcome)

    assert len(memory_store.memories) == 1
    memory = memory_store.memories[0]
    assert memory.memory_type == MemoryType.OUTCOME
    assert memory.scenario == "payment_risk_intervention"
    assert memory.outcome_signal == "ENROLLED"
    assert "action ACT-001" in memory.content
    assert any(record.event_type == "MEMORY_STORED" for record in audit_writer.records)


async def test_sdk_client_returns_existing_result_and_records_outcome():
    """SDK client should read completed runner status and route outcome events."""
    runner = BlueprintRunner()
    router = OutcomeRouterStub()
    result = ExecutionResult(
        trace_id="trace_client",
        action_id="ACT-001",
        action_executed=True,
        status="EXECUTED",
        channel="PUSH",
        delivery_receipt=None,
        outcome_tracking_id="otk_client",
        customer_message="message",
        pending_actions=[],
    )
    runner.status_by_trace["trace_client"] = {"execution_result": result.model_dump(mode="json")}
    client = BankingAgenticAIClient(runner=runner, outcome_router=router)  # type: ignore[arg-type]

    loaded = await client.execute("trace_client", "ACT-001", "caller")
    missing = await client.execute("trace_missing", "ACT-404", "caller")
    await client.record_outcome(
        trace_id="trace_client",
        action_id="ACT-001",
        outcome_type="ENROLLED",
        outcome_ts=datetime.now(UTC),
        metadata={"customer_id": "C002"},
    )

    assert loaded.action_id == "ACT-001"
    assert missing.status == "FAILED"
    assert router.events[0].customer_id == "C002"
