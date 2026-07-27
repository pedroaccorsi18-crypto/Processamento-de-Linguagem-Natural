from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from synapse_ai.application.interfaces import (
    HistoricalAnalysisLoader,
    HistoricalPatternReportGenerator,
    HistoricalPatternReportSaver,
    SemanticSourceRetriever,
)
from synapse_ai.application.result import ResultSeverity, UseCaseResult
from synapse_ai.services.analysis_repository import AnalysisPersistenceError
from synapse_ai.services.analysis_service import AnalysisGenerationError
from synapse_ai.services.chunk_repository import ChunkPersistenceError
from synapse_ai.services.embedding_service import EmbeddingGenerationError
from synapse_ai.services.pattern_service import HistoricalPatternReport, PatternGenerationError

HISTORICAL_PATTERNS_QUERY = (
    "padrões históricos, recorrência, riscos repetidos, atrasos recorrentes, orçamento "
    "pendente, responsáveis ausentes, tensão comunicacional, inconsistências repetidas "
    "e decisões conflitantes"
)
HISTORICAL_PATTERNS_SOURCE_LIMIT = 12
HISTORICAL_ANALYSES_LIMIT = 30


@dataclass(frozen=True)
class HistoricalPatternsCommand:
    """Input data required to recognize historical patterns."""

    supabase_client: Any
    openai_client: Any
    user_id: str
    embedding_model: str
    generation_model: str
    save_to_history: bool
    selected_document_ids: list[str]


@dataclass(frozen=True)
class HistoricalPatternsOutput:
    """Successful output of the historical-patterns use case."""

    report: HistoricalPatternReport
    saved_to_history: bool
    persistence_warning: str | None = None


class HistoricalPatternsUseCase:
    """Orchestrates history loading, semantic retrieval, generation and persistence."""

    def __init__(
        self,
        historical_analysis_loader: HistoricalAnalysisLoader,
        semantic_retriever: SemanticSourceRetriever,
        historical_pattern_report_generator: HistoricalPatternReportGenerator,
        historical_pattern_report_saver: HistoricalPatternReportSaver,
    ) -> None:
        self._historical_analysis_loader = historical_analysis_loader
        self._semantic_retriever = semantic_retriever
        self._historical_pattern_report_generator = historical_pattern_report_generator
        self._historical_pattern_report_saver = historical_pattern_report_saver

    def execute(
        self,
        command: HistoricalPatternsCommand,
    ) -> UseCaseResult[HistoricalPatternsOutput]:
        historical_analyses = self._historical_analysis_loader(
            command.supabase_client,
            command.user_id,
            limit=HISTORICAL_ANALYSES_LIMIT,
        )

        try:
            sources = self._semantic_retriever.retrieve(
                supabase_client=command.supabase_client,
                openai_client=command.openai_client,
                user_id=command.user_id,
                query=HISTORICAL_PATTERNS_QUERY,
                embedding_model=command.embedding_model,
                selected_document_ids=command.selected_document_ids,
                limit=HISTORICAL_PATTERNS_SOURCE_LIMIT,
            )
            if not sources:
                return UseCaseResult.fail(
                    "Nenhum trecho relevante foi encontrado. "
                    "Atualize a base semântica antes de reconhecer padrões históricos.",
                    ResultSeverity.INFO,
                )

            report = self._historical_pattern_report_generator(
                command.openai_client,
                sources,
                historical_analyses,
                command.generation_model,
            )
        except (
            AnalysisGenerationError,
            ChunkPersistenceError,
            EmbeddingGenerationError,
            PatternGenerationError,
        ) as exc:
            return UseCaseResult.fail(str(exc), ResultSeverity.ERROR)

        persistence_warning = self._persist_if_requested(command, report)
        return UseCaseResult.ok(
            HistoricalPatternsOutput(
                report=report,
                saved_to_history=command.save_to_history and persistence_warning is None,
                persistence_warning=persistence_warning,
            )
        )

    def _persist_if_requested(
        self,
        command: HistoricalPatternsCommand,
        report: HistoricalPatternReport,
    ) -> str | None:
        if not command.save_to_history:
            return None

        try:
            self._historical_pattern_report_saver(
                command.supabase_client,
                command.user_id,
                report,
                command.generation_model,
            )
        except AnalysisPersistenceError as exc:
            return str(exc)
        return None

