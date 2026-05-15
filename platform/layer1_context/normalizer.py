"""Source data normalization for Layer 1 context assembly.

Author: Sarala Biswal
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from platform.core.schemas import (
    BankingProfile,
    BehavioralProfile,
    CardProfile,
    Channel,
    CRMProfile,
    CustomerProfile,
    ModelSignals,
    Segment,
)
from typing import Any


def normalize_card(raw: dict[str, Any] | None) -> CardProfile:
    """Map raw card source fields to the canonical card schema."""
    if raw is None:
        return CardProfile(
            balance=Decimal("0"),
            credit_limit=Decimal("1"),
            utilization=0.0,
            missed_pmts=0,
        )
    balance = Decimal(str(raw["bal"]))
    credit_limit = Decimal(str(raw["limit"]))
    utilization = float(balance / credit_limit) if credit_limit else 0.0
    return CardProfile(
        balance=balance,
        credit_limit=credit_limit,
        utilization=round(utilization, 2),
        missed_pmts=int(raw["missed_pmts_90d"]),
        past_due=Decimal(str(raw.get("past_due_amt", "0"))),
        days_since_last_payment=int(raw["days_since_last_pmt"]),
    )


def normalize_banking(raw: dict[str, Any] | None) -> BankingProfile:
    """Map raw core-banking fields to the canonical banking schema."""
    if raw is None:
        return BankingProfile(checking_balance=Decimal("0"), savings_balance=Decimal("0"))
    return BankingProfile(
        checking_balance=Decimal(str(raw["checking_amt"])),
        savings_balance=Decimal(str(raw["savings_amt"])),
        last_deposit_at=datetime.fromisoformat(str(raw["last_dep_ts"])),
        overdrafts_30d=int(raw["od_30d"]),
        direct_deposit=bool(raw["dd_flag"]),
    )


def normalize_crm(raw: dict[str, Any] | None) -> CRMProfile | None:
    """Map raw CRM fields to the canonical CRM schema, or None when degraded."""
    if raw is None:
        return None
    return CRMProfile(
        tenure_months=int(raw["tenure_m"]),
        nps_score=int(raw["nps"]),
        open_tickets=int(raw["open_case_count"]),
        last_contact_at=datetime.fromisoformat(str(raw["last_touch_ts"])),
    )


def normalize_behavioral(raw: dict[str, Any] | None) -> BehavioralProfile:
    """Map raw behavioral fields to the canonical behavioral schema."""
    if raw is None:
        return BehavioralProfile(
            app_logins_30d=0,
            preferred_channel=Channel.MOBILE,
            sms_ok=False,
            push_enabled=False,
            email_ok=False,
        )
    return BehavioralProfile(
        app_logins_30d=int(raw["logins_30"]),
        preferred_channel=Channel(str(raw["pref_channel"])),
        sms_ok=bool(raw["sms_consent"]),
        push_enabled=bool(raw["push_ok"]),
        email_ok=bool(raw["email_consent"]),
    )


def normalize_customer_profile(
    customer_id: str,
    source_data: dict[str, dict[str, Any] | None],
    signals: ModelSignals,
    assembled_at: datetime,
    assembly_latency_ms: int,
    sources_available: list[str],
    sources_degraded: list[str],
) -> CustomerProfile:
    """Merge normalized source data and model signals into a CustomerProfile."""
    card_raw = source_data.get("card")
    name = str(card_raw.get("display_name", customer_id)) if card_raw else customer_id
    segment = (
        Segment(str(card_raw.get("segment_code", "STANDARD")))
        if card_raw
        else Segment.STANDARD
    )
    return CustomerProfile(
        customer_id=customer_id,
        name=name,
        segment=segment,
        card=normalize_card(card_raw),
        banking=normalize_banking(source_data.get("banking")),
        crm=normalize_crm(source_data.get("crm")),
        behavioral=normalize_behavioral(source_data.get("behavioral")),
        signals=signals,
        assembled_at=assembled_at,
        assembly_latency_ms=assembly_latency_ms,
        sources_available=sources_available,
        sources_degraded=sources_degraded,
        partial_context=bool(sources_degraded),
    )
