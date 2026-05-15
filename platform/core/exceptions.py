"""Typed exception hierarchy for platform failures.

Author: Sarala Biswal
"""

from __future__ import annotations


class PlatformError(Exception):
    """Base class for all platform-specific failures."""


class SourceTimeoutError(PlatformError):
    """Raised when an upstream source exceeds its hard timeout."""


class SourceUnavailableError(PlatformError):
    """Raised when an upstream source is unavailable."""


class SessionExpiredError(PlatformError):
    """Raised when session-scoped TTL context has expired."""


class DuplicateSessionError(PlatformError):
    """Raised when a context session key already exists."""


class SchemaValidationError(PlatformError):
    """Raised when cross-boundary data fails schema validation."""


class ToolAuthorizationError(PlatformError):
    """Raised when an agent attempts to call an unauthorized tool."""


class GuardrailBlockError(PlatformError):
    """Raised when guardrails block an action."""


class PipelineError(PlatformError):
    """Raised when orchestration cannot complete a pipeline."""
