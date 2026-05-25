"""Schemas for cross-session customer memory.

Author: Sarala Biswal
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    """Supported long-term memory categories."""

    INTERVENTION = "intervention"
    OUTCOME = "outcome"
    PREFERENCE = "preference"
    RESOLUTION = "resolution"
    RISK_EVENT = "risk_event"


class CustomerMemory(BaseModel):
    """Cross-session memory stored in the customer memory vector collection."""

    memory_id: str
    customer_id: str
    memory_type: MemoryType
    content: str
    embedding: list[float] | None = None
    session_id: str
    trace_id: str
    scenario: str
    outcome_signal: str | None = None
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
