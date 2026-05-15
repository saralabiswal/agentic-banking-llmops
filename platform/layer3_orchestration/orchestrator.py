"""Hub-and-spoke pipeline orchestrator for Layer 3.

Author: Sarala Biswal
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from platform.core.config import Settings, settings
from platform.core.exceptions import PipelineError, SessionExpiredError, ToolAuthorizationError
from platform.core.interfaces import AuditWriter, ContextStore, LLMClient
from platform.core.schemas import (
    AgentContext,
    AgentOutput,
    AuditRecord,
    CustomerProfile,
    OrchestratorOutput,
    PolicyChunk,
    ProposedAction,
)
from platform.layer3_orchestration.agents import (
    BaseAgent,
    ChurnSignalAgent,
    DisputeTriageAgent,
    InterventionAgent,
    ResolutionAgent,
    RetentionOfferAgent,
    RiskScoringAgent,
)
from platform.layer3_orchestration.pipeline_registry import BranchStep, PipelineStep, get_pipeline
from platform.layer3_orchestration.state_manager import PipelineStateManager
from platform.layer3_orchestration.tool_registry import authorized_tools_for_agent
from platform.observability.metrics import metered
from platform.observability.tracing import traced
from typing import Any

import structlog
from pydantic import ValidationError

logger = structlog.get_logger()


@dataclass(frozen=True)
class HumanReviewItem:
    """Failure routed to the human review queue."""

    queue_id: str
    trace_id: str
    session_id: str
    customer_id: str
    scenario: str
    failure_type: str
    step_name: str
    reason: str
    prior_outputs: list[AgentOutput]
    proposed_actions: list[ProposedAction]


class HumanReviewQueue:
    """In-memory human review queue used by Layer 3 tests and demos."""

    def __init__(self) -> None:
        """Create an empty review queue."""
        self.items: list[HumanReviewItem] = []

    async def enqueue(self, item: HumanReviewItem) -> None:
        """Append a human review item."""
        self.items.append(item)


class Orchestrator:
    """Routes typed agent contexts through static hub-and-spoke pipelines."""

    def __init__(
        self,
        context_store: ContextStore,
        llm_client: LLMClient,
        audit_writer: AuditWriter | None = None,
        state_manager: PipelineStateManager | None = None,
        human_review_queue: HumanReviewQueue | None = None,
        agents: dict[str, BaseAgent] | None = None,
        config: Settings = settings,
    ) -> None:
        """Create an orchestrator with injected infrastructure and agents."""
        self._context_store = context_store
        self._llm_client = llm_client
        self._audit_writer = audit_writer
        self._state_manager = state_manager or PipelineStateManager(context_store, config)
        self._human_review_queue = human_review_queue or HumanReviewQueue()
        self._agents = agents or _default_agents()
        self._config = config

    @property
    def human_review_queue(self) -> HumanReviewQueue:
        """Return the human review queue for inspection."""
        return self._human_review_queue

    @traced(layer="L3", operation="orchestration")
    @metered(layer="L3")
    async def run_pipeline(
        self,
        session_id: str,
        scenario: str,
        policy_chunks: list[PolicyChunk],
        trace_id: str,
    ) -> OrchestratorOutput:
        """Run the static pipeline for a scenario and return proposed actions."""
        started = time.perf_counter()
        profile = await self._load_customer_profile(session_id)
        pipeline = get_pipeline(scenario)
        prior_outputs: list[AgentOutput] = []
        branch_decisions: list[dict[str, Any]] = []
        required_next_agent: str | None = None

        logger.info(
            "orchestration_started",
            trace_id=trace_id,
            layer="3",
            operation="run_pipeline",
            session_id=session_id,
            customer_id=profile.customer_id,
            scenario=scenario,
        )

        for pipeline_step, step in enumerate(pipeline.steps, start=1):
            if isinstance(step, BranchStep):
                # Branch steps inspect prior typed outputs and choose the next spoke agent.
                routed_to = await self._handle_branch(
                    session_id=session_id,
                    trace_id=trace_id,
                    step=step,
                    prior_outputs=prior_outputs,
                    branch_decisions=branch_decisions,
                )
                required_next_agent = routed_to
                if routed_to is None:
                    break
                continue

            if required_next_agent is not None and step.agent != required_next_agent:
                # Skip agents outside the selected branch; agents never call each other directly.
                continue
            required_next_agent = None

            try:
                # Each agent receives the full policy context and all prior outputs.
                output = await self._run_agent_step(
                    step=step,
                    pipeline_step=pipeline_step,
                    session_id=session_id,
                    scenario=scenario,
                    profile=profile,
                    policy_chunks=policy_chunks,
                    prior_outputs=prior_outputs,
                    trace_id=trace_id,
                )
            except TimeoutError as exc:
                return await self._route_failure(
                    failure_type="TIMEOUT",
                    reason=str(exc),
                    step_name=step.agent,
                    started=started,
                    session_id=session_id,
                    scenario=scenario,
                    profile=profile,
                    trace_id=trace_id,
                    prior_outputs=prior_outputs,
                    branch_decisions=branch_decisions,
                )
            except (ValidationError, ToolAuthorizationError, PipelineError) as exc:
                return await self._route_failure(
                    failure_type=type(exc).__name__,
                    reason=str(exc),
                    step_name=step.agent,
                    started=started,
                    session_id=session_id,
                    scenario=scenario,
                    profile=profile,
                    trace_id=trace_id,
                    prior_outputs=prior_outputs,
                    branch_decisions=branch_decisions,
                )

            prior_outputs.append(output)
            # Checkpoints make long-running orchestration resumable and explainable.
            await self._state_manager.checkpoint(
                session_id=session_id,
                trace_id=trace_id,
                step_name=step.agent,
                state={
                    "status": "STEP_COMPLETE",
                    "agent": step.agent,
                    "output_hash": _output_hash(output),
                },
            )
            logger.info(
                "agent_step_complete",
                trace_id=trace_id,
                layer="3",
                operation="run_agent",
                agent=step.agent,
                latency_ms=output.latency_ms,
            )

        proposed_actions = _proposed_actions_from_outputs(prior_outputs)
        orchestration_ms = int((time.perf_counter() - started) * 1000)
        result = OrchestratorOutput(
            trace_id=trace_id,
            session_id=session_id,
            customer_id=profile.customer_id,
            scenario=scenario,
            status="PENDING_GUARDRAILS",
            agent_outputs=prior_outputs,
            proposed_actions=proposed_actions,
            branch_decisions=branch_decisions,
            requires_approval=any(action.requires_approval for action in proposed_actions),
            orchestration_ms=orchestration_ms,
        )
        await self._write_audit(result)
        logger.info(
            "orchestration_complete",
            trace_id=trace_id,
            layer="3",
            operation="run_pipeline",
            status=result.status,
            proposed_action_count=len(proposed_actions),
            orchestration_ms=orchestration_ms,
        )
        return result

    async def _load_customer_profile(self, session_id: str) -> CustomerProfile:
        """Load customer profile context written by Layer 1."""
        raw_profile = await self._context_store.get(f"session:{session_id}:customer_profile")
        if raw_profile is None:
            message = f"Session profile expired or missing: {session_id}"
            raise SessionExpiredError(message)
        return CustomerProfile.model_validate_json(raw_profile)

    async def _run_agent_step(
        self,
        *,
        step: PipelineStep,
        pipeline_step: int,
        session_id: str,
        scenario: str,
        profile: CustomerProfile,
        policy_chunks: list[PolicyChunk],
        prior_outputs: list[AgentOutput],
        trace_id: str,
    ) -> AgentOutput:
        """Run one authorized agent step with a hard timeout."""
        agent = self._agents.get(step.agent)
        if agent is None:
            message = f"No registered agent for pipeline step: {step.agent}"
            raise PipelineError(message)
        context = AgentContext(
            session_id=session_id,
            customer_id=profile.customer_id,
            scenario=scenario,
            pipeline_step=pipeline_step,
            trace_id=trace_id,
            policy_chunks=policy_chunks,
            prior_outputs=prior_outputs,
            authorized_tools=authorized_tools_for_agent(step.agent),
            max_tokens=agent.max_tokens,
            timeout_ms=step.timeout_ms,
        )
        # Timeout is enforced in code so prompt behavior cannot bypass the SLA.
        return await asyncio.wait_for(
            agent.run(context=context, llm=self._llm_client),
            timeout=step.timeout_ms / 1000,
        )

    async def _handle_branch(
        self,
        *,
        session_id: str,
        trace_id: str,
        step: BranchStep,
        prior_outputs: list[AgentOutput],
        branch_decisions: list[dict[str, Any]],
    ) -> str | None:
        """Evaluate a branch condition and record the resulting route."""
        if not prior_outputs:
            message = "Branch step requires a prior agent output"
            raise PipelineError(message)
        value = str(prior_outputs[-1].output.get(step.branch_on, ""))
        routed_to = step.if_true if value in step.true_values else step.if_false
        decision = {
            "step": "BRANCH",
            "condition": f"{step.branch_on}={value}",
            "routed_to": routed_to,
            "description": step.description,
        }
        branch_decisions.append(decision)
        await self._state_manager.checkpoint(
            session_id=session_id,
            trace_id=trace_id,
            step_name="BRANCH",
            state={"status": "BRANCH_COMPLETE", **decision},
        )
        logger.info(
            "branch_decision",
            trace_id=trace_id,
            layer="3",
            operation="branch",
            condition=decision["condition"],
            routed_to=routed_to,
        )
        return routed_to

    async def _route_failure(
        self,
        *,
        failure_type: str,
        reason: str,
        step_name: str,
        started: float,
        session_id: str,
        scenario: str,
        profile: CustomerProfile,
        trace_id: str,
        prior_outputs: list[AgentOutput],
        branch_decisions: list[dict[str, Any]],
    ) -> OrchestratorOutput:
        proposed_actions = _proposed_actions_from_outputs(prior_outputs)
        item = HumanReviewItem(
            queue_id=f"hr_{datetime.now(UTC):%Y%m%d_%H%M%S_%f}_{profile.customer_id}",
            trace_id=trace_id,
            session_id=session_id,
            customer_id=profile.customer_id,
            scenario=scenario,
            failure_type=failure_type,
            step_name=step_name,
            reason=reason,
            prior_outputs=prior_outputs,
            proposed_actions=proposed_actions,
        )
        await self._human_review_queue.enqueue(item)
        await self._state_manager.checkpoint(
            session_id=session_id,
            trace_id=trace_id,
            step_name=step_name,
            state={
                "status": "HUMAN_REVIEW",
                "failure_type": failure_type,
                "reason": reason,
            },
        )
        logger.warning(
            "orchestration_routed_to_human_review",
            trace_id=trace_id,
            layer="3",
            operation="failure_route",
            failure_type=failure_type,
            step_name=step_name,
            reason=reason,
        )
        return OrchestratorOutput(
            trace_id=trace_id,
            session_id=session_id,
            customer_id=profile.customer_id,
            scenario=scenario,
            status="HUMAN_REVIEW",
            agent_outputs=prior_outputs,
            proposed_actions=proposed_actions,
            branch_decisions=branch_decisions,
            requires_approval=True,
            orchestration_ms=int((time.perf_counter() - started) * 1000),
        )

    async def _write_audit(self, result: OrchestratorOutput) -> None:
        if self._audit_writer is None:
            return
        timestamp = datetime.now(UTC)
        await self._audit_writer.write(
            AuditRecord(
                audit_id=f"aud_orch_{timestamp:%Y%m%d_%H%M%S_%f}_{result.customer_id}",
                event_type="ORCHESTRATION_COMPLETE",
                trace_id=result.trace_id,
                session_id=result.session_id,
                customer_id=result.customer_id,
                timestamp=timestamp,
                layer="3",
                payload=result.model_dump(mode="json"),
            )
        )


def _default_agents() -> dict[str, BaseAgent]:
    return {
        "RiskScoringAgent": RiskScoringAgent(),
        "InterventionAgent": InterventionAgent(),
        "DisputeTriageAgent": DisputeTriageAgent(),
        "ResolutionAgent": ResolutionAgent(),
        "ChurnSignalAgent": ChurnSignalAgent(),
        "RetentionOfferAgent": RetentionOfferAgent(),
    }


def _proposed_actions_from_outputs(outputs: list[AgentOutput]) -> list[ProposedAction]:
    proposed_actions: list[ProposedAction] = []
    for output in outputs:
        raw_actions = output.output.get("proposed_actions", [])
        if isinstance(raw_actions, list):
            proposed_actions.extend(
                ProposedAction.model_validate(action)
                for action in raw_actions
                if isinstance(action, dict)
            )
    return proposed_actions


def _output_hash(output: AgentOutput) -> str:
    digest = hashlib.sha256(output.model_dump_json().encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
