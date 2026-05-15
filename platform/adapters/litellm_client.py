"""LiteLLM client adapter for cloud model providers.

Author: Sarala Biswal
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel


class LiteLLMClient:
    """LLMClient implementation using LiteLLM provider abstraction."""

    def __init__(self, model: str, api_key: str | None = None) -> None:
        """Create a LiteLLM client for a configured model."""
        self._model = model
        self._api_key = api_key

    async def complete(self, system: str, user: str, schema: type[BaseModel]) -> dict[str, Any]:
        """Request JSON output through LiteLLM and validate it against schema."""
        import litellm

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        if self._api_key is not None:
            kwargs["api_key"] = self._api_key
        response = await litellm.acompletion(**kwargs)
        content = str(response.choices[0].message.content)
        cleaned = content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned.removeprefix("```json").removesuffix("```").strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```").removesuffix("```").strip()
        data = json.loads(cleaned)
        return schema.model_validate(data).model_dump(mode="json")
