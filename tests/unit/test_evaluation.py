"""Unit tests for offline evaluation and LLM judge.

Author: Sarala Biswal
"""

from __future__ import annotations

import pickle
from datetime import UTC, datetime
from pathlib import Path
from platform.api.routers import evaluation as evaluation_router
from platform.core.config import Settings
from platform.evaluation.gates.benchmark import run_benchmark_gate
from platform.evaluation.gates.fairness import run_fairness_gate
from platform.evaluation.judge import LLMJudgeEvaluator
from platform.evaluation.pipeline import EvaluationPipeline
from platform.evaluation.schemas import EvaluationReport, GateResult, JudgeResult
from platform.evaluation.store import InMemoryEvaluationStore
from platform.llm_inference.schemas import InferenceResult, TaskType
from platform.ml.generate_training_data import RISK_FEATURES, generate_payment_risk_data

import pytest
from sklearn.ensemble import GradientBoostingClassifier


class JudgeLLMStub:
    """LLM inference stub returning a valid judge result."""

    async def complete(
        self,
        messages: list[dict[str, str]],
        task_type: TaskType,
        trace_id: str,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        schema: type[object] | None = None,
    ) -> InferenceResult:
        """Return a valid serialized judge result."""
        del messages, task_type, max_tokens, temperature, schema
        return InferenceResult(
            content=JudgeResult(
                score=4,
                reasoning="Reasoning cites risk and action.",
                flags=[],
                trace_id=trace_id,
            ).model_dump_json(),
            model_id="mock",
            backend="mock",
            latency_ms=1.0,
            prompt_tokens=10,
            completion_tokens=8,
            fallback_used=False,
            trace_id=trace_id,
        )


def test_benchmark_and_fairness_gates_pass_for_trained_synthetic_model() -> None:
    """A model trained on synthetic data should clear benchmark and fairness gates."""
    data = generate_payment_risk_data(n_samples=2000, seed=42)
    model = GradientBoostingClassifier(random_state=42).fit(data[RISK_FEATURES], data["label"])
    benchmark = generate_payment_risk_data(n_samples=200, seed=4242)

    benchmark_result = run_benchmark_gate(model, benchmark, RISK_FEATURES)
    fairness_result = run_fairness_gate(model, benchmark, RISK_FEATURES)

    assert benchmark_result.passed is True
    assert fairness_result.passed is True
    assert benchmark_result.metrics["auc_roc"] >= 0.72
    assert fairness_result.metrics["air"] >= 0.80


@pytest.mark.asyncio
async def test_evaluation_pipeline_runs_all_three_gates(tmp_path: Path) -> None:
    """EvaluationPipeline should load an artifact and return all gate results."""
    data = generate_payment_risk_data(n_samples=2000, seed=42)
    model = GradientBoostingClassifier(random_state=42).fit(data[RISK_FEATURES], data["label"])
    with (tmp_path / "payment_risk_model.pkl").open("wb") as artifact:
        pickle.dump(model, artifact)

    report = await EvaluationPipeline(
        artifact_dir=tmp_path,
        config=Settings(MLFLOW_TRACKING_URI=f"file:{tmp_path / 'mlruns'}"),
    ).run(
        model_name="payment_risk_model",
        candidate_version="1",
        trace_id="trace_eval_unit",
    )

    assert [gate.gate for gate in report.gates] == ["benchmark", "fairness", "regression"]
    assert report.promotion_allowed is True


@pytest.mark.asyncio
async def test_llm_judge_returns_valid_result() -> None:
    """LLMJudgeEvaluator should validate routed judge output."""
    result = await LLMJudgeEvaluator(JudgeLLMStub()).evaluate_reasoning(
        agent_output="Risk is high; propose hardship enrollment under KB-HARD-001.",
        scenario="payment_risk_intervention",
        customer_context="C002 has missed payments and low checking balance.",
        trace_id="trace_judge_unit",
    )

    assert result.score == 4
    assert result.trace_id == "trace_judge_unit"


@pytest.mark.asyncio
async def test_in_memory_evaluation_store_matches_durable_store_contract() -> None:
    """The store contract should preserve full report and judge payloads."""
    store = InMemoryEvaluationStore()
    report = EvaluationReport(
        model_name="payment_risk_model",
        candidate_version="1",
        champion_version=None,
        gates=[
            GateResult(
                gate="benchmark",
                passed=True,
                metrics={"auc_roc": 0.9},
            )
        ],
        overall_passed=True,
        promotion_allowed=True,
        evaluated_at=datetime.now(UTC),
        trace_id="trace_store_unit",
    )
    judge = JudgeResult(
        score=5,
        reasoning="Specific policy and action are cited.",
        flags=[],
        trace_id="trace_store_unit",
    )

    await store.save_report(report)
    await store.save_judge_result(judge)

    assert (await store.history(model_name="payment_risk_model")) == [report]
    assert (await store.judge_history(trace_id="trace_store_unit")) == [judge]


@pytest.mark.asyncio
async def test_evaluation_options_discovers_versions_from_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Evaluation selector options should include versions already evaluated."""
    store = InMemoryEvaluationStore()
    await store.save_report(
        EvaluationReport(
            model_name="payment_risk_model",
            candidate_version="7",
            champion_version="6",
            gates=[],
            overall_passed=True,
            promotion_allowed=True,
            evaluated_at=datetime.now(UTC),
            trace_id="trace_eval_options",
        )
    )
    monkeypatch.setattr(evaluation_router, "_mlflow_versions_for", lambda model_name: {"8"})

    options = await evaluation_router.evaluation_options(store=store)  # type: ignore[arg-type]
    payment = next(
        model for model in options.models if model.model_name == "payment_risk_model"
    )

    assert options.storage_ok is True
    assert payment.versions[:3] == ["8", "7", "1"]
    assert payment.default_version == "7"


@pytest.mark.asyncio
async def test_evaluation_options_surfaces_storage_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """The options endpoint should still return defaults when durable storage is unavailable."""
    monkeypatch.setattr(evaluation_router, "_mlflow_versions_for", lambda model_name: set())

    class BrokenStore:
        async def history(
            self,
            model_name: str | None = None,
            limit: int = 20,
        ) -> list[EvaluationReport]:
            del model_name, limit
            raise RuntimeError("relation evaluation_reports does not exist")

    options = await evaluation_router.evaluation_options(store=BrokenStore())  # type: ignore[arg-type]

    assert options.storage_ok is False
    assert "evaluation_reports" in (options.storage_error or "")
    assert options.models[0].versions == ["1"]
