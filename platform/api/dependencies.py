"""FastAPI dependency wiring for local platform services.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.layer6_sdk.blueprint_runner import BlueprintRunner
from platform.layer6_sdk.outcome_router import OutcomeRouter

runner = BlueprintRunner()
outcome_router = OutcomeRouter(
    experiment_service=runner.experiment_service,
    audit_writer=runner.audit_writer,
)


def get_runner() -> BlueprintRunner:
    """Return the process-local blueprint runner."""
    return runner


def get_outcome_router() -> OutcomeRouter:
    """Return the process-local outcome router."""
    return outcome_router
