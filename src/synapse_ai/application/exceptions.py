from __future__ import annotations


class ApplicationError(RuntimeError):
    """Base error for application-layer failures."""


class UseCaseExecutionError(ApplicationError):
    """Raised when a use case cannot complete its orchestration."""

