"""PostgreSQL-backed feature store adapter.

Author: Sarala Biswal
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from platform.core.schemas import ModelSignals
from typing import Any

import psycopg
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def normalize_postgres_url(url: str) -> str:
    """Convert SQLAlchemy-style Postgres URLs into psycopg connection URLs."""
    return url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg://", "postgresql://"
    )


class PostgresFeatureStore:
    """FeatureStore implementation backed by PostgreSQL."""

    def __init__(self, url: str) -> None:
        """Store the connection URL for lazy async connections."""
        self._url = normalize_postgres_url(url)

    async def _connect(self) -> AsyncConnection[Any]:
        """Create an async psycopg connection."""
        return await psycopg.AsyncConnection.connect(self._url, row_factory=dict_row)

    async def get_signals(self, customer_id: str) -> ModelSignals:
        """Load model signals for a customer from row-wise feature storage."""
        async with await self._connect() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                    SELECT feature_name, value, model_version
                    FROM feature_store
                    WHERE customer_id = %s
                    """,
                (customer_id,),
            )
            rows = await cur.fetchall()

        values = {str(row["feature_name"]): row["value"] for row in rows}
        versions = {str(row["feature_name"]): str(row["model_version"]) for row in rows}
        return ModelSignals(
            risk_score=float(values["risk_score"]),
            churn_probability=float(values["churn_probability"]),
            clv_estimate=Decimal(str(values["clv_estimate"])),
            last_intervention=(
                datetime.fromisoformat(str(values["last_intervention"]))
                if values.get("last_intervention")
                else None
            ),
            intervention_7d=int(values.get("intervention_7d", 0)),
            payment_propensity=float(values["payment_propensity"]),
            model_versions=versions,
        )

    async def upsert_signals(self, customer_id: str, signals: ModelSignals) -> None:
        """Upsert each model signal as a feature row."""
        rows = {
            "risk_score": signals.risk_score,
            "churn_probability": signals.churn_probability,
            "clv_estimate": str(signals.clv_estimate),
            "last_intervention": (
                signals.last_intervention.isoformat() if signals.last_intervention else None
            ),
            "intervention_7d": signals.intervention_7d,
            "payment_propensity": signals.payment_propensity,
        }
        computed_at = datetime.now(UTC)
        async with await self._connect() as conn, conn.cursor() as cur:
            for feature_name, value in rows.items():
                await cur.execute(
                    """
                        INSERT INTO feature_store
                            (customer_id, feature_name, value, computed_at, model_version)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (customer_id, feature_name)
                        DO UPDATE SET
                            value = EXCLUDED.value,
                            computed_at = EXCLUDED.computed_at,
                            model_version = EXCLUDED.model_version
                        """,
                    (
                        customer_id,
                        feature_name,
                        Jsonb(value),
                        computed_at,
                        signals.model_versions.get(feature_name, "unknown"),
                    ),
                )
