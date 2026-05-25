"""Prometheus metrics for LLM inference.

Author: Sarala Biswal
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

LLM_INFERENCE_TOTAL = Counter(
    "llm_inference_total",
    "Total LLM inference calls",
    labelnames=["task_type", "backend", "fallback"],
)

LLM_INFERENCE_LATENCY_MS = Histogram(
    "llm_inference_latency_ms",
    "LLM inference latency in milliseconds",
    labelnames=["task_type", "backend"],
    buckets=[50, 100, 250, 500, 800, 1000, 1200, 2000, 5000, 10000],
)


def record_llm_inference(
    task_type: str,
    backend: str,
    fallback_used: bool,
    latency_ms: float,
) -> None:
    """Record one observed LLM inference call."""
    LLM_INFERENCE_TOTAL.labels(
        task_type=task_type,
        backend=backend,
        fallback=str(fallback_used).lower(),
    ).inc()
    LLM_INFERENCE_LATENCY_MS.labels(task_type=task_type, backend=backend).observe(latency_ms)
