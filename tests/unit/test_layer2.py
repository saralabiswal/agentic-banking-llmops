"""Unit tests for Layer 2 vector search.

Author: Sarala Biswal
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from platform.core.schemas import (
    BankingProfile,
    BehavioralProfile,
    CardProfile,
    Channel,
    CustomerProfile,
    ModelSignals,
    Segment,
)
from platform.layer2_vector.chunker import HierarchicalChunker
from platform.layer2_vector.kb_loader import KnowledgeBaseLoader
from platform.layer2_vector.query_builder import build_retrieval_query
from platform.layer2_vector.reranker import CrossEncoderReranker
from platform.layer2_vector.service import VectorSearchService

import yaml


class MemoryContextStore:
    """Test context store."""

    def __init__(self):
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, ttl):
        self.values[key] = value

    async def delete(self, key):
        self.values.pop(key, None)


class MemoryAuditWriter:
    """Test audit writer."""

    def __init__(self):
        self.records = []

    async def write(self, record):
        self.records.append(record)


def test_hierarchical_chunker_creates_document_section_paragraph_chunks():
    path = Path("knowledge_base/hardship_eligibility.yaml")
    document = yaml.safe_load(path.read_text(encoding="utf-8"))

    chunks = HierarchicalChunker().chunk(document)

    chunk_types = {chunk.chunk_type for chunk in chunks}
    paragraph_chunks = [chunk for chunk in chunks if chunk.chunk_type == "PARAGRAPH"]
    assert chunk_types == {"DOCUMENT", "SECTION", "PARAGRAPH"}
    assert len(paragraph_chunks) == 7
    assert all(chunk.parent_chunk_id for chunk in paragraph_chunks)
    assert paragraph_chunks[0].chunk_id == "KB-HARD-001-2.3-PARAGRAPH-1"
    assert paragraph_chunks[0].document_id == "KB-HARD-001"


def test_payment_risk_query_uses_canonical_customer_profile_fields():
    profile = _c002_profile()

    query = build_retrieval_query(profile, "payment_risk_intervention")

    assert query == (
        "Customer with critical payment risk. 2 missed payments, "
        "checking balance $312.40, no direct deposit. Utilization 76%. "
        "Payment propensity 31%. Hardship program eligibility, intervention options, "
        "payment deferral, contact frequency."
    )


async def test_kb_loader_loads_all_five_yaml_files_on_startup():
    index = await KnowledgeBaseLoader().load_and_index()

    assert len(index.source_files) == 5
    assert {path.name for path in index.source_files} == {
        "contact_frequency_guidelines.yaml",
        "credit_limit_policy.yaml",
        "dispute_resolution_reg.yaml",
        "hardship_eligibility.yaml",
        "payment_intervention_playbook.yaml",
    }
    assert {chunk.document_id for chunk in index.chunks} == {
        "KB-CL-004",
        "KB-COMP-003",
        "KB-HARD-001",
        "KB-PAY-007",
        "KB-REG-E-1005",
    }
    assert index.sparse_embedder.token_count() > 0


async def test_c002_payment_risk_query_returns_hardship_top_one():
    context_store = MemoryContextStore()
    audit_writer = MemoryAuditWriter()
    session_id = "sess_C002_layer2_unit"
    await context_store.set(
        f"session:{session_id}:customer_profile",
        _c002_profile().model_dump_json(),
        ttl=300,
    )
    service = VectorSearchService(
        context_store=context_store,
        audit_writer=audit_writer,
        kb_loader=KnowledgeBaseLoader(),
    )

    result = await service.retrieve(session_id, "payment_risk_intervention")

    assert result.chunks[0].document_id == "KB-HARD-001"
    assert result.chunks[0].rerank_score > result.chunks[1].rerank_score
    assert audit_writer.records[-1].event_type == "VECTOR_RETRIEVAL"
    assert audit_writer.records[-1].payload["chunks_retrieved"][0]["document_id"] == "KB-HARD-001"


async def test_hybrid_search_outperforms_pure_vector_on_exact_regulatory_citation():
    index = await KnowledgeBaseLoader().load_and_index()
    query = "section 1005.11"
    dense_query = index.dense_embedder.embed_one(query)
    sparse_query = index.sparse_embedder.embed_one(query)
    filters = {"product_line": "credit_card", "jurisdiction": "US"}

    vector_only = await index.retriever.search_vector_only(dense_query, filters, top_k=20)
    hybrid = await index.retriever.search(dense_query, sparse_query, filters, top_k=20)
    reranked = CrossEncoderReranker().rerank(query, hybrid, top_k=3)

    vector_rank = _rank_document(vector_only, "KB-REG-E-1005")
    hybrid_rank = _rank_document(hybrid, "KB-REG-E-1005")
    assert hybrid[0].document_id == "KB-REG-E-1005"
    assert reranked[0].document_id == "KB-REG-E-1005"
    assert hybrid_rank < vector_rank


def _rank_document(chunks, document_id):
    for index, chunk in enumerate(chunks, start=1):
        if chunk.document_id == document_id:
            return index
    return 999


def _c002_profile():
    return CustomerProfile(
        customer_id="C002",
        name="Marcus Webb",
        segment=Segment.STANDARD,
        card=CardProfile(
            balance=Decimal("7600.00"),
            credit_limit=Decimal("10000.00"),
            utilization=0.76,
            missed_pmts=2,
            past_due=Decimal("410.00"),
            days_since_last_payment=48,
        ),
        banking=BankingProfile(
            checking_balance=Decimal("312.40"),
            savings_balance=Decimal("25.00"),
            last_deposit_at=None,
            overdrafts_30d=2,
            direct_deposit=False,
        ),
        crm=None,
        behavioral=BehavioralProfile(
            app_logins_30d=3,
            preferred_channel=Channel.SMS,
            sms_ok=True,
            push_enabled=False,
            email_ok=True,
        ),
        signals=ModelSignals(
            risk_score=0.71,
            churn_probability=0.27,
            clv_estimate=Decimal("2400.00"),
            last_intervention=None,
            intervention_7d=1,
            payment_propensity=0.31,
            model_versions={"payment_risk": "v3.2.1"},
        ),
        assembled_at=datetime.now(UTC),
        assembly_latency_ms=167,
        sources_available=["card", "banking", "behavioral", "feature_store"],
        sources_degraded=["crm"],
        partial_context=True,
    )
