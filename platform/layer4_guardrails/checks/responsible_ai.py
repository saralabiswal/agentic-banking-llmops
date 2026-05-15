"""Responsible AI runtime checks for Layer 4.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.core.schemas import CheckResult, CustomerProfile, ProposedAction, RiskAssessment

CONFIDENCE_THRESHOLDS: dict[str, float] = {
    "SEND_PUSH_NOTIFICATION": 0.70,
    "SEND_SMS": 0.70,
    "CREATE_HARDSHIP_ENROLLMENT_CASE": 0.75,
    "APPLY_RATE_REDUCTION": 0.80,
    "ENROLL_PAYMENT_PLAN": 0.80,
    "ESCALATE_TO_COLLECTIONS": 0.85,
}

ACCOUNT_ACTIONS = {
    "CREATE_HARDSHIP_ENROLLMENT_CASE",
    "APPLY_RATE_REDUCTION",
    "ENROLL_PAYMENT_PLAN",
    "CREDIT_LIMIT_DECREASE",
}


class ConfidenceCheck:
    """Checks action confidence against per-action thresholds."""

    def __init__(self, thresholds: dict[str, float] | None = None) -> None:
        """Create a confidence checker."""
        self._thresholds = thresholds or CONFIDENCE_THRESHOLDS

    def check(
        self,
        action: ProposedAction,
        agent_confidence: float,
        partial_context: bool,
    ) -> CheckResult:
        """Return a confidence check result for an action."""
        threshold = self._thresholds.get(action.action_type, 0.70)
        if partial_context:
            threshold += 0.05
        status = "APPROVED" if agent_confidence >= threshold else "FLAGGED"
        message = (
            "AI-001: approved"
            if status == "APPROVED"
            else f"AI-001: confidence {agent_confidence:.2f} below threshold {threshold:.2f}"
        )
        return CheckResult(
            status=status,
            rule_id="AI-001",
            category="RESPONSIBLE_AI",
            severity="MEDIUM",
            message=message,
            details={"confidence": agent_confidence, "threshold": threshold},
        )


class PartialContextCheck:
    """Flags account-modifying actions when source context is degraded."""

    def check(self, action: ProposedAction, profile: CustomerProfile) -> CheckResult:
        """Return a partial-context check result."""
        flagged = profile.partial_context and action.action_type in ACCOUNT_ACTIONS
        return CheckResult(
            status="FLAGGED" if flagged else "APPROVED",
            rule_id="AI-002",
            category="RESPONSIBLE_AI",
            severity="MEDIUM",
            message=(
                "AI-002: CRM unavailable on account action" if flagged else "AI-002: approved"
            ),
            details={
                "partial_context": profile.partial_context,
                "sources_degraded": profile.sources_degraded,
            },
        )


class ConsistencyCheck:
    """Validates that high-severity risk outputs have enough profile support."""

    def check(self, risk_assessment: RiskAssessment, profile: CustomerProfile) -> CheckResult:
        """Return a consistency check result."""
        supporting = 0
        if risk_assessment.risk_level == "CRITICAL":
            if profile.card.missed_pmts >= 2:
                supporting += 1
            if profile.card.utilization > 0.70:
                supporting += 1
            if profile.banking.checking_balance < 500:
                supporting += 1
            if profile.signals.risk_score > 0.65:
                supporting += 1
            if profile.signals.payment_propensity < 0.40:
                supporting += 1
        status = (
            "APPROVED"
            if risk_assessment.risk_level != "CRITICAL" or supporting >= 2
            else "FLAGGED"
        )
        return CheckResult(
            status=status,
            rule_id="AI-003",
            category="RESPONSIBLE_AI",
            severity="MEDIUM",
            message=(
                "AI-003: approved"
                if status == "APPROVED"
                else f"AI-003: CRITICAL risk has only {supporting}/5 supporting signals"
            ),
            details={"supporting_signals": supporting},
        )


class AnomalyCheck:
    """Checks recent action distributions for simple 3-sigma anomalies."""

    def check(self, action_type: str, recent_actions: list[str]) -> CheckResult:
        """Return an anomaly check result."""
        if not recent_actions:
            z_score = 0.0
        else:
            share = recent_actions.count(action_type) / len(recent_actions)
            z_score = 0.0 if share <= 0.95 else 3.1
        status = "FLAGGED" if z_score > 3.0 else "APPROVED"
        return CheckResult(
            status=status,
            rule_id="AI-004",
            category="RESPONSIBLE_AI",
            severity="MEDIUM",
            message=(
                "AI-004: action distribution anomaly"
                if status == "FLAGGED"
                else "AI-004: approved"
            ),
            details={"z_score": z_score},
        )
