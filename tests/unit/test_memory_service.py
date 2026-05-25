"""Unit tests for long-term memory service behavior.

Author: Sarala Biswal
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from platform.memory.schemas import CustomerMemory, MemoryType
from platform.memory.service import QdrantMemoryStore

import pytest
import respx
from httpx import HTTPStatusError, Response


@pytest.mark.asyncio
async def test_qdrant_memory_store_store_retrieve_and_recent() -> None:
    """Memory service should shape Qdrant requests and rebuild memory payloads."""
    memory = _memory("mem_1", created_at=datetime(2026, 5, 24, 12, 0, tzinfo=UTC))
    older = _memory("mem_0", created_at=datetime(2026, 5, 23, 12, 0, tzinfo=UTC))
    store = QdrantMemoryStore(
        url="http://qdrant.test",
        collection="customer_memory_test",
        vector_size=3,
        embedder=lambda text: [0.1, 0.2] if "C002" in text else [0.3, 0.4, 0.5, 0.6],
    )

    with respx.mock(assert_all_called=False) as router:
        collection_route = router.put(
            "http://qdrant.test/collections/customer_memory_test"
        ).mock(return_value=Response(200, json={"result": True}))
        index_route = router.put(
            "http://qdrant.test/collections/customer_memory_test/index"
        ).mock(return_value=Response(409, json={"status": "already_exists"}))
        points_route = router.put(
            "http://qdrant.test/collections/customer_memory_test/points"
        ).mock(return_value=Response(200, json={"result": True}))
        search_route = router.post(
            "http://qdrant.test/collections/customer_memory_test/points/search"
        ).mock(
            return_value=Response(
                200,
                json={"result": [{"payload": memory.model_dump(mode="json")}]},
            )
        )
        scroll_route = router.post(
            "http://qdrant.test/collections/customer_memory_test/points/scroll"
        ).mock(
            return_value=Response(
                200,
                json={
                    "result": {
                        "points": [
                            {"payload": older.model_dump(mode="json")},
                            {"payload": memory.model_dump(mode="json")},
                        ]
                    }
                },
            )
        )

        assert await store.store(memory) == "mem_1"
        retrieved = await store.retrieve(
            customer_id="C002",
            scenario="payment_risk_intervention",
            top_k=3,
            memory_types=[MemoryType.OUTCOME],
        )
        recent = await store.get_recent("C002", limit=2)

    assert collection_route.called
    assert index_route.called
    assert points_route.calls.last.request.content
    assert search_route.calls.last.request.content
    assert retrieved == [memory]
    assert [item.memory_id for item in recent] == ["mem_1", "mem_0"]
    assert scroll_route.called


@pytest.mark.asyncio
async def test_qdrant_memory_store_embed_fallback_and_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Embedding fallback should be deterministic and store failures should surface."""
    store = QdrantMemoryStore(
        url="http://qdrant.test",
        collection="customer_memory_test",
        vector_size=4,
    )
    monkeypatch.setattr(
        store,
        "_sentence_transformer_embedding",
        lambda text: (_ for _ in ()).throw(RuntimeError("embed boom")),
    )

    vector = await store._embed("same text")  # noqa: SLF001
    assert vector == await store._embed("same text")  # noqa: SLF001
    assert len(vector) == 4

    with respx.mock(assert_all_called=False) as router:
        router.put("http://qdrant.test/collections/customer_memory_test").mock(
            return_value=Response(500, json={"error": "down"})
        )
        with pytest.raises(HTTPStatusError):
            await store.retrieve("C002", "payment_risk_intervention")


def _memory(memory_id: str, created_at: datetime) -> CustomerMemory:
    return CustomerMemory(
        memory_id=memory_id,
        customer_id="C002",
        memory_type=MemoryType.OUTCOME,
        content="Scenario payment_risk_intervention: action ACT-001, outcome ENROLLED",
        session_id="sess_memory_test",
        trace_id="trace_memory_test",
        scenario="payment_risk_intervention",
        outcome_signal="ENROLLED",
        created_at=created_at,
        metadata={"action_id": "ACT-001"},
    )


def test_memory_payload_filter_and_vector_helpers() -> None:
    """Helper methods should produce Qdrant-compatible payloads and filters."""
    store = QdrantMemoryStore(
        url="http://qdrant.test/",
        collection="customer_memory_test",
        vector_size=3,
    )
    memory = _memory("mem_helper", datetime.now(UTC) - timedelta(days=1))

    payload = store._payload(memory.model_copy(update={"embedding": [1.0, 2.0, 3.0]}))  # noqa: SLF001
    query_filter = store._filter("C002", "payment_risk_intervention", [MemoryType.OUTCOME])  # noqa: SLF001

    assert payload["embedding"] is None
    assert store._normalized_vector([1.0]) == [1.0, 0.0, 0.0]  # noqa: SLF001
    assert query_filter["must"][0]["match"]["value"] == "C002"
    assert query_filter["must"][2]["should"][0]["match"]["value"] == "outcome"
