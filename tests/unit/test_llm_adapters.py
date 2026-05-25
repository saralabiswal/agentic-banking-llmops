"""Unit tests for LLM provider adapters.

Author: Sarala Biswal
"""

from __future__ import annotations

import sys
from platform.adapters.litellm_client import LiteLLMClient
from platform.adapters.ollama_llm_client import OllamaLLMClient
from types import SimpleNamespace
from typing import Any

import pytest
import respx
from httpx import Response
from pydantic import BaseModel


class TinySchema(BaseModel):
    """Simple response schema for adapter tests."""

    value: str


@pytest.mark.asyncio
async def test_litellm_client_cleans_markdown_json_and_passes_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LiteLLM adapter should validate fenced JSON responses."""
    calls: list[dict[str, Any]] = []

    async def fake_completion(**kwargs: Any) -> object:
        calls.append(kwargs)
        message = SimpleNamespace(content='```json\n{"value": "ok"}\n```')
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(acompletion=fake_completion))

    result = await LiteLLMClient(model="gpt-test", api_key="secret").complete(
        system="system",
        user="user",
        schema=TinySchema,
    )

    assert result == {"value": "ok"}
    assert calls[0]["api_key"] == "secret"
    assert calls[0]["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_litellm_client_accepts_plain_fenced_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """LiteLLM adapter should also parse non-json fenced blocks."""

    async def fake_completion(**kwargs: Any) -> object:
        del kwargs
        message = SimpleNamespace(content='```\n{"value": "plain"}\n```')
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(acompletion=fake_completion))

    result = await LiteLLMClient(model="anthropic-test").complete("system", "user", TinySchema)

    assert result == {"value": "plain"}


@pytest.mark.asyncio
async def test_ollama_client_posts_chat_and_validates_schema() -> None:
    """Ollama adapter should call /api/chat with JSON mode enabled."""
    with respx.mock(assert_all_called=True) as router:
        route = router.post("http://ollama.test/api/chat").mock(
            return_value=Response(
                200,
                json={"message": {"content": '{"value": "local"}'}},
            )
        )

        result = await OllamaLLMClient("llama3.2", "http://ollama.test/").complete(
            "system",
            "user",
            TinySchema,
        )

    assert result == {"value": "local"}
    assert route.calls.last.request.url.path == "/api/chat"
    assert b'"format":{"description"' in route.calls.last.request.content
    assert b'"properties":{"value"' in route.calls.last.request.content
    assert b"Return one JSON object" in route.calls.last.request.content
