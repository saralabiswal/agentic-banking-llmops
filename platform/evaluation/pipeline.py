"""Offline model evaluation pipeline.

Author: Sarala Biswal
"""

from __future__ import annotations

import pickle
from datetime import UTC, datetime
from pathlib import Path
from platform.core.config import Settings, settings
from platform.evaluation.gates.benchmark import run_benchmark_gate
from platform.evaluation.gates.fairness import run_fairness_gate
from platform.evaluation.gates.regression import run_regression_gate
from platform.evaluation.schemas import EvaluationReport
from platform.evaluation.store import EvaluationStore
from platform.ml.generate_training_data import (
    CHURN_FEATURES,
    RISK_FEATURES,
    generate_benchmark_set,
)
from platform.ml.scoring_service import ARTIFACT_DIR
from typing import Any

import mlflow
import structlog

logger = structlog.get_logger()


class EvaluationPipeline:
    """Runs benchmark, fairness, and regression gates before promotion."""

    def __init__(
        self,
        artifact_dir: Path | str = ARTIFACT_DIR,
        store: EvaluationStore | None = None,
        config: Settings = settings,
    ) -> None:
        """Create an evaluation pipeline."""
        self._artifact_dir = Path(artifact_dir)
        self._store = store
        self._config = config

    async def run(
        self,
        model_name: str,
        candidate_version: str,
        trace_id: str,
    ) -> EvaluationReport:
        """Run all evaluation gates for a candidate model artifact."""
        model = _load_pickle(self._artifact_for(model_name))
        benchmark = generate_benchmark_set()[model_name]
        feature_columns = _features_for(model_name)
        gates = [
            run_benchmark_gate(model, benchmark, feature_columns),
            run_fairness_gate(model, benchmark, feature_columns),
            run_regression_gate(model, None, benchmark, feature_columns),
        ]
        overall = all(gate.passed for gate in gates)
        report = EvaluationReport(
            model_name=model_name,
            candidate_version=candidate_version,
            champion_version=None,
            gates=gates,
            overall_passed=overall,
            promotion_allowed=overall,
            evaluated_at=datetime.now(UTC),
            trace_id=trace_id,
        )
        await self._tag_mlflow(report)
        if self._store is not None:
            await self._store.save_report(report)
        logger.info(
            "evaluation.pipeline_complete",
            trace_id=trace_id,
            model_name=model_name,
            candidate_version=candidate_version,
            overall_passed=overall,
        )
        return report

    async def _tag_mlflow(self, report: EvaluationReport) -> None:
        """Best-effort MLflow tagging for the candidate evaluation result."""
        try:
            mlflow.set_tracking_uri(self._config.MLFLOW_TRACKING_URI)
            with mlflow.start_run(run_name=f"eval-{report.model_name}-{report.candidate_version}"):
                mlflow.set_tag("eval.gate1", _status(report.gates[0].passed))
                mlflow.set_tag("eval.gate2", _status(report.gates[1].passed))
                mlflow.set_tag("eval.gate3", _status(report.gates[2].passed))
                mlflow.set_tag("eval.overall", _status(report.overall_passed))
                mlflow.set_tag("eval.evaluated_at", report.evaluated_at.isoformat())
                for gate in report.gates:
                    for metric, value in gate.metrics.items():
                        mlflow.log_metric(f"eval.{gate.gate}.{metric}", value)
        except Exception as exc:
            logger.warning("evaluation.mlflow_tag_failed", reason=str(exc))

    def _artifact_for(self, model_name: str) -> Path:
        if model_name == "payment_risk_model":
            return self._artifact_dir / "payment_risk_model.pkl"
        if model_name == "churn_propensity_model":
            return self._artifact_dir / "churn_propensity_model.pkl"
        raise ValueError(f"Unsupported model_name: {model_name}")


def _features_for(model_name: str) -> list[str]:
    if model_name == "payment_risk_model":
        return RISK_FEATURES
    if model_name == "churn_propensity_model":
        return CHURN_FEATURES
    raise ValueError(f"Unsupported model_name: {model_name}")


def _load_pickle(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing model artifact: {path}")
    with path.open("rb") as artifact:
        return pickle.load(artifact)


def _status(passed: bool) -> str:
    return "PASSED" if passed else "FAILED"


async def _main(model_name: str, version: str) -> None:
    report = await EvaluationPipeline().run(
        model_name=model_name,
        candidate_version=version,
        trace_id=f"eval_{model_name}_{version}",
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    asyncio.run(_main(args.model, args.version))
