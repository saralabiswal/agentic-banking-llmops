"""Outcome capture API router.

Author: Sarala Biswal
"""

from __future__ import annotations

from datetime import UTC, datetime
from platform.api.dependencies import get_outcome_router
from platform.core.schemas import OutcomeEvent
from platform.layer6_sdk.outcome_router import OutcomeRouter
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

router = APIRouter()

OutcomeType = Literal["PUSH_OPENED", "ENROLLED", "IGNORED", "OPT_OUT", "COMPLAINT"]


class OutcomeRequest(BaseModel):
    """Request body for recording a customer outcome."""

    action_id: str
    customer_id: str = "unknown"
    outcome_type: OutcomeType
    metadata: dict[str, object] = Field(default_factory=dict)


@router.post("/outcomes/{trace_id}")
async def record_outcome(
    trace_id: str,
    request: OutcomeRequest,
    router_dependency: OutcomeRouter = Depends(get_outcome_router),
) -> dict[str, str]:
    """Record and route an outcome event."""
    outcome = OutcomeEvent(
        outcome_id=f"out_{uuid4().hex[:12]}",
        trace_id=trace_id,
        action_id=request.action_id,
        customer_id=request.customer_id,
        outcome_type=request.outcome_type,
        outcome_ts=datetime.now(UTC),
        metadata=request.metadata,
    )
    await router_dependency.route(outcome)
    return {"status": "recorded", "outcome_id": outcome.outcome_id}
