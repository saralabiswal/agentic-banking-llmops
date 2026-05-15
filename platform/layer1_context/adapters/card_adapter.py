"""Card system source adapter.

Author: Sarala Biswal
"""

from __future__ import annotations

import asyncio
from typing import Any

CARD_FIXTURES: dict[str, dict[str, Any]] = {
    "C001": {
        "sys_id": "card-001",
        "display_name": "Alexandra Chen",
        "segment_code": "PRIME",
        "bal": "800",
        "limit": "10000",
        "missed_pmts_90d": 0,
        "past_due_amt": "0",
        "days_since_last_pmt": 6,
    },
    "C002": {
        "sys_id": "card-002",
        "display_name": "Marcus Webb",
        "segment_code": "STANDARD",
        "bal": "3800",
        "limit": "5000",
        "missed_pmts_90d": 2,
        "past_due_amt": "420",
        "days_since_last_pmt": 41,
    },
    "C003": {
        "sys_id": "card-003",
        "display_name": "Priya Sharma",
        "segment_code": "AFFLUENT",
        "bal": "450",
        "limit": "15000",
        "missed_pmts_90d": 0,
        "past_due_amt": "0",
        "days_since_last_pmt": 3,
    },
}


class CardSystemAdapter:
    """Simulates the Card System API with realistic source-shaped fields."""

    name = "card"

    async def fetch(self, customer_id: str) -> dict[str, Any]:
        """Fetch raw card data for a customer."""
        await asyncio.sleep(0.038)
        return dict(CARD_FIXTURES[customer_id])
