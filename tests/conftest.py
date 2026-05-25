"""Shared pytest configuration and fixtures.

Author: Sarala Biswal
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _ensure_local_platform_package() -> None:
    """Ensure tests import the repository platform package, not stdlib platform."""
    repo_root = Path(__file__).resolve().parents[1]
    package_dir = repo_root / "platform"
    init_file = package_dir / "__init__.py"
    loaded = sys.modules.get("platform")

    if loaded is not None and getattr(loaded, "__path__", None) is not None:
        return

    spec = importlib.util.spec_from_file_location(
        "platform",
        init_file,
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        message = f"Could not load local platform package from {init_file}"
        raise ImportError(message)

    module = importlib.util.module_from_spec(spec)
    sys.modules["platform"] = module
    spec.loader.exec_module(module)


_ensure_local_platform_package()


@pytest.fixture(autouse=True)
def _use_mock_llm_backend_for_tests():
    """Keep tests deterministic even when the app default is local Ollama."""
    from platform.core.config import settings

    original_backend = settings.LLM_BACKEND
    original_model = settings.LLM_MODEL
    original_base_url = settings.OLLAMA_BASE_URL
    settings.LLM_BACKEND = "mock"
    settings.LLM_MODEL = "mock"
    settings.OLLAMA_BASE_URL = "http://localhost:11434"
    try:
        yield
    finally:
        settings.LLM_BACKEND = original_backend
        settings.LLM_MODEL = original_model
        settings.OLLAMA_BASE_URL = original_base_url
