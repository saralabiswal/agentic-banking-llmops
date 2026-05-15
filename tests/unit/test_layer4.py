"""Unit tests for Layer 4 guardrails.

Author: Sarala Biswal
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from platform.core.schemas import (
    AgentOutput,
    BankingProfile,
    BehavioralProfile,
    CardProfile,
    Channel,
    CustomerProfile,
    ModelSignals,
    OrchestratorOutput,
    PolicyMatch,
    ProposedAction,
    RiskAssessment,
    Segment,
)
from platform.layer4_guardrails.approval_queue import ApprovalQueueService
from platform.layer4_guardrails.checks.responsible_ai import ConfidenceCheck
from platform.layer4_guardrails.fairness import BisgFairnessChecker
from platform.layer4_guardrails.rule_engine import RuleEvaluator, RuleLoader
from platform.layer4_guardrails.service import GuardrailsService

import yaml


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


async def test_guardrails_approves_push_and_flags_hardship_case():
    context_store = MemoryContextStore()
    approval_queue = ApprovalQueueService()
    session_id = "sess_C002_layer4"
    await _store_profile(context_store, session_id, _c002_profile())
    result = await GuardrailsService(
        context_store=context_store,
        approval_queue=approval_queue,
    ).evaluate(_orchestrator_output(session_id), session_id)

    assert [action.action_id for action in result.approved_actions] == ["ACT-001"]
    assert [action.action_id for action in result.flagged_actions] == ["ACT-002"]
    act_001_checks = [check for check in result.checks if check.details["action_id"] == "ACT-001"]
    assert len(act_001_checks) == 8
    assert all(check.status == "APPROVED" for check in act_001_checks)
    act_002_flags = [
        check.message
        for check in result.checks
        if check.details["action_id"] == "ACT-002" and check.status == "FLAGGED"
    ]
    assert act_002_flags == [
        "B-002: standard approval",
        "AI-002: CRM unavailable on account action",
    ]
    pending = await approval_queue.get_pending()
    assert pending[0].priority == "STANDARD"
    assert pending[0].sla_deadline - pending[0].created_at == timedelta(hours=4)


async def test_regulatory_block_stops_before_business_policy_rules():
    context_store = MemoryContextStore()
    session_id = "sess_C002_layer4_block"
    await _store_profile(context_store, session_id, _c002_profile())
    output = _orchestrator_output(
        session_id,
        actions=[
            ProposedAction(
                action_id="ACT-BLOCK",
                action_type="SEND_PUSH_NOTIFICATION",
                requires_approval=False,
                channel=Channel.PUSH,
                customer_message="Pay today or legal action may follow.",
                metadata={"intervention_7d": 0},
            )
        ],
    )

    result = await GuardrailsService(context_store=context_store).evaluate(output, session_id)

    assert [action.action_id for action in result.blocked_actions] == ["ACT-BLOCK"]
    assert [check.rule_id for check in result.checks] == ["R-001"]
    assert "B-001" not in {check.rule_id for check in result.checks}


async def test_rule_hot_reload_applies_changed_threshold(tmp_path):
    rules_dir = tmp_path / "rules"
    shutil.copytree(Path("rules"), rules_dir)
    loader = RuleLoader(rules_dir=rules_dir)
    rules = await loader.load_rules()
    action = ProposedAction(
        action_id="ACT-001",
        action_type="SEND_PUSH_NOTIFICATION",
        requires_approval=False,
        channel=Channel.PUSH,
        customer_message="We may be able to help.",
        metadata={"intervention_7d": 3},
    )
    profile = _c002_profile()
    before = RuleEvaluator().evaluate(action, profile, rules, categories=("BUSINESS_POLICY",))
    assert any(check.rule_id == "B-001" and check.status == "FLAGGED" for check in before)

    rule_path = rules_dir / "business_policy" / "b001_contact_frequency.yaml"
    data = yaml.safe_load(rule_path.read_text(encoding="utf-8"))
    data["condition"]["value"] = 99
    rule_path.write_text(yaml.safe_dump(data), encoding="utf-8")

    reloaded = await loader.get_rules()
    after = RuleEvaluator().evaluate(action, profile, reloaded, categories=("BUSINESS_POLICY",))
    assert any(check.rule_id == "B-001" and check.status == "APPROVED" for check in after)


def test_fairness_balanced_data_returns_approved():
    records = [
        {
            "action_type": "CREATE_HARDSHIP_ENROLLMENT_CASE",
            "customer_segment": "STANDARD",
            "cohort": "A",
            "offered": True,
        },
        {
            "action_type": "CREATE_HARDSHIP_ENROLLMENT_CASE",
            "customer_segment": "STANDARD",
            "cohort": "A",
            "offered": False,
        },
        {
            "action_type": "CREATE_HARDSHIP_ENROLLMENT_CASE",
            "customer_segment": "STANDARD",
            "cohort": "B",
            "offered": True,
        },
        {
            "action_type": "CREATE_HARDSHIP_ENROLLMENT_CASE",
            "customer_segment": "STANDARD",
            "cohort": "B",
            "offered": False,
        },
    ]

    result = BisgFairnessChecker().check(
        "CREATE_HARDSHIP_ENROLLMENT_CASE",
        "STANDARD",
        records,
    )

    assert result.status == "APPROVED"
    assert result.details["air"] == 1.0


def test_confidence_check_flags_low_hardship_confidence():
    action = ProposedAction(
        action_id="ACT-002",
        action_type="CREATE_HARDSHIP_ENROLLMENT_CASE",
        requires_approval=True,
    )

    result = ConfidenceCheck().check(action, agent_confidence=0.65, partial_context=False)

    assert result.status == "FLAGGED"
    assert result.rule_id == "AI-001"


async def _store_profile(context_store, session_id, profile):
    await context_store.set(
        f"session:{session_id}:customer_profile",
        profile.model_dump_json(),
        ttl=300,
    )


def _orchestrator_output(session_id, actions=None):
    proposed_actions = actions or [
        ProposedAction(
            action_id="ACT-001",
            action_type="SEND_PUSH_NOTIFICATION",
            requires_approval=False,
            channel=Channel.PUSH,
            customer_message="We noticed recent account activity and may be able to help.",
            metadata={"intervention_7d": 0, "sms_ok": True},
        ),
        ProposedAction(
            action_id="ACT-002",
            action_type="CREATE_HARDSHIP_ENROLLMENT_CASE",
            requires_approval=True,
            case_type="PAYMENT_DEFERRAL_90_DAY",
            amount=Decimal("420.00"),
            approval_reason="Standard approval queue for account action.",
            metadata={"open_hardship_case": False},
        ),
    ]
    risk = RiskAssessment(
        risk_level="CRITICAL",
        risk_score=0.71,
        confidence=0.89,
        lower_confidence_reason="CRM unavailable -- NPS and tenure absent",
        primary_signals=["2 missed payments", "checking below $500"],
        protective_signals=[],
        policy_match=PolicyMatch(
            hardship_eligible=True,
            reason="2+ missed payments and checking below $500",
            policy_ref="KB-HARD-001-v2.3",
        ),
        recommended_next="InterventionAgent",
    )
    return OrchestratorOutput(
        trace_id=f"trace_{session_id}",
        session_id=session_id,
        customer_id="C002",
        scenario="payment_risk_intervention",
        status="PENDING_GUARDRAILS",
        agent_outputs=[
            AgentOutput(
                agent_name="RiskScoringAgent",
                output=risk.model_dump(mode="json"),
                latency_ms=12,
            )
        ],
        proposed_actions=proposed_actions,
        branch_decisions=[],
        requires_approval=True,
        orchestration_ms=22,
    )


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
