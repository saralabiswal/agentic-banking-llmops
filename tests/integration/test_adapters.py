"""Integration tests for infrastructure adapters against real local services.

Author: Sarala Biswal
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from platform.adapters.mock_llm_client import MockLLMClient
from platform.adapters.postgres_audit_writer import PostgresAuditWriter
from platform.adapters.postgres_feature_store import PostgresFeatureStore
from platform.adapters.postgres_queue_store import PostgresQueueStore
from platform.adapters.qdrant_vector_store import QdrantVectorStore
from platform.adapters.valkey_context_store import ValkeyContextStore
from platform.core.config import settings
from platform.core.exceptions import DuplicateSessionError
from platform.core.schemas import (
    ApprovalQueueItem,
    AuditRecord,
    ModelSignals,
    PolicyChunk,
    ProposedAction,
    RiskAssessment,
)
from uuid import uuid4

import httpx
import psycopg
import pytest

POSTGRES_DSN = "postgresql://platform:platform@localhost:5432/platform"


async def _prepare_postgres() -> None:
    """Create the tables used by adapter integration tests."""
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
        await cur.execute(
            """
            CREATE TABLE IF NOT EXISTS approval_queue (
                queue_id TEXT PRIMARY KEY,
                trace_id TEXT NOT NULL,
                customer_id TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                proposed_action JSONB NOT NULL,
                flags JSONB NOT NULL,
                sla_deadline TIMESTAMPTZ NOT NULL,
                created_at TIMESTAMPTZ NOT NULL,
                decided_at TIMESTAMPTZ,
                decision_reason TEXT
            )
            """
        )


@pytest.mark.asyncio
async def test_valkey_ttl_and_nx_semantics() -> None:
    """Valkey adapter should expire keys and reject duplicate session writes."""
    store = ValkeyContextStore(settings.VALKEY_URL)
    key = "test:adapter:ttl"
    await store.delete(key)
    await store.set(key, "first", ttl=1)

    assert await store.get(key) == "first"
    with pytest.raises(DuplicateSessionError):
        await store.set(key, "second", ttl=1)

    await asyncio.sleep(1.2)
    assert await store.get(key) is None
    await store.close()


@pytest.mark.asyncio
async def test_postgres_feature_audit_and_queue_crud() -> None:
    """PostgreSQL adapters should persist feature, audit, and queue data."""
    await _prepare_postgres()
    now = datetime.now(UTC)
    suffix = uuid4().hex[:8]
    feature_store = PostgresFeatureStore(settings.POSTGRES_URL)
    audit_writer = PostgresAuditWriter(settings.POSTGRES_URL)
    queue_store = PostgresQueueStore(settings.POSTGRES_URL)

    signals = ModelSignals(
        risk_score=0.71,
        churn_probability=0.58,
        clv_estimate=Decimal("1240"),
        last_intervention=now,
        intervention_7d=0,
        payment_propensity=0.31,
        model_versions={
            "risk_score": "risk-v4.2.1",
            "churn_probability": "churn-v3.0.8",
            "clv_estimate": "clv-v2.1.4",
            "payment_propensity": "pay-v2.0.3",
        },
    )
    await feature_store.upsert_signals("C002", signals)
    loaded = await feature_store.get_signals("C002")

    assert loaded.risk_score == 0.71
    assert loaded.model_versions["risk_score"] == "risk-v4.2.1"

    record = AuditRecord(
        audit_id=f"aud_test_adapters_{suffix}",
        event_type="CONTEXT_ASSEMBLY",
        trace_id="trace_test_adapters",
        session_id="sess_test_adapters",
        customer_id="C002",
        timestamp=now,
        layer="1",
        payload={"partial_context": True},
    )
    await audit_writer.write(record)
    await audit_writer.write(record)

    action = ProposedAction(
        action_id="ACT-002",
        action_type="CREATE_HARDSHIP_ENROLLMENT_CASE",
        requires_approval=True,
        amount=Decimal("420.00"),
    )
    item = ApprovalQueueItem(
        queue_id=f"appr_test_adapters_{suffix}",
        status="PENDING",
        priority="STANDARD",
        created_at=now,
        sla_deadline=now + timedelta(hours=4),
        escalation_at=now + timedelta(hours=8),
        action=action,
        flag_reasons=["B-002: standard approval"],
        context={"trace_id": "trace_test_adapters", "customer_id": "C002"},
    )
    await queue_store.enqueue(item)
    pending = await queue_store.dequeue_pending("STANDARD", 5)
    assert any(entry.queue_id == item.queue_id for entry in pending)

    await queue_store.update_decision(item.queue_id, "APPROVED", "valid test decision")
    pending_after_decision = await queue_store.dequeue_pending("STANDARD", 5)
    assert all(entry.queue_id != item.queue_id for entry in pending_after_decision)


@pytest.mark.asyncio
async def test_qdrant_upsert_search_and_metadata_filter() -> None:
    """Qdrant adapter should upsert chunks and search with metadata filters."""
    collection = "test_adapters_knowledge_base"
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.delete(f"{settings.QDRANT_URL}/collections/{collection}")

    store = QdrantVectorStore(settings.QDRANT_URL, collection=collection)
    hardship = PolicyChunk(
        chunk_id="KB-HARD-001-v2.3-PARAGRAPH-001",
        document_id="KB-HARD-001",
        document_title="Hardship Program Eligibility Criteria",
        document_type="POLICY",
        doc_version="2.3",
        raw_text="Customers with 2+ missed payments and checking below $500 qualify.",
        rerank_score=0.0,
        product_line="credit_card",
        jurisdiction="US",
    )
    dispute = PolicyChunk(
        chunk_id="KB-DISP-001-v1.0-PARAGRAPH-001",
        document_id="KB-DISP-001",
        document_title="Billing Dispute Rules",
        document_type="REGULATION",
        doc_version="1.0",
        raw_text="Regulation E billing dispute investigation requirements.",
        rerank_score=0.0,
        product_line="deposit_account",
        jurisdiction="US",
    )
    await store.upsert([hardship, dispute])

    results = await store.search(
        dense_vector=store.vector_for_text(hardship.raw_text),
        sparse_vector={},
        filters={"product_line": "credit_card", "jurisdiction": "US"},
        top_k=3,
    )

    assert results[0].document_id == "KB-HARD-001"
    assert all(chunk.product_line == "credit_card" for chunk in results)


@pytest.mark.asyncio
async def test_mock_llm_schema_conformance_for_all_customers_and_scenarios() -> None:
    """Mock LLM should return valid schema data for all customer/scenario combinations."""
    client = MockLLMClient()
    customers = ["C001", "C002", "C003"]
    scenarios = [
        "payment_risk_intervention",
        "billing_dispute_resolution",
        "churn_prevention",
    ]

    for customer_id in customers:
        for scenario in scenarios:
            response = await client.complete(
                system="You are a banking risk agent.",
                user=f"customer_id={customer_id}; scenario={scenario}",
                schema=RiskAssessment,
            )
            assessment = RiskAssessment.model_validate(response)
            if customer_id == "C002" and scenario == "payment_risk_intervention":
                assert assessment.risk_level == "CRITICAL"
                assert assessment.policy_match.hardship_eligible is True
            if customer_id == "C003":
                assert assessment.risk_level == "LOW"
