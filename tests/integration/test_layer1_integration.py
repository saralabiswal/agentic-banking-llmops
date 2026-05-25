"""Integration tests for Layer 1 with real Valkey and PostgreSQL services.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.adapters.postgres_audit_writer import PostgresAuditWriter
from platform.adapters.postgres_feature_store import PostgresFeatureStore
from platform.adapters.valkey_context_store import ValkeyContextStore
from platform.core.config import settings
from platform.core.schemas import CustomerProfile
from platform.layer1_context.service import ContextAssemblyService
from uuid import uuid4

import psycopg
import pytest

POSTGRES_DSN = "postgresql://platform:platform@localhost:5432/platform"


async def _prepare_postgres() -> None:
    """Create PostgreSQL tables used by Layer 1 integration tests."""
    async with await psycopg.AsyncConnection.connect(POSTGRES_DSN) as conn, conn.cursor() as cur:
        await cur.execute(
            """
            CREATE TABLE IF NOT EXISTS feature_store (
                customer_id TEXT NOT NULL,
                feature_name TEXT NOT NULL,
                value JSONB NOT NULL,
                computed_at TIMESTAMPTZ NOT NULL,
                model_version TEXT NOT NULL,
                PRIMARY KEY (customer_id, feature_name)
            )
            """
        )
        await cur.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                audit_id TEXT PRIMARY KEY,
                trace_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                customer_id TEXT,
                payload JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL
            )
            """
        )


@pytest.mark.asyncio
async def test_layer1_integration_writes_profile_to_valkey_and_audit_to_postgres() -> None:
    """Layer 1 should assemble C002, persist context, and write an audit record."""
    await _prepare_postgres()
    context_store = ValkeyContextStore(settings.VALKEY_URL)
    audit_writer = PostgresAuditWriter(settings.POSTGRES_URL)
    feature_store = PostgresFeatureStore(settings.POSTGRES_URL)
    service = ContextAssemblyService(
        context_store=context_store,
        audit_writer=audit_writer,
        feature_store=feature_store,
    )
    session_id = f"sess_C002_integration_{uuid4().hex[:6]}"
    key = f"session:{session_id}:customer_profile"
    await context_store.delete(key)

    result = await service.assemble("C002", session_id, "payment_risk_intervention")
    stored = await context_store.get(key)
    await context_store.close()

    assert result.partial_context is True
    assert result.sources_degraded == ["crm"]
    assert result.assembly_ms < 350
    assert stored is not None
    profile = CustomerProfile.model_validate_json(stored)
    assert profile.customer_id == "C002"
    assert profile.partial_context is True
