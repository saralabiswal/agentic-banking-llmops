"""Qdrant-backed long-term memory store.

Author: Sarala Biswal
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections.abc import Callable
from platform.memory.schemas import CustomerMemory, MemoryType
from typing import Any

import httpx
import structlog
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

logger = structlog.get_logger()


class QdrantMemoryStore:
    """Stores and retrieves cross-session customer memories in Qdrant."""

    def __init__(
        self,
        url: str,
        collection: str = "customer_memory",
        embedding_model: str = "all-MiniLM-L6-v2",
        vector_size: int = 384,
        embedder: Callable[[str], list[float]] | None = None,
    ) -> None:
        """Create a Qdrant-backed memory store with an optional test embedder."""
        self._url = url.rstrip("/")
        self._collection = collection
        self._embedding_model = embedding_model
        self._vector_size = vector_size
        self._embedder = embedder
        self._model: Any | None = None
        self._collection_ready = False

    async def store(self, memory: CustomerMemory) -> str:
        """Embed and store a customer memory, returning its memory ID."""
        started = time.perf_counter()
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("memory.store") as span:
            span.set_attribute("trace_id", memory.trace_id)
            span.set_attribute("customer_id", memory.customer_id)
            span.set_attribute("scenario", memory.scenario)
            span.set_attribute("memory_type", memory.memory_type.value)
            try:
                await self._ensure_collection()
                embedding = await self._embed(memory.content)
                # Store the vector in Qdrant while keeping the payload schema Pydantic-friendly.
                enriched = memory.model_copy(update={"embedding": embedding})
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.put(
                        f"{self._url}/collections/{self._collection}/points",
                        json={
                            "points": [
                                {
                                    "id": memory.memory_id,
                                    "vector": embedding,
                                    "payload": self._payload(enriched),
                                }
                            ]
                        },
                    )
                    response.raise_for_status()
                span.set_attribute("latency_ms", int((time.perf_counter() - started) * 1000))
                logger.info(
                    "memory.stored",
                    trace_id=memory.trace_id,
                    customer_id=memory.customer_id,
                    scenario=memory.scenario,
                    memory_id=memory.memory_id,
                    memory_type=memory.memory_type.value,
                )
                return memory.memory_id
            except Exception as exc:
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                logger.warning(
                    "memory.store_failed",
                    trace_id=memory.trace_id,
                    customer_id=memory.customer_id,
                    scenario=memory.scenario,
                    reason=str(exc),
                )
                raise

    async def retrieve(
        self,
        customer_id: str,
        scenario: str,
        top_k: int = 5,
        memory_types: list[MemoryType] | None = None,
    ) -> list[CustomerMemory]:
        """Retrieve semantically relevant memories for a customer and scenario."""
        started = time.perf_counter()
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("memory.retrieve") as span:
            span.set_attribute("customer_id", customer_id)
            span.set_attribute("scenario", scenario)
            span.set_attribute("top_k", top_k)
            try:
                await self._ensure_collection()
                query_vector = await self._embed(f"{customer_id} {scenario}")
                # Retrieval is scoped by customer/scenario before semantic ranking is applied.
                body: dict[str, Any] = {
                    "vector": query_vector,
                    "limit": top_k,
                    "with_payload": True,
                    "filter": self._filter(customer_id, scenario, memory_types),
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        f"{self._url}/collections/{self._collection}/points/search",
                        json=body,
                    )
                    response.raise_for_status()
                    payload = response.json()
                memories = [
                    CustomerMemory.model_validate(item["payload"])
                    for item in payload.get("result", [])
                    if item.get("payload") is not None
                ]
                span.set_attribute("latency_ms", int((time.perf_counter() - started) * 1000))
                span.set_attribute("count", len(memories))
                logger.info(
                    "memory.retrieved",
                    customer_id=customer_id,
                    scenario=scenario,
                    count=len(memories),
                )
                return memories
            except Exception as exc:
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                logger.warning(
                    "memory.retrieve_failed",
                    customer_id=customer_id,
                    scenario=scenario,
                    reason=str(exc),
                )
                raise

    async def get_recent(self, customer_id: str, limit: int = 10) -> list[CustomerMemory]:
        """Return the most recent memories for a customer."""
        await self._ensure_collection()
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self._url}/collections/{self._collection}/points/scroll",
                json={
                    "limit": limit,
                    "with_payload": True,
                    "filter": {"must": [{"key": "customer_id", "match": {"value": customer_id}}]},
                },
            )
            response.raise_for_status()
            payload = response.json()
        points = payload.get("result", {}).get("points", [])
        memories = [
            CustomerMemory.model_validate(item["payload"])
            for item in points
            if item.get("payload") is not None
        ]
        return sorted(memories, key=lambda memory: memory.created_at, reverse=True)[:limit]

    async def _ensure_collection(self) -> None:
        """Create the customer memory collection and payload index if needed."""
        if self._collection_ready:
            return
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Qdrant PUT is idempotent here, so startup can safely call this multiple times.
            response = await client.put(
                f"{self._url}/collections/{self._collection}",
                json={"vectors": {"size": self._vector_size, "distance": "Cosine"}},
            )
            response.raise_for_status()
            index_response = await client.put(
                f"{self._url}/collections/{self._collection}/index",
                json={"field_name": "customer_id", "field_schema": "keyword"},
            )
            if index_response.status_code not in {200, 201, 409}:
                index_response.raise_for_status()
        self._collection_ready = True

    async def _embed(self, text: str) -> list[float]:
        """Embed text with sentence-transformers, falling back to a deterministic vector."""
        if self._embedder is not None:
            return self._normalized_vector(self._embedder(text))
        try:
            return await asyncio.to_thread(self._sentence_transformer_embedding, text)
        except Exception as exc:
            logger.warning(
                "memory.embedding_fallback",
                embedding_model=self._embedding_model,
                reason=str(exc),
            )
            return self._hash_embedding(text)

    def _sentence_transformer_embedding(self, text: str) -> list[float]:
        """Load the configured sentence-transformers model lazily and encode text."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._embedding_model)
        vector = self._model.encode(text, normalize_embeddings=True)
        return self._normalized_vector([float(value) for value in vector])

    def _hash_embedding(self, text: str) -> list[float]:
        """Return a deterministic vector for offline tests and degraded local runs."""
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = [
            ((digest[index % len(digest)] / 255.0) * 2.0) - 1.0
            for index in range(self._vector_size)
        ]
        return values

    def _normalized_vector(self, vector: list[float]) -> list[float]:
        """Pad or trim vectors to the configured Qdrant vector size."""
        return (vector + [0.0] * self._vector_size)[: self._vector_size]

    def _payload(self, memory: CustomerMemory) -> dict[str, Any]:
        """Build the Qdrant payload without duplicating the vector."""
        payload = memory.model_dump(mode="json", exclude={"embedding"})
        payload["embedding"] = None
        return payload

    def _filter(
        self,
        customer_id: str,
        scenario: str,
        memory_types: list[MemoryType] | None,
    ) -> dict[str, Any]:
        """Build a Qdrant payload filter for customer, scenario, and optional types."""
        # Customer and scenario are mandatory isolation boundaries for banking memory.
        must: list[dict[str, Any]] = [
            {"key": "customer_id", "match": {"value": customer_id}},
            {"key": "scenario", "match": {"value": scenario}},
        ]
        if memory_types:
            must.append(
                {
                    "should": [
                        {"key": "memory_type", "match": {"value": memory_type.value}}
                        for memory_type in memory_types
                    ]
                }
            )
        return {"must": must}
