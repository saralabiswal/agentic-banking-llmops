"""CRM source adapter.

Author: Sarala Biswal
"""

from __future__ import annotations

import asyncio
from typing import Any

CRM_FIXTURES: dict[str, dict[str, Any]] = {
    "C001": {
        "crm_id": "crm-001",
        "tenure_m": 84,
        "nps": 74,
        "open_case_count": 0,
        "last_touch_ts": "2026-05-02T16:00:00+00:00",
    },
    "C002": {
        "crm_id": "crm-002",
        "tenure_m": 18,
        "nps": 12,
        "open_case_count": 1,
        "last_touch_ts": "2026-05-10T16:00:00+00:00",
    },
    "C003": {
        "crm_id": "crm-003",
        "tenure_m": 120,
        "nps": 88,
        "open_case_count": 0,
        "last_touch_ts": "2026-04-29T16:00:00+00:00",
    },
}


class CRMAdapter:
    """Simulates the CRM API and the C002 payment-risk timeout path."""

    name = "crm"

    def __init__(self) -> None:
        """Create a CRM adapter with scenario context set by the caller."""
        self.scenario = ""

    async def fetch(self, customer_id: str) -> dict[str, Any]:
        """Fetch raw CRM data for a customer."""
        if customer_id == "C002" and self.scenario == "payment_risk_intervention":
            await asyncio.sleep(0.160)
        else:
            await asyncio.sleep(0.050)
        return dict(CRM_FIXTURES[customer_id])
