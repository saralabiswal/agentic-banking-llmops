"""Business policy guardrail check runner.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.core.schemas import CheckResult, CustomerProfile, ProposedAction
from platform.layer4_guardrails.rule_engine import GuardrailRule, RuleEvaluator


class BusinessPolicyChecks:
    """Runs configurable business policy rules."""

    def __init__(self, evaluator: RuleEvaluator | None = None) -> None:
        """Create a business policy check runner."""
        self._evaluator = evaluator or RuleEvaluator()

    def check(
        self,
        action: ProposedAction,
        profile: CustomerProfile,
        rules: list[GuardrailRule],
    ) -> list[CheckResult]:
        """Evaluate business policy rules for one action."""
        return self._evaluator.evaluate(action, profile, rules, categories=("BUSINESS_POLICY",))
