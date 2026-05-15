"""PostgreSQL-backed immutable audit writer adapter.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.adapters.postgres_feature_store import normalize_postgres_url
from platform.core.schemas import AuditRecord
from typing import Any

import psycopg
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


class PostgresAuditWriter:
    """AuditWriter implementation using idempotent PostgreSQL inserts."""

    def __init__(self, url: str) -> None:
        """Store the connection URL for lazy async writes."""
        self._url = normalize_postgres_url(url)

    async def _connect(self) -> AsyncConnection[Any]:
        """Create an async psycopg connection."""
        return await psycopg.AsyncConnection.connect(self._url, row_factory=dict_row)

    async def write(self, record: AuditRecord) -> None:
        """Insert an audit record without overwriting an existing audit_id."""
        async with await self._connect() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                    INSERT INTO audit_log
                        (audit_id, trace_id, event_type, customer_id, payload, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (audit_id) DO NOTHING
                    """,
                (
                    record.audit_id,
                    record.trace_id,
                    record.event_type,
                    record.customer_id,
                    Jsonb(record.model_dump(mode="json")),
                    record.timestamp,
                ),
            )
