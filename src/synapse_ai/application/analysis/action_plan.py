from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from synapse_ai.application.interfaces import (
    ActionPlanGenerator,
    ActionPlanSaver,
    SemanticSourceRetriever,
)
from synapse_ai.application.result import ResultSeverity, UseCaseResult
from synapse_ai.services.analysis_repository import AnalysisPersistenceError
from synapse_ai.services.analysis_service import ActionPlan, AnalysisGenerationError
from synapse_ai.services.chunk_repository import ChunkPersistenceError
from synapse_ai.services.embedding_service import EmbeddingGenerationError

ACTION_PLAN_QUERY = (
    "decisões, responsáveis, prazos, riscos, pendências, ações recomendadas "
    "e critérios de aceite"
)
ACTION_PLAN_SOURCE_LIMIT = 8


@dataclass(frozen=True)
class ActionPlanCommand:
    """Input data required to generate an action plan with sources."""

    supabase_client: Any
    openai_client: Any
    user_id: str
    embedding_model: str
    generation_model: str
    save_to_history: bool
    selected_document_ids: list[str]


@dataclass(frozen=True)
class ActionPlanOutput:
    """Successful output of the action-plan use case."""

    action_plan: ActionPlan
    saved_to_history: bool
    persistence_warning: str | None = None


class ActionPlanUseCase:
    """Orchestrates semantic retrieval, action-plan generation and optional persistence."""

    def __init__(
        self,
        semantic_retriever: SemanticSourceRetriever,
        action_plan_generator: ActionPlanGenerator,
        action_plan_saver: ActionPlanSaver,
    ) -> None:
        self._semantic_retriever = semantic_retriever
        self._action_plan_generator = action_plan_generator
        self._action_plan_saver = action_plan_saver

    def execute(self, command: ActionPlanCommand) -> UseCaseResult[ActionPlanOutput]:
        try:
            sources = self._semantic_retriever.retrieve(
                supabase_client=command.supabase_client,
                openai_client=command.openai_client,
                user_id=command.user_id,
                query=ACTION_PLAN_QUERY,
                embedding_model=command.embedding_model,
                selected_document_ids=command.selected_document_ids,
                limit=ACTION_PLAN_SOURCE_LIMIT,
            )
            if not sources:
                return UseCaseResult.fail(
                    "Nenhum trecho relevante foi encontrado. "
                    "Atualize a base semântica antes de gerar o plano.",
                    ResultSeverity.INFO,
                )

            action_plan = self._action_plan_generator(
                command.openai_client,
                sources,
                command.generation_model,
            )
        except (AnalysisGenerationError, ChunkPersistenceError, EmbeddingGenerationError) as exc:
            return UseCaseResult.fail(str(exc), ResultSeverity.ERROR)

        persistence_warning = self._persist_if_requested(command, action_plan)
        return UseCaseResult.ok(
            ActionPlanOutput(
                action_plan=action_plan,
                saved_to_history=command.save_to_history and persistence_warning is None,
                persistence_warning=persistence_warning,
            )
        )

    def _persist_if_requested(
        self,
        command: ActionPlanCommand,
        action_plan: ActionPlan,
    ) -> str | None:
        if not command.save_to_history:
            return None

        try:
            self._action_plan_saver(
                command.supabase_client,
                command.user_id,
                action_plan,
                command.generation_model,
            )
        except AnalysisPersistenceError as exc:
            return str(exc)
        return None

