"""Tests for core Pydantic schemas.

Author: Sarala Biswal
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from platform.core.schemas import (
    AssemblyResult,
    BankingProfile,
    BehavioralProfile,
    CardProfile,
    Channel,
    CRMProfile,
    CustomerProfile,
    ModelSignals,
    Segment,
)

import pytest
from pydantic import ValidationError


def _now() -> datetime:
    """Return a stable timezone-aware timestamp for schema tests."""
    return datetime(2026, 5, 11, 10, 42, 33, tzinfo=UTC)


def test_customer_profile_accepts_valid_data() -> None:
    """Valid Marcus Webb profile data should validate."""
    profile = CustomerProfile(
        customer_id="C002",
        name="Marcus Webb",
        segment=Segment.STANDARD,
        card=CardProfile(
            balance=Decimal("3800"),
            credit_limit=Decimal("5000"),
            utilization=0.76,
            missed_pmts=2,
            past_due=Decimal("420"),
            days_since_last_payment=41,
        ),
        banking=BankingProfile(
            checking_balance=Decimal("312.40"),
            savings_balance=Decimal("0"),
            last_deposit_at=_now(),
            overdrafts_30d=1,
            direct_deposit=False,
        ),
        crm=None,
        behavioral=BehavioralProfile(
            app_logins_30d=14,
            preferred_channel=Channel.MOBILE,
            sms_ok=True,
            push_enabled=True,
        ),
        signals=ModelSignals(
            risk_score=0.71,
            churn_probability=0.58,
            clv_estimate=Decimal("1240"),
            last_intervention=_now(),
            intervention_7d=0,
            payment_propensity=0.31,
            model_versions={"risk": "risk-v4.2.1"},
        ),
        assembled_at=_now(),
        assembly_latency_ms=167,
        sources_available=["card", "banking", "behavioral", "feature_store"],
        sources_degraded=["crm"],
        partial_context=True,
    )

    assert profile.card.missed_pmts == 2
    assert profile.crm is None
    assert profile.partial_context is True


def test_invalid_score_values_are_rejected() -> None:
    """Scores outside the documented 0.0 to 1.0 range should fail validation."""
    with pytest.raises(ValidationError):
        ModelSignals(
            risk_score=1.25,
            churn_probability=0.58,
            clv_estimate=Decimal("1240"),
            payment_propensity=0.31,
            model_versions={"risk": "risk-v4.2.1"},
        )


def test_optional_fields_default_correctly() -> None:
    """Optional and list fields should use documented defaults."""
    result = AssemblyResult(
        status="ASSEMBLED",
        session_id="sess_C002_20260511_104233_f3a2b9",
        customer_id="C002",
        partial_context=False,
        ttl_expires_at=_now() + timedelta(seconds=300),
        assembly_ms=166,
    )
    crm = CRMProfile(tenure_months=24)

    assert result.sources_degraded == []
    assert crm.nps_score is None
    assert crm.open_tickets == 0


def test_enums_reject_invalid_values() -> None:
    """Enum-backed fields should reject unsupported values."""
    with pytest.raises(ValidationError):
        CustomerProfile(
            customer_id="C001",
            name="Alexandra Chen",
            segment="GOLD",
            card=CardProfile(
                balance=Decimal("800"),
                credit_limit=Decimal("10000"),
                utilization=0.08,
                missed_pmts=0,
            ),
            banking=BankingProfile(
                checking_balance=Decimal("5000"),
                savings_balance=Decimal("12000"),
            ),
            behavioral=BehavioralProfile(
                app_logins_30d=4,
                preferred_channel=Channel.WEB,
                sms_ok=True,
                push_enabled=True,
            ),
            signals=ModelSignals(
                risk_score=0.08,
                churn_probability=0.04,
                clv_estimate=Decimal("6400"),
                payment_propensity=0.82,
                model_versions={"risk": "risk-v4.2.1"},
            ),
            assembled_at=_now(),
            assembly_latency_ms=120,
            sources_available=["card", "banking", "crm", "behavioral", "feature_store"],
        )
