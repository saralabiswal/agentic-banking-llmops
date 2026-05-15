"""Configurable YAML rule loading and evaluation for Layer 4.

Author: Sarala Biswal
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from platform.core.config import Settings, settings
from platform.core.exceptions import SchemaValidationError
from platform.core.schemas import CheckResult, CustomerProfile, ProposedAction
from typing import Any, Literal, cast

import yaml

RuleCategory = Literal["REGULATORY", "BUSINESS_POLICY", "RESPONSIBLE_AI"]
RuleOutcome = Literal["BLOCK", "FLAG"]
RuleSeverity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
CheckStatus = Literal["APPROVED", "FLAGGED", "BLOCKED"]

CATEGORY_SEQUENCE: tuple[RuleCategory, ...] = (
    "REGULATORY",
    "BUSINESS_POLICY",
    "RESPONSIBLE_AI",
)


@dataclass(frozen=True)
class GuardrailRule:
    """Versioned guardrail rule loaded from YAML."""

    rule_id: str
    name: str
    category: RuleCategory
    version: str
    effective_date: date
    expires_date: date | None
    condition: dict[str, Any]
    outcome: RuleOutcome
    severity: RuleSeverity
    flag_message: str


class RuleLoader:
    """Loads active guardrail rules from YAML and hot-reloads file changes."""

    def __init__(
        self,
        rules_dir: str | Path = settings.RULES_DIR,
        config: Settings = settings,
    ) -> None:
        """Create a rule loader."""
        self._rules_dir = Path(rules_dir)
        self._config = config
        self._rules: list[GuardrailRule] = []
        self._snapshot: dict[Path, float] = {}

    async def get_rules(self) -> list[GuardrailRule]:
        """Return active rules, reloading YAML files when the directory changes."""
        snapshot = await asyncio.to_thread(self._current_snapshot)
        if snapshot != self._snapshot:
            self._rules = await asyncio.to_thread(self._load_rules_sync)
            self._snapshot = snapshot
        return list(self._rules)

    async def load_rules(self) -> list[GuardrailRule]:
        """Force a reload of all active rules."""
        self._rules = await asyncio.to_thread(self._load_rules_sync)
        self._snapshot = await asyncio.to_thread(self._current_snapshot)
        return list(self._rules)

    def _current_snapshot(self) -> dict[Path, float]:
        return {path: path.stat().st_mtime for path in sorted(self._rules_dir.rglob("*.yaml"))}

    def _load_rules_sync(self) -> list[GuardrailRule]:
        if not self._rules_dir.exists():
            message = f"Rules directory does not exist: {self._rules_dir}"
            raise SchemaValidationError(message)
        rules: list[GuardrailRule] = []
        today = datetime.now(UTC).date()
        for path in sorted(self._rules_dir.rglob("*.yaml")):
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                message = f"Rule YAML must be a mapping: {path}"
                raise SchemaValidationError(message)
            rule = _rule_from_mapping(loaded)
            if rule.effective_date <= today and (
                rule.expires_date is None or rule.expires_date > today
            ):
                rules.append(rule)
        return rules


class RuleEvaluator:
    """Evaluates guardrail rules in strict regulatory, business, AI sequence."""

    def evaluate(
        self,
        action: ProposedAction,
        profile: CustomerProfile,
        rules: Iterable[GuardrailRule],
        categories: tuple[RuleCategory, ...] = CATEGORY_SEQUENCE,
    ) -> list[CheckResult]:
        """Evaluate rules for one action and stop immediately on regulatory block."""
        rules_by_category = {
            category: [rule for rule in rules if rule.category == category]
            for category in categories
        }
        results: list[CheckResult] = []
        for category in categories:
            for rule in rules_by_category[category]:
                result = self._evaluate_rule(action, profile, rule)
                results.append(result)
                if category == "REGULATORY" and result.status == "BLOCKED":
                    return results
        return results

    def _evaluate_rule(
        self,
        action: ProposedAction,
        profile: CustomerProfile,
        rule: GuardrailRule,
    ) -> CheckResult:
        triggered = _condition_matches(action, profile, rule.condition)
        status = _status_for_rule(rule) if triggered else "APPROVED"
        return CheckResult(
            status=status,
            rule_id=rule.rule_id,
            category=rule.category,
            severity=rule.severity,
            message=rule.flag_message if triggered else f"{rule.rule_id}: approved",
            details={"version": rule.version, "condition": rule.condition},
        )


def _rule_from_mapping(data: dict[str, Any]) -> GuardrailRule:
    return GuardrailRule(
        rule_id=_text(data, "rule_id"),
        name=_text(data, "name"),
        category=cast("RuleCategory", _text(data, "category")),
        version=_text(data, "version"),
        effective_date=_required_date_value(data.get("effective_date")),
        expires_date=_date_value(data.get("expires_date")),
        condition=_condition(data.get("condition")),
        outcome=cast("RuleOutcome", _text(data, "outcome")),
        severity=cast("RuleSeverity", _text(data, "severity")),
        flag_message=_text(data, "flag_message"),
    )


def _condition_matches(
    action: ProposedAction,
    profile: CustomerProfile,
    condition: dict[str, Any],
) -> bool:
    action_type = condition.get("action_type")
    if isinstance(action_type, str) and action_type not in {"*", action.action_type}:
        return False

    operator = str(condition.get("operator", "ALWAYS"))
    field_value = _field_value(action, profile, str(condition.get("field", "")))
    expected = condition.get("value")
    match operator:
        case "ALWAYS":
            return True
        case "EQUALS":
            return bool(field_value == expected)
        case "GREATER_THAN":
            return _number(field_value) > _number(expected)
        case "LESS_THAN":
            return _number(field_value) < _number(expected)
        case "LESS_THAN_OR_EQUAL":
            return _number(field_value) <= _number(expected)
        case "CONTAINS_ANY":
            return _contains_any(field_value, expected)
        case "NOT_CONTAINS_ANY":
            return not _contains_any(field_value, expected)
        case _:
            return False


def _field_value(action: ProposedAction, profile: CustomerProfile, field: str) -> Any:
    if field.startswith("metadata."):
        return action.metadata.get(field.removeprefix("metadata."))
    if field == "partial_context":
        return profile.partial_context
    if field == "customer_message":
        return action.customer_message or ""
    if hasattr(action, field):
        return getattr(action, field)
    return None


def _contains_any(field_value: Any, expected: Any) -> bool:
    if not isinstance(field_value, str) or not isinstance(expected, list):
        return False
    lowered = field_value.lower()
    return any(isinstance(item, str) and item.lower() in lowered for item in expected)


def _status_for_rule(rule: GuardrailRule) -> CheckStatus:
    return "BLOCKED" if rule.outcome == "BLOCK" else "FLAGGED"


def _number(value: Any) -> float:
    if value is None:
        return 0.0
    return float(value)


def _text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        message = f"Rule missing required text field: {key}"
        raise SchemaValidationError(message)
    return value


def _date_value(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    message = "Rule date field must be ISO date string or null"
    raise SchemaValidationError(message)


def _required_date_value(value: Any) -> date:
    parsed = _date_value(value)
    if parsed is None:
        message = "Rule effective_date is required"
        raise SchemaValidationError(message)
    return parsed


def _condition(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        message = "Rule condition must be a mapping"
        raise SchemaValidationError(message)
    return dict(value)
