"""Layer 6 helper for writing outcome memory.

Author: Sarala Biswal
"""

from __future__ import annotations

from datetime import UTC, datetime
from platform.core.interfaces import AuditWriter, MemoryStore
from platform.core.schemas import AuditRecord, OutcomeEvent
from platform.memory.schemas import CustomerMemory, MemoryType
from uuid import uuid4

import structlog

logger = structlog.get_logger()


class MemoryWriter:
    """Writes customer outcome events into the long-term memory store."""

    def __init__(
        self,
        memory_store: MemoryStore,
        audit_writer: AuditWriter | None = None,
    ) -> None:
        """Create a memory writer with injected storage and audit dependencies."""
        self._memory_store = memory_store
        self._audit_writer = audit_writer

    async def write(self, outcome: OutcomeEvent) -> str:
        """Convert an outcome event into an OUTCOME memory and store it."""
        scenario = str(outcome.metadata.get("scenario", "unknown"))
        session_id = str(outcome.metadata.get("session_id", "unknown"))
        memory = CustomerMemory(
            memory_id=str(uuid4()),
            customer_id=outcome.customer_id,
            memory_type=MemoryType.OUTCOME,
            content=(
                f"Scenario {scenario}: action {outcome.action_id}, "
                f"outcome {outcome.outcome_type}"
            ),
            session_id=session_id,
            trace_id=outcome.trace_id,
            scenario=scenario,
            outcome_signal=outcome.outcome_type,
            created_at=datetime.now(UTC),
            metadata={
                "action_id": outcome.action_id,
                "outcome_id": outcome.outcome_id,
                "experiment_id": outcome.metadata.get("experiment_id"),
                "variant_id": outcome.metadata.get("variant_id"),
            },
        )
        memory_id = await self._memory_store.store(memory)
        await self._write_audit(memory, memory_id)
        logger.info(
            "memory.outcome_written",
            trace_id=outcome.trace_id,
            customer_id=outcome.customer_id,
            scenario=scenario,
            memory_id=memory_id,
        )
        return memory_id

    async def _write_audit(self, memory: CustomerMemory, memory_id: str) -> None:
        """Write the MEMORY_STORED audit record."""
        if self._audit_writer is None:
            return
        await self._audit_writer.write(
            AuditRecord(
                audit_id=f"aud_memory_stored_{memory_id}",
                event_type="MEMORY_STORED",
                trace_id=memory.trace_id,
                session_id=memory.session_id,
                customer_id=memory.customer_id,
                timestamp=memory.created_at,
                layer="6",
                payload={
                    "memory_id": memory_id,
                    "memory_type": memory.memory_type.value,
                    "scenario": memory.scenario,
                    "outcome_signal": memory.outcome_signal,
                    "content": memory.content,
                },
            )
        )
