"""Unit tests for routed LLM inference.

Author: Sarala Biswal
"""

from __future__ import annotations

import asyncio
import json
from platform.core.config import Settings
from platform.llm_inference.router import route_for_task
from platform.llm_inference.schemas import TaskType
from platform.llm_inference.service import RoutedLLMInferenceService
from typing import Any

import pytest
from pydantic import BaseModel


class SimpleResponse(BaseModel):
    """Small schema for inference tests."""

    answer: str


class StaticLLM:
    """Schema-aware LLM test double."""

    async def complete(self, system: str, user: str, schema: type[BaseModel]) -> dict[str, Any]:
        """Return one validated payload."""
        del system, user
        return schema.model_validate({"answer": "primary"}).model_dump(mode="json")


class SlowFailingLLM:
    """LLM test double that exceeds the risk-scoring budget."""

    async def complete(self, system: str, user: str, schema: type[BaseModel]) -> dict[str, Any]:
        """Sleep past the shortest configured budget."""
        del system, user
        await asyncio.sleep(1.0)
        return schema.model_validate({"answer": "too-late"}).model_dump(mode="json")


class FallbackLLM:
    """Fallback LLM test double."""

    async def complete(self, system: str, user: str, schema: type[BaseModel]) -> dict[str, Any]:
        """Return the fallback response."""
        del system, user
        return schema.model_validate({"answer": "fallback"}).model_dump(mode="json")


@pytest.mark.asyncio
async def test_inference_service_returns_primary_result() -> None:
    """Primary calls should return content and observability metadata."""
    service = RoutedLLMInferenceService(primary_client=StaticLLM())

    result = await service.complete(
        messages=[
            {"role": "system", "content": "Answer in JSON."},
            {"role": "user", "content": "hello"},
        ],
        task_type=TaskType.RISK_SCORING,
        trace_id="trace_inference_primary",
        schema=SimpleResponse,
    )

    assert json.loads(result.content)["answer"] == "primary"
    assert result.backend == "mock"
    assert result.fallback_used is False
    assert result.prompt_tokens is not None
    assert result.completion_tokens is not None


@pytest.mark.asyncio
async def test_timeout_uses_fallback_result() -> None:
    """Timeouts should fall back to the configured mock-safe backend."""
    service = RoutedLLMInferenceService(
        primary_client=SlowFailingLLM(),
        fallback_client=FallbackLLM(),
    )

    result = await service.complete(
        messages=[
            {"role": "system", "content": "Answer in JSON."},
            {"role": "user", "content": "hello"},
        ],
        task_type=TaskType.RISK_SCORING,
        trace_id="trace_inference_fallback",
        schema=SimpleResponse,
    )

    assert json.loads(result.content)["answer"] == "fallback"
    assert result.backend == "mock"
    assert result.fallback_used is True


def test_task_routes_have_expected_latency_budgets() -> None:
    """Task routing table should expose backend-appropriate latency budgets."""
    mock_config = Settings(LLM_BACKEND="mock", LLM_MODEL="mock")
    ollama_config = Settings(LLM_BACKEND="ollama", LLM_MODEL="llama3.2")

    assert route_for_task(TaskType.RISK_SCORING, mock_config).latency_budget_ms == 800
    assert route_for_task(TaskType.INTERVENTION_REASONING, mock_config).latency_budget_ms == 1200
    assert route_for_task(TaskType.DISPUTE_ANALYSIS, mock_config).latency_budget_ms == 2000
    assert route_for_task(TaskType.CHURN_ASSESSMENT, mock_config).latency_budget_ms == 1000
    assert route_for_task(TaskType.RISK_SCORING, ollama_config).latency_budget_ms == 15_000
    assert (
        route_for_task(TaskType.INTERVENTION_REASONING, ollama_config).latency_budget_ms
        == 20_000
    )
    assert route_for_task(TaskType.DISPUTE_ANALYSIS, ollama_config).latency_budget_ms == 25_000
    assert route_for_task(TaskType.CHURN_ASSESSMENT, ollama_config).latency_budget_ms == 18_000
