"""Integration tests for the FastAPI Layer 6 surface.

Author: Sarala Biswal
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from platform.api.dependencies import get_outcome_router, get_runner
from platform.api.main import app
from platform.api.routers import config as config_router
from platform.core.config import settings
from platform.core.runtime_config import LLMBackend, runtime_config
from platform.layer6_sdk.blueprint_runner import BlueprintRunner
from platform.layer6_sdk.outcome_router import OutcomeRouter
from typing import Any

import httpx
from pydantic import BaseModel, SecretStr


@dataclass(frozen=True)
class LLMSettingsState:
    """Mutable LLM settings captured before a test changes runtime config."""

    llm_backend: LLMBackend
    llm_model: str
    ollama_base_url: str
    anthropic_api_key: SecretStr | None
    openai_api_key: SecretStr | None
    anthropic_env: str | None
    openai_env: str | None


async def test_config_endpoint_returns_runtime_settings_without_secrets() -> None:
    state = _capture_llm_settings()
    try:
        runtime_config.update_llm("mock", "mock", "http://localhost:11434")
        async with _api_client() as client:
            response = await client.get("/config")

        assert response.status_code == 200
        body = response.json()
        assert body["llm_backend"] == "mock"
        assert body["llm_mode_label"] == "Mock LLM"
        assert body["context_ttl_seconds"] == 300
        assert body["source_adapter_timeout_ms"] == 150
        assert "api_key" not in body
        assert "anthropic_api_key" not in body
        assert "openai_api_key" not in body
    finally:
        _restore_llm_settings(state)


async def test_mock_llm_connection_test_succeeds() -> None:
    async with _api_client() as client:
        response = await client.post(
            "/config/test-llm",
            json={
                "llm_backend": "mock",
                "llm_model": "mock",
                "ollama_base_url": "http://localhost:11434",
            },
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "message": "Mock LLM is available."}


async def test_ollama_connection_test_reports_unreachable_without_raising() -> None:
    async with _api_client() as client:
        response = await client.post(
            "/config/test-llm",
            json={
                "llm_backend": "ollama",
                "llm_model": "llama3.2",
                "ollama_base_url": "http://127.0.0.1:1",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert "Ollama not reachable" in body["message"]


async def test_ollama_models_endpoint_returns_detected_models(monkeypatch) -> None:
    async def fake_fetch_ollama_models(base_url: str) -> config_router.OllamaModelsResponse:
        assert base_url == "http://ollama.test"
        return config_router.OllamaModelsResponse(
            ok=True,
            message="Ollama reachable. Installed models: llama3, llama3.1.",
            models=["llama3", "llama3.1"],
        )

    monkeypatch.setattr(config_router, "_fetch_ollama_models", fake_fetch_ollama_models)

    async with _api_client() as client:
        response = await client.get(
            "/config/ollama-models",
            params={"base_url": "http://ollama.test"},
        )

    assert response.status_code == 200
    assert response.json()["models"] == ["llama3", "llama3.1"]


async def test_ollama_backend_update_rejects_unavailable_model(monkeypatch) -> None:
    state = _capture_llm_settings()

    async def fake_test_ollama(base_url: str, model: str) -> config_router.ConnectionTestResponse:
        assert base_url == "http://localhost:11434"
        assert model == "llama3.2"
        return config_router.ConnectionTestResponse(
            ok=False,
            message="Ollama reachable, but model llama3.2 was not found.",
        )

    monkeypatch.setattr(config_router, "_test_ollama", fake_test_ollama)

    try:
        async with _api_client() as client:
            response = await client.post(
                "/config/llm-backend",
                json={
                    "llm_backend": "ollama",
                    "llm_model": "llama3.2",
                    "ollama_base_url": "http://localhost:11434",
                },
            )

        assert response.status_code == 400
        assert "llama3.2 was not found" in response.json()["detail"]
        assert state.llm_backend == settings.LLM_BACKEND
        assert state.llm_model == settings.LLM_MODEL
    finally:
        _restore_llm_settings(state)


async def test_api_backend_update_validates_key_before_accepting(monkeypatch) -> None:
    state = _capture_llm_settings()
    settings.ANTHROPIC_API_KEY = None
    settings.OPENAI_API_KEY = None

    class FakeLiteLLMClient:
        """LiteLLM test double that records the server-side key path."""

        def __init__(self, model: str, api_key: str | None = None) -> None:
            self.model = model
            self.api_key = api_key

        async def complete(
            self,
            system: str,
            user: str,
            schema: type[BaseModel],
        ) -> dict[str, Any]:
            del system, user
            assert self.model == "claude-sonnet-4-20250514"
            assert self.api_key == "test-api-key"
            return schema(ok=True).model_dump(mode="json")

    monkeypatch.setattr(config_router, "LiteLLMClient", FakeLiteLLMClient)

    try:
        async with _api_client() as client:
            response = await client.post(
                "/config/llm-backend",
                json={
                    "llm_backend": "api",
                    "llm_model": "claude-sonnet-4-20250514",
                    "ollama_base_url": "http://localhost:11434",
                    "api_key": "test-api-key",
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["llm_backend"] == "api"
        assert body["llm_model"] == "claude-sonnet-4-20250514"
        assert body["api_key_configured"] is True
        assert "api_key" not in body
        assert settings.ANTHROPIC_API_KEY is not None
        assert settings.ANTHROPIC_API_KEY.get_secret_value() == "test-api-key"
    finally:
        _restore_llm_settings(state)


async def test_pipeline_runs_returns_newest_run_first() -> None:
    runner = BlueprintRunner()
    runner.status_by_trace["trace_sess_C001_20260514_100000_old001"] = {
        "trace_id": "trace_sess_C001_20260514_100000_old001",
        "session_id": "sess_C001_20260514_100000_old001",
        "status": "completed",
        "customer_id": "C001",
        "scenario": "churn_prevention",
        "started_at": "2026-05-14T10:00:00+00:00",
        "completed_at": "2026-05-14T10:00:01+00:00",
    }
    runner.status_by_trace["trace_sess_C002_20260514_100500_new001"] = {
        "trace_id": "trace_sess_C002_20260514_100500_new001",
        "session_id": "sess_C002_20260514_100500_new001",
        "status": "running",
        "customer_id": "C002",
        "scenario": "payment_risk_intervention",
        "started_at": "2026-05-14T10:05:00+00:00",
    }
    app.dependency_overrides[get_runner] = lambda: runner

    try:
        async with _api_client() as client:
            response = await client.get("/pipeline/runs")

        assert response.status_code == 200
        body = response.json()
        assert [run["trace_id"] for run in body] == [
            "trace_sess_C002_20260514_100500_new001",
            "trace_sess_C001_20260514_100000_old001",
        ]
        assert body[0]["customer_id"] == "C002"
        assert body[0]["scenario"] == "payment_risk_intervention"
    finally:
        app.dependency_overrides.clear()


async def test_pipeline_run_status_sse_and_outcome_updates_experiment_count():
    runner = BlueprintRunner()
    outcome_router = OutcomeRouter(
        experiment_service=runner.experiment_service,
        audit_writer=runner.audit_writer,
    )
    app.dependency_overrides[get_runner] = lambda: runner
    app.dependency_overrides[get_outcome_router] = lambda: outcome_router

    try:
        async with _api_client() as client:
            run_response = await client.post(
                "/pipeline/run",
                json={
                    "customer_id": "C002",
                    "scenario": "payment_risk_intervention",
                    "caller_id": "mobile_app_team",
                    "trigger": "payment_risk_scheduler",
                },
            )
            assert run_response.status_code == 200
            run_body = run_response.json()
            trace_id = run_body["trace_id"]
            assert trace_id
            assert run_body["status"] == "started"

            status_body = await _wait_for_completed(client, trace_id)
            assert status_body["status"] == "completed"
            assert status_body["execution_result"]["action_executed"] is True

            events_response = await client.get(f"/pipeline/events/{trace_id}")
            assert events_response.status_code == 200
            completed_events = [
                line
                for line in events_response.text.splitlines()
                if line.startswith("event: layer_completed")
            ]
            assert len(completed_events) == 6

            experiment = runner.experiment_service.get_experiment("exp_payment_message_v3")
            before = experiment.variants["A"].conversion_count
            outcome_response = await client.post(
                f"/outcomes/{trace_id}",
                json={
                    "action_id": "ACT-001",
                    "customer_id": "C002",
                    "outcome_type": "ENROLLED",
                    "metadata": {
                        "session_id": status_body["session_id"],
                        "experiment_id": "exp_payment_message_v3",
                        "variant_id": "A",
                    },
                },
            )
            assert outcome_response.status_code == 200
            assert outcome_response.json()["status"] == "recorded"
            assert experiment.variants["A"].conversion_count == before + 1
    finally:
        app.dependency_overrides.clear()


async def _wait_for_completed(
    client: httpx.AsyncClient,
    trace_id: str,
) -> dict[str, object]:
    for _ in range(30):
        response = await client.get(f"/pipeline/status/{trace_id}")
        assert response.status_code == 200
        body = response.json()
        if body["status"] == "completed":
            return body
        if body["status"] == "failed":
            raise AssertionError(body["error"])
        await asyncio.sleep(0.05)
    raise AssertionError("pipeline did not complete")


def _api_client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


def _capture_llm_settings() -> LLMSettingsState:
    return LLMSettingsState(
        llm_backend=settings.LLM_BACKEND,
        llm_model=settings.LLM_MODEL,
        ollama_base_url=settings.OLLAMA_BASE_URL,
        anthropic_api_key=settings.ANTHROPIC_API_KEY,
        openai_api_key=settings.OPENAI_API_KEY,
        anthropic_env=os.environ.get("ANTHROPIC_API_KEY"),
        openai_env=os.environ.get("OPENAI_API_KEY"),
    )


def _restore_llm_settings(state: LLMSettingsState) -> None:
    settings.LLM_BACKEND = state.llm_backend
    settings.LLM_MODEL = state.llm_model
    settings.OLLAMA_BASE_URL = state.ollama_base_url
    settings.ANTHROPIC_API_KEY = state.anthropic_api_key
    settings.OPENAI_API_KEY = state.openai_api_key
    _restore_env_value("ANTHROPIC_API_KEY", state.anthropic_env)
    _restore_env_value("OPENAI_API_KEY", state.openai_env)


def _restore_env_value(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
        return
    os.environ[name] = value
