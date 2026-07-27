from __future__ import annotations

from typing import Generic, Protocol, TypeVar

from synapse_ai.application.result import UseCaseResult

InputT = TypeVar("InputT", contravariant=True)
OutputT = TypeVar("OutputT")


class UseCase(Protocol, Generic[InputT, OutputT]):
    """Contract for application use cases."""

    def execute(self, command: InputT) -> UseCaseResult[OutputT]:
        """Execute the use case with the provided command."""
