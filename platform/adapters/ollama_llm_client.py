"""Ollama LLM client adapter for local model inference.

Author: Sarala Biswal
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import BaseModel


class OllamaLLMClient:
    """LLMClient implementation for Ollama's local chat API."""

    def __init__(self, model: str, base_url: str) -> None:
        """Create an Ollama client for a model and base URL."""
        self._model = model
        self._base_url = base_url.rstrip("/")

    async def complete(self, system: str, user: str, schema: type[BaseModel]) -> dict[str, Any]:
        """Request JSON output from Ollama and validate it against schema."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "format": "json",
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            response.raise_for_status()
        content = response.json()["message"]["content"]
        data = json.loads(content)
        return schema.model_validate(data).model_dump(mode="json")
