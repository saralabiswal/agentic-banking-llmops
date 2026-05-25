"""Routed LLM inference service with timeout fallback and observability.

Author: Sarala Biswal
"""

from __future__ import annotations

import asyncio
import json
import time
from platform.adapters.mock_llm_client import MockLLMClient
from platform.core.config import Settings, settings
from platform.core.interfaces import LLMClient
from platform.llm_inference.metrics import record_llm_inference
from platform.llm_inference.router import route_for_task
from platform.llm_inference.schemas import InferenceResult, TaskType
from typing import Any

import structlog
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from pydantic import BaseModel

logger = structlog.get_logger()


class RoutedLLMInferenceService:
    """Routes LLM calls through primary and fallback backends with observability."""

    def __init__(
        self,
        primary_client: LLMClient,
        fallback_client: LLMClient | None = None,
        config: Settings = settings,
    ) -> None:
        """Create an inference service with injected primary and fallback clients."""
        self._primary_client = primary_client
        self._fallback_client = fallback_client or MockLLMClient()
        self._config = config

    async def complete(
        self,
        messages: list[dict[str, str]],
        task_type: TaskType,
        trace_id: str,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        schema: type[BaseModel] | None = None,
    ) -> InferenceResult:
        """Complete one routed LLM request, falling back to mock on timeout/provider errors."""
        del max_tokens, temperature
        route = route_for_task(task_type, self._config)
        system, user = _split_messages(messages)
        started = time.perf_counter()
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("llm.inference") as span:
            span.set_attribute("task_type", task_type.value)
            span.set_attribute("trace_id", trace_id)
            prompt_tokens = _token_estimate(system) + _token_estimate(user)
            try:
                content = await asyncio.wait_for(
                    self._call_client(self._primary_client, system, user, schema),
                    timeout=route.latency_budget_ms / 1000,
                )
                latency_ms = (time.perf_counter() - started) * 1000
                result = InferenceResult(
                    content=content,
                    model_id=route.primary_model_id,
                    backend=route.primary_backend,
                    primary_model_id=route.primary_model_id,
                    primary_backend=route.primary_backend,
                    fallback_reason=None,
                    latency_ms=latency_ms,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=_token_estimate(content),
                    fallback_used=False,
                    trace_id=trace_id,
                )
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                logger.warning(
                    "llm.inference.primary_failed",
                    trace_id=trace_id,
                    task_type=task_type.value,
                    backend=route.primary_backend,
                    reason=str(exc),
                )
                content = await self._call_client(self._fallback_client, system, user, schema)
                latency_ms = (time.perf_counter() - started) * 1000
                result = InferenceResult(
                    content=content,
                    model_id=route.fallback_model_id,
                    backend=route.fallback_backend,
                    primary_model_id=route.primary_model_id,
                    primary_backend=route.primary_backend,
                    fallback_reason=_fallback_reason(exc),
                    latency_ms=latency_ms,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=_token_estimate(content),
                    fallback_used=True,
                    trace_id=trace_id,
                )
            _set_span_attributes(span.set_attribute, result, task_type)
            record_llm_inference(
                task_type=task_type.value,
                backend=result.backend,
                fallback_used=result.fallback_used,
                latency_ms=result.latency_ms,
            )
            logger.info(
                "llm.inference.complete",
                trace_id=trace_id,
                task_type=task_type.value,
                model_id=result.model_id,
                backend=result.backend,
                latency_ms=result.latency_ms,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                fallback_used=result.fallback_used,
            )
            return result

    async def _call_client(
        self,
        client: LLMClient,
        system: str,
        user: str,
        schema: type[BaseModel] | None,
    ) -> str:
        """Call a schema-aware LLM client and serialize the validated content."""
        if schema is None:
            schema = _TextResponse
        payload = await client.complete(system=system, user=user, schema=schema)
        return json.dumps(payload, sort_keys=True)


class _TextResponse(BaseModel):
    """Fallback response schema for non-agent calls."""

    content: str = ""


def _split_messages(messages: list[dict[str, str]]) -> tuple[str, str]:
    system = "\n".join(
        message["content"] for message in messages if message.get("role") == "system"
    )
    user = "\n".join(message["content"] for message in messages if message.get("role") == "user")
    return system, user


def _token_estimate(text: str) -> int:
    return max(1, len(text.split())) if text else 0


def _set_span_attributes(
    set_attribute: Any,
    result: InferenceResult,
    task_type: TaskType,
) -> None:
    set_attribute("task_type", task_type.value)
    set_attribute("model_id", result.model_id)
    set_attribute("backend", result.backend)
    if result.primary_model_id is not None:
        set_attribute("primary_model_id", result.primary_model_id)
    if result.primary_backend is not None:
        set_attribute("primary_backend", result.primary_backend)
    if result.fallback_reason is not None:
        set_attribute("fallback_reason", result.fallback_reason)
    set_attribute("latency_ms", result.latency_ms)
    if result.prompt_tokens is not None:
        set_attribute("prompt_tokens", result.prompt_tokens)
    if result.completion_tokens is not None:
        set_attribute("completion_tokens", result.completion_tokens)
    set_attribute("fallback_used", result.fallback_used)
    set_attribute("trace_id", result.trace_id)


def _fallback_reason(exc: Exception) -> str:
    """Return a concise fallback reason for UI and audit summaries."""
    message = str(exc).strip()
    if message:
        return f"{type(exc).__name__}: {message}"
    return type(exc).__name__
