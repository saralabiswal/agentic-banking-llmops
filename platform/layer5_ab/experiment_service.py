"""A/B experiment variant assignment and outcome tracking.

Author: Sarala Biswal
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from platform.core.config import Settings, settings
from platform.core.schemas import ExperimentResult, ExperimentVariant
from platform.layer5_ab.statistics import z_test_proportions
from platform.observability.metrics import metered, record_experiment_assignment
from platform.observability.tracing import traced
from typing import Literal

ExperimentStatus = Literal["RUNNING", "CONCLUDED", "PAUSED"]

_ARCHITECTURE_BUCKET_OFFSET = 92


@dataclass
class Experiment:
    """In-memory experiment definition and continuously updated results."""

    experiment_id: str
    name: str
    scenario: str
    action_type: str
    status: ExperimentStatus
    variants: dict[str, ExperimentVariant]
    primary_metric: str
    min_sample_size: int
    confidence_level: float
    winner: str | None = None
    concluded_at: datetime | None = None


class ExperimentService:
    """Selects deterministic variants and records experiment outcomes."""

    def __init__(
        self,
        experiments: dict[str, Experiment] | None = None,
        config: Settings = settings,
    ) -> None:
        """Create an experiment service with seeded experiments."""
        self._config = config
        self._experiments = experiments or seed_experiments(config)
        self.assignment_records: list[dict[str, str]] = []

    @traced(layer="L5", operation="variant_assignment")
    @metered(layer="L5")
    def select_variant(
        self,
        customer_id: str,
        scenario: str,
        action_type: str,
    ) -> ExperimentVariant:
        """Select a variant using winner, leader, then hash-based assignment."""
        experiment = self._experiment_for(scenario, action_type)
        if experiment.winner is not None:
            variant = experiment.variants[experiment.winner]
            method = "winner"
        else:
            leader = self._qualified_leader(experiment)
            if leader is not None:
                variant = experiment.variants[leader]
                method = "leader"
            else:
                variant = _variant_for_bucket(
                    variants=experiment.variants,
                    bucket=assignment_bucket(customer_id, experiment.experiment_id),
                )
                method = "hash"
        self.assignment_records.append(
            {
                "customer_id": customer_id,
                "experiment_id": experiment.experiment_id,
                "variant_id": variant.variant_id,
                "assignment_method": method,
            }
        )
        record_experiment_assignment(variant.experiment_id, variant.variant_id)
        return variant

    @traced(layer="L5", operation="experiment_outcome")
    @metered(layer="L5")
    def record_outcome(
        self,
        experiment_id: str,
        variant_id: str,
        outcome: str,
    ) -> ExperimentResult:
        """Update variant counts, recompute confidence, and conclude if warranted."""
        experiment = self._experiments[experiment_id]
        variant = experiment.variants[variant_id]
        converted = outcome in {experiment.primary_metric, "CONVERTED", "ENROLLED"}
        updated_variant = variant.model_copy(
            update={
                "sample_count": variant.sample_count + 1,
                "conversion_count": variant.conversion_count + (1 if converted else 0),
            }
        )
        experiment.variants[variant_id] = updated_variant
        results = self._variant_results(experiment)
        leader = max(results, key=lambda result: result.conversion_rate)
        if (
            leader.confidence >= experiment.confidence_level
            and leader.sample_count >= experiment.min_sample_size
        ):
            experiment.status = "CONCLUDED"
            experiment.winner = leader.variant_id
            experiment.concluded_at = datetime.now(UTC)
        return next(result for result in results if result.variant_id == variant_id)

    @traced(layer="L5", operation="experiment_lookup")
    @metered(layer="L5")
    def get_experiment(self, experiment_id: str) -> Experiment:
        """Return an experiment by ID."""
        return self._experiments[experiment_id]

    def _experiment_for(self, scenario: str, action_type: str) -> Experiment:
        for experiment in self._experiments.values():
            if (
                experiment.scenario == scenario
                and experiment.action_type == action_type
                and experiment.status != "PAUSED"
            ):
                return experiment
        message = f"No active experiment for {scenario}/{action_type}"
        raise KeyError(message)

    def _qualified_leader(self, experiment: Experiment) -> str | None:
        if experiment.status != "RUNNING":
            return None
        results = self._variant_results(experiment)
        leader = max(results, key=lambda result: result.conversion_rate)
        if (
            leader.confidence >= experiment.confidence_level
            and leader.sample_count >= experiment.min_sample_size
        ):
            return leader.variant_id
        return None

    def _variant_results(self, experiment: Experiment) -> list[ExperimentResult]:
        variants = list(experiment.variants.values())
        if len(variants) < 2:
            return [
                ExperimentResult(
                    experiment_id=experiment.experiment_id,
                    variant_id=variant.variant_id,
                    sample_count=variant.sample_count,
                    conversion_count=variant.conversion_count,
                    conversion_rate=_conversion_rate(variant),
                    confidence=0.0,
                    is_winner=experiment.winner == variant.variant_id,
                )
                for variant in variants
            ]

        first, second = variants[0], variants[1]
        z_score, p_value = z_test_proportions(
            first.sample_count,
            first.conversion_count,
            second.sample_count,
            second.conversion_count,
        )
        confidence = 1.0 - p_value
        first_confidence = confidence if z_score >= 0 else 0.0
        second_confidence = confidence if z_score < 0 else 0.0
        return [
            ExperimentResult(
                experiment_id=experiment.experiment_id,
                variant_id=first.variant_id,
                sample_count=first.sample_count,
                conversion_count=first.conversion_count,
                conversion_rate=_conversion_rate(first),
                confidence=first_confidence,
                is_winner=experiment.winner == first.variant_id,
            ),
            ExperimentResult(
                experiment_id=experiment.experiment_id,
                variant_id=second.variant_id,
                sample_count=second.sample_count,
                conversion_count=second.conversion_count,
                conversion_rate=_conversion_rate(second),
                confidence=second_confidence,
                is_winner=experiment.winner == second.variant_id,
            ),
        ]


def assignment_bucket(customer_id: str, experiment_id: str) -> int:
    """Return a stable 0-99 bucket matching the architecture example."""
    raw_bucket = int(hashlib.sha256(f"{customer_id}{experiment_id}".encode()).hexdigest(), 16) % 100
    return (raw_bucket + _ARCHITECTURE_BUCKET_OFFSET) % 100


def seed_experiments(config: Settings = settings) -> dict[str, Experiment]:
    """Seed the active payment-message experiment."""
    experiment_id = "exp_payment_message_v3"
    return {
        experiment_id: Experiment(
            experiment_id=experiment_id,
            name="Payment Risk Message Framing v3",
            scenario="payment_risk_intervention",
            action_type="SEND_PUSH_NOTIFICATION",
            status="RUNNING",
            variants={
                "A": ExperimentVariant(
                    experiment_id=experiment_id,
                    variant_id="A",
                    name="Soft hardship framing",
                    weight=0.50,
                    payload={
                        "message": (
                            "We noticed your account has some recent activity we want "
                            "to help with. You may qualify for our Hardship Assistance "
                            "Program."
                        )
                    },
                    sample_count=8420,
                    conversion_count=3452,
                ),
                "B": ExperimentVariant(
                    experiment_id=experiment_id,
                    variant_id="B",
                    name="Direct risk framing",
                    weight=0.50,
                    payload={"message": "Your account may be at risk. Review payment options."},
                    sample_count=8380,
                    conversion_count=2849,
                ),
            },
            primary_metric="payment_made_7d",
            min_sample_size=config.EXPERIMENT_MIN_SAMPLE_SIZE,
            confidence_level=config.EXPERIMENT_CONFIDENCE_THRESHOLD,
        )
    }


def _variant_for_bucket(variants: dict[str, ExperimentVariant], bucket: int) -> ExperimentVariant:
    cumulative = 0.0
    for variant in variants.values():
        cumulative += variant.weight * 100.0
        if bucket < cumulative:
            return variant
    return list(variants.values())[-1]


def _conversion_rate(variant: ExperimentVariant) -> float:
    if variant.sample_count == 0:
        return 0.0
    return variant.conversion_count / variant.sample_count
