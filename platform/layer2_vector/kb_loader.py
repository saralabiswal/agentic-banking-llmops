"""Knowledge-base loading, chunking, embedding, and indexing.

Author: Sarala Biswal
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from platform.core.config import Settings, settings
from platform.core.exceptions import SchemaValidationError
from platform.core.interfaces import VectorStore
from platform.core.schemas import PolicyChunk
from platform.layer2_vector.chunker import HierarchicalChunker
from platform.layer2_vector.embedder import DenseEmbedder, SparseEmbedder
from platform.layer2_vector.retriever import HybridRetriever
from typing import Any, cast

import yaml


@dataclass(frozen=True)
class KnowledgeBaseIndex:
    """In-memory representation of the active knowledge-base index."""

    kb_version: str
    chunks: list[PolicyChunk]
    retriever: HybridRetriever
    dense_embedder: DenseEmbedder
    sparse_embedder: SparseEmbedder
    source_files: list[Path]


class KnowledgeBaseLoader:
    """Loads YAML policy documents and prepares the Layer 2 retrieval index."""

    def __init__(
        self,
        kb_dir: str | Path = settings.KB_DIR,
        vector_store: VectorStore | None = None,
        config: Settings = settings,
        chunker: HierarchicalChunker | None = None,
        dense_embedder: DenseEmbedder | None = None,
        sparse_embedder: SparseEmbedder | None = None,
    ) -> None:
        """Create a knowledge-base loader."""
        self._kb_dir = Path(kb_dir)
        self._vector_store = vector_store
        self._config = config
        self._chunker = chunker or HierarchicalChunker()
        self._dense_embedder = dense_embedder or DenseEmbedder(model_name=config.EMBEDDING_MODEL)
        self._sparse_embedder = sparse_embedder or SparseEmbedder()
        self._index: KnowledgeBaseIndex | None = None

    async def load_and_index(self) -> KnowledgeBaseIndex:
        """Read all KB YAML files, chunk them, embed them, and index them."""
        if self._index is not None:
            return self._index

        documents, source_files = await asyncio.to_thread(self._read_documents)
        chunks = [chunk for document in documents for chunk in self._chunker.chunk(document)]
        if not chunks:
            message = f"No knowledge-base chunks loaded from {self._kb_dir}"
            raise SchemaValidationError(message)

        corpus = [chunk.raw_text for chunk in chunks]
        self._sparse_embedder.fit(corpus)
        dense_vectors = await asyncio.to_thread(self._dense_embedder.embed, corpus)
        retriever = HybridRetriever(
            sparse_embedder=self._sparse_embedder,
            alpha=self._config.HYBRID_ALPHA,
        )
        retriever.index(chunks, dense_vectors)

        if self._vector_store is not None:
            await self._vector_store.upsert(chunks)

        self._index = KnowledgeBaseIndex(
            kb_version=datetime.now(UTC).date().isoformat(),
            chunks=chunks,
            retriever=retriever,
            dense_embedder=self._dense_embedder,
            sparse_embedder=self._sparse_embedder,
            source_files=source_files,
        )
        return self._index

    def clear_cache(self) -> None:
        """Clear the cached in-memory index so the next call reloads YAML files."""
        self._index = None

    def _read_documents(self) -> tuple[list[Mapping[str, Any]], list[Path]]:
        if not self._kb_dir.exists():
            message = f"Knowledge-base directory does not exist: {self._kb_dir}"
            raise SchemaValidationError(message)

        source_files = sorted(self._kb_dir.glob("*.yaml"))
        if not source_files:
            message = f"Knowledge-base directory contains no YAML files: {self._kb_dir}"
            raise SchemaValidationError(message)

        documents: list[Mapping[str, Any]] = []
        for source_file in source_files:
            loaded = yaml.safe_load(source_file.read_text(encoding="utf-8"))
            if not isinstance(loaded, Mapping):
                message = f"Knowledge-base YAML must be a mapping: {source_file}"
                raise SchemaValidationError(message)
            documents.append(cast("Mapping[str, Any]", loaded))
        return documents, source_files
