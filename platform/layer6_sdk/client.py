"""Typed SDK client surface for Layer 6.

Author: Sarala Biswal
"""

from __future__ import annotations

from datetime import datetime
from platform.core.schemas import ExecutionResult, OutcomeEvent
from platform.layer6_sdk.blueprint_runner import BlueprintRunner
from platform.layer6_sdk.outcome_router import OutcomeRouter
from platform.observability.metrics import metered
from platform.observability.tracing import traced
from uuid import uuid4


class IFXActionClient:
    """Product-team client for executing actions and recording outcomes."""

    def __init__(
        self,
        runner: BlueprintRunner | None = None,
        outcome_router: OutcomeRouter | None = None,
    ) -> None:
        """Create an SDK client."""
        self._runner = runner or BlueprintRunner()
        self._outcome_router = outcome_router or OutcomeRouter(
            experiment_service=self._runner.experiment_service,
            audit_writer=self._runner.audit_writer,
        )

    @traced(layer="L6", operation="client_execute")
    @metered(layer="L6")
    async def execute(self, trace_id: str, action_id: str, caller_id: str) -> ExecutionResult:
        """Return an existing execution result for an authorized action."""
        del action_id, caller_id
        status = self._runner.status_by_trace.get(trace_id, {})
        result = status.get("execution_result")
        if isinstance(result, dict):
            return ExecutionResult.model_validate(result)
        return ExecutionResult(
            trace_id=trace_id,
            action_id="",
            action_executed=False,
            status="FAILED",
            channel=None,
            delivery_receipt=None,
            outcome_tracking_id=None,
            customer_message=None,
            pending_actions=[],
        )

    @traced(layer="L6", operation="client_record_outcome")
    @metered(layer="L6")
    async def record_outcome(
        self,
        trace_id: str,
        action_id: str,
        outcome_type: str,
        outcome_ts: datetime,
        metadata: dict[str, object] | None = None,
    ) -> None:
        """Record an asynchronous customer outcome."""
        event = OutcomeEvent(
            outcome_id=f"out_{uuid4().hex[:12]}",
            trace_id=trace_id,
            action_id=action_id,
            customer_id=str((metadata or {}).get("customer_id", "unknown")),
            outcome_type=outcome_type,
            outcome_ts=outcome_ts,
            metadata=metadata or {},
        )
        await self._outcome_router.route(event)
