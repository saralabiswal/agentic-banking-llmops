"""Static pipeline definitions for hub-and-spoke orchestration.

Author: Sarala Biswal
"""

from __future__ import annotations

from dataclasses import dataclass
from platform.core.schemas import InterventionProposal, RiskAssessment, Scenario
from typing import Literal

from pydantic import BaseModel

FailureRoute = Literal["human_review"]


@dataclass(frozen=True)
class PipelineStep:
    """A deterministic agent invocation step in a pipeline."""

    agent: str
    timeout_ms: int
    output_schema: type[BaseModel]
    on_failure: FailureRoute = "human_review"


@dataclass(frozen=True)
class BranchStep:
    """A deterministic branch evaluated by the orchestrator."""

    branch_on: str
    true_values: tuple[str, ...]
    if_true: str
    if_false: str | None
    description: str


@dataclass(frozen=True)
class Pipeline:
    """Static pipeline definition for one scenario."""

    scenario: str
    steps: tuple[PipelineStep | BranchStep, ...]


PIPELINES: dict[str, Pipeline] = {
    Scenario.PAYMENT_RISK.value: Pipeline(
        scenario=Scenario.PAYMENT_RISK.value,
        steps=(
            PipelineStep(
                agent="RiskScoringAgent",
                timeout_ms=8000,
                output_schema=RiskAssessment,
            ),
            BranchStep(
                branch_on="risk_level",
                true_values=("HIGH", "CRITICAL"),
                if_true="InterventionAgent",
                if_false=None,
                description="risk_level in HIGH or CRITICAL routes to InterventionAgent",
            ),
            PipelineStep(
                agent="InterventionAgent",
                timeout_ms=10000,
                output_schema=InterventionProposal,
            ),
        ),
    ),
    Scenario.BILLING_DISPUTE.value: Pipeline(
        scenario=Scenario.BILLING_DISPUTE.value,
        steps=(
            PipelineStep(
                agent="DisputeTriageAgent",
                timeout_ms=8000,
                output_schema=RiskAssessment,
            ),
            PipelineStep(
                agent="ResolutionAgent",
                timeout_ms=10000,
                output_schema=InterventionProposal,
            ),
        ),
    ),
    Scenario.CHURN_PREVENTION.value: Pipeline(
        scenario=Scenario.CHURN_PREVENTION.value,
        steps=(
            PipelineStep(
                agent="ChurnSignalAgent",
                timeout_ms=8000,
                output_schema=RiskAssessment,
            ),
            PipelineStep(
                agent="RetentionOfferAgent",
                timeout_ms=10000,
                output_schema=InterventionProposal,
            ),
        ),
    ),
}


def get_pipeline(scenario: str) -> Pipeline:
    """Return the static pipeline for a scenario."""
    return PIPELINES[scenario]
