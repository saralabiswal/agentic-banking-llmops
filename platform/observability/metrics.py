"""Prometheus metrics and metering decorators for platform services.

Author: Sarala Biswal
"""

from __future__ import annotations

import functools
import inspect
import time
from collections.abc import Awaitable, Callable
from platform.core.schemas import CheckResult
from platform.observability.tracing import extract_observability_context
from typing import TypeVar, cast

from prometheus_client import Counter, Histogram

F = TypeVar("F", bound=Callable[..., object])

LAYER_LATENCY = Histogram(
    "platform_layer_latency_seconds",
    "Latency per layer",
    labelnames=["layer", "scenario", "status"],
    buckets=[0.05, 0.1, 0.2, 0.5, 1.0, 3.0, 10.0, 30.0],
)

ADAPTER_LATENCY = Histogram(
    "platform_adapter_latency_seconds",
    "Latency per source adapter",
    labelnames=["adapter", "status"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.15, 0.2, 0.5, 1.0],
)

GUARDRAIL_CHECKS = Counter(
    "platform_guardrail_checks_total",
    "Guardrail check outcomes",
    labelnames=["category", "status", "rule_id"],
)

AGENT_TOOL_CALLS = Counter(
    "platform_agent_tool_calls_total",
    "Agent tool authorization calls",
    labelnames=["agent", "tool", "status"],
)

EXPERIMENT_ASSIGNMENTS = Counter(
    "platform_experiment_assignments_total",
    "Experiment variant assignments",
    labelnames=["experiment_id", "variant_id"],
)


def metered(layer: str) -> Callable[[F], F]:
    """Decorate a service method and record latency/status to Prometheus."""

    def decorator(func: F) -> F:
        """Wrap sync and async functions while preserving their original signature metadata."""
        if inspect.iscoroutinefunction(func):
            async_func = cast("Callable[..., Awaitable[object]]", func)

            @functools.wraps(func)
            async def async_wrapper(*args: object, **kwargs: object) -> object:
                """Record async method duration and mark the metric status on exceptions."""
                started = time.perf_counter()
                context = extract_observability_context(func, args, kwargs)
                status = "success"
                try:
                    return await async_func(*args, **kwargs)
                except Exception:
                    status = "error"
                    raise
                finally:
                    _observe_layer_latency(layer, context.scenario, status, started)

            return cast("F", async_wrapper)

        sync_func = cast("Callable[..., object]", func)

        @functools.wraps(func)
        def sync_wrapper(*args: object, **kwargs: object) -> object:
            """Record sync method duration and mark the metric status on exceptions."""
            started = time.perf_counter()
            context = extract_observability_context(func, args, kwargs)
            status = "success"
            try:
                return sync_func(*args, **kwargs)
            except Exception:
                status = "error"
                raise
            finally:
                _observe_layer_latency(layer, context.scenario, status, started)

        return cast("F", sync_wrapper)

    return decorator


def record_adapter_latency(adapter: str, status: str, latency_ms: int) -> None:
    """Record source-adapter latency in seconds."""
    ADAPTER_LATENCY.labels(adapter=adapter, status=status).observe(latency_ms / 1000)


def record_guardrail_checks(checks: list[CheckResult]) -> None:
    """Record guardrail check outcomes by category, status, and rule ID."""
    for check in checks:
        GUARDRAIL_CHECKS.labels(
            category=check.category,
            status=check.status,
            rule_id=check.rule_id,
        ).inc()


def record_agent_tool_call(agent: str, tool: str, status: str) -> None:
    """Record an agent tool authorization decision."""
    AGENT_TOOL_CALLS.labels(agent=agent, tool=tool, status=status).inc()


def record_experiment_assignment(experiment_id: str, variant_id: str) -> None:
    """Record a deterministic experiment assignment."""
    EXPERIMENT_ASSIGNMENTS.labels(
        experiment_id=experiment_id,
        variant_id=variant_id,
    ).inc()


def _observe_layer_latency(layer: str, scenario: str, status: str, started: float) -> None:
    LAYER_LATENCY.labels(layer=layer, scenario=scenario, status=status).observe(
        time.perf_counter() - started
    )
