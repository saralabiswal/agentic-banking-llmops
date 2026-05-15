"""Dynamic retrieval query construction from customer context.

Author: Sarala Biswal
"""

from __future__ import annotations

from decimal import Decimal
from platform.core.schemas import CustomerProfile, Scenario


def build_retrieval_query(profile: CustomerProfile, scenario: str) -> str:
    """Construct a semantically rich retrieval query from customer signals."""
    match scenario:
        case Scenario.PAYMENT_RISK.value:
            return _payment_risk_query(profile)
        case Scenario.BILLING_DISPUTE.value:
            return _billing_dispute_query(profile)
        case Scenario.CHURN_PREVENTION.value:
            return _churn_prevention_query(profile)
        case _:
            return _generic_query(profile, scenario)


def _payment_risk_query(profile: CustomerProfile) -> str:
    risk_level = (
        "critical"
        if profile.signals.risk_score > 0.70
        else "high"
        if profile.signals.risk_score > 0.50
        else "moderate"
    )
    hardship_signals: list[str] = []
    if profile.card.missed_pmts > 0:
        payment_word = "payment" if profile.card.missed_pmts == 1 else "payments"
        hardship_signals.append(f"{profile.card.missed_pmts} missed {payment_word}")
    if profile.banking.checking_balance < Decimal("500"):
        hardship_signals.append(f"checking balance {_currency(profile.banking.checking_balance)}")
    if not profile.banking.direct_deposit:
        hardship_signals.append("no direct deposit")
    if not hardship_signals:
        hardship_signals.append("no acute hardship indicators")

    return (
        f"Customer with {risk_level} payment risk. "
        f"{', '.join(hardship_signals)}. "
        f"Utilization {profile.card.utilization:.0%}. "
        f"Payment propensity {profile.signals.payment_propensity:.0%}. "
        "Hardship program eligibility, intervention options, payment deferral, "
        "contact frequency."
    )


def _billing_dispute_query(profile: CustomerProfile) -> str:
    ticket_count = profile.crm.open_tickets if profile.crm is not None else 0
    return (
        "Customer billing dispute resolution. "
        f"Open servicing tickets {ticket_count}. "
        f"Segment {profile.segment.value}. "
        "Regulation E section 1005.11 investigation timing, provisional credit, "
        "customer notice requirements, suppress payment pressure during dispute."
    )


def _churn_prevention_query(profile: CustomerProfile) -> str:
    return (
        "Customer churn prevention and retention offer evaluation. "
        f"Churn probability {profile.signals.churn_probability:.0%}. "
        f"Estimated CLV {_currency(profile.signals.clv_estimate)}. "
        f"Segment {profile.segment.value}. "
        "Credit limit policy, responsible lending suppressions, retention offer options."
    )


def _generic_query(profile: CustomerProfile, scenario: str) -> str:
    return (
        f"Customer scenario {scenario}. "
        f"Risk score {profile.signals.risk_score:.0%}. "
        f"Churn probability {profile.signals.churn_probability:.0%}. "
        f"Segment {profile.segment.value}. Relevant banking policy and compliance guidance."
    )


def _currency(value: Decimal) -> str:
    return f"${value:.2f}"
