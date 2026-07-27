from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from synapse_ai.application.interfaces import (
    DocumentComparisonGenerator,
    DocumentComparisonSaver,
    SemanticSourceRetriever,
)
from synapse_ai.application.result import ResultSeverity, UseCaseResult
from synapse_ai.services.analysis_repository import AnalysisPersistenceError
from synapse_ai.services.analysis_service import AnalysisGenerationError
from synapse_ai.services.chunk_repository import ChunkPersistenceError
from synapse_ai.services.comparison_service import (
    ComparisonGenerationError,
    DocumentComparisonReport,
)
from synapse_ai.services.embedding_service import EmbeddingGenerationError

DOCUMENT_COMPARISON_QUERY = (
    "comparar documentos, datas conflitantes, decisões divergentes, responsáveis diferentes, "
    "riscos omitidos, mudanças de cronograma, escopo inconsistente e evidências conflitantes"
)
DOCUMENT_COMPARISON_SOURCE_LIMIT = 12


@dataclass(frozen=True)
class DocumentComparisonCommand:
    """Input data required to compare selected documents."""

    supabase_client: Any
    openai_client: Any
    user_id: str
    embedding_model: str
    generation_model: str
    save_to_history: bool
    selected_document_ids: list[str]


@dataclass(frozen=True)
class DocumentComparisonOutput:
    """Successful output of the document-comparison use case."""

    report: DocumentComparisonReport
    saved_to_history: bool
    persistence_warning: str | None = None


class DocumentComparisonUseCase:
    """Orchestrates semantic retrieval, document comparison and optional persistence."""

    def __init__(
        self,
        semantic_retriever: SemanticSourceRetriever,
        document_comparison_generator: DocumentComparisonGenerator,
        document_comparison_saver: DocumentComparisonSaver,
    ) -> None:
        self._semantic_retriever = semantic_retriever
        self._document_comparison_generator = document_comparison_generator
        self._document_comparison_saver = document_comparison_saver

    def execute(
        self,
        command: DocumentComparisonCommand,
    ) -> UseCaseResult[DocumentComparisonOutput]:
        if len(set(command.selected_document_ids)) < 2:
            return UseCaseResult.fail(
                "Selecione pelo menos dois documentos para executar a comparação documental.",
                ResultSeverity.WARNING,
            )

        try:
            sources = self._semantic_retriever.retrieve(
                supabase_client=command.supabase_client,
                openai_client=command.openai_client,
                user_id=command.user_id,
                query=DOCUMENT_COMPARISON_QUERY,
                embedding_model=command.embedding_model,
                selected_document_ids=command.selected_document_ids,
                limit=DOCUMENT_COMPARISON_SOURCE_LIMIT,
            )
            if not sources:
                return UseCaseResult.fail(
                    "Nenhum trecho relevante foi encontrado. "
                    "Atualize a base semântica antes de comparar os documentos.",
                    ResultSeverity.INFO,
                )

            report = self._document_comparison_generator(
                command.openai_client,
                sources,
                command.generation_model,
            )
        except (
            AnalysisGenerationError,
            ChunkPersistenceError,
            ComparisonGenerationError,
            EmbeddingGenerationError,
        ) as exc:
            return UseCaseResult.fail(str(exc), ResultSeverity.ERROR)

        persistence_warning = self._persist_if_requested(command, report)
        return UseCaseResult.ok(
            DocumentComparisonOutput(
                report=report,
                saved_to_history=command.save_to_history and persistence_warning is None,
                persistence_warning=persistence_warning,
            )
        )

    def _persist_if_requested(
        self,
        command: DocumentComparisonCommand,
        report: DocumentComparisonReport,
    ) -> str | None:
        if not command.save_to_history:
            return None

        try:
            self._document_comparison_saver(
                command.supabase_client,
                command.user_id,
                report,
                command.generation_model,
            )
        except AnalysisPersistenceError as exc:
            return str(exc)
        return None

