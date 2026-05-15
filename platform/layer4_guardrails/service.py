"""Guardrails service for Layer 4 policy enforcement.

Author: Sarala Biswal
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from platform.core.exceptions import SessionExpiredError
from platform.core.interfaces import AuditWriter, ContextStore
from platform.core.schemas import (
    ApprovalQueueItem,
    AuditRecord,
    CheckResult,
    CustomerProfile,
    GuardrailsResult,
    OrchestratorOutput,
    ProposedAction,
)
from platform.layer4_guardrails.approval_queue import ApprovalQueueService
from platform.layer4_guardrails.checks.responsible_ai import ConfidenceCheck, PartialContextCheck
from platform.layer4_guardrails.rule_engine import GuardrailRule, RuleEvaluator, RuleLoader
from platform.observability.metrics import metered, record_guardrail_checks
from platform.observability.tracing import traced

import structlog

logger = structlog.get_logger()


class GuardrailsService:
    """Evaluates proposed actions before any customer-facing execution."""

    def __init__(
        self,
        context_store: ContextStore,
        rule_loader: RuleLoader | None = None,
        approval_queue: ApprovalQueueService | None = None,
        audit_writer: AuditWriter | None = None,
        evaluator: RuleEvaluator | None = None,
    ) -> None:
        """Create a guardrails service with injected dependencies."""
        self._context_store = context_store
        self._rule_loader = rule_loader or RuleLoader()
        self._approval_queue = approval_queue or ApprovalQueueService()
        self._audit_writer = audit_writer
        self._evaluator = evaluator or RuleEvaluator()
        self._confidence_check = ConfidenceCheck()
        self._partial_context_check = PartialContextCheck()

    @traced(layer="L4", operation="guardrails")
    @metered(layer="L4")
    async def evaluate(
        self,
        orchestrator_output: OrchestratorOutput,
        session_id: str,
    ) -> GuardrailsResult:
        """Evaluate every proposed action and return approved, flagged, and blocked sets."""
        started = time.perf_counter()
        profile = await self._read_profile(session_id)
        rules = await self._rule_loader.get_rules()
        approved_actions: list[ProposedAction] = []
        flagged_actions: list[ProposedAction] = []
        blocked_actions: list[ProposedAction] = []
        all_checks: list[CheckResult] = []

        for action in orchestrator_output.proposed_actions:
            # Every proposed action is evaluated independently so one bad action cannot taint all.
            raw_checks = await self._evaluate_action(action, profile, orchestrator_output, rules)
            action_checks = [
                check.model_copy(
                    update={"details": {**check.details, "action_id": action.action_id}}
                )
                for check in raw_checks
            ]
            all_checks.extend(action_checks)
            blocked = [check for check in action_checks if check.status == "BLOCKED"]
            flagged = [check for check in action_checks if check.status == "FLAGGED"]
            if blocked:
                # Regulatory blocks stop the action from reaching approval or execution.
                blocked_actions.append(action)
            elif flagged:
                flagged_actions.append(action)
                # Flagged but non-blocked actions are routed to the human approval queue.
                await self._approval_queue.enqueue(
                    action=action,
                    flags=flagged,
                    context={
                        "trace_id": orchestrator_output.trace_id,
                        "session_id": session_id,
                        "customer_id": orchestrator_output.customer_id,
                        "risk_level": _risk_level(orchestrator_output),
                        "customer_profile_key": f"session:{session_id}:customer_profile",
                    },
                    priority="STANDARD",
                )
            else:
                approved_actions.append(action)

        result = GuardrailsResult(
            trace_id=orchestrator_output.trace_id,
            session_id=session_id,
            customer_id=orchestrator_output.customer_id,
            approved_actions=approved_actions,
            flagged_actions=flagged_actions,
            blocked_actions=blocked_actions,
            checks=all_checks,
            requires_human_review=bool(flagged_actions),
        )
        await self._write_audit(result, int((time.perf_counter() - started) * 1000), rules)
        record_guardrail_checks(result.checks)
        logger.info(
            "guardrails_evaluation_complete",
            trace_id=orchestrator_output.trace_id,
            layer="4",
            operation="evaluate",
            approved=len(approved_actions),
            flagged=len(flagged_actions),
            blocked=len(blocked_actions),
        )
        return result

    @traced(layer="L4", operation="pending_approvals")
    @metered(layer="L4")
    async def pending_approvals(self, limit: int = 50) -> list[ApprovalQueueItem]:
        """Return pending approval queue items."""
        return await self._approval_queue.get_pending(limit)

    async def _read_profile(self, session_id: str) -> CustomerProfile:
        """Load the assembled customer profile for policy evaluation."""
        raw_profile = await self._context_store.get(f"session:{session_id}:customer_profile")
        if raw_profile is None:
            message = f"Session profile expired or missing: {session_id}"
            raise SessionExpiredError(message)
        return CustomerProfile.model_validate_json(raw_profile)

    async def _evaluate_action(
        self,
        action: ProposedAction,
        profile: CustomerProfile,
        orchestrator_output: OrchestratorOutput,
        rules: list[GuardrailRule],
    ) -> list[CheckResult]:
        """Evaluate one action in strict regulatory, business, and AI order."""
        regulatory = self._evaluator.evaluate(
            action,
            profile,
            rules,
            categories=("REGULATORY",),
        )
        if any(check.status == "BLOCKED" for check in regulatory):
            # Regulatory failure short-circuits the remaining categories by design.
            return regulatory
        business = self._evaluator.evaluate(
            action,
            profile,
            rules,
            categories=("BUSINESS_POLICY",),
        )
        responsible_ai = [
            # Responsible-AI checks use orchestration confidence and profile completeness.
            self._confidence_check.check(
                action=action,
                agent_confidence=_agent_confidence(orchestrator_output),
                partial_context=profile.partial_context,
            ),
            self._partial_context_check.check(action, profile),
        ]
        return [*regulatory, *business, *responsible_ai]

    async def _write_audit(
        self,
        result: GuardrailsResult,
        latency_ms: int,
        rules: list[GuardrailRule],
    ) -> None:
        """Persist rule versions and check outcomes for compliance review."""
        if self._audit_writer is None:
            return
        timestamp = datetime.now(UTC)
        await self._audit_writer.write(
            AuditRecord(
                audit_id=f"aud_guard_{timestamp:%Y%m%d_%H%M%S_%f}_{result.customer_id}",
                event_type="GUARDRAILS_EVALUATION",
                trace_id=result.trace_id,
                session_id=result.session_id,
                customer_id=result.customer_id,
                timestamp=timestamp,
                layer="4",
                payload={
                    "actions_evaluated": [
                        {
                            "action_id": action.action_id,
                            "action_type": action.action_type,
                        }
                        for action in [
                            *result.approved_actions,
                            *result.flagged_actions,
                            *result.blocked_actions,
                        ]
                    ],
                    "guardrails_latency_ms": latency_ms,
                    "rule_versions_used": {rule.rule_id: rule.version for rule in rules},
                    "checks": [check.model_dump(mode="json") for check in result.checks],
                },
            )
        )


def _agent_confidence(orchestrator_output: OrchestratorOutput) -> float:
    for output in orchestrator_output.agent_outputs:
        confidence = output.output.get("confidence")
        if isinstance(confidence, int | float):
            return float(confidence)
    return 0.0


def _risk_level(orchestrator_output: OrchestratorOutput) -> str | None:
    for output in orchestrator_output.agent_outputs:
        risk_level = output.output.get("risk_level")
        if isinstance(risk_level, str):
            return risk_level
    return None
