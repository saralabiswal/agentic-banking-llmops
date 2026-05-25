"""Pydantic schemas for cross-boundary platform data.

Author: Sarala Biswal
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from platform.memory.schemas import CustomerMemory
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class FrozenModel(BaseModel):
    """Immutable base model for platform schemas."""

    model_config = ConfigDict(frozen=True)


class Segment(str, Enum):
    """Customer banking segment."""

    STANDARD = "STANDARD"
    PRIME = "PRIME"
    AFFLUENT = "AFFLUENT"
    PRIVATE = "PRIVATE"


class Channel(str, Enum):
    """Customer communication or interaction channel."""

    MOBILE = "MOBILE"
    WEB = "WEB"
    PHONE = "PHONE"
    BRANCH = "BRANCH"
    SMS = "SMS"
    PUSH = "PUSH"
    EMAIL = "EMAIL"
    CRM = "CRM"


class Scenario(str, Enum):
    """Supported decision scenarios."""

    PAYMENT_RISK = "payment_risk_intervention"
    BILLING_DISPUTE = "billing_dispute_resolution"
    CHURN_PREVENTION = "churn_prevention"


class CardProfile(FrozenModel):
    """Canonical card-system profile fields."""

    balance: Decimal
    credit_limit: Decimal
    utilization: float = Field(ge=0.0, le=1.0)
    missed_pmts: int = Field(ge=0)
    past_due: Decimal = Decimal("0")
    days_since_last_payment: int | None = Field(default=None, ge=0)


class BankingProfile(FrozenModel):
    """Canonical core-banking profile fields."""

    checking_balance: Decimal
    savings_balance: Decimal
    last_deposit_at: datetime | None = None
    overdrafts_30d: int = Field(default=0, ge=0)
    direct_deposit: bool = False


class CRMProfile(FrozenModel):
    """Canonical CRM profile fields."""

    tenure_months: int = Field(ge=0)
    nps_score: int | None = Field(default=None, ge=-100, le=100)
    open_tickets: int = Field(default=0, ge=0)
    last_contact_at: datetime | None = None


class BehavioralProfile(FrozenModel):
    """Canonical behavioral signal profile fields."""

    app_logins_30d: int = Field(ge=0)
    preferred_channel: Channel
    sms_ok: bool
    push_enabled: bool
    email_ok: bool = True


class ModelSignals(FrozenModel):
    """Precomputed model signals with model lineage."""

    risk_score: float = Field(ge=0.0, le=1.0)
    churn_probability: float = Field(ge=0.0, le=1.0)
    clv_estimate: Decimal
    last_intervention: datetime | None = None
    intervention_7d: int = Field(default=0, ge=0)
    payment_propensity: float = Field(ge=0.0, le=1.0)
    model_versions: dict[str, str]


class CustomerProfile(FrozenModel):
    """Unified customer profile assembled from live sources and feature store."""

    customer_id: str
    name: str
    segment: Segment
    card: CardProfile
    banking: BankingProfile
    crm: CRMProfile | None = None
    behavioral: BehavioralProfile
    signals: ModelSignals
    assembled_at: datetime
    assembly_latency_ms: int = Field(ge=0)
    sources_available: list[str]
    sources_degraded: list[str] = Field(default_factory=list)
    long_term_memory: list[CustomerMemory] = Field(default_factory=list)
    partial_context: bool = False


class AssemblyResult(FrozenModel):
    """Layer 1 context assembly result."""

    status: Literal["ASSEMBLED", "DEGRADED", "FAILED"]
    session_id: str
    customer_id: str
    partial_context: bool
    sources_available: list[str] = Field(default_factory=list)
    sources_degraded: list[str] = Field(default_factory=list)
    model_versions_used: dict[str, str] = Field(default_factory=dict)
    ttl_expires_at: datetime
    assembly_ms: int = Field(ge=0)


class PolicyChunk(FrozenModel):
    """Policy, regulation, playbook, or compliance chunk retrieved for an agent."""

    chunk_id: str
    document_id: str
    document_title: str
    document_type: Literal["POLICY", "REGULATION", "PLAYBOOK", "COMPLIANCE"]
    doc_version: str
    raw_text: str
    rerank_score: float = Field(default=0.0, ge=0.0)
    chunk_type: Literal["DOCUMENT", "SECTION", "PARAGRAPH"] = "PARAGRAPH"
    parent_chunk_id: str | None = None
    product_line: str | None = None
    jurisdiction: str | None = None


class RetrievalResult(FrozenModel):
    """Layer 2 policy retrieval result."""

    session_id: str
    query: str
    chunks: list[PolicyChunk]
    kb_version: str
    retrieval_ms: int = Field(ge=0)
    embedding_model: str
    reranker_model: str


class AgentOutput(FrozenModel):
    """Generic validated agent output envelope."""

    agent_name: str
    output: dict[str, Any]
    latency_ms: int = Field(ge=0)


class OrchestratorOutput(FrozenModel):
    """Layer 3 orchestration result handed to guardrails."""

    trace_id: str
    session_id: str
    customer_id: str
    scenario: str
    status: Literal["PENDING_GUARDRAILS", "HUMAN_REVIEW", "FAILED"]
    agent_outputs: list[AgentOutput]
    proposed_actions: list[ProposedAction] = Field(default_factory=list)
    branch_decisions: list[dict[str, Any]] = Field(default_factory=list)
    requires_approval: bool
    orchestration_ms: int = Field(ge=0)


class AgentContext(FrozenModel):
    """Typed contract passed from orchestrator to specialized agents."""

    session_id: str
    customer_id: str
    scenario: str
    pipeline_step: int = Field(ge=0)
    trace_id: str
    policy_chunks: list[PolicyChunk]
    prior_outputs: list[AgentOutput] = Field(default_factory=list)
    authorized_tools: list[str]
    max_tokens: int = Field(gt=0)
    timeout_ms: int = Field(gt=0)


class PolicyMatch(FrozenModel):
    """Policy match details used by agent outputs."""

    hardship_eligible: bool = False
    reason: str
    policy_ref: str


class RiskAssessment(FrozenModel):
    """Output schema for the RiskScoringAgent."""

    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    risk_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    lower_confidence_reason: str | None = None
    primary_signals: list[str]
    protective_signals: list[str] = Field(default_factory=list)
    policy_match: PolicyMatch
    recommended_next: str


class ProposedAction(FrozenModel):
    """Action proposed by an agent and evaluated by guardrails before execution."""

    action_id: str
    action_type: str
    requires_approval: bool
    channel: Channel | None = None
    case_type: str | None = None
    amount: Decimal | None = None
    approval_reason: str | None = None
    customer_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyCompliance(FrozenModel):
    """Policy compliance evidence attached to an intervention proposal."""

    contact_frequency_ok: bool
    reason: str
    policy_ref: str


class InterventionProposal(FrozenModel):
    """Output schema for the InterventionAgent."""

    intervention_type: str
    intervention_channel: Channel
    customer_message: str
    internal_note: str
    proposed_actions: list[ProposedAction]
    policy_compliance: PolicyCompliance
    estimated_impact: str
    fallback_if_no_response: str | None = None


class CheckResult(FrozenModel):
    """Single guardrail check result."""

    status: Literal["APPROVED", "FLAGGED", "BLOCKED"]
    rule_id: str
    category: Literal["REGULATORY", "BUSINESS_POLICY", "RESPONSIBLE_AI"]
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class GuardrailsResult(FrozenModel):
    """Layer 4 guardrails evaluation result."""

    trace_id: str
    session_id: str
    customer_id: str
    approved_actions: list[ProposedAction] = Field(default_factory=list)
    flagged_actions: list[ProposedAction] = Field(default_factory=list)
    blocked_actions: list[ProposedAction] = Field(default_factory=list)
    checks: list[CheckResult]
    requires_human_review: bool


class ApprovalQueueItem(FrozenModel):
    """Human approval queue item with SLA and feedback routing fields."""

    queue_id: str
    status: Literal["PENDING", "APPROVED", "REJECTED", "ESCALATED", "AUTO_REJECTED"]
    priority: Literal["URGENT", "HIGH", "STANDARD", "LOW"]
    created_at: datetime
    sla_deadline: datetime
    escalation_at: datetime
    assigned_to: str | None = None
    action: ProposedAction
    flag_reasons: list[str]
    context: dict[str, Any]
    decision: Literal["APPROVED", "REJECTED"] | None = None
    decision_by: str | None = None
    decision_at: datetime | None = None
    rejection_reason: str | None = None
    feedback_sent_to_agent: bool = False
    feedback_sent_to_mlops: bool = False


class ExperimentVariant(FrozenModel):
    """A/B experiment variant definition and counters."""

    experiment_id: str
    variant_id: str
    name: str
    weight: float = Field(ge=0.0, le=1.0)
    payload: dict[str, Any]
    sample_count: int = Field(default=0, ge=0)
    conversion_count: int = Field(default=0, ge=0)


class ExperimentResult(FrozenModel):
    """A/B experiment result statistics."""

    experiment_id: str
    variant_id: str
    sample_count: int = Field(ge=0)
    conversion_count: int = Field(ge=0)
    conversion_rate: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    is_winner: bool = False


class DeliveryReceipt(FrozenModel):
    """Delivery confirmation returned by a channel adapter."""

    receipt_id: str
    action_id: str
    channel: Channel
    status: Literal["DELIVERED", "FAILED", "QUEUED"]
    delivered_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionResult(FrozenModel):
    """Layer 6 action execution result returned to product teams."""

    trace_id: str
    action_id: str
    action_executed: bool
    status: Literal["EXECUTED", "PENDING_APPROVAL", "BLOCKED", "FAILED"]
    channel: Channel | None = None
    delivery_receipt: DeliveryReceipt | None = None
    outcome_tracking_id: str | None = None
    customer_message: str | None = None
    pending_actions: list[ApprovalQueueItem] = Field(default_factory=list)


class OutcomeEvent(FrozenModel):
    """Customer outcome event captured after action delivery."""

    outcome_id: str
    trace_id: str
    action_id: str
    customer_id: str
    outcome_type: Literal["PUSH_OPENED", "ENROLLED", "IGNORED", "OPT_OUT", "COMPLAINT"]
    outcome_ts: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditRecord(FrozenModel):
    """Unified immutable audit record base schema."""

    audit_id: str
    event_type: Literal[
        "CONTEXT_ASSEMBLY",
        "VECTOR_RETRIEVAL",
        "ORCHESTRATION_COMPLETE",
        "GUARDRAILS_EVALUATION",
        "AB_ASSIGNMENT",
        "ACTION_EXECUTED",
        "OUTCOME_CAPTURED",
        "MEMORY_RETRIEVED",
        "MEMORY_STORED",
    ]
    trace_id: str
    session_id: str
    customer_id: str
    timestamp: datetime
    layer: Literal["1", "2", "3", "4", "5", "6"]
    payload: dict[str, Any] = Field(default_factory=dict)
