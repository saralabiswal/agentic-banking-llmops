"""Regulatory guardrail check runner.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.core.schemas import CheckResult, CustomerProfile, ProposedAction
from platform.layer4_guardrails.rule_engine import GuardrailRule, RuleEvaluator


class RegulatoryChecks:
    """Runs regulatory rules and stops on a regulatory block."""

    def __init__(self, evaluator: RuleEvaluator | None = None) -> None:
        """Create a regulatory check runner."""
        self._evaluator = evaluator or RuleEvaluator()

    def check(
        self,
        action: ProposedAction,
        profile: CustomerProfile,
        rules: list[GuardrailRule],
    ) -> list[CheckResult]:
        """Evaluate regulatory rules for one action."""
        return self._evaluator.evaluate(action, profile, rules, categories=("REGULATORY",))
