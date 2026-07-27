from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from synapse_ai.application.interfaces import (
    HistoricalAnalysisLoader,
    MultiAgentReportGenerator,
    MultiAgentReportSaver,
    SemanticSourceRetriever,
)
from synapse_ai.application.result import ResultSeverity, UseCaseResult
from synapse_ai.services.agent_service import AgentOrchestrationError, MultiAgentReport
from synapse_ai.services.analysis_repository import AnalysisPersistenceError
from synapse_ai.services.analysis_service import AnalysisGenerationError
from synapse_ai.services.chunk_repository import ChunkPersistenceError
from synapse_ai.services.embedding_service import EmbeddingGenerationError

MULTI_AGENT_REPORT_QUERY = (
    "decisões, riscos, inconsistências, sentimentos, governança, responsáveis, prazos, "
    "evidências, recomendações, padrões históricos e lacunas de auditoria"
)
MULTI_AGENT_REPORT_SOURCE_LIMIT = 14
MULTI_AGENT_HISTORY_LIMIT = 30


@dataclass(frozen=True)
class MultiAgentReportCommand:
    """Input data required to generate a multi-agent report."""

    supabase_client: Any
    openai_client: Any
    user_id: str
    embedding_model: str
    generation_model: str
    save_to_history: bool
    selected_document_ids: list[str]


@dataclass(frozen=True)
class MultiAgentReportOutput:
    """Successful output of the multi-agent report use case."""

    report: MultiAgentReport
    saved_to_history: bool
    persistence_warning: str | None = None


class MultiAgentReportUseCase:
    """Orchestrates history loading, semantic retrieval, generation and persistence."""

    def __init__(
        self,
        historical_analysis_loader: HistoricalAnalysisLoader,
        semantic_retriever: SemanticSourceRetriever,
        multi_agent_report_generator: MultiAgentReportGenerator,
        multi_agent_report_saver: MultiAgentReportSaver,
    ) -> None:
        self._historical_analysis_loader = historical_analysis_loader
        self._semantic_retriever = semantic_retriever
        self._multi_agent_report_generator = multi_agent_report_generator
        self._multi_agent_report_saver = multi_agent_report_saver

    def execute(
        self,
        command: MultiAgentReportCommand,
    ) -> UseCaseResult[MultiAgentReportOutput]:
        validation_message = _validate_command(command)
        if validation_message:
            return UseCaseResult.fail(validation_message, ResultSeverity.WARNING)

        historical_analyses = self._historical_analysis_loader(
            command.supabase_client,
            command.user_id,
            limit=MULTI_AGENT_HISTORY_LIMIT,
        )

        try:
            sources = self._semantic_retriever.retrieve(
                supabase_client=command.supabase_client,
                openai_client=command.openai_client,
                user_id=command.user_id,
                query=MULTI_AGENT_REPORT_QUERY,
                embedding_model=command.embedding_model,
                selected_document_ids=command.selected_document_ids,
                limit=MULTI_AGENT_REPORT_SOURCE_LIMIT,
            )
            if not sources:
                return UseCaseResult.fail(
                    "Nenhum trecho relevante foi encontrado. "
                    "Atualize a base semântica antes de executar os agentes.",
                    ResultSeverity.INFO,
                )

            report = self._multi_agent_report_generator(
                command.openai_client,
                sources,
                historical_analyses,
                command.generation_model,
            )
        except (
            AgentOrchestrationError,
            AnalysisGenerationError,
            ChunkPersistenceError,
            EmbeddingGenerationError,
        ) as exc:
            return UseCaseResult.fail(str(exc), ResultSeverity.ERROR)

        persistence_warning = self._persist_if_requested(command, report)
        return UseCaseResult.ok(
            MultiAgentReportOutput(
                report=report,
                saved_to_history=command.save_to_history and persistence_warning is None,
                persistence_warning=persistence_warning,
            )
        )

    def _persist_if_requested(
        self,
        command: MultiAgentReportCommand,
        report: MultiAgentReport,
    ) -> str | None:
        if not command.save_to_history:
            return None

        try:
            self._multi_agent_report_saver(
                command.supabase_client,
                command.user_id,
                report,
                command.generation_model,
            )
        except AnalysisPersistenceError as exc:
            return str(exc)
        return None


def _validate_command(command: MultiAgentReportCommand) -> str:
    if not command.user_id.strip():
        return "Não conseguimos confirmar sua conta nesta aba. Atualize a página para continuar."
    if not command.selected_document_ids:
        return "Selecione pelo menos um documento para definir o escopo da análise."
    return ""
