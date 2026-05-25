"""Evaluation report persistence abstractions.

Author: Sarala Biswal
"""

from __future__ import annotations

from datetime import UTC, datetime
from platform.adapters.postgres_feature_store import normalize_postgres_url
from platform.evaluation.schemas import EvaluationReport, JudgeResult
from typing import Any, Protocol
from uuid import uuid4

import psycopg
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


class EvaluationStore(Protocol):
    """Persistence contract for evaluation history stores."""

    async def save_report(self, report: EvaluationReport) -> None:
        """Persist an evaluation report."""
        ...

    async def history(
        self,
        model_name: str | None = None,
        limit: int = 20,
    ) -> list[EvaluationReport]:
        """Return recent evaluation reports."""
        ...

    async def save_judge_result(self, result: JudgeResult) -> None:
        """Persist an LLM judge result."""
        ...

    async def judge_history(self, trace_id: str | None = None) -> list[JudgeResult]:
        """Return judge results."""
        ...


class InMemoryEvaluationStore:
    """Process-local evaluation report and judge-result store for API/UI runs."""

    def __init__(self) -> None:
        """Create an empty store."""
        self.reports: list[EvaluationReport] = []
        self.judge_results: list[JudgeResult] = []

    async def save_report(self, report: EvaluationReport) -> None:
        """Persist an evaluation report."""
        self.reports.append(report)

    async def history(
        self,
        model_name: str | None = None,
        limit: int = 20,
    ) -> list[EvaluationReport]:
        """Return recent evaluation reports."""
        reports = [
            report
            for report in self.reports
            if model_name is None or report.model_name == model_name
        ]
        return list(reversed(reports))[:limit]

    async def save_judge_result(self, result: JudgeResult) -> None:
        """Persist a judge result."""
        self.judge_results.append(result)

    async def judge_history(self, trace_id: str | None = None) -> list[JudgeResult]:
        """Return judge results, optionally filtered by trace."""
        return [
            result
            for result in self.judge_results
            if trace_id is None or result.trace_id == trace_id
        ]


class PostgresEvaluationStore:
    """Durable PostgreSQL-backed evaluation report and judge-result store."""

    def __init__(self, url: str) -> None:
        """Store the connection URL for lazy async operations."""
        self._url = normalize_postgres_url(url)

    async def _connect(self) -> AsyncConnection[Any]:
        """Create an async psycopg connection."""
        return await psycopg.AsyncConnection.connect(self._url, row_factory=dict_row)

    async def save_report(self, report: EvaluationReport) -> None:
        """Persist or update an evaluation report."""
        async with await self._connect() as conn, conn.cursor() as cur:
            # The report_id is deterministic so rerunning the same candidate updates evidence.
            await cur.execute(
                """
                    INSERT INTO evaluation_reports
                        (
                            report_id, trace_id, model_name, candidate_version,
                            champion_version, gates, overall_passed, promotion_allowed,
                            payload, evaluated_at, created_at
                        )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (report_id)
                    DO UPDATE SET
                        gates = EXCLUDED.gates,
                        overall_passed = EXCLUDED.overall_passed,
                        promotion_allowed = EXCLUDED.promotion_allowed,
                        payload = EXCLUDED.payload,
                        evaluated_at = EXCLUDED.evaluated_at
                    """,
                (
                    _report_id(report),
                    report.trace_id,
                    report.model_name,
                    report.candidate_version,
                    report.champion_version,
                    Jsonb([gate.model_dump(mode="json") for gate in report.gates]),
                    report.overall_passed,
                    report.promotion_allowed,
                    Jsonb(report.model_dump(mode="json")),
                    report.evaluated_at,
                    datetime.now(UTC),
                ),
            )

    async def history(
        self,
        model_name: str | None = None,
        limit: int = 20,
    ) -> list[EvaluationReport]:
        """Return recent durable evaluation reports."""
        query = "SELECT payload FROM evaluation_reports"
        params: list[Any] = []
        if model_name is not None:
            # Optional filtering powers the model selector without duplicating query methods.
            query += " WHERE model_name = %s"
            params.append(model_name)
        query += " ORDER BY evaluated_at DESC LIMIT %s"
        params.append(limit)

        async with await self._connect() as conn, conn.cursor() as cur:
            await cur.execute(query, params)
            rows = await cur.fetchall()

        return [EvaluationReport.model_validate(row["payload"]) for row in rows]

    async def save_judge_result(self, result: JudgeResult) -> None:
        """Persist an LLM judge result."""
        async with await self._connect() as conn, conn.cursor() as cur:
            # Judge results are append-only; each score is an independent evaluation artifact.
            await cur.execute(
                """
                    INSERT INTO evaluation_judge_results
                        (judge_id, trace_id, score, reasoning, flags, payload, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                (
                    f"judge_{uuid4().hex[:16]}",
                    result.trace_id,
                    result.score,
                    result.reasoning,
                    Jsonb(result.flags),
                    Jsonb(result.model_dump(mode="json")),
                    datetime.now(UTC),
                ),
            )

    async def judge_history(self, trace_id: str | None = None) -> list[JudgeResult]:
        """Return durable judge results, optionally filtered by trace."""
        query = "SELECT payload FROM evaluation_judge_results"
        params: list[Any] = []
        if trace_id is not None:
            query += " WHERE trace_id = %s"
            params.append(trace_id)
        query += " ORDER BY created_at DESC"

        async with await self._connect() as conn, conn.cursor() as cur:
            await cur.execute(query, params)
            rows = await cur.fetchall()

        return [JudgeResult.model_validate(row["payload"]) for row in rows]


def _report_id(report: EvaluationReport) -> str:
    """Build the stable primary key for one candidate evaluation run."""
    return f"{report.model_name}:{report.candidate_version}:{report.trace_id}"
