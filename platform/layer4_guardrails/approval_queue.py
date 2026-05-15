"""Approval queue service with SLA tiers for flagged guardrail actions.

Author: Sarala Biswal
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from platform.core.interfaces import QueueStore
from platform.core.schemas import ApprovalQueueItem, CheckResult, ProposedAction
from platform.observability.metrics import metered
from platform.observability.tracing import traced
from typing import Literal

Priority = Literal["URGENT", "HIGH", "STANDARD", "LOW"]

SLA_BY_PRIORITY: dict[Priority, timedelta] = {
    "URGENT": timedelta(minutes=30),
    "HIGH": timedelta(hours=2),
    "STANDARD": timedelta(hours=4),
    "LOW": timedelta(hours=24),
}


class ApprovalQueueService:
    """Creates and manages approval queue items for flagged actions."""

    def __init__(self, queue_store: QueueStore | None = None) -> None:
        """Create an approval queue service."""
        self._queue_store = queue_store
        self._items: list[ApprovalQueueItem] = []

    @traced(layer="L4", operation="approval_enqueue")
    @metered(layer="L4")
    async def enqueue(
        self,
        action: ProposedAction,
        flags: list[CheckResult],
        context: dict[str, object],
        priority: Priority | None = None,
    ) -> ApprovalQueueItem:
        """Create a queue item with SLA deadline and optional persistence."""
        created_at = datetime.now(UTC)
        selected_priority = priority or derive_priority(flags)
        sla = SLA_BY_PRIORITY[selected_priority]
        item = ApprovalQueueItem(
            queue_id=f"appr_{created_at:%Y%m%d_%H%M%S_%f}_{action.action_id}",
            status="PENDING",
            priority=selected_priority,
            created_at=created_at,
            sla_deadline=created_at + sla,
            escalation_at=created_at + (sla * 2),
            assigned_to="reviewer_007",
            action=action,
            flag_reasons=[flag.message for flag in flags],
            context=context,
            decision=None,
            decision_by=None,
            decision_at=None,
            rejection_reason=None,
            feedback_sent_to_agent=False,
            feedback_sent_to_mlops=False,
        )
        self._items.append(item)
        if self._queue_store is not None:
            await self._queue_store.enqueue(item)
        return item

    @traced(layer="L4", operation="approval_get_pending")
    @metered(layer="L4")
    async def get_pending(self, limit: int = 50) -> list[ApprovalQueueItem]:
        """Return pending items ordered by SLA deadline."""
        pending = [item for item in self._items if item.status == "PENDING"]
        pending.sort(key=lambda item: item.sla_deadline)
        return pending[:limit]

    @traced(layer="L4", operation="approval_record_decision")
    @metered(layer="L4")
    async def record_decision(self, queue_id: str, decision: str, reason: str) -> None:
        """Record a human approval decision in memory and optional storage."""
        if self._queue_store is not None:
            await self._queue_store.update_decision(queue_id, decision, reason)
        updated: list[ApprovalQueueItem] = []
        for item in self._items:
            if item.queue_id == queue_id:
                updated.append(
                    item.model_copy(
                        update={
                            "status": decision,
                            "decision": decision,
                            "decision_at": datetime.now(UTC),
                            "rejection_reason": reason if decision == "REJECTED" else None,
                        }
                    )
                )
            else:
                updated.append(item)
        self._items = updated


def derive_priority(flags: list[CheckResult]) -> Priority:
    """Derive queue priority from flag category and severity."""
    if any(flag.category == "REGULATORY" or flag.severity == "CRITICAL" for flag in flags):
        return "URGENT"
    if any(flag.severity == "HIGH" for flag in flags):
        return "HIGH"
    if flags:
        return "STANDARD"
    return "LOW"
