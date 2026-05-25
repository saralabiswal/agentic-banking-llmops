"""Unit tests for local DB seed helpers.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform import db_seed
from platform.core.schemas import ModelSignals
from typing import Any

import pytest


class FeatureStoreStub:
    """Feature-store test double used by seed_database."""

    instances: list[FeatureStoreStub] = []

    def __init__(self, url: str) -> None:
        self.url = url
        self.upserts: list[tuple[str, ModelSignals]] = []
        self.instances.append(self)

    async def upsert_signals(self, customer_id: str, signals: ModelSignals) -> None:
        self.upserts.append((customer_id, signals))


class CursorStub:
    """Async cursor recording executed statements."""

    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[object, ...]]] = []

    async def __aenter__(self) -> CursorStub:
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        del exc_type, exc, traceback

    async def execute(self, statement: str, params: tuple[object, ...]) -> None:
        self.executed.append((statement, params))


class ConnectionStub:
    """Async connection returning a cursor stub."""

    def __init__(self) -> None:
        self.cursor_stub = CursorStub()

    async def __aenter__(self) -> ConnectionStub:
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        del exc_type, exc, traceback

    def cursor(self) -> CursorStub:
        return self.cursor_stub


@pytest.mark.asyncio
async def test_seed_database_upserts_feature_fixtures_and_experiments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """seed_database should write feature fixtures before experiment metadata."""
    FeatureStoreStub.instances = []
    seed_called = False

    async def fake_seed_experiments() -> None:
        nonlocal seed_called
        seed_called = True

    monkeypatch.setattr(db_seed, "PostgresFeatureStore", FeatureStoreStub)
    monkeypatch.setattr(db_seed, "_seed_experiments", fake_seed_experiments)

    await db_seed.seed_database()

    assert seed_called is True
    assert len(FeatureStoreStub.instances[0].upserts) == 3
    assert {customer_id for customer_id, _ in FeatureStoreStub.instances[0].upserts} == {
        "C001",
        "C002",
        "C003",
    }


@pytest.mark.asyncio
async def test_seed_experiments_executes_idempotent_upserts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Experiment seed should emit upserts for experiment, variants, and results."""
    connection = ConnectionStub()

    async def fake_connect() -> ConnectionStub:
        return connection

    monkeypatch.setattr(db_seed, "_connect", fake_connect)

    await db_seed._seed_experiments()  # noqa: SLF001

    statements = [statement for statement, _ in connection.cursor_stub.executed]
    assert any("INSERT INTO experiments" in statement for statement in statements)
    assert sum("INSERT INTO experiment_variants" in statement for statement in statements) == 2
    assert sum("INSERT INTO experiment_results" in statement for statement in statements) == 2


@pytest.mark.asyncio
async def test_seed_main_prints_summary(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    """CLI entrypoint should run seed_database and print a concise summary."""
    called = False

    async def fake_seed_database() -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(db_seed, "seed_database", fake_seed_database)

    await db_seed._main()  # noqa: SLF001

    assert called is True
    assert "Seeded feature_store" in capsys.readouterr().out
