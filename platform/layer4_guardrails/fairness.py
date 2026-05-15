"""BISG-style fairness disparity analysis for Layer 4.

Author: Sarala Biswal
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable
from platform.core.schemas import CheckResult
from typing import Any


class BisgFairnessChecker:
    """Computes aggregate adverse-impact checks over historical decisions."""

    def check(
        self,
        action_type: str,
        customer_segment: str,
        db_session: Iterable[dict[str, Any]] | None,
    ) -> CheckResult:
        """Return APPROVED when aggregate offer rates are balanced."""
        records = [
            record
            for record in (db_session or [])
            if record.get("action_type") == action_type
            and record.get("customer_segment", customer_segment) == customer_segment
        ]
        air = _adverse_impact_ratio(records)
        p_value = _rough_p_value(records)
        status = "FLAGGED" if air < 0.80 and p_value < 0.05 else "APPROVED"
        return CheckResult(
            status=status,
            rule_id="R-003",
            category="REGULATORY",
            severity="HIGH",
            message=(
                "R-003: fair lending disparity detected"
                if status == "FLAGGED"
                else "R-003: fairness approved"
            ),
            details={"air": air, "p_value": p_value, "methodology": "BISG proxy AIR"},
        )


def _adverse_impact_ratio(records: list[dict[str, Any]]) -> float:
    if not records:
        return 1.0
    offered_by_cohort: dict[str, list[bool]] = defaultdict(list)
    for record in records:
        cohort = str(record.get("cohort", "reference"))
        offered_by_cohort[cohort].append(bool(record.get("offered", False)))
    rates = [
        sum(1 for offered in values if offered) / len(values)
        for values in offered_by_cohort.values()
        if values
    ]
    if not rates or max(rates) == 0.0:
        return 1.0
    return min(rates) / max(rates)


def _rough_p_value(records: list[dict[str, Any]]) -> float:
    if len(records) < 2:
        return 1.0
    groups: dict[str, list[bool]] = defaultdict(list)
    for record in records:
        groups[str(record.get("cohort", "reference"))].append(bool(record.get("offered", False)))
    if len(groups) < 2:
        return 1.0
    values = list(groups.values())[:2]
    n_a = len(values[0])
    n_b = len(values[1])
    if n_a == 0 or n_b == 0:
        return 1.0
    p_a = sum(values[0]) / n_a
    p_b = sum(values[1]) / n_b
    pooled = (sum(values[0]) + sum(values[1])) / (n_a + n_b)
    standard_error = math.sqrt(pooled * (1.0 - pooled) * ((1.0 / n_a) + (1.0 / n_b)))
    if standard_error == 0.0:
        return 1.0
    z_score = abs(p_a - p_b) / standard_error
    return math.erfc(z_score / math.sqrt(2.0))
