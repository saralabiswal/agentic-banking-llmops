"""Banking Agentic AI Platform backend package.

This package intentionally uses the architecture name ``platform``. The helper
below keeps common stdlib ``platform`` attributes available for tooling that
imports ``platform`` while running from the repository root.

Author: Sarala Biswal
"""

from __future__ import annotations

import importlib.util
import sysconfig
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from types import ModuleType


def _load_stdlib_platform() -> ModuleType:
    """Load the standard-library platform module under an internal name."""
    stdlib_path = Path(sysconfig.get_path("stdlib")) / "platform.py"
    spec = importlib.util.spec_from_file_location("_stdlib_platform", stdlib_path)
    if spec is None or spec.loader is None:
        msg = f"Could not load stdlib platform module from {stdlib_path}"
        raise ImportError(msg)

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_stdlib_platform = _load_stdlib_platform()

for _name in dir(_stdlib_platform):
    if not _name.startswith("__"):
        globals().setdefault(_name, getattr(_stdlib_platform, _name))


def __getattr__(name: str) -> Any:
    """Delegate unknown attributes to the standard-library platform module."""
    return getattr(_stdlib_platform, name)
