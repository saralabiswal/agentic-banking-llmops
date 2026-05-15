"""Behavioral signals source adapter.

Author: Sarala Biswal
"""

from __future__ import annotations

import asyncio
from typing import Any

BEHAVIORAL_FIXTURES: dict[str, dict[str, Any]] = {
    "C001": {
        "behavior_id": "beh-001",
        "logins_30": 8,
        "pref_channel": "WEB",
        "sms_consent": True,
        "push_ok": True,
        "email_consent": True,
    },
    "C002": {
        "behavior_id": "beh-002",
        "logins_30": 14,
        "pref_channel": "MOBILE",
        "sms_consent": True,
        "push_ok": True,
        "email_consent": True,
    },
    "C003": {
        "behavior_id": "beh-003",
        "logins_30": 5,
        "pref_channel": "MOBILE",
        "sms_consent": False,
        "push_ok": True,
        "email_consent": True,
    },
}


class BehavioralSignalsAdapter:
    """Simulates the behavioral signals API."""

    name = "behavioral"

    async def fetch(self, customer_id: str) -> dict[str, Any]:
        """Fetch raw behavioral signal data for a customer."""
        await asyncio.sleep(0.089)
        return dict(BEHAVIORAL_FIXTURES[customer_id])
