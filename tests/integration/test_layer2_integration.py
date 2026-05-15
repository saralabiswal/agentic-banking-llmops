"""Integration tests for Layer 2 vector search.

Author: Sarala Biswal
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from platform.adapters.qdrant_vector_store import QdrantVectorStore
from platform.core.schemas import (
    BankingProfile,
    BehavioralProfile,
    CardProfile,
    Channel,
    CustomerProfile,
    ModelSignals,
    Segment,
)
from platform.layer2_vector.kb_loader import KnowledgeBaseLoader
from platform.layer2_vector.service import VectorSearchService
from uuid import uuid4

import httpx
from testcontainers.core.container import DockerContainer


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


async def test_layer2_qdrant_testcontainer_loads_kb_and_retrieves_c002_top_policy():
    _configure_docker_host_for_colima()
    collection = f"kb_test_{uuid4().hex}"
    with DockerContainer("qdrant/qdrant:latest").with_exposed_ports(6333) as container:
        url = f"http://{container.get_container_host_ip()}:{container.get_exposed_port(6333)}"
        await _wait_for_qdrant(url)
        vector_store = QdrantVectorStore(url=url, collection=collection)
        loader = KnowledgeBaseLoader(vector_store=vector_store)

        index = await loader.load_and_index()
        await _wait_for_count(url, collection, len(index.chunks))

        context_store = MemoryContextStore()
        session_id = "sess_C002_layer2_integration"
        await context_store.set(
            f"session:{session_id}:customer_profile",
            _c002_profile().model_dump_json(),
            ttl=300,
        )
        result = await VectorSearchService(
            context_store=context_store,
            audit_writer=None,
            kb_loader=loader,
        ).retrieve(session_id, "payment_risk_intervention")

    assert len(index.source_files) == 5
    assert result.chunks[0].document_id == "KB-HARD-001"
    assert result.kb_version


async def _wait_for_qdrant(url):
    async with httpx.AsyncClient(timeout=2.0) as client:
        for _ in range(60):
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                await asyncio.sleep(0.5)
    raise AssertionError(f"Qdrant did not become ready at {url}")


async def _wait_for_count(url, collection, expected):
    async with httpx.AsyncClient(timeout=5.0) as client:
        for _ in range(30):
            response = await client.post(
                f"{url}/collections/{collection}/points/count",
                json={"exact": True},
            )
            if response.status_code == 200 and response.json()["result"]["count"] == expected:
                return
            await asyncio.sleep(0.2)
    raise AssertionError(f"Qdrant collection {collection} did not reach {expected} points")


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


def _configure_docker_host_for_colima():
    os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")
    if "DOCKER_HOST" in os.environ:
        return
    colima_socket = Path.home() / ".colima" / "default" / "docker.sock"
    if colima_socket.exists():
        os.environ["DOCKER_HOST"] = f"unix://{colima_socket}"
