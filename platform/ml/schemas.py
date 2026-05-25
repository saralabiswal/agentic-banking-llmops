"""Schemas for classical ML training and scoring.

Author: Sarala Biswal
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ModelScore(BaseModel):
    """Risk and churn scores produced by trained propensity models."""

    risk_score: float = Field(ge=0.0, le=1.0)
    churn_probability: float = Field(ge=0.0, le=1.0)
    model_versions: dict[str, str]
    scored_at: datetime


class TrainingSample(BaseModel):
    """Synthetic tabular sample used for model training and tests."""

    features: dict[str, float]
    label: int = Field(ge=0, le=1)
    segment: str
