"""Evaluation API routes.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.api.dependencies import get_evaluation_store
from platform.core.config import settings
from platform.evaluation.pipeline import EvaluationPipeline
from platform.evaluation.schemas import (
    EvaluationModelOption,
    EvaluationOptions,
    EvaluationReport,
    JudgeResult,
)
from platform.evaluation.store import PostgresEvaluationStore
from uuid import uuid4

import mlflow
from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/evaluation", tags=["evaluation"])

SUPPORTED_MODELS: dict[str, str] = {
    "payment_risk_model": "Payment Risk Model",
    "churn_propensity_model": "Churn Propensity Model",
}


class EvaluationRunRequest(BaseModel):
    """Request body for an offline model evaluation run."""

    model_name: str
    candidate_version: str


@router.get("/options")
async def evaluation_options(
    store: PostgresEvaluationStore = Depends(get_evaluation_store),
) -> EvaluationOptions:
    """Return model/version options discovered from MLflow and evaluation history."""
    storage_ok = True
    storage_error: str | None = None
    history: list[EvaluationReport] = []
    try:
        history = await store.history(limit=100)
    except Exception as exc:
        storage_ok = False
        storage_error = str(exc)

    models = [
        EvaluationModelOption(
            model_name=model_name,
            label=label,
            versions=_versions_for(model_name, history),
            default_version=_default_version_for(model_name, history),
        )
        for model_name, label in SUPPORTED_MODELS.items()
    ]
    return EvaluationOptions(
        models=models,
        storage_ok=storage_ok,
        storage_error=storage_error,
    )


@router.post("/run")
async def run_evaluation(
    request: EvaluationRunRequest,
    store: PostgresEvaluationStore = Depends(get_evaluation_store),
) -> EvaluationReport:
    """Run all offline gates for a candidate model artifact."""
    return await EvaluationPipeline(store=store).run(
        model_name=request.model_name,
        candidate_version=request.candidate_version,
        trace_id=f"eval_{uuid4().hex[:12]}",
    )


@router.get("/history")
async def evaluation_history(
    model_name: str | None = None,
    limit: int = 20,
    store: PostgresEvaluationStore = Depends(get_evaluation_store),
) -> list[EvaluationReport]:
    """Return recent evaluation reports."""
    return await store.history(model_name=model_name, limit=limit)


@router.get("/judge-results")
async def judge_results(
    trace_id: str | None = None,
    store: PostgresEvaluationStore = Depends(get_evaluation_store),
) -> list[JudgeResult]:
    """Return stored LLM judge results."""
    return await store.judge_history(trace_id=trace_id)


def _versions_for(model_name: str, history: list[EvaluationReport]) -> list[str]:
    """Return known versions from MLflow and prior evaluation reports."""
    versions = {
        report.candidate_version for report in history if report.model_name == model_name
    }
    versions.update(_mlflow_versions_for(model_name))
    versions.add("1")
    return sorted(versions, key=_version_sort_key, reverse=True)


def _default_version_for(model_name: str, history: list[EvaluationReport]) -> str:
    """Prefer the latest evaluated version, otherwise the highest discovered version."""
    for report in history:
        if report.model_name == model_name:
            return report.candidate_version
    versions = _versions_for(model_name, history)
    return versions[0] if versions else "1"


def _mlflow_versions_for(model_name: str) -> set[str]:
    """Best-effort model version discovery from MLflow registry."""
    try:
        mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
        versions = mlflow.search_model_versions(filter_string=f"name = '{model_name}'")
    except Exception:
        return set()
    return {str(version.version) for version in versions if version.version is not None}


def _version_sort_key(value: str) -> tuple[int, str]:
    """Sort numeric model versions ahead of free-form versions."""
    return (int(value), value) if value.isdigit() else (-1, value)
