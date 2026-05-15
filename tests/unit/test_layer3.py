"""Unit tests for Layer 3 orchestration.

Author: Sarala Biswal
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from platform.adapters.mock_llm_client import MockLLMClient
from platform.core.exceptions import ToolAuthorizationError
from platform.core.schemas import (
    BankingProfile,
    BehavioralProfile,
    CardProfile,
    Channel,
    CustomerProfile,
    ModelSignals,
    PolicyChunk,
    Segment,
)
from platform.layer3_orchestration.orchestrator import HumanReviewQueue, Orchestrator
from platform.layer3_orchestration.pipeline_registry import PIPELINES, Pipeline, PipelineStep
from platform.layer3_orchestration.tool_registry import authorize_tool_call

import pytest
from pydantic import BaseModel


class MemoryContextStore:
    """Test context store."""

    def __init__(self):
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, ttl):
        self.values[key] = value

    async def delete(self, key):
        self.values.pop(key, None)

    def checkpoint_payloads(self, session_id):
        prefix = f"session:{session_id}:pipeline_state:"
        return [
            json.loads(self.values[key])
            for key in sorted(self.values)
            if key.startswith(prefix)
        ]


class MemoryAuditWriter:
    """Test audit writer."""

    def __init__(self):
        self.records = []

    async def write(self, record):
        self.records.append(record)


class SlowLLM:
    """LLM that exceeds a short test timeout."""

    async def complete(self, system, user, schema):
        await asyncio.sleep(0.02)
        return await MockLLMClient().complete(system=system, user=user, schema=schema)


class InvalidLLM:
    """LLM that returns schema-invalid output."""

    async def complete(self, system, user, schema):
        del system, user, schema
        return {"risk_level": "CRITICAL"}


async def test_c002_payment_risk_pipeline_executes_all_steps_in_order():
    context_store = MemoryContextStore()
    audit_writer = MemoryAuditWriter()
    session_id = "sess_C002_layer3_unit"
    await _store_profile(context_store, session_id, _c002_profile())
    orchestrator = Orchestrator(
        context_store=context_store,
        llm_client=MockLLMClient(),
        audit_writer=audit_writer,
    )

    result = await orchestrator.run_pipeline(
        session_id=session_id,
        scenario="payment_risk_intervention",
        policy_chunks=_policy_chunks(),
        trace_id="trace_layer3_c002",
    )

    assert result.status == "PENDING_GUARDRAILS"
    assert [output.agent_name for output in result.agent_outputs] == [
        "RiskScoringAgent",
        "InterventionAgent",
    ]
    assert result.branch_decisions == [
        {
            "step": "BRANCH",
            "condition": "risk_level=CRITICAL",
            "routed_to": "InterventionAgent",
            "description": "risk_level in HIGH or CRITICAL routes to InterventionAgent",
        }
    ]
    assert [action.action_type for action in result.proposed_actions] == [
        "SEND_PUSH_NOTIFICATION",
        "CREATE_HARDSHIP_ENROLLMENT_CASE",
    ]
    assert all(not action.action_type.startswith("EXECUTE") for action in result.proposed_actions)
    assert result.requires_approval is True
    assert audit_writer.records[-1].event_type == "ORCHESTRATION_COMPLETE"


def test_tool_authorization_blocks_intervention_execute_payment_deferral():
    with pytest.raises(ToolAuthorizationError):
        authorize_tool_call("InterventionAgent", "execute_payment_deferral")


async def test_agent_timeout_routes_to_human_review_queue(monkeypatch):
    context_store = MemoryContextStore()
    review_queue = HumanReviewQueue()
    session_id = "sess_C002_layer3_timeout"
    await _store_profile(context_store, session_id, _c002_profile())
    monkeypatch.setitem(
        PIPELINES,
        "payment_risk_intervention",
        Pipeline(
            scenario="payment_risk_intervention",
            steps=(
                PipelineStep(
                    agent="RiskScoringAgent",
                    timeout_ms=1,
                    output_schema=BaseModel,
                ),
            ),
        ),
    )

    result = await Orchestrator(
        context_store=context_store,
        llm_client=SlowLLM(),
        human_review_queue=review_queue,
    ).run_pipeline(
        session_id=session_id,
        scenario="payment_risk_intervention",
        policy_chunks=_policy_chunks(),
        trace_id="trace_layer3_timeout",
    )

    assert result.status == "HUMAN_REVIEW"
    assert review_queue.items[-1].failure_type == "TIMEOUT"
    assert review_queue.items[-1].step_name == "RiskScoringAgent"


async def test_schema_validation_failure_routes_to_human_review_queue():
    context_store = MemoryContextStore()
    review_queue = HumanReviewQueue()
    session_id = "sess_C002_layer3_schema"
    await _store_profile(context_store, session_id, _c002_profile())

    result = await Orchestrator(
        context_store=context_store,
        llm_client=InvalidLLM(),
        human_review_queue=review_queue,
    ).run_pipeline(
        session_id=session_id,
        scenario="payment_risk_intervention",
        policy_chunks=_policy_chunks(),
        trace_id="trace_layer3_schema",
    )

    assert result.status == "HUMAN_REVIEW"
    assert review_queue.items[-1].failure_type == "ValidationError"
    assert review_queue.items[-1].step_name == "RiskScoringAgent"


async def test_pipeline_state_checkpointed_after_each_step():
    context_store = MemoryContextStore()
    session_id = "sess_C002_layer3_checkpoints"
    await _store_profile(context_store, session_id, _c002_profile())

    await Orchestrator(
        context_store=context_store,
        llm_client=MockLLMClient(),
    ).run_pipeline(
        session_id=session_id,
        scenario="payment_risk_intervention",
        policy_chunks=_policy_chunks(),
        trace_id="trace_layer3_checkpoints",
    )

    checkpoints = context_store.checkpoint_payloads(session_id)
    assert [checkpoint["step_name"] for checkpoint in checkpoints] == [
        "RiskScoringAgent",
        "BRANCH",
        "InterventionAgent",
    ]
    assert [checkpoint["status"] for checkpoint in checkpoints] == [
        "STEP_COMPLETE",
        "BRANCH_COMPLETE",
        "STEP_COMPLETE",
    ]


async def _store_profile(context_store, session_id, profile):
    await context_store.set(
        f"session:{session_id}:customer_profile",
        profile.model_dump_json(),
        ttl=300,
    )


def _policy_chunks():
    return [
        PolicyChunk(
            chunk_id="KB-HARD-001-2.3-PARAGRAPH-1",
            document_id="KB-HARD-001",
            document_title="Hardship Program Eligibility Criteria",
            document_type="POLICY",
            doc_version="2.3",
            raw_text="Customers with 2+ missed payments and checking below $500 are eligible.",
            rerank_score=0.96,
            chunk_type="PARAGRAPH",
            parent_chunk_id="KB-HARD-001-2.3-SECTION-1",
            product_line="credit_card",
            jurisdiction="US",
        ),
        PolicyChunk(
            chunk_id="KB-PAY-007-1.8-PARAGRAPH-1",
            document_id="KB-PAY-007",
            document_title="Payment Risk Intervention Playbook",
            document_type="PLAYBOOK",
            doc_version="1.8",
            raw_text="High risk customers should receive hardship intervention proposals.",
            rerank_score=0.93,
            chunk_type="PARAGRAPH",
            parent_chunk_id="KB-PAY-007-1.8-SECTION-1",
            product_line="credit_card",
            jurisdiction="US",
        ),
        PolicyChunk(
            chunk_id="KB-COMP-003-3.1-PARAGRAPH-1",
            document_id="KB-COMP-003",
            document_title="Contact Frequency Guidelines",
            document_type="COMPLIANCE",
            doc_version="3.1",
            raw_text="Maximum 3 outbound contacts per customer per rolling 7-day window.",
            rerank_score=0.91,
            chunk_type="PARAGRAPH",
            parent_chunk_id="KB-COMP-003-3.1-SECTION-1",
            product_line="credit_card",
            jurisdiction="US",
        ),
    ]


def _c002_profile():
    return CustomerProfile(
        customer_id="C002",
        name="Marcus Webb",
        segment=Segment.STANDARD,
        card=CardProfile(
            balance=Decimal("7600.00"),
            credit_limit=Decimal("10000.00"),
            utilization=0.76,
            missed_pmts=2,
            past_due=Decimal("410.00"),
            days_since_last_payment=48,
        ),
        banking=BankingProfile(
            checking_balance=Decimal("312.40"),
            savings_balance=Decimal("25.00"),
            last_deposit_at=None,
            overdrafts_30d=2,
            direct_deposit=False,
        ),
        crm=None,
        behavioral=BehavioralProfile(
            app_logins_30d=14,
            preferred_channel=Channel.SMS,
            sms_ok=True,
            push_enabled=True,
            email_ok=True,
        ),
        signals=ModelSignals(
            risk_score=0.71,
            churn_probability=0.27,
            clv_estimate=Decimal("2400.00"),
            last_intervention=None,
            intervention_7d=0,
            payment_propensity=0.31,
            model_versions={"payment_risk": "v3.2.1"},
        ),
        assembled_at=datetime.now(UTC),
        assembly_latency_ms=167,
        sources_available=["card", "banking", "behavioral", "feature_store"],
        sources_degraded=["crm"],
        partial_context=True,
    )
