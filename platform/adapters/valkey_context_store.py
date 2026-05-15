"""Valkey-backed TTL context store adapter.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.core.exceptions import DuplicateSessionError
from typing import Any

import redis.asyncio as redis


class ValkeyContextStore:
    """Implements the context store using Valkey's Redis-compatible protocol."""

    def __init__(self, url: str) -> None:
        """Create a pooled Valkey connection from a Redis URL."""
        self._pool: Any = redis.ConnectionPool.from_url(url, decode_responses=True)
        self._client: Any = redis.Redis(connection_pool=self._pool)

    async def get(self, key: str) -> str | None:
        """Return a value by key, or None when the key is absent or expired."""
        value = await self._client.get(key)
        return str(value) if value is not None else None

    async def set(self, key: str, value: str, ttl: int) -> None:
        """Write a value once with Redis-enforced EX and NX semantics."""
        written = await self._client.set(key, value, ex=ttl, nx=True)
        if not written:
            raise DuplicateSessionError(f"Context key already exists: {key}")

    async def delete(self, key: str) -> None:
        """Delete a key, silently succeeding when the key is absent."""
        await self._client.delete(key)

    async def close(self) -> None:
        """Close the underlying Redis client and connection pool."""
        await self._client.aclose()
        await self._pool.aclose()
