"""Tests for process-local runtime configuration overrides.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.core.config import Settings
from platform.core.runtime_config import RuntimeConfigStore


def test_runtime_config_updates_cloud_backend_without_exposing_secret(monkeypatch) -> None:
    """Runtime config stores API keys in process memory and omits them from snapshots."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config = Settings(_env_file=None)
    store = RuntimeConfigStore(config)

    snapshot = store.update_llm(
        backend="api",
        model="claude-sonnet-4-20250514",
        ollama_base_url="http://localhost:11434",
        api_key="test-secret",
    )

    assert snapshot["llm_backend"] == "api"
    assert snapshot["llm_model"] == "claude-sonnet-4-20250514"
    assert snapshot["api_key_configured"] is True
    assert "test-secret" not in str(snapshot)
    assert store.api_key_for_model("claude-sonnet-4-20250514") == "test-secret"


def test_runtime_config_routes_openai_keys_by_model_family(monkeypatch) -> None:
    """OpenAI model names use the OpenAI key slot instead of Anthropic."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config = Settings(_env_file=None)
    store = RuntimeConfigStore(config)

    store.update_llm(
        backend="api",
        model="gpt-4o",
        ollama_base_url="http://localhost:11434",
        api_key="openai-secret",
    )

    assert store.api_key_for_model("gpt-4o") == "openai-secret"
    assert config.OPENAI_API_KEY is not None
    assert config.ANTHROPIC_API_KEY is None
