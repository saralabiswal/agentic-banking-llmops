"""Protocol interfaces for platform infrastructure adapters.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.core.schemas import (
    ApprovalQueueItem,
    AuditRecord,
    DeliveryReceipt,
    ModelSignals,
    PolicyChunk,
    ProposedAction,
)
from platform.llm_inference.schemas import InferenceResult, TaskType
from platform.memory.schemas import CustomerMemory, MemoryType
from typing import Any, Protocol

from pydantic import BaseModel


class ContextStore(Protocol):
    """TTL-bound key-value store for session-scoped platform state."""

    async def get(self, key: str) -> str | None:
        """Return the stored value for a key, or None when absent."""
        ...

    async def set(self, key: str, value: str, ttl: int) -> None:
        """Store a value with a TTL, enforcing adapter-specific write semantics."""
        ...

    async def delete(self, key: str) -> None:
        """Delete a key if present."""
        ...


class FeatureStore(Protocol):
    """Feature store for model signals."""

    async def get_signals(self, customer_id: str) -> ModelSignals:
        """Load model signals for a customer."""
        ...

    async def upsert_signals(self, customer_id: str, signals: ModelSignals) -> None:
        """Create or replace model signals for a customer."""
        ...


class AuditWriter(Protocol):
    """Append-only audit writer."""

    async def write(self, record: AuditRecord) -> None:
        """Persist an immutable audit record."""
        ...


class MemoryStore(Protocol):
    """Long-term cross-session customer memory store."""

    async def store(self, memory: CustomerMemory) -> str:
        """Store a customer memory and return its identifier."""
        ...

    async def retrieve(
        self,
        customer_id: str,
        scenario: str,
        top_k: int = 5,
        memory_types: list[MemoryType] | None = None,
    ) -> list[CustomerMemory]:
        """Retrieve relevant memories for a customer and scenario."""
        ...

    async def get_recent(self, customer_id: str, limit: int = 10) -> list[CustomerMemory]:
        """Return recent memories for a customer."""
        ...


class QueueStore(Protocol):
    """Human approval queue persistence interface."""

    async def enqueue(self, item: ApprovalQueueItem) -> None:
        """Persist a queue item."""
        ...

    async def dequeue_pending(self, priority: str | None, limit: int) -> list[ApprovalQueueItem]:
        """Return pending queue items ordered by SLA urgency."""
        ...

    async def update_decision(self, queue_id: str, decision: str, reason: str) -> None:
        """Record a human decision for a queue item."""
        ...


class VectorStore(Protocol):
    """Vector store for policy chunks."""

    async def upsert(self, chunks: list[PolicyChunk]) -> None:
        """Upsert policy chunks and their vectors."""
        ...

    async def search(
        self,
        dense_vector: list[float],
        sparse_vector: dict[int, float],
        filters: dict[str, str],
        top_k: int,
    ) -> list[PolicyChunk]:
        """Search policy chunks with dense, sparse, and metadata criteria."""
        ...


class LLMClient(Protocol):
    """LLM provider abstraction."""

    async def complete(self, system: str, user: str, schema: type[BaseModel]) -> dict[str, Any]:
        """Return a JSON-compatible response that validates against schema."""
        ...


class LLMInferenceService(Protocol):
    """Routed LLM inference service interface."""

    async def complete(
        self,
        messages: list[dict[str, str]],
        task_type: TaskType,
        trace_id: str,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        schema: type[BaseModel] | None = None,
    ) -> InferenceResult:
        """Return a routed inference result."""
        ...


class ChannelAdapter(Protocol):
    """Delivery adapter for customer or associate channels."""

    async def send(self, action: ProposedAction) -> DeliveryReceipt:
        """Send a proposed action through a delivery channel."""
        ...
