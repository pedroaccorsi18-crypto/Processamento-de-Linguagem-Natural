from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeVar

OutputT = TypeVar("OutputT")


class ResultSeverity(StrEnum):
    """User-facing severity for application results."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class UseCaseResult(Generic[OutputT]):
    """Structured result returned by application use cases."""

    success: bool
    value: OutputT | None = None
    message: str = ""
    severity: ResultSeverity = ResultSeverity.INFO

    @classmethod
    def ok(
        cls,
        value: OutputT,
        message: str = "",
        severity: ResultSeverity = ResultSeverity.SUCCESS,
    ) -> UseCaseResult[OutputT]:
        return cls(success=True, value=value, message=message, severity=severity)

    @classmethod
    def fail(
        cls,
        message: str,
        severity: ResultSeverity = ResultSeverity.ERROR,
    ) -> UseCaseResult[OutputT]:
        return cls(success=False, value=None, message=message, severity=severity)
