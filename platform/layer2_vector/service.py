"""Layer 2 vector search service.

Author: Sarala Biswal
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from platform.core.config import Settings, settings
from platform.core.exceptions import SchemaValidationError, SessionExpiredError
from platform.core.interfaces import AuditWriter, ContextStore
from platform.core.schemas import AuditRecord, CustomerProfile, PolicyChunk, RetrievalResult
from platform.layer2_vector.kb_loader import KnowledgeBaseLoader
from platform.layer2_vector.query_builder import build_retrieval_query
from platform.layer2_vector.reranker import CrossEncoderReranker
from platform.observability.metrics import metered
from platform.observability.tracing import traced

import structlog

logger = structlog.get_logger()


class VectorSearchService:
    """
    Retrieves policy context for an assembled customer session.

    The service consumes the Layer 1 customer profile from the TTL context
    store, constructs a dynamic query, performs hybrid retrieval, reranks the
    top candidates, writes an audit record, and returns the top policy chunks.
    """

    def __init__(
        self,
        context_store: ContextStore,
        audit_writer: AuditWriter | None = None,
        kb_loader: KnowledgeBaseLoader | None = None,
        config: Settings = settings,
    ) -> None:
        """Create a vector search service with injected infrastructure."""
        self._context_store = context_store
        self._audit_writer = audit_writer
        self._kb_loader = kb_loader or KnowledgeBaseLoader(config=config)
        self._config = config

    @traced(layer="L2", operation="vector_search")
    @metered(layer="L2")
    async def retrieve(
        self,
        session_id: str,
        scenario: str,
        top_k: int = 3,
    ) -> RetrievalResult:
        """Retrieve the top policy chunks for a session and scenario."""
        if top_k <= 0:
            message = "top_k must be positive"
            raise SchemaValidationError(message)

        started = time.perf_counter()
        trace_id = f"trace_{session_id}"
        profile = await self._read_customer_profile(session_id)
        # Query text is generated from customer risk signals and scenario intent.
        query = build_retrieval_query(profile, scenario)
        # The loader returns a reusable local hybrid index for dense and sparse search.
        index = await self._kb_loader.load_and_index()

        dense_query = index.dense_embedder.embed_one(query)
        sparse_query = index.sparse_embedder.embed_one(query)
        filters = {"product_line": "credit_card", "jurisdiction": "US"}
        # Retrieve a broad candidate set before cross-encoder reranking narrows to top_k.
        candidates = await index.retriever.search(
            dense_q=dense_query,
            sparse_q=sparse_query,
            filters=filters,
            top_k=20,
        )
        chunks = self._rerank(query, candidates, top_k)
        retrieval_ms = int((time.perf_counter() - started) * 1000)

        result = RetrievalResult(
            session_id=session_id,
            query=query,
            chunks=chunks,
            kb_version=index.kb_version,
            retrieval_ms=retrieval_ms,
            embedding_model=self._config.EMBEDDING_MODEL,
            reranker_model=self._config.RERANKER_MODEL,
        )
        # Persist retrieved document/version evidence for later regulatory replay.
        await self._write_audit(trace_id, profile, result)

        logger.info(
            "vector_retrieval_complete",
            trace_id=trace_id,
            layer="2",
            operation="retrieve",
            customer_id=profile.customer_id,
            session_id=session_id,
            chunk_ids=[chunk.chunk_id for chunk in chunks],
            retrieval_ms=retrieval_ms,
        )
        return result

    async def _read_customer_profile(self, session_id: str) -> CustomerProfile:
        """Load the Layer 1 profile from the TTL context store."""
        key = f"session:{session_id}:customer_profile"
        raw_profile = await self._context_store.get(key)
        if raw_profile is None:
            message = f"Session profile expired or missing: {session_id}"
            raise SessionExpiredError(message)
        return CustomerProfile.model_validate_json(raw_profile)

    def _rerank(self, query: str, candidates: list[PolicyChunk], top_k: int) -> list[PolicyChunk]:
        """Rerank hybrid-search candidates with the configured cross-encoder."""
        reranker = CrossEncoderReranker(model_name=self._config.RERANKER_MODEL)
        return reranker.rerank(query, candidates, top_k=top_k)

    async def _write_audit(
        self,
        trace_id: str,
        profile: CustomerProfile,
        result: RetrievalResult,
    ) -> None:
        """Write the retrieval audit record used by the Audit Trail page."""
        if self._audit_writer is None:
            return

        timestamp = datetime.now(UTC)
        await self._audit_writer.write(
            AuditRecord(
                audit_id=f"aud_vec_{timestamp:%Y%m%d_%H%M%S_%f}_{profile.customer_id}",
                event_type="VECTOR_RETRIEVAL",
                trace_id=trace_id,
                session_id=result.session_id,
                customer_id=profile.customer_id,
                timestamp=timestamp,
                layer="2",
                payload={
                    "query": result.query,
                    "chunks_retrieved": [
                        {
                            "chunk_id": chunk.chunk_id,
                            "document_id": chunk.document_id,
                            "score": chunk.rerank_score,
                            "doc_version": chunk.doc_version,
                        }
                        for chunk in result.chunks
                    ],
                    "embedding_model": result.embedding_model,
                    "reranker_model": result.reranker_model,
                    "kb_version": result.kb_version,
                    "retrieval_ms": result.retrieval_ms,
                },
            )
        )
