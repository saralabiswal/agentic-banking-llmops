"""Factory functions for wiring infrastructure adapters.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.adapters.litellm_client import LiteLLMClient
from platform.adapters.mock_channel_adapter import MockCRMAdapter, MockPushAdapter, MockSMSAdapter
from platform.adapters.mock_llm_client import MockLLMClient
from platform.adapters.ollama_llm_client import OllamaLLMClient
from platform.adapters.postgres_audit_writer import PostgresAuditWriter
from platform.adapters.postgres_feature_store import PostgresFeatureStore
from platform.adapters.postgres_queue_store import PostgresQueueStore
from platform.adapters.qdrant_vector_store import QdrantVectorStore
from platform.adapters.valkey_context_store import ValkeyContextStore
from platform.core.config import Settings, settings
from platform.core.interfaces import (
    AuditWriter,
    ChannelAdapter,
    ContextStore,
    FeatureStore,
    LLMClient,
    QueueStore,
    VectorStore,
)


def create_context_store(config: Settings = settings) -> ContextStore:
    """Create the configured context store."""
    return ValkeyContextStore(config.VALKEY_URL)


def create_feature_store(config: Settings = settings) -> FeatureStore:
    """Create the configured feature store."""
    return PostgresFeatureStore(config.POSTGRES_URL)


def create_audit_writer(config: Settings = settings) -> AuditWriter:
    """Create the configured audit writer."""
    return PostgresAuditWriter(config.POSTGRES_URL)


def create_queue_store(config: Settings = settings) -> QueueStore:
    """Create the configured queue store."""
    return PostgresQueueStore(config.POSTGRES_URL)


def create_vector_store(config: Settings = settings) -> VectorStore:
    """Create the configured vector store."""
    return QdrantVectorStore(config.QDRANT_URL, config.QDRANT_COLLECTION)


def create_llm_client(config: Settings = settings) -> LLMClient:
    """Create the configured LLM client."""
    match config.LLM_BACKEND:
        case "mock":
            return MockLLMClient()
        case "ollama":
            return OllamaLLMClient(model=config.LLM_MODEL, base_url=config.OLLAMA_BASE_URL)
        case "api":
            key = (
                config.OPENAI_API_KEY
                if config.LLM_MODEL.startswith(("gpt-", "openai/"))
                else config.ANTHROPIC_API_KEY
            )
            return LiteLLMClient(
                model=config.LLM_MODEL,
                api_key=key.get_secret_value() if key is not None else None,
            )


def create_channel_adapter(channel_type: str, config: Settings = settings) -> ChannelAdapter:
    """Create a mock channel adapter for a delivery channel."""
    audit_writer = create_audit_writer(config)
    match channel_type.upper():
        case "PUSH" | "MOBILE_PUSH":
            return MockPushAdapter(audit_writer)
        case "SMS":
            return MockSMSAdapter(audit_writer)
        case "CRM" | "CASE":
            return MockCRMAdapter(audit_writer)
        case _:
            return MockPushAdapter(audit_writer)
