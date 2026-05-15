"""Process-local runtime configuration overrides.

Author: Sarala Biswal
"""

from __future__ import annotations

import os
from platform.core.config import Settings, settings
from threading import RLock
from typing import Literal

from pydantic import SecretStr

LLMBackend = Literal["mock", "ollama", "api"]

LLM_MODE_LABELS: dict[LLMBackend, str] = {
    "mock": "Mock LLM",
    "ollama": "Ollama",
    "api": "API",
}


class RuntimeConfigStore:
    """Stores process-local configuration overrides without writing files."""

    def __init__(self, config: Settings = settings) -> None:
        """Create a runtime config store backed by the settings singleton."""
        self._settings = config
        self._lock = RLock()

    def snapshot(self) -> dict[str, str | int | float | bool]:
        """Return non-secret runtime and platform configuration values."""
        with self._lock:
            return {
                "llm_backend": self._settings.LLM_BACKEND,
                "llm_mode_label": LLM_MODE_LABELS[self._settings.LLM_BACKEND],
                "llm_model": self._settings.LLM_MODEL,
                "ollama_base_url": self._settings.OLLAMA_BASE_URL,
                "api_key_configured": self.api_key_for_model(self._settings.LLM_MODEL) is not None,
                "environment": self._settings.ENVIRONMENT,
                "context_ttl_seconds": self._settings.CONTEXT_TTL_SECONDS,
                "source_adapter_timeout_ms": self._settings.SOURCE_ADAPTER_TIMEOUT_MS,
                "retrieval_top_k": self._settings.RETRIEVAL_TOP_K,
                "hybrid_alpha": self._settings.HYBRID_ALPHA,
                "experiment_confidence_threshold": self._settings.EXPERIMENT_CONFIDENCE_THRESHOLD,
            }

    def update_llm(
        self,
        backend: LLMBackend,
        model: str,
        ollama_base_url: str,
        api_key: str | None = None,
    ) -> dict[str, str | int | float | bool]:
        """Update LLM settings in memory and return the new public snapshot."""
        with self._lock:
            self._settings.LLM_BACKEND = backend
            self._settings.LLM_MODEL = model
            self._settings.OLLAMA_BASE_URL = ollama_base_url
            if api_key is not None and api_key.strip():
                self._set_api_key(model, api_key.strip())
            return self.snapshot()

    def api_key_for_model(self, model: str) -> str | None:
        """Return the configured in-memory API key for a model without exposing it publicly."""
        key = (
            self._settings.OPENAI_API_KEY
            if _is_openai_model(model)
            else self._settings.ANTHROPIC_API_KEY
        )
        return key.get_secret_value() if key is not None else None

    def _set_api_key(self, model: str, api_key: str) -> None:
        if _is_openai_model(model):
            self._settings.OPENAI_API_KEY = SecretStr(api_key)
            os.environ["OPENAI_API_KEY"] = api_key
        else:
            self._settings.ANTHROPIC_API_KEY = SecretStr(api_key)
            os.environ["ANTHROPIC_API_KEY"] = api_key


def _is_openai_model(model: str) -> bool:
    return model.startswith(("gpt-", "openai/"))


runtime_config = RuntimeConfigStore()
