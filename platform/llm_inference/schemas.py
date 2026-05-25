"""Schemas for routed LLM inference.

Author: Sarala Biswal
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    """LLM task categories with independent latency budgets."""

    RISK_SCORING = "risk_scoring"
    INTERVENTION_REASONING = "intervention_reasoning"
    DISPUTE_ANALYSIS = "dispute_analysis"
    CHURN_ASSESSMENT = "churn_assessment"


class InferenceResult(BaseModel):
    """Observed result of one routed LLM call."""

    content: str
    model_id: str
    backend: str
    primary_model_id: str | None = None
    primary_backend: str | None = None
    fallback_reason: str | None = None
    latency_ms: float = Field(ge=0.0)
    prompt_tokens: int | None
    completion_tokens: int | None
    fallback_used: bool
    trace_id: str


class ModelRoute(BaseModel):
    """Primary and fallback model route for a task type."""

    task_type: TaskType
    primary_backend: str
    primary_model_id: str
    latency_budget_ms: int
    fallback_backend: str = "mock"
    fallback_model_id: str = "mock-deterministic"
