"""Runtime configuration API router.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.adapters.litellm_client import LiteLLMClient
from platform.core.runtime_config import LLMBackend, runtime_config

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class LLMBackendRequest(BaseModel):
    """Request body for testing or applying a runtime LLM backend."""

    llm_backend: LLMBackend
    llm_model: str
    ollama_base_url: str = "http://localhost:11434"
    api_key: str | None = None


class ConnectionTestResponse(BaseModel):
    """Connection test result returned to the Settings UI."""

    ok: bool
    message: str


class OllamaModelsResponse(BaseModel):
    """Installed Ollama models detected from the configured base URL."""

    ok: bool
    message: str
    models: list[str]


class TestLLMResponse(BaseModel):
    """Tiny schema used to validate cloud LLM JSON connectivity."""

    ok: bool


@router.get("/config")
async def get_config() -> dict[str, str | int | float | bool]:
    """Return non-secret runtime configuration for UI clients."""
    return runtime_config.snapshot()


@router.post("/config/llm-backend")
async def update_llm_backend(request: LLMBackendRequest) -> dict[str, str | int | float | bool]:
    """Update the process-local LLM backend without writing files or restarting."""
    if request.llm_backend != "mock":
        test = (
            await _test_ollama(request.ollama_base_url, request.llm_model)
            if request.llm_backend == "ollama"
            else await _test_api(request.llm_model, request.api_key)
        )
        if not test.ok:
            raise HTTPException(status_code=400, detail=test.message)
    return runtime_config.update_llm(
        backend=request.llm_backend,
        model=request.llm_model,
        ollama_base_url=request.ollama_base_url,
        api_key=request.api_key,
    )


@router.post("/config/test-llm")
async def test_llm_backend(request: LLMBackendRequest) -> ConnectionTestResponse:
    """Test a runtime LLM backend without persisting browser-side state."""
    match request.llm_backend:
        case "mock":
            return ConnectionTestResponse(ok=True, message="Mock LLM is available.")
        case "ollama":
            return await _test_ollama(request.ollama_base_url, request.llm_model)
        case "api":
            return await _test_api(request.llm_model, request.api_key)


@router.get("/config/ollama-models")
async def get_ollama_models(base_url: str = "http://localhost:11434") -> OllamaModelsResponse:
    """Return installed local Ollama LLM models for the Settings UI."""
    return await _fetch_ollama_models(base_url)


async def _test_ollama(base_url: str, model: str) -> ConnectionTestResponse:
    """Check whether Ollama is reachable and the requested model is present."""
    result = await _fetch_ollama_models(base_url)
    if not result.ok:
        return ConnectionTestResponse(ok=False, message=result.message)
    if model in result.models:
        return ConnectionTestResponse(ok=True, message=f"Ollama reachable. Model {model} found.")
    installed = ", ".join(result.models) if result.models else "none"
    return ConnectionTestResponse(
        ok=False,
        message=(
            f"Ollama reachable, but model {model} was not found. "
            f"Installed models: {installed}."
        ),
    )


async def _fetch_ollama_models(base_url: str) -> OllamaModelsResponse:
    """Fetch installed Ollama chat models from a base URL."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{base_url.rstrip('/')}/api/tags")
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return OllamaModelsResponse(ok=False, message=f"Ollama not reachable: {exc}", models=[])

    payload = response.json()
    models = payload.get("models", []) if isinstance(payload, dict) else []
    names = _normalise_ollama_model_names(models)
    message = (
        f"Ollama reachable. Installed models: {', '.join(names)}."
        if names
        else "Ollama reachable, but no chat models were found."
    )
    return OllamaModelsResponse(ok=True, message=message, models=names)


def _normalise_ollama_model_names(models: object) -> list[str]:
    """Return unique Ollama chat model names suitable for the model picker."""
    if not isinstance(models, list):
        return []
    names: list[str] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        raw_name = item.get("name")
        if not isinstance(raw_name, str) or not _is_ollama_chat_model(item, raw_name):
            continue
        display_name = raw_name.removesuffix(":latest")
        if display_name not in names:
            names.append(display_name)
    return names


def _is_ollama_chat_model(model: dict[object, object], name: str) -> bool:
    """Return whether an Ollama model looks like a chat/generation model."""
    details = model.get("details")
    family_values: list[str] = []
    if isinstance(details, dict):
        family = details.get("family")
        if isinstance(family, str):
            family_values.append(family)
        families = details.get("families")
        if isinstance(families, list):
            family_values.extend(item for item in families if isinstance(item, str))
    searchable = " ".join([name, *family_values]).lower()
    return not any(marker in searchable for marker in ("embed", "bert"))


async def _test_api(model: str, api_key: str | None) -> ConnectionTestResponse:
    """Validate a cloud model API key with a small JSON test call."""
    key = (
        api_key.strip()
        if api_key is not None and api_key.strip()
        else runtime_config.api_key_for_model(model)
    )
    if key is None:
        return ConnectionTestResponse(ok=False, message="API key is required for cloud LLM mode.")
    try:
        await LiteLLMClient(model=model, api_key=key).complete(
            system="Return only JSON matching the requested schema.",
            user='Return {"ok": true}.',
            schema=TestLLMResponse,
        )
    except Exception as exc:  # noqa: BLE001 - provider SDKs raise diverse exception types.
        return ConnectionTestResponse(ok=False, message=f"API test failed: {exc}")
    return ConnectionTestResponse(ok=True, message="Cloud LLM API key validated.")
