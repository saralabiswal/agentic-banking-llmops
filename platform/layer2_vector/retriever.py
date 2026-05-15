"""Hybrid ANN and BM25 retrieval with reciprocal rank fusion.

Author: Sarala Biswal
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Mapping
from dataclasses import dataclass
from platform.core.config import settings
from platform.core.exceptions import SchemaValidationError
from platform.core.schemas import PolicyChunk
from platform.layer2_vector.embedder import SparseEmbedder


@dataclass(frozen=True)
class _IndexedChunk:
    chunk: PolicyChunk
    dense_vector: list[float]
    corpus_index: int


class HybridRetriever:
    """Retrieves policy chunks by merging dense vector rank and BM25 rank."""

    def __init__(
        self,
        sparse_embedder: SparseEmbedder,
        alpha: float = settings.HYBRID_ALPHA,
    ) -> None:
        """Create an empty hybrid retriever."""
        self._sparse_embedder = sparse_embedder
        self._alpha = alpha
        self._indexed_chunks: list[_IndexedChunk] = []

    def index(self, chunks: list[PolicyChunk], dense_vectors: list[list[float]]) -> None:
        """Load chunks and their dense vectors into the retriever."""
        if len(chunks) != len(dense_vectors):
            message = "Chunk and dense vector counts must match"
            raise SchemaValidationError(message)
        self._indexed_chunks = [
            _IndexedChunk(chunk=chunk, dense_vector=dense_vectors[index], corpus_index=index)
            for index, chunk in enumerate(chunks)
        ]

    async def search(
        self,
        dense_q: list[float],
        sparse_q: dict[int, float],
        filters: Mapping[str, str],
        top_k: int = 20,
    ) -> list[PolicyChunk]:
        """Run dense and sparse searches in parallel and merge ranks with RRF."""
        vector_task = asyncio.to_thread(self._vector_rank, dense_q, filters, top_k)
        bm25_task = asyncio.to_thread(self._bm25_rank, sparse_q, filters, top_k)
        vector_ranked, bm25_ranked = await asyncio.gather(vector_task, bm25_task)
        return self._rrf_merge([vector_ranked, bm25_ranked], top_k=top_k)

    async def search_vector_only(
        self,
        dense_q: list[float],
        filters: Mapping[str, str],
        top_k: int = 20,
    ) -> list[PolicyChunk]:
        """Run only dense vector retrieval for benchmark comparisons."""
        ranked = await asyncio.to_thread(self._vector_rank, dense_q, filters, top_k)
        return [
            item.chunk.model_copy(update={"rerank_score": max(score, 0.0)})
            for item, score in ranked[:top_k]
        ]

    def _vector_rank(
        self,
        dense_q: list[float],
        filters: Mapping[str, str],
        top_k: int,
    ) -> list[tuple[_IndexedChunk, float]]:
        filtered = self._filtered_chunks(filters)
        ranked = [
            (item, _cosine_similarity(dense_q, item.dense_vector))
            for item in filtered
            if item.chunk.chunk_type == "PARAGRAPH"
        ]
        ranked.sort(key=lambda result: result[1], reverse=True)
        return ranked[:top_k]

    def _bm25_rank(
        self,
        sparse_q: dict[int, float],
        filters: Mapping[str, str],
        top_k: int,
    ) -> list[tuple[_IndexedChunk, float]]:
        scores = self._sparse_embedder.scores(sparse_q)
        filtered = self._filtered_chunks(filters)
        ranked = [
            (item, scores[item.corpus_index])
            for item in filtered
            if item.chunk.chunk_type == "PARAGRAPH"
            and item.corpus_index < len(scores)
            and scores[item.corpus_index] > 0.0
        ]
        ranked.sort(key=lambda result: result[1], reverse=True)
        return ranked[:top_k]

    def _filtered_chunks(self, filters: Mapping[str, str]) -> list[_IndexedChunk]:
        return [
            item
            for item in self._indexed_chunks
            if all(_metadata_value(item.chunk, key) == value for key, value in filters.items())
        ]

    def _rrf_merge(
        self,
        ranked_lists: list[list[tuple[_IndexedChunk, float]]],
        top_k: int,
    ) -> list[PolicyChunk]:
        scores: dict[str, float] = {}
        chunks: dict[str, PolicyChunk] = {}
        for ranked in ranked_lists:
            for rank, (item, _score) in enumerate(ranked, start=1):
                scores[item.chunk.chunk_id] = scores.get(item.chunk.chunk_id, 0.0) + (
                    1.0 / (60.0 + float(rank))
                )
                chunks[item.chunk.chunk_id] = item.chunk

        sorted_ids = sorted(scores, key=lambda chunk_id: scores[chunk_id], reverse=True)
        return [
            chunks[chunk_id].model_copy(update={"rerank_score": scores[chunk_id]})
            for chunk_id in sorted_ids[:top_k]
        ]


def _metadata_value(chunk: PolicyChunk, key: str) -> str | None:
    match key:
        case "product_line":
            return chunk.product_line
        case "jurisdiction":
            return chunk.jurisdiction
        case "document_type":
            return chunk.document_type
        case "document_id":
            return chunk.document_id
        case _:
            return None


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    length = min(len(left), len(right))
    if length == 0:
        return 0.0
    numerator = sum(left[index] * right[index] for index in range(length))
    left_norm = math.sqrt(sum(value * value for value in left[:length]))
    right_norm = math.sqrt(sum(value * value for value in right[:length]))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return numerator / (left_norm * right_norm)
