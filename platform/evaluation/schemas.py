"""Schemas for offline model and agent-output evaluation.

Author: Sarala Biswal
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class GateResult(BaseModel):
    """Result of one model evaluation gate."""

    gate: str
    passed: bool
    metrics: dict[str, float]
    failure_reason: str | None = None


class EvaluationReport(BaseModel):
    """Complete offline evaluation report for one candidate model version."""

    model_name: str
    candidate_version: str
    champion_version: str | None
    gates: list[GateResult]
    overall_passed: bool
    promotion_allowed: bool
    evaluated_at: datetime
    trace_id: str


class JudgeResult(BaseModel):
    """LLM-as-judge result for agent reasoning quality."""

    score: int = Field(ge=1, le=5)
    reasoning: str
    flags: list[str] = Field(default_factory=list)
    trace_id: str


class EvaluationModelOption(BaseModel):
    """Model and candidate versions available to the evaluation UI."""

    model_name: str
    label: str
    versions: list[str]
    default_version: str


class EvaluationOptions(BaseModel):
    """Evaluation selector options and storage-discovery status."""

    models: list[EvaluationModelOption]
    storage_ok: bool = True
    storage_error: str | None = None
