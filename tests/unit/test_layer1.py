"""Unit tests for Layer 1 context assembly.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.core.exceptions import DuplicateSessionError, SourceUnavailableError
from platform.core.schemas import AuditRecord, CustomerProfile
from platform.layer1_context.adapters.banking_adapter import CoreBankingAdapter
from platform.layer1_context.adapters.behavioral_adapter import BehavioralSignalsAdapter
from platform.layer1_context.adapters.card_adapter import CardSystemAdapter
from platform.layer1_context.adapters.crm_adapter import CRMAdapter
from platform.layer1_context.service import ContextAssemblyService
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
