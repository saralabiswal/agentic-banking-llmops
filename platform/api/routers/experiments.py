"""Experiments API router.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.api.dependencies import get_runner
from platform.layer6_sdk.blueprint_runner import BlueprintRunner

from fastapi import APIRouter, Depends

router = APIRouter()


@router.get("/experiments")
async def get_experiments(runner: BlueprintRunner = Depends(get_runner)) -> list[dict[str, object]]:
    """Return in-memory experiments."""
    experiment = runner.experiment_service.get_experiment("exp_payment_message_v3")
    return [
        {
            "experiment_id": experiment.experiment_id,
            "status": experiment.status,
            "winner": experiment.winner,
            "variants": [
                variant.model_dump(mode="json") for variant in experiment.variants.values()
            ],
        }
    ]
