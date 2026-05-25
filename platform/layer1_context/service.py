"""Context assembly service for Layer 1.

Author: Sarala Biswal
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from platform.core.config import Settings, settings
from platform.core.exceptions import SourceUnavailableError
from platform.core.interfaces import AuditWriter, ContextStore, FeatureStore, MemoryStore
from platform.core.schemas import AssemblyResult, AuditRecord, CustomerProfile
from platform.layer1_context.adapters.banking_adapter import CoreBankingAdapter
from platform.layer1_context.adapters.behavioral_adapter import BehavioralSignalsAdapter
from platform.layer1_context.adapters.card_adapter import CardSystemAdapter
from platform.layer1_context.adapters.crm_adapter import CRMAdapter
from platform.layer1_context.feature_store import pull_signals
from platform.layer1_context.normalizer import normalize_customer_profile
from platform.memory.schemas import CustomerMemory
from platform.ml.schemas import ModelScore
from platform.observability.metrics import metered, record_adapter_latency
from platform.observability.tracing import traced
from typing import Any, Protocol

import structlog
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

logger = structlog.get_logger()


class SourceAdapter(Protocol):
    """Protocol for Layer 1 source adapters."""

    name: str

    async def fetch(self, customer_id: str) -> dict[str, Any]:
        """Fetch raw source data for a customer."""
        ...


class MLScorer(Protocol):
    """Protocol for Layer 1 classical ML scoring."""

    async def score(self, profile: CustomerProfile, trace_id: str) -> ModelScore:
        """Score a normalized customer profile."""
        ...


@dataclass(frozen=True)
class SourceFetchResult:
    """Internal source fetch result with latency and degradation metadata."""

    name: str
    data: dict[str, Any] | None
    latency_ms: int
    degraded: bool
    reason: str | None = None


class ContextAssemblyService:
    """
    Assembles a unified customer profile from multiple source systems.

    The service writes one immutable session-scoped profile to Valkey and one
    permanent audit record. Source failures degrade the profile rather than
    failing the pipeline.
    """

    def __init__(
        self,
        context_store: ContextStore,
        audit_writer: AuditWriter | None = None,
        feature_store: FeatureStore | None = None,
        memory_store: MemoryStore | None = None,
        ml_scoring_service: MLScorer | None = None,
        source_adapters: list[SourceAdapter] | None = None,
        config: Settings = settings,
    ) -> None:
        """Create a context assembly service with injected interfaces."""
        self._context_store = context_store
        self._audit_writer = audit_writer
        self._feature_store = feature_store
        self._memory_store = memory_store
        self._ml_scoring_service = ml_scoring_service
        self._config = config
        self._source_adapters = source_adapters or [
            CardSystemAdapter(),
            CoreBankingAdapter(),
            CRMAdapter(),
            BehavioralSignalsAdapter(),
        ]

    @traced(layer="L1", operation="context_assembly")
    @metered(layer="L1")
    async def assemble(self, customer_id: str, session_id: str, scenario: str) -> AssemblyResult:
        """Assemble and persist a unified customer context for a session."""
        started = time.perf_counter()
        trace_id = f"trace_{session_id}"
        self._set_scenario(scenario)

        # Source adapters run concurrently so one slow system cannot consume the full SLA.
        fetch_results = await asyncio.gather(
            *[
                self._fetch_with_timeout(adapter, customer_id, trace_id)
                for adapter in self._source_adapters
            ]
        )

        source_data = {result.name: result.data for result in fetch_results}
        sources_degraded = [result.name for result in fetch_results if result.degraded]
        sources_available = [result.name for result in fetch_results if not result.degraded]
        # Feature-store signals are fetched separately because model versions must be audited.
        signals_task = asyncio.create_task(pull_signals(customer_id, self._feature_store))
        signals = await signals_task
        sources_available.append("feature_store")

        assembled_at = datetime.now(UTC)
        assembly_ms = int((time.perf_counter() - started) * 1000)
        profile = normalize_customer_profile(
            customer_id=customer_id,
            source_data=source_data,
            signals=signals,
            assembled_at=assembled_at,
            assembly_latency_ms=assembly_ms,
            sources_available=sources_available,
            sources_degraded=sources_degraded,
        )
        if self._ml_scoring_service is not None:
            profile, ml_degraded = await self._score_profile(profile, trace_id)
            if ml_degraded:
                sources_degraded.append("ml_scoring")
            else:
                sources_available.append("ml_scoring")
            profile = profile.model_copy(
                update={
                    "sources_available": sources_available,
                    "sources_degraded": sources_degraded,
                    "partial_context": bool(sources_degraded),
                }
            )
        if self._memory_store is not None:
            memories, memory_degraded = await self._retrieve_memory(
                customer_id=customer_id,
                session_id=session_id,
                scenario=scenario,
                trace_id=trace_id,
                assembled_at=assembled_at,
            )
            if memory_degraded:
                sources_degraded.append("memory")
            else:
                sources_available.append("memory")
            profile = profile.model_copy(
                update={
                    "long_term_memory": memories,
                    "sources_available": sources_available,
                    "sources_degraded": sources_degraded,
                    "partial_context": bool(sources_degraded),
                }
            )
        profile_json = profile.model_dump_json()
        context_key = f"session:{session_id}:customer_profile"
        # The profile is session-scoped; downstream layers read it by this stable context key.
        await self._context_store.set(
            context_key,
            profile_json,
            ttl=self._config.CONTEXT_TTL_SECONDS,
        )

        ttl_expires_at = assembled_at + timedelta(seconds=self._config.CONTEXT_TTL_SECONDS)
        profile_hash = hashlib.sha256(profile_json.encode("utf-8")).hexdigest()
        audit_id = f"aud_{assembled_at:%Y%m%d_%H%M%S}_{customer_id}"
        if self._audit_writer is not None:
            # The audit payload records both success and degradation for regulatory replay.
            await self._audit_writer.write(
                AuditRecord(
                    audit_id=audit_id,
                    event_type="CONTEXT_ASSEMBLY",
                    trace_id=trace_id,
                    session_id=session_id,
                    customer_id=customer_id,
                    timestamp=assembled_at,
                    layer="1",
                    payload={
                        "sources_succeeded": sources_available,
                        "sources_failed": sources_degraded,
                        "failure_reasons": {
                            result.name: result.reason
                            for result in fetch_results
                            if result.reason is not None
                        },
                        "adapter_latencies_ms": {
                            result.name: result.latency_ms for result in fetch_results
                        },
                        "assembly_latency_ms": assembly_ms,
                        "profile_hash": f"sha256:{profile_hash}",
                        "model_versions_used": profile.signals.model_versions,
                        "partial_context": profile.partial_context,
                        "ttl_expires_at": ttl_expires_at.isoformat(),
                    },
                )
            )

        status = "DEGRADED" if sources_degraded else "ASSEMBLED"
        logger.info(
            "context_assembly_complete",
            trace_id=trace_id,
            layer="1",
            operation="assemble",
            customer_id=customer_id,
            latency_ms=assembly_ms,
            sources_degraded=sources_degraded,
        )
        return AssemblyResult(
            status=status,
            session_id=session_id,
            customer_id=customer_id,
            partial_context=profile.partial_context,
            sources_available=profile.sources_available,
            sources_degraded=sources_degraded,
            model_versions_used=profile.signals.model_versions,
            ttl_expires_at=ttl_expires_at,
            assembly_ms=assembly_ms,
        )

    async def _score_profile(
        self,
        profile: CustomerProfile,
        trace_id: str,
    ) -> tuple[CustomerProfile, bool]:
        """Apply classical ML scores, falling back to feature-store signals on failure."""
        assert self._ml_scoring_service is not None
        try:
            model_score = await self._ml_scoring_service.score(profile, trace_id)
            updated_versions = {
                **profile.signals.model_versions,
                **model_score.model_versions,
            }
            updated_signals = profile.signals.model_copy(
                update={
                    "risk_score": model_score.risk_score,
                    "churn_probability": model_score.churn_probability,
                    "model_versions": updated_versions,
                }
            )
            logger.info(
                "ml.scoring_applied",
                trace_id=trace_id,
                customer_id=profile.customer_id,
                risk_score=model_score.risk_score,
                churn_probability=model_score.churn_probability,
                model_versions=model_score.model_versions,
            )
            return profile.model_copy(update={"signals": updated_signals}), False
        except Exception as exc:
            logger.warning(
                "ml.scoring_degraded",
                trace_id=trace_id,
                customer_id=profile.customer_id,
                reason=str(exc),
            )
            return profile, True

    async def _retrieve_memory(
        self,
        customer_id: str,
        session_id: str,
        scenario: str,
        trace_id: str,
        assembled_at: datetime,
    ) -> tuple[list[CustomerMemory], bool]:
        """Retrieve long-term memory without making Qdrant a hard Layer 1 dependency."""
        assert self._memory_store is not None
        try:
            memories = await self._memory_store.retrieve(customer_id, scenario, top_k=5)
            await self._write_memory_retrieved_audit(
                customer_id=customer_id,
                session_id=session_id,
                scenario=scenario,
                trace_id=trace_id,
                timestamp=assembled_at,
                count=len(memories),
                degraded=False,
                reason=None,
            )
            logger.info(
                "memory.retrieved",
                count=len(memories),
                customer_id=customer_id,
                trace_id=trace_id,
                scenario=scenario,
            )
            return memories, False
        except Exception as exc:
            await self._write_memory_retrieved_audit(
                customer_id=customer_id,
                session_id=session_id,
                scenario=scenario,
                trace_id=trace_id,
                timestamp=assembled_at,
                count=0,
                degraded=True,
                reason=str(exc),
            )
            logger.warning(
                "memory.retrieve_degraded",
                count=0,
                customer_id=customer_id,
                trace_id=trace_id,
                scenario=scenario,
                reason=str(exc),
            )
            return [], True

    async def _write_memory_retrieved_audit(
        self,
        customer_id: str,
        session_id: str,
        scenario: str,
        trace_id: str,
        timestamp: datetime,
        count: int,
        degraded: bool,
        reason: str | None,
    ) -> None:
        """Write the Layer 1 memory retrieval audit record."""
        if self._audit_writer is None:
            return
        await self._audit_writer.write(
            AuditRecord(
                audit_id=f"aud_memory_retrieved_{timestamp:%Y%m%d_%H%M%S_%f}_{customer_id}",
                event_type="MEMORY_RETRIEVED",
                trace_id=trace_id,
                session_id=session_id,
                customer_id=customer_id,
                timestamp=timestamp,
                layer="1",
                payload={
                    "scenario": scenario,
                    "memory_count": count,
                    "degraded": degraded,
                    "reason": reason,
                },
            )
        )

    def _set_scenario(self, scenario: str) -> None:
        """Pass scenario context to adapters that simulate scenario-specific behavior."""
        for adapter in self._source_adapters:
            if hasattr(adapter, "scenario"):
                adapter.scenario = scenario

    async def _fetch_with_timeout(
        self,
        adapter: SourceAdapter,
        customer_id: str,
        trace_id: str,
    ) -> SourceFetchResult:
        """Fetch one source with a hard timeout and graceful degradation."""
        started = time.perf_counter()
        timeout = self._config.SOURCE_ADAPTER_TIMEOUT_MS / 1000
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span(f"{adapter.name}_adapter_fetch") as span:
            span.set_attribute("layer", "L1")
            span.set_attribute("operation", f"{adapter.name}_adapter_fetch")
            span.set_attribute("trace_id", trace_id)
            span.set_attribute("customer_id", customer_id)
            span.set_attribute("adapter", adapter.name)
            try:
                # asyncio.wait_for enforces the hard per-source timeout from Settings.
                data = await asyncio.wait_for(adapter.fetch(customer_id), timeout=timeout)
                latency_ms = int((time.perf_counter() - started) * 1000)
                span.set_attribute("status", "OK")
                record_adapter_latency(adapter.name, "success", latency_ms)
                logger.info(
                    "source_adapter_fetch_complete",
                    trace_id=trace_id,
                    layer="1",
                    operation="fetch_source",
                    adapter=adapter.name,
                    latency_ms=latency_ms,
                )
                return SourceFetchResult(adapter.name, data, latency_ms, degraded=False)
            except (TimeoutError, SourceUnavailableError) as exc:
                latency_ms = int((time.perf_counter() - started) * 1000)
                timed_out = isinstance(exc, (TimeoutError, asyncio.TimeoutError))
                # Degraded sources are reported as data gaps, not fatal pipeline failures.
                reason = "TIMEOUT_150MS" if timed_out else str(exc)
                status = "timeout" if timed_out else "error"
                span.set_attribute("status", "TIMEOUT" if timed_out else "ERROR")
                span.set_status(Status(StatusCode.ERROR, reason))
                span.add_event("source_adapter_failed", {"reason": reason})
                record_adapter_latency(adapter.name, status, latency_ms)
                logger.warning(
                    "source_adapter_failed",
                    trace_id=trace_id,
                    layer="1",
                    operation="fetch_source",
                    adapter=adapter.name,
                    latency_ms=latency_ms,
                    reason=reason,
                )
                return SourceFetchResult(
                    adapter.name,
                    None,
                    latency_ms,
                    degraded=True,
                    reason=reason,
                )
