"""Guardrails API router.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.api.dependencies import get_runner
from platform.layer6_sdk.blueprint_runner import BlueprintRunner

from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter()


class DecisionRequest(BaseModel):
    """Request body for recording a human approval decision."""

    decision: str
    reason: str = ""


@router.get("/guardrails/rules")
async def get_rules() -> list[dict[str, object]]:
    """Return seeded guardrail rule metadata for the UI shell."""
    return [
        {
            "rule_id": "R-001",
            "category": "REGULATORY",
            "version": "2.0",
            "description": "UDAAP communication language blocklist",
            "condition": {"field": "customer_message", "operator": "CONTAINS_ANY"},
            "outcome": "BLOCK",
        },
        {
            "rule_id": "R-002",
            "category": "REGULATORY",
            "version": "2.0",
            "description": "TCPA consent required for SMS actions",
            "condition": {"field": "metadata.sms_ok", "operator": "EQUALS", "value": False},
            "outcome": "BLOCK",
        },
        {
            "rule_id": "R-003",
            "category": "REGULATORY",
            "version": "1.4",
            "description": "Fair lending adverse action protection",
            "condition": {"field": "metadata.adverse_action_notice", "operator": "EQUALS"},
            "outcome": "BLOCK",
        },
        {
            "rule_id": "B-001",
            "category": "BUSINESS_POLICY",
            "version": "3.1",
            "description": "Contact frequency cap",
            "condition": {
                "field": "metadata.intervention_7d",
                "operator": "GREATER_THAN",
                "value": 2,
            },
            "outcome": "FLAG",
        },
        {
            "rule_id": "B-002",
            "category": "BUSINESS_POLICY",
            "version": "3.1",
            "description": "Supervisor approval threshold",
            "condition": {"field": "requires_approval", "operator": "EQUALS", "value": True},
            "outcome": "FLAG",
        },
        {
            "rule_id": "AI-001",
            "category": "RESPONSIBLE_AI",
            "version": "1.0",
            "description": "Minimum confidence by action type",
            "condition": {"field": "confidence", "operator": "GREATER_THAN_OR_EQUAL"},
            "outcome": "FLAG",
        },
        {
            "rule_id": "AI-002",
            "category": "RESPONSIBLE_AI",
            "version": "1.0",
            "description": "Partial context review for account actions",
            "condition": {"field": "partial_context", "operator": "EQUALS", "value": True},
            "outcome": "FLAG",
        },
    ]


@router.get("/guardrails/queue")
async def get_queue(runner: BlueprintRunner = Depends(get_runner)) -> list[dict[str, object]]:
    """Return pending approval queue items."""
    pending = await runner.approval_queue.get_pending()
    return [item.model_dump(mode="json") for item in pending]


@router.post("/guardrails/queue/{queue_id}/decision")
@router.put("/guardrails/queue/{queue_id}/decision")
async def record_decision(
    queue_id: str,
    request: DecisionRequest,
    runner: BlueprintRunner = Depends(get_runner),
) -> dict[str, str]:
    """Record a reviewer decision for a pending approval item."""
    await runner.approval_queue.record_decision(queue_id, request.decision, request.reason)
    return {"status": "recorded"}
