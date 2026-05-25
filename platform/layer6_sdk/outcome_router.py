"""Outcome routing for Layer 6 feedback.

Author: Sarala Biswal
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from platform.core.interfaces import AuditWriter
from platform.core.schemas import AuditRecord, OutcomeEvent
from platform.layer5_ab.experiment_service import ExperimentService
from platform.layer5_ab.outcome_processor import OutcomeProcessor
from platform.memory.writer import MemoryWriter
from platform.observability.metrics import metered
from platform.observability.tracing import traced

import structlog

logger = structlog.get_logger()


class OutcomeRouter:
    """Routes outcomes to experiments, model governance, approval feedback, and audit."""

    def __init__(
        self,
        experiment_service: ExperimentService,
        audit_writer: AuditWriter | None = None,
        memory_writer: MemoryWriter | None = None,
    ) -> None:
        """Create an outcome router."""
        self._experiment_service = experiment_service
        self._outcome_processor = OutcomeProcessor(experiment_service)
        self._audit_writer = audit_writer
        self._memory_writer = memory_writer
        self.model_governance_events: list[OutcomeEvent] = []

    @traced(layer="L6", operation="outcome_route")
    @metered(layer="L6")
    async def route(self, outcome: OutcomeEvent) -> None:
        """Route an outcome event to all Layer 6 feedback destinations."""
        await asyncio.gather(
            asyncio.to_thread(self._outcome_processor.record_outcome, outcome),
            asyncio.to_thread(self.model_governance_events.append, outcome),
            self._write_audit(outcome),
            self._write_memory(outcome),
        )

    async def _write_memory(self, outcome: OutcomeEvent) -> None:
        if self._memory_writer is None:
            return
        try:
            await self._memory_writer.write(outcome)
        except Exception as exc:
            logger.warning(
                "memory.outcome_write_degraded",
                trace_id=outcome.trace_id,
                customer_id=outcome.customer_id,
                outcome_id=outcome.outcome_id,
                reason=str(exc),
            )
            return

    async def _write_audit(self, outcome: OutcomeEvent) -> None:
        if self._audit_writer is None:
            return
        await self._audit_writer.write(
            AuditRecord(
                audit_id=f"aud_outcome_{outcome.outcome_id}",
                event_type="OUTCOME_CAPTURED",
                trace_id=outcome.trace_id,
                session_id=str(outcome.metadata.get("session_id", "unknown")),
                customer_id=outcome.customer_id,
                timestamp=datetime.now(UTC),
                layer="6",
                payload=outcome.model_dump(mode="json"),
            )
        )
