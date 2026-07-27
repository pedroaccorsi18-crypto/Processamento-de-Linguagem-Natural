from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from synapse_ai.application.interfaces import (
    IntelligentExecutiveReportGenerator,
    SemanticSourceRetriever,
)
from synapse_ai.application.result import ResultSeverity, UseCaseResult
from synapse_ai.services.analysis_service import AnalysisGenerationError
from synapse_ai.services.chunk_repository import ChunkPersistenceError
from synapse_ai.services.embedding_service import EmbeddingGenerationError
from synapse_ai.services.report_service import IntelligentExecutiveReport, ReportGenerationError

INTELLIGENT_EXECUTIVE_REPORT_QUERY = (
    "decisões, riscos, inconsistências, responsáveis, prazos, pendências, recomendações, "
    "impactos, evidências e plano de ação executivo"
)
INTELLIGENT_EXECUTIVE_REPORT_SOURCE_LIMIT = 10


@dataclass(frozen=True)
class IntelligentExecutiveReportCommand:
    """Input data required to generate an intelligent executive report."""

    supabase_client: Any
    openai_client: Any
    user_id: str
    documents: list[dict[str, Any]]
    analyses: list[dict[str, Any]]
    prepared_document_ids: list[str]
    embedding_model: str
    generation_model: str


@dataclass(frozen=True)
class IntelligentExecutiveReportOutput:
    """Successful output of intelligent executive report generation."""

    report: IntelligentExecutiveReport


class IntelligentExecutiveReportUseCase:
    """Orchestrates semantic retrieval and intelligent executive report generation."""

    def __init__(
        self,
        semantic_retriever: SemanticSourceRetriever,
        intelligent_executive_report_generator: IntelligentExecutiveReportGenerator,
    ) -> None:
        self._semantic_retriever = semantic_retriever
        self._intelligent_executive_report_generator = intelligent_executive_report_generator

    def execute(
        self,
        command: IntelligentExecutiveReportCommand,
    ) -> UseCaseResult[IntelligentExecutiveReportOutput]:
        validation_message = _validate_command(command)
        if validation_message:
            return UseCaseResult.fail(validation_message, ResultSeverity.INFO)

        try:
            sources = self._semantic_retriever.retrieve(
                supabase_client=command.supabase_client,
                openai_client=command.openai_client,
                user_id=command.user_id,
                query=INTELLIGENT_EXECUTIVE_REPORT_QUERY,
                embedding_model=command.embedding_model,
                selected_document_ids=command.prepared_document_ids,
                limit=INTELLIGENT_EXECUTIVE_REPORT_SOURCE_LIMIT,
            )
            if not sources:
                return UseCaseResult.fail(
                    "Nenhuma evidência relevante foi encontrada para compor o relatório.",
                    ResultSeverity.INFO,
                )

            report = self._intelligent_executive_report_generator(
                command.openai_client,
                sources,
                command.documents,
                command.analyses,
                command.generation_model,
            )
        except (
            AnalysisGenerationError,
            ChunkPersistenceError,
            EmbeddingGenerationError,
            ReportGenerationError,
        ) as exc:
            return UseCaseResult.fail(str(exc), ResultSeverity.ERROR)

        return UseCaseResult.ok(IntelligentExecutiveReportOutput(report=report))


def _validate_command(command: IntelligentExecutiveReportCommand) -> str:
    if not command.user_id.strip():
        return "Não conseguimos confirmar sua conta nesta aba. Atualize a página para continuar."
    if not command.prepared_document_ids:
        return "Prepare ao menos um documento para IA antes de gerar o relatório inteligente."
    return ""
