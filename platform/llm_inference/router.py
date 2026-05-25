"""Routing table for task-specific LLM inference.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.core.config import Settings, settings
from platform.llm_inference.schemas import ModelRoute, TaskType

FAST_LATENCY_BUDGETS_MS: dict[TaskType, int] = {
    TaskType.RISK_SCORING: 800,
    TaskType.INTERVENTION_REASONING: 1200,
    TaskType.DISPUTE_ANALYSIS: 2000,
    TaskType.CHURN_ASSESSMENT: 1000,
}

LOCAL_LLM_LATENCY_BUDGETS_MS: dict[TaskType, int] = {
    TaskType.RISK_SCORING: 15_000,
    TaskType.INTERVENTION_REASONING: 20_000,
    TaskType.DISPUTE_ANALYSIS: 25_000,
    TaskType.CHURN_ASSESSMENT: 18_000,
}

API_LLM_LATENCY_BUDGETS_MS: dict[TaskType, int] = {
    TaskType.RISK_SCORING: 20_000,
    TaskType.INTERVENTION_REASONING: 25_000,
    TaskType.DISPUTE_ANALYSIS: 30_000,
    TaskType.CHURN_ASSESSMENT: 22_000,
}


def route_for_task(
    task_type: TaskType,
    config: Settings = settings,
) -> ModelRoute:
    """Return the configured route for a task type."""
    return ModelRoute(
        task_type=task_type,
        primary_backend=config.LLM_BACKEND,
        primary_model_id=config.LLM_MODEL if config.LLM_BACKEND != "mock" else "mock-deterministic",
        latency_budget_ms=_latency_budget_for(task_type, config),
    )


def _latency_budget_for(task_type: TaskType, config: Settings) -> int:
    """Return a task budget sized for the active backend."""
    if config.LLM_BACKEND == "ollama":
        return LOCAL_LLM_LATENCY_BUDGETS_MS[task_type]
    if config.LLM_BACKEND == "api":
        return API_LLM_LATENCY_BUDGETS_MS[task_type]
    return FAST_LATENCY_BUDGETS_MS[task_type]
