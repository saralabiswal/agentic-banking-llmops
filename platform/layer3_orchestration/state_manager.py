"""Pipeline state checkpointing for Layer 3.

Author: Sarala Biswal
"""

from __future__ import annotations

import json
from platform.core.config import Settings, settings
from platform.core.interfaces import ContextStore
from typing import Any


class PipelineStateManager:
    """Writes Redis-compatible recovery checkpoints after each pipeline step."""

    def __init__(
        self,
        context_store: ContextStore,
        config: Settings = settings,
    ) -> None:
        """Create a state manager backed by the session context store."""
        self._context_store = context_store
        self._config = config
        self._checkpoint_counts: dict[str, int] = {}

    async def checkpoint(
        self,
        session_id: str,
        trace_id: str,
        step_name: str,
        state: dict[str, Any],
    ) -> str:
        """Persist one immutable checkpoint and return its context-store key."""
        next_index = self._checkpoint_counts.get(session_id, 0) + 1
        self._checkpoint_counts[session_id] = next_index
        key = f"session:{session_id}:pipeline_state:{next_index:02d}"
        payload = {
            "trace_id": trace_id,
            "session_id": session_id,
            "checkpoint_index": next_index,
            "step_name": step_name,
            **state,
        }
        await self._context_store.set(
            key,
            json.dumps(payload, sort_keys=True),
            ttl=self._config.PIPELINE_STATE_TTL_SECONDS,
        )
        return key
