"""OpenTelemetry tracing setup and decorators.

Author: Sarala Biswal
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Awaitable, Callable, Mapping
from contextvars import Token
from dataclasses import dataclass
from platform.core.config import Settings
from typing import Any, TypeVar, cast

import structlog
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode

F = TypeVar("F", bound=Callable[..., object])
logger = structlog.get_logger()
_TRACING_CONFIGURED = False


@dataclass(frozen=True)
class ObservabilityContext:
    """Context extracted from a decorated service call."""

    trace_id: str
    customer_id: str
    scenario: str


def configure_tracing(settings: Settings) -> None:
    """Configure OpenTelemetry with an OTLP exporter pointing at Jaeger."""
    global _TRACING_CONFIGURED
    if _TRACING_CONFIGURED:
        return

    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": "banking-agentic-platform",
                "deployment.environment": settings.ENVIRONMENT,
            }
        )
    )
    exporter = OTLPSpanExporter(endpoint=settings.JAEGER_ENDPOINT, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _TRACING_CONFIGURED = True


def traced(layer: str, operation: str) -> Callable[[F], F]:
    """
    Decorate a service method with an OpenTelemetry span.

    The span includes layer, operation, trace_id, customer_id, and scenario
    when those fields can be inferred from arguments or schema objects.
    Exceptions are recorded and mark the span as ERROR.
    """

    def decorator(func: F) -> F:
        tracer = trace.get_tracer(func.__module__)

        if inspect.iscoroutinefunction(func):
            async_func = cast("Callable[..., Awaitable[object]]", func)

            @functools.wraps(func)
            async def async_wrapper(*args: object, **kwargs: object) -> object:
                context = extract_observability_context(func, args, kwargs)
                tokens = _bind_log_context(layer, operation, context)
                try:
                    with tracer.start_as_current_span(operation) as span:
                        _set_span_attributes(span.set_attribute, layer, operation, context)
                        try:
                            return await async_func(*args, **kwargs)
                        except Exception as exc:
                            span.record_exception(exc)
                            span.set_status(Status(StatusCode.ERROR, str(exc)))
                            raise
                finally:
                    structlog.contextvars.reset_contextvars(**tokens)

            return cast("F", async_wrapper)

        sync_func = cast("Callable[..., object]", func)

        @functools.wraps(func)
        def sync_wrapper(*args: object, **kwargs: object) -> object:
            context = extract_observability_context(func, args, kwargs)
            tokens = _bind_log_context(layer, operation, context)
            try:
                with tracer.start_as_current_span(operation) as span:
                    _set_span_attributes(span.set_attribute, layer, operation, context)
                    try:
                        return sync_func(*args, **kwargs)
                    except Exception as exc:
                        span.record_exception(exc)
                        span.set_status(Status(StatusCode.ERROR, str(exc)))
                        raise
            finally:
                structlog.contextvars.reset_contextvars(**tokens)

        return cast("F", sync_wrapper)

    return decorator


def extract_observability_context(
    func: Callable[..., object],
    args: tuple[object, ...],
    kwargs: Mapping[str, object],
) -> ObservabilityContext:
    """Extract trace, customer, and scenario values from call arguments."""
    values = _bound_values(func, args, kwargs)
    trace_id = _first_string(values, ("trace_id",))
    session_id = _first_string(values, ("session_id",))
    if trace_id == "unknown" and session_id != "unknown":
        trace_id = f"trace_{session_id}"
    if trace_id == "unknown":
        trace_id = _first_attr(values, "trace_id")
    return ObservabilityContext(
        trace_id=trace_id,
        customer_id=_first_string(values, ("customer_id",), fallback_attr="customer_id"),
        scenario=_first_string(values, ("scenario",), fallback_attr="scenario"),
    )


def force_flush_traces(timeout_millis: int = 1000) -> None:
    """Flush pending spans before short-lived demo processes exit."""
    provider = trace.get_tracer_provider()
    force_flush = getattr(provider, "force_flush", None)
    if callable(force_flush):
        try:
            force_flush(timeout_millis=timeout_millis)
        except Exception as exc:
            # Exporter availability is environment-specific in local runs.
            logger.warning(
                "trace_flush_failed",
                trace_id="unknown",
                layer="observability",
                operation="force_flush",
                error=str(exc),
            )


def _bind_log_context(
    layer: str,
    operation: str,
    context: ObservabilityContext,
) -> Mapping[str, Token[Any]]:
    return structlog.contextvars.bind_contextvars(
        trace_id=context.trace_id,
        layer=layer,
        operation=operation,
        customer_id=context.customer_id,
        scenario=context.scenario,
    )


def _set_span_attributes(
    set_attribute: Callable[[str, str], None],
    layer: str,
    operation: str,
    context: ObservabilityContext,
) -> None:
    set_attribute("layer", layer)
    set_attribute("operation", operation)
    set_attribute("trace_id", context.trace_id)
    set_attribute("customer_id", context.customer_id)
    set_attribute("scenario", context.scenario)


def _bound_values(
    func: Callable[..., object],
    args: tuple[object, ...],
    kwargs: Mapping[str, object],
) -> dict[str, object]:
    try:
        bound = inspect.signature(func).bind_partial(*args, **kwargs)
    except TypeError:
        return dict(kwargs)
    return dict(bound.arguments)


def _first_string(
    values: Mapping[str, object],
    keys: tuple[str, ...],
    fallback_attr: str | None = None,
) -> str:
    for key in keys:
        value = values.get(key)
        if isinstance(value, str) and value:
            return value
    if fallback_attr is not None:
        return _first_attr(values, fallback_attr)
    return "unknown"


def _first_attr(values: Mapping[str, object], attr: str) -> str:
    for value in values.values():
        nested = getattr(value, attr, None)
        if isinstance(nested, str) and nested:
            return nested
    return "unknown"
