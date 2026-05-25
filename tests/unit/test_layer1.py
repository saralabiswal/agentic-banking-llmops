"""Unit tests for Layer 1 context assembly.

Author: Sarala Biswal
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from platform.core.exceptions import DuplicateSessionError, SourceUnavailableError
from platform.core.schemas import AuditRecord, CustomerProfile
from platform.layer1_context.adapters.banking_adapter import CoreBankingAdapter
from platform.layer1_context.adapters.behavioral_adapter import BehavioralSignalsAdapter
from platform.layer1_context.adapters.card_adapter import CardSystemAdapter
from platform.layer1_context.adapters.crm_adapter import CRMAdapter
from platform.layer1_context.service import ContextAssemblyService
from platform.memory.schemas import CustomerMemory, MemoryType
from platform.ml.schemas import ModelScore
from typing import Any
from uuid import uuid4

import pytest


class MemoryContextStore:
    """In-memory context store with NX semantics for unit tests."""

    def __init__(self) -> None:
        """Create an empty store."""
        self.values: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        """Return a stored value."""
        return self.values.get(key)

    async def set(self, key: str, value: str, ttl: int) -> None:
        """Set a key once."""
        del ttl
        if key in self.values:
            raise DuplicateSessionError(key)
        self.values[key] = value

    async def delete(self, key: str) -> None:
        """Delete a key."""
        self.values.pop(key, None)


class MemoryAuditWriter:
    """In-memory audit writer for unit tests."""

    def __init__(self) -> None:
        """Create an empty writer."""
        self.records: list[AuditRecord] = []

    async def write(self, record: AuditRecord) -> None:
        """Store an audit record."""
        self.records.append(record)


class DownAdapter:
    """Source adapter that always fails."""

    def __init__(self, name: str) -> None:
        """Create a failing adapter with a source name."""
        self.name = name

    async def fetch(self, customer_id: str) -> dict[str, Any]:
        """Raise source unavailable for any customer."""
        raise SourceUnavailableError(f"{self.name} down for {customer_id}")


class Layer1MemoryStoreStub:
    """Memory store test double."""

    def __init__(self, memories: list[CustomerMemory] | None = None, fail: bool = False) -> None:
        """Create a memory store that returns fixed memories or raises."""
        self.memories = memories or []
        self.fail = fail

    async def store(self, memory: CustomerMemory) -> str:
        """Store a memory in the test double."""
        self.memories.append(memory)
        return memory.memory_id

    async def retrieve(
        self,
        customer_id: str,
        scenario: str,
        top_k: int = 5,
        memory_types: list[MemoryType] | None = None,
    ) -> list[CustomerMemory]:
        """Return fixed memories or raise to exercise degraded memory behavior."""
        del customer_id, scenario, top_k, memory_types
        if self.fail:
            raise RuntimeError("qdrant unavailable")
        return self.memories

    async def get_recent(self, customer_id: str, limit: int = 10) -> list[CustomerMemory]:
        """Return recent test memories."""
        del customer_id
        return self.memories[:limit]


class Layer1MLScorerStub:
    """ML scoring service test double."""

    def __init__(self, score: ModelScore | None = None, fail: bool = False) -> None:
        """Create a scorer that returns a fixed score or raises."""
        self.score_result = score
        self.fail = fail

    async def score(self, profile: CustomerProfile, trace_id: str) -> ModelScore:
        """Score a profile or raise to exercise fallback behavior."""
        del profile, trace_id
        if self.fail:
            raise RuntimeError("model artifact missing")
        assert self.score_result is not None
        return self.score_result


@pytest.mark.asyncio
async def test_c002_payment_risk_degrades_on_crm_timeout_under_200ms() -> None:
    """C002 payment risk should time out CRM and still assemble under 200ms."""
    context_store = MemoryContextStore()
    audit_writer = MemoryAuditWriter()
    service = ContextAssemblyService(
        context_store=context_store,
        audit_writer=audit_writer,
        source_adapters=[
            CardSystemAdapter(),
            CoreBankingAdapter(),
            CRMAdapter(),
            BehavioralSignalsAdapter(),
        ],
    )
    session_id = f"sess_C002_test_{uuid4().hex[:6]}"

    result = await service.assemble("C002", session_id, "payment_risk_intervention")
    stored = await context_store.get(f"session:{session_id}:customer_profile")

    assert result.partial_context is True
    assert result.sources_degraded == ["crm"]
    assert result.assembly_ms < 200
    assert stored is not None
    profile = CustomerProfile.model_validate_json(stored)
    assert profile.card.missed_pmts == 2
    assert profile.crm is None
    assert audit_writer.records[-1].payload["profile_hash"].startswith("sha256:")


@pytest.mark.asyncio
async def test_assembly_overlays_ml_scores_when_scorer_succeeds() -> None:
    """Layer 1 should replace fixture risk/churn scores with trained model scores."""
    context_store = MemoryContextStore()
    audit_writer = MemoryAuditWriter()
    service = ContextAssemblyService(
        context_store=context_store,
        audit_writer=audit_writer,
        ml_scoring_service=Layer1MLScorerStub(
            ModelScore(
                risk_score=0.44,
                churn_probability=0.22,
                model_versions={
                    "risk_score": "payment_risk_model:v1",
                    "churn_probability": "churn_propensity_model:v1",
                },
                scored_at=datetime.now(UTC),
            )
        ),
    )
    session_id = f"sess_C002_ml_{uuid4().hex[:6]}"

    result = await service.assemble("C002", session_id, "payment_risk_intervention")
    stored = await context_store.get(f"session:{session_id}:customer_profile")

    assert result.status == "DEGRADED"
    assert stored is not None
    profile = CustomerProfile.model_validate_json(stored)
    assert profile.signals.risk_score == 0.44
    assert profile.signals.churn_probability == 0.22
    assert profile.signals.clv_estimate == Decimal("1240")
    assert "ml_scoring" in profile.sources_available
    assert profile.signals.model_versions["risk_score"] == "payment_risk_model:v1"
    assert audit_writer.records[-1].payload["model_versions_used"]["risk_score"] == (
        "payment_risk_model:v1"
    )


@pytest.mark.asyncio
async def test_assembly_falls_back_to_feature_signals_when_ml_scoring_fails() -> None:
    """Layer 1 should preserve existing feature-store signals if ML scoring fails."""
    context_store = MemoryContextStore()
    service = ContextAssemblyService(
        context_store=context_store,
        ml_scoring_service=Layer1MLScorerStub(fail=True),
    )
    session_id = f"sess_C002_ml_down_{uuid4().hex[:6]}"

    result = await service.assemble("C002", session_id, "payment_risk_intervention")
    stored = await context_store.get(f"session:{session_id}:customer_profile")

    assert result.status == "DEGRADED"
    assert "ml_scoring" in result.sources_degraded
    assert stored is not None
    profile = CustomerProfile.model_validate_json(stored)
    assert profile.signals.risk_score == 0.71
    assert profile.signals.churn_probability == 0.58
    assert "ml_scoring" in profile.sources_degraded


@pytest.mark.asyncio
async def test_assembly_includes_long_term_memory_when_store_returns_memories() -> None:
    """Layer 1 should place retrieved memories into the persisted CustomerProfile."""
    context_store = MemoryContextStore()
    audit_writer = MemoryAuditWriter()
    memory = CustomerMemory(
        memory_id="mem_test_layer1",
        customer_id="C002",
        memory_type=MemoryType.OUTCOME,
        content="Scenario payment_risk_intervention: action ACT-001, outcome ENROLLED",
        session_id="sess_previous",
        trace_id="trace_previous",
        scenario="payment_risk_intervention",
        outcome_signal="ENROLLED",
        created_at=datetime.now(UTC),
    )
    service = ContextAssemblyService(
        context_store=context_store,
        audit_writer=audit_writer,
        memory_store=Layer1MemoryStoreStub(memories=[memory]),
    )
    session_id = f"sess_C002_memory_{uuid4().hex[:6]}"

    result = await service.assemble("C002", session_id, "payment_risk_intervention")
    stored = await context_store.get(f"session:{session_id}:customer_profile")

    assert result.status == "DEGRADED"
    assert stored is not None
    profile = CustomerProfile.model_validate_json(stored)
    assert profile.long_term_memory == [memory]
    assert "memory" in profile.sources_available
    memory_audits = [
        record for record in audit_writer.records if record.event_type == "MEMORY_RETRIEVED"
    ]
    assert memory_audits[-1].payload["memory_count"] == 1
    assert memory_audits[-1].payload["degraded"] is False


@pytest.mark.asyncio
async def test_assembly_degrades_when_memory_store_fails() -> None:
    """Memory retrieval failure should not fail context assembly."""
    context_store = MemoryContextStore()
    audit_writer = MemoryAuditWriter()
    service = ContextAssemblyService(
        context_store=context_store,
        audit_writer=audit_writer,
        memory_store=Layer1MemoryStoreStub(fail=True),
    )
    session_id = f"sess_C002_memory_down_{uuid4().hex[:6]}"

    result = await service.assemble("C002", session_id, "payment_risk_intervention")
    stored = await context_store.get(f"session:{session_id}:customer_profile")

    assert result.status == "DEGRADED"
    assert "memory" in result.sources_degraded
    assert stored is not None
    profile = CustomerProfile.model_validate_json(stored)
    assert profile.long_term_memory == []
    assert "memory" in profile.sources_degraded
    memory_audits = [
        record for record in audit_writer.records if record.event_type == "MEMORY_RETRIEVED"
    ]
    assert memory_audits[-1].payload["degraded"] is True
    assert memory_audits[-1].payload["reason"] == "qdrant unavailable"


@pytest.mark.asyncio
async def test_assembly_succeeds_when_all_sources_are_down() -> None:
    """Source failures should produce a degraded profile rather than a failed pipeline."""
    context_store = MemoryContextStore()
    service = ContextAssemblyService(
        context_store=context_store,
        source_adapters=[
            DownAdapter("card"),
            DownAdapter("banking"),
            DownAdapter("crm"),
            DownAdapter("behavioral"),
        ],
    )
    session_id = f"sess_C002_down_{uuid4().hex[:6]}"

    result = await service.assemble("C002", session_id, "payment_risk_intervention")
    stored = await context_store.get(f"session:{session_id}:customer_profile")

    assert result.status == "DEGRADED"
    assert result.partial_context is True
    assert result.sources_degraded == ["card", "banking", "crm", "behavioral"]
    assert stored is not None
