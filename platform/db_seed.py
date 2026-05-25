"""Seed local PostgreSQL tables for clean development runs.

Author: Sarala Biswal
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from platform.adapters.postgres_feature_store import PostgresFeatureStore, normalize_postgres_url
from platform.core.config import settings
from platform.layer1_context.feature_store import SIGNAL_FIXTURES
from platform.layer5_ab.experiment_service import seed_experiments
from typing import Any

import psycopg
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


async def seed_database() -> None:
    """Seed feature-store signals and experiment metadata."""
    feature_store = PostgresFeatureStore(settings.POSTGRES_URL)
    for customer_id, signals in SIGNAL_FIXTURES.items():
        await feature_store.upsert_signals(customer_id, signals)
    await _seed_experiments()


async def _seed_experiments() -> None:
    """Persist the in-memory experiment fixtures into the local DB tables."""
    now = datetime.now(UTC)
    async with await _connect() as conn, conn.cursor() as cur:
        for experiment in seed_experiments().values():
            await cur.execute(
                """
                    INSERT INTO experiments
                        (
                            experiment_id, scenario, action_type, status,
                            winner_variant_id, min_sample_size, confidence_threshold,
                            created_at, concluded_at
                        )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (experiment_id)
                    DO UPDATE SET
                        scenario = EXCLUDED.scenario,
                        action_type = EXCLUDED.action_type,
                        status = EXCLUDED.status,
                        winner_variant_id = EXCLUDED.winner_variant_id,
                        min_sample_size = EXCLUDED.min_sample_size,
                        confidence_threshold = EXCLUDED.confidence_threshold,
                        concluded_at = EXCLUDED.concluded_at
                    """,
                (
                    experiment.experiment_id,
                    experiment.scenario,
                    experiment.action_type,
                    experiment.status,
                    experiment.winner,
                    experiment.min_sample_size,
                    experiment.confidence_level,
                    now,
                    experiment.concluded_at,
                ),
            )
            for variant in experiment.variants.values():
                await cur.execute(
                    """
                        INSERT INTO experiment_variants
                            (variant_id, experiment_id, name, weight, payload)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (variant_id)
                        DO UPDATE SET
                            experiment_id = EXCLUDED.experiment_id,
                            name = EXCLUDED.name,
                            weight = EXCLUDED.weight,
                            payload = EXCLUDED.payload
                        """,
                    (
                        variant.variant_id,
                        variant.experiment_id,
                        variant.name,
                        variant.weight,
                        Jsonb(variant.payload),
                    ),
                )
                result_id = f"{experiment.experiment_id}:{variant.variant_id}"
                await cur.execute(
                    """
                        INSERT INTO experiment_results
                            (
                                result_id, experiment_id, variant_id, sample_count,
                                conversion_count, confidence, updated_at
                            )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (result_id)
                        DO UPDATE SET
                            sample_count = EXCLUDED.sample_count,
                            conversion_count = EXCLUDED.conversion_count,
                            confidence = EXCLUDED.confidence,
                            updated_at = EXCLUDED.updated_at
                        """,
                    (
                        result_id,
                        experiment.experiment_id,
                        variant.variant_id,
                        variant.sample_count,
                        variant.conversion_count,
                        0.0,
                        now,
                    ),
                )


async def _connect() -> AsyncConnection[Any]:
    """Create an async psycopg connection for seed writes."""
    return await psycopg.AsyncConnection.connect(
        normalize_postgres_url(settings.POSTGRES_URL),
        row_factory=dict_row,
    )


async def _main() -> None:
    await seed_database()
    print("Seeded feature_store, experiments, experiment_variants, and experiment_results.")


if __name__ == "__main__":
    asyncio.run(_main())
