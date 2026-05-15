"""Core banking source adapter.

Author: Sarala Biswal
"""

from __future__ import annotations

import asyncio
from typing import Any

BANKING_FIXTURES: dict[str, dict[str, Any]] = {
    "C001": {
        "core_id": "bank-001",
        "checking_amt": "5000",
        "savings_amt": "12000",
        "last_dep_ts": "2026-05-09T09:00:00+00:00",
        "od_30d": 0,
        "dd_flag": True,
    },
    "C002": {
        "core_id": "bank-002",
        "checking_amt": "312.40",
        "savings_amt": "0",
        "last_dep_ts": "2026-04-15T09:00:00+00:00",
        "od_30d": 1,
        "dd_flag": False,
    },
    "C003": {
        "core_id": "bank-003",
        "checking_amt": "18500",
        "savings_amt": "72000",
        "last_dep_ts": "2026-05-10T09:00:00+00:00",
        "od_30d": 0,
        "dd_flag": True,
    },
}


class CoreBankingAdapter:
    """Simulates the Core Banking API."""

    name = "banking"

    async def fetch(self, customer_id: str) -> dict[str, Any]:
        """Fetch raw core banking data for a customer."""
        await asyncio.sleep(0.061)
        return dict(BANKING_FIXTURES[customer_id])
