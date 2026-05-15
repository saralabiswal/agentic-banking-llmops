"""Outcome processing for Layer 5 experiment feedback.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.core.schemas import ExperimentResult, OutcomeEvent
from platform.layer5_ab.experiment_service import ExperimentService
from platform.observability.metrics import metered
from platform.observability.tracing import traced


class OutcomeProcessor:
    """Routes outcome events back into the experiment service."""

    def __init__(self, experiment_service: ExperimentService) -> None:
        """Create an outcome processor."""
        self._experiment_service = experiment_service

    @traced(layer="L5", operation="outcome_processing")
    @metered(layer="L5")
    def record_outcome(self, event: OutcomeEvent) -> ExperimentResult | None:
        """Record an outcome when experiment metadata is present."""
        experiment_id = event.metadata.get("experiment_id")
        variant_id = event.metadata.get("variant_id")
        if not isinstance(experiment_id, str) or not isinstance(variant_id, str):
            return None
        return self._experiment_service.record_outcome(
            experiment_id=experiment_id,
            variant_id=variant_id,
            outcome=event.outcome_type,
        )
