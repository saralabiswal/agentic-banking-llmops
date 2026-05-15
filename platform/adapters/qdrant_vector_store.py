"""Qdrant-backed vector store adapter.

Author: Sarala Biswal
"""

from __future__ import annotations

import hashlib
import uuid
from platform.core.schemas import PolicyChunk
from typing import Any

import httpx


class QdrantVectorStore:
    """VectorStore implementation backed by Qdrant's HTTP API."""

    def __init__(self, url: str, collection: str = "knowledge_base", vector_size: int = 8) -> None:
        """Create a Qdrant adapter for a collection."""
        self._url = url.rstrip("/")
        self._collection = collection
        self._vector_size = vector_size

    def vector_for_text(self, text: str) -> list[float]:
        """Create a deterministic small vector for local tests and demos."""
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [((digest[index] / 255.0) * 2.0) - 1.0 for index in range(self._vector_size)]

    async def _ensure_collection(self) -> None:
        """Create the collection if it does not already exist."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.put(
                f"{self._url}/collections/{self._collection}",
                json={
                    "vectors": {
                        "size": self._vector_size,
                        "distance": "Cosine",
                    }
                },
            )
            if response.status_code not in {200, 201}:
                response.raise_for_status()

    async def upsert(self, chunks: list[PolicyChunk]) -> None:
        """Store chunks with deterministic vectors and metadata payloads."""
        await self._ensure_collection()
        points = []
        for chunk in chunks:
            payload = chunk.model_dump(mode="json")
            points.append(
                {
                    "id": str(uuid.uuid5(uuid.NAMESPACE_URL, chunk.chunk_id)),
                    "vector": self.vector_for_text(chunk.raw_text),
                    "payload": payload,
                }
            )
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.put(
                f"{self._url}/collections/{self._collection}/points",
                json={"points": points},
            )
            response.raise_for_status()

    async def search(
        self,
        dense_vector: list[float],
        sparse_vector: dict[int, float],
        filters: dict[str, str],
        top_k: int,
    ) -> list[PolicyChunk]:
        """Search chunks using Qdrant vector search plus metadata filters."""
        del sparse_vector
        vector = (dense_vector + [0.0] * self._vector_size)[: self._vector_size]
        must = [
            {"key": key, "match": {"value": value}}
            for key, value in filters.items()
            if key in {"product_line", "jurisdiction", "document_type"}
        ]
        body: dict[str, Any] = {
            "vector": vector,
            "limit": top_k,
            "with_payload": True,
        }
        if must:
            body["filter"] = {"must": must}

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self._url}/collections/{self._collection}/points/search",
                json=body,
            )
            response.raise_for_status()
            payload = response.json()

        chunks: list[PolicyChunk] = []
        for item in payload.get("result", []):
            chunk_payload = dict(item["payload"])
            chunk_payload["rerank_score"] = float(item.get("score", 0.0))
            chunks.append(PolicyChunk.model_validate(chunk_payload))
        return chunks
