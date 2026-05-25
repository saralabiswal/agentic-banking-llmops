"""Blueprint runner that orchestrates all six platform layers.

Author: Sarala Biswal
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from platform.adapters.adapter_factory import create_llm_inference_service
from platform.adapters.mock_channel_adapter import MockCRMAdapter, MockPushAdapter, MockSMSAdapter
from platform.core.interfaces import AuditWriter, ChannelAdapter, ContextStore, MemoryStore
from platform.core.schemas import (
    AssemblyResult,
    AuditRecord,
    Channel,
    ExecutionResult,
    GuardrailsResult,
    OrchestratorOutput,
    ProposedAction,
    RetrievalResult,
)
from platform.layer1_context.service import ContextAssemblyService, MLScorer
from platform.layer2_vector.kb_loader import KnowledgeBaseLoader
from platform.layer2_vector.service import VectorSearchService
from platform.layer3_orchestration.orchestrator import Orchestrator
from platform.layer4_guardrails.approval_queue import ApprovalQueueService
from platform.layer4_guardrails.service import GuardrailsService
from platform.layer5_ab.experiment_service import ExperimentService
from platform.layer6_sdk.blueprints import BlueprintConfig
from platform.observability.metrics import metered
from platform.observability.tracing import traced
from typing import Any, TypeVar
from uuid import uuid4

import structlog

logger = structlog.get_logger()
T = TypeVar("T")


class InMemoryContextStore:
    """In-memory ContextStore for demo and API test runs."""

    def __init__(self) -> None:
        """Create an empty context store."""
        self.values: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        """Return a stored value by key."""
        return self.values.get(key)

    async def set(self, key: str, value: str, ttl: int) -> None:
        """Store a value with a TTL-compatible signature."""
        del ttl
        self.values[key] = value

    async def delete(self, key: str) -> None:
        """Delete a key if present."""
        self.values.pop(key, None)


class InMemoryAuditWriter:
    """In-memory AuditWriter for demo and API test runs."""

    def __init__(self) -> None:
        """Create an empty audit writer."""
        self.records: list[AuditRecord] = []

    async def write(self, record: AuditRecord) -> None:
        """Append an audit record."""
        self.records.append(record)


@dataclass(frozen=True)
class PipelineEvent:
    """Single pipeline event emitted to the SSE bus."""

    event_type: str
    trace_id: str
    payload: dict[str, Any]


class PipelineEventBus:
    """In-memory event bus with replay for SSE subscribers."""

    def __init__(self) -> None:
        """Create an empty event bus."""
        self._events: dict[str, list[PipelineEvent]] = {}
        self._queues: dict[str, list[asyncio.Queue[PipelineEvent]]] = {}

    async def publish(self, trace_id: str, event_type: str, payload: dict[str, Any]) -> None:
        """Publish and retain an event for a trace."""
        event = PipelineEvent(event_type=event_type, trace_id=trace_id, payload=payload)
        self._events.setdefault(trace_id, []).append(event)
        for queue in self._queues.get(trace_id, []):
            await queue.put(event)

    async def stream(self, trace_id: str) -> AsyncIterator[PipelineEvent]:
        """Yield retained and future events for one trace until pipeline_done."""
        queue: asyncio.Queue[PipelineEvent] = asyncio.Queue()
        self._queues.setdefault(trace_id, []).append(queue)
        try:
            for event in self._events.get(trace_id, []):
                yield event
                if event.event_type == "pipeline_done":
                    return
            while True:
                event = await queue.get()
                yield event
                if event.event_type == "pipeline_done":
                    return
        finally:
            self._queues.get(trace_id, []).remove(queue)

    def events_for(self, trace_id: str) -> list[PipelineEvent]:
        """Return retained events for a trace."""
        return list(self._events.get(trace_id, []))


class BlueprintRunner:
    """Runs a platform blueprint through all six layers."""

    def __init__(
        self,
        context_store: ContextStore | None = None,
        audit_writer: AuditWriter | None = None,
        event_bus: PipelineEventBus | None = None,
        experiment_service: ExperimentService | None = None,
        approval_queue: ApprovalQueueService | None = None,
        memory_store: MemoryStore | None = None,
        ml_scoring_service: MLScorer | None = None,
    ) -> None:
        """Create a blueprint runner with in-memory defaults."""
        self.context_store = context_store or InMemoryContextStore()
        self.audit_writer = audit_writer or InMemoryAuditWriter()
        self.event_bus = event_bus or PipelineEventBus()
        self.experiment_service = experiment_service or ExperimentService()
        self.approval_queue = approval_queue or ApprovalQueueService()
        self.memory_store = memory_store
        self.ml_scoring_service = ml_scoring_service
        self.status_by_trace: dict[str, dict[str, Any]] = {}

    @traced(layer="L6", operation="blueprint_run")
    @metered(layer="L6")
    async def run(
        self,
        blueprint: BlueprintConfig,
        customer_id: str,
        trigger: str,
        caller_id: str,
        session_id: str | None = None,
        trace_id: str | None = None,
    ) -> ExecutionResult:
        """Run all six layers and execute approved actions."""
        started = time.perf_counter()
        # External callers can supply IDs; local demos generate traceable IDs once at entry.
        session_id = session_id or (
            f"sess_{customer_id}_{datetime.now(UTC):%Y%m%d_%H%M%S}_{uuid4().hex[:6]}"
        )
        trace_id = trace_id or f"trace_{session_id}"
        existing_status = self.status_by_trace.get(trace_id, {})
        self.status_by_trace[trace_id] = {
            **existing_status,
            "trace_id": trace_id,
            "session_id": session_id,
            "status": "running",
            "customer_id": customer_id,
            "scenario": blueprint.scenario,
            "started_at": existing_status.get("started_at", datetime.now(UTC).isoformat()),
        }

        # L1 builds live customer context and persists the TTL-bound profile.
        assembly: AssemblyResult = await self._run_layer(
            trace_id,
            "L1",
            lambda: ContextAssemblyService(
                context_store=self.context_store,
                audit_writer=self.audit_writer,
                feature_store=None,
                memory_store=self.memory_store,
                ml_scoring_service=self.ml_scoring_service,
            ).assemble(customer_id, session_id, blueprint.scenario),
        )
        # L2 retrieves policy evidence before any agent proposes an action.
        retrieval: RetrievalResult = await self._run_layer(
            trace_id,
            "L2",
            lambda: VectorSearchService(
                context_store=self.context_store,
                audit_writer=self.audit_writer,
                kb_loader=KnowledgeBaseLoader(),
            ).retrieve(session_id, blueprint.scenario),
        )
        # L3 agents propose only; execution is intentionally deferred to L6.
        orchestration: OrchestratorOutput = await self._run_layer(
            trace_id,
            "L3",
            lambda: Orchestrator(
                context_store=self.context_store,
                llm_inference_service=create_llm_inference_service(),
                audit_writer=self.audit_writer,
            ).run_pipeline(session_id, blueprint.scenario, retrieval.chunks, trace_id),
        )
        # L4 enforces regulatory, business, and responsible-AI policy before action selection.
        guardrails: GuardrailsResult = await self._run_layer(
            trace_id,
            "L4",
            lambda: GuardrailsService(
                context_store=self.context_store,
                approval_queue=self.approval_queue,
                audit_writer=self.audit_writer,
            ).evaluate(orchestration, session_id),
        )
        # L5 attaches deterministic experiment variants to approved customer messages.
        approved_actions: list[ProposedAction] = await self._run_layer(
            trace_id,
            "L5",
            lambda: self._select_variants(
                trace_id=trace_id,
                session_id=session_id,
                customer_id=customer_id,
                scenario=blueprint.scenario,
                actions=guardrails.approved_actions,
            ),
        )
        # L6 is the only layer allowed to execute approved actions against delivery channels.
        result: ExecutionResult = await self._run_layer(
            trace_id,
            "L6",
            lambda: self._execute_actions(
                trace_id=trace_id,
                session_id=session_id,
                customer_id=customer_id,
                caller_id=caller_id,
                actions=approved_actions,
            ),
        )

        pending = await self.approval_queue.get_pending()
        # Include the approval queue snapshot so UI and SDK callers can explain pending work.
        final_result: ExecutionResult = result.model_copy(update={"pending_actions": pending})
        self.status_by_trace[trace_id] = {
            **self.status_by_trace[trace_id],
            "status": "completed",
            "execution_result": final_result.model_dump(mode="json"),
            "assembly_status": assembly.status,
            "trigger": trigger,
            "completed_at": datetime.now(UTC).isoformat(),
        }
        await self.event_bus.publish(
            trace_id,
            "pipeline_done",
            {"trace_id": trace_id, "total_ms": int((time.perf_counter() - started) * 1000)},
        )
        return final_result

    async def _run_layer(
        self,
        trace_id: str,
        layer: str,
        operation: Callable[[], Awaitable[T]],
    ) -> T:
        """Run a layer operation while emitting SSE lifecycle events."""
        # Start and completion events power the live architecture overlay and execution log.
        await self.event_bus.publish(
            trace_id,
            "layer_started",
            {"layer": layer, "timestamp": datetime.now(UTC).isoformat()},
        )
        started = time.perf_counter()
        try:
            output = await operation()
        except Exception as exc:
            # Publish layer_error before re-raising so observers see the failure boundary.
            await self.event_bus.publish(
                trace_id,
                "layer_error",
                {"layer": layer, "error": str(exc)},
            )
            raise
        latency_ms = int((time.perf_counter() - started) * 1000)
        # Summaries are intentionally compact; full evidence remains in audit records.
        await self.event_bus.publish(
            trace_id,
            "layer_completed",
            {
                "layer": layer,
                "latency_ms": latency_ms,
                "output_summary": _summary_for_output(output),
            },
        )
        logger.info(
            "blueprint_layer_complete",
            trace_id=trace_id,
            layer="6",
            operation="run_layer",
            completed_layer=layer,
            latency_ms=latency_ms,
        )
        return output

    async def _select_variants(
        self,
        *,
        trace_id: str,
        session_id: str,
        customer_id: str,
        scenario: str,
        actions: list[ProposedAction],
    ) -> list[ProposedAction]:
        """Attach experiment variants to approved actions and audit the assignment result."""
        selected: list[ProposedAction] = []
        assignments: list[dict[str, str | None]] = []
        for action in actions:
            try:
                variant = self.experiment_service.select_variant(
                    customer_id,
                    scenario,
                    action.action_type,
                )
                # Variant metadata travels with the action, execution, and outcome records.
                metadata = {
                    **action.metadata,
                    "trace_id": trace_id,
                    "session_id": session_id,
                    "customer_id": customer_id,
                    "scenario": scenario,
                    "experiment_id": variant.experiment_id,
                    "variant_id": variant.variant_id,
                }
                selected.append(
                    action.model_copy(
                        update={
                            "customer_message": variant.payload.get(
                                "message",
                                action.customer_message,
                            ),
                            "metadata": metadata,
                        }
                    )
                )
                assignments.append(
                    {
                        "action_id": action.action_id,
                        "action_type": action.action_type,
                        "experiment_id": variant.experiment_id,
                        "variant_id": variant.variant_id,
                    }
                )
            except KeyError:
                # Missing experiments are non-fatal; the approved action still executes unchanged.
                selected.append(
                    action.model_copy(
                        update={
                            "metadata": {
                                **action.metadata,
                                "trace_id": trace_id,
                                "session_id": session_id,
                                "customer_id": customer_id,
                                "scenario": scenario,
                            }
                        }
                    )
                )
                assignments.append(
                    {
                        "action_id": action.action_id,
                        "action_type": action.action_type,
                        "experiment_id": None,
                        "variant_id": None,
                    }
                )
        if self.audit_writer is not None:
            timestamp = datetime.now(UTC)
            await self.audit_writer.write(
                AuditRecord(
                    audit_id=f"aud_ab_{timestamp:%Y%m%d_%H%M%S_%f}_{customer_id}",
                    event_type="AB_ASSIGNMENT",
                    trace_id=trace_id,
                    session_id=session_id,
                    customer_id=customer_id,
                    timestamp=timestamp,
                    layer="5",
                    payload={
                        "scenario": scenario,
                        "assignments": assignments,
                        "assignment_count": len(assignments),
                    },
                )
            )
        return selected

    @traced(layer="L6", operation="sdk_execution")
    @metered(layer="L6")
    async def _execute_actions(
        self,
        *,
        trace_id: str,
        session_id: str,
        customer_id: str,
        caller_id: str,
        actions: list[ProposedAction],
    ) -> ExecutionResult:
        """Execute the first approved action or record the no-action path for replay."""
        if not actions:
            timestamp = datetime.now(UTC)
            if self.audit_writer is not None:
                await self.audit_writer.write(
                    AuditRecord(
                        audit_id=f"aud_exec_no_action_{timestamp:%Y%m%d_%H%M%S_%f}_{customer_id}",
                        event_type="ACTION_EXECUTED",
                        trace_id=trace_id,
                        session_id=session_id,
                        customer_id=customer_id,
                        timestamp=timestamp,
                        layer="6",
                        payload={
                            "action_id": "NO_ACTION",
                            "caller_id": caller_id,
                            "status": "PENDING_APPROVAL",
                            "reason": "No approved customer-facing action was produced.",
                        },
                    )
                )
            return ExecutionResult(
                trace_id=trace_id,
                action_id="NO_ACTION",
                action_executed=False,
                status="PENDING_APPROVAL",
                channel=None,
                delivery_receipt=None,
                outcome_tracking_id=None,
                customer_message=None,
                pending_actions=[],
            )

        # The reference runner executes one approved action per run; other actions remain auditable.
        action = actions[0].model_copy(
            update={"metadata": {**actions[0].metadata, "caller_id": caller_id}}
        )
        adapter = _adapter_for_action(action)
        receipt = await adapter.send(action)
        outcome_tracking_id = f"otk_{customer_id}_{action.action_id}_{uuid4().hex[:8]}"
        await self.audit_writer.write(
            AuditRecord(
                audit_id=f"aud_exec_{receipt.receipt_id}",
                event_type="ACTION_EXECUTED",
                trace_id=trace_id,
                session_id=session_id,
                customer_id=customer_id,
                timestamp=receipt.delivered_at,
                layer="6",
                payload={
                    "action_id": action.action_id,
                    "caller_id": caller_id,
                    "outcome_tracking_id": outcome_tracking_id,
                    "receipt": receipt.model_dump(mode="json"),
                    "experiment_id": action.metadata.get("experiment_id"),
                    "variant_id": action.metadata.get("variant_id"),
                },
            )
        )
        return ExecutionResult(
            trace_id=trace_id,
            action_id=action.action_id,
            action_executed=True,
            status="EXECUTED",
            channel=receipt.channel,
            delivery_receipt=receipt,
            outcome_tracking_id=outcome_tracking_id,
            customer_message=action.customer_message,
            pending_actions=[],
        )


def _adapter_for_action(action: ProposedAction) -> ChannelAdapter:
    """Choose the local mock delivery adapter that matches the proposed action."""
    if action.channel == Channel.SMS:
        return MockSMSAdapter()
    if action.channel == Channel.CRM or action.action_type.startswith("CREATE_"):
        return MockCRMAdapter()
    return MockPushAdapter()


def _summary_for_output(output: Any) -> dict[str, Any]:
    """Convert layer outputs into compact JSON-safe summaries for SSE/UI consumers."""
    if hasattr(output, "model_dump"):
        dumped = output.model_dump(mode="json")
        return json.loads(json.dumps(dumped, default=str)) if isinstance(dumped, dict) else {}
    if isinstance(output, list):
        items = [
            json.loads(json.dumps(item.model_dump(mode="json"), default=str))
            if hasattr(item, "model_dump")
            else json.loads(json.dumps(item, default=str))
            for item in output
        ]
        return {"count": len(output), "items": items}
    return {"value": str(output)}
