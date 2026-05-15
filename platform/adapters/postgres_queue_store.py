"""PostgreSQL-backed approval queue adapter.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.adapters.postgres_feature_store import normalize_postgres_url
from platform.core.schemas import ApprovalQueueItem
from typing import Any

import psycopg
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


class PostgresQueueStore:
    """QueueStore implementation for human approval workflow."""

    def __init__(self, url: str) -> None:
        """Store the connection URL for lazy async queue operations."""
        self._url = normalize_postgres_url(url)

    async def _connect(self) -> AsyncConnection[Any]:
        """Create an async psycopg connection."""
        return await psycopg.AsyncConnection.connect(self._url, row_factory=dict_row)

    async def enqueue(self, item: ApprovalQueueItem) -> None:
        """Persist an approval queue item."""
        async with await self._connect() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                    INSERT INTO approval_queue
                        (
                            queue_id, trace_id, customer_id, priority, status,
                            proposed_action, flags, sla_deadline, created_at,
                            decided_at, decision_reason
                        )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (queue_id) DO NOTHING
                    """,
                (
                    item.queue_id,
                    str(item.context.get("trace_id", "")),
                    str(item.context.get("customer_id", "")),
                    item.priority,
                    item.status,
                    Jsonb(item.action.model_dump(mode="json")),
                    Jsonb(item.flag_reasons),
                    item.sla_deadline,
                    item.created_at,
                    item.decision_at,
                    item.rejection_reason,
                ),
            )

    async def dequeue_pending(self, priority: str | None, limit: int) -> list[ApprovalQueueItem]:
        """Return pending items ordered by nearest SLA deadline first."""
        query = "SELECT proposed_action, flags, * FROM approval_queue WHERE status = 'PENDING'"
        params: list[Any] = []
        if priority is not None:
            query += " AND priority = %s"
            params.append(priority)
        query += " ORDER BY sla_deadline ASC LIMIT %s"
        params.append(limit)

        async with await self._connect() as conn, conn.cursor() as cur:
            await cur.execute(query, params)
            rows = await cur.fetchall()

        items: list[ApprovalQueueItem] = []
        for row in rows:
            items.append(
                ApprovalQueueItem(
                    queue_id=str(row["queue_id"]),
                    status=str(row["status"]),
                    priority=str(row["priority"]),
                    created_at=row["created_at"],
                    sla_deadline=row["sla_deadline"],
                    escalation_at=row["sla_deadline"],
                    action=row["proposed_action"],
                    flag_reasons=list(row["flags"]),
                    context={
                        "trace_id": row["trace_id"],
                        "customer_id": row["customer_id"],
                    },
                    decision=None,
                )
            )
        return items

    async def update_decision(self, queue_id: str, decision: str, reason: str) -> None:
        """Mark a queue item as approved or rejected."""
        async with await self._connect() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                    UPDATE approval_queue
                    SET status = %s, decided_at = NOW(), decision_reason = %s
                    WHERE queue_id = %s
                    """,
                (decision, reason, queue_id),
            )
