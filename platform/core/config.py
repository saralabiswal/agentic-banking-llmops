"""Typed runtime settings for the platform.

Author: Sarala Biswal
"""

from __future__ import annotations

from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed platform settings."""

    LLM_BACKEND: Literal["mock", "ollama", "api"] = "mock"
    LLM_MODEL: str = "llama3.2"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    ANTHROPIC_API_KEY: SecretStr | None = None
    OPENAI_API_KEY: SecretStr | None = None

    VALKEY_URL: str = "redis://localhost:6379"
    POSTGRES_URL: str = "postgresql+asyncpg://platform:platform@localhost:5432/platform"
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "knowledge_base"
    MLFLOW_TRACKING_URI: str = "http://localhost:5001"
    JAEGER_ENDPOINT: str = "http://localhost:4317"
    PROMETHEUS_PORT: int = 8001

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    RULES_DIR: str = "rules"
    KB_DIR: str = "knowledge_base"
    RULES_RELOAD_INTERVAL_SEC: int = 5

    CONTEXT_TTL_SECONDS: int = 300
    SOURCE_ADAPTER_TIMEOUT_MS: int = 150

    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RETRIEVAL_TOP_K: int = 3
    HYBRID_ALPHA: float = 0.7

    AGENT_DEFAULT_TIMEOUT_MS: int = 8000
    PIPELINE_STATE_TTL_SECONDS: int = 300

    EXPERIMENT_MIN_SAMPLE_SIZE: int = 5000
    EXPERIMENT_CONFIDENCE_THRESHOLD: float = 0.95
    PSI_WARNING_THRESHOLD: float = 0.10
    PSI_ALERT_THRESHOLD: float = 0.25
    RECALL_ALERT_THRESHOLD: float = 0.78

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


settings = Settings()
