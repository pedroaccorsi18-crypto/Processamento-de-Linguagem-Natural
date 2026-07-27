from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from synapse_ai.application.interfaces import (
    SemanticSourceRetriever,
    SentimentReportGenerator,
    SentimentReportSaver,
)
from synapse_ai.application.result import ResultSeverity, UseCaseResult
from synapse_ai.services.analysis_repository import AnalysisPersistenceError
from synapse_ai.services.analysis_service import AnalysisGenerationError
from synapse_ai.services.chunk_repository import ChunkPersistenceError
from synapse_ai.services.embedding_service import EmbeddingGenerationError
from synapse_ai.services.sentiment_service import SentimentGenerationError, SentimentReport

SENTIMENT_ANALYSIS_QUERY = (
    "sentimento organizacional, tom comunicacional, urgência, tensão, confiança, conflito, "
    "frustração, alinhamento, risco percebido e sinais emocionais em documentos corporativos"
)
SENTIMENT_ANALYSIS_SOURCE_LIMIT = 10


@dataclass(frozen=True)
class SentimentAnalysisCommand:
    """Input data required to generate an organizational sentiment analysis."""

    supabase_client: Any
    openai_client: Any
    user_id: str
    embedding_model: str
    generation_model: str
    save_to_history: bool
    selected_document_ids: list[str]


@dataclass(frozen=True)
class SentimentAnalysisOutput:
    """Successful output of the sentiment-analysis use case."""

    report: SentimentReport
    saved_to_history: bool
    persistence_warning: str | None = None


class SentimentAnalysisUseCase:
    """Orchestrates semantic retrieval, sentiment generation and optional persistence."""

    def __init__(
        self,
        semantic_retriever: SemanticSourceRetriever,
        sentiment_report_generator: SentimentReportGenerator,
        sentiment_report_saver: SentimentReportSaver,
    ) -> None:
        self._semantic_retriever = semantic_retriever
        self._sentiment_report_generator = sentiment_report_generator
        self._sentiment_report_saver = sentiment_report_saver

    def execute(
        self,
        command: SentimentAnalysisCommand,
    ) -> UseCaseResult[SentimentAnalysisOutput]:
        try:
            sources = self._semantic_retriever.retrieve(
                supabase_client=command.supabase_client,
                openai_client=command.openai_client,
                user_id=command.user_id,
                query=SENTIMENT_ANALYSIS_QUERY,
                embedding_model=command.embedding_model,
                selected_document_ids=command.selected_document_ids,
                limit=SENTIMENT_ANALYSIS_SOURCE_LIMIT,
            )
            if not sources:
                return UseCaseResult.fail(
                    "Nenhum trecho relevante foi encontrado. "
                    "Atualize a base semântica antes de analisar sentimentos.",
                    ResultSeverity.INFO,
                )

            report = self._sentiment_report_generator(
                command.openai_client,
                sources,
                command.generation_model,
            )
        except (
            AnalysisGenerationError,
            ChunkPersistenceError,
            EmbeddingGenerationError,
            SentimentGenerationError,
        ) as exc:
            return UseCaseResult.fail(str(exc), ResultSeverity.ERROR)

        persistence_warning = self._persist_if_requested(command, report)
        return UseCaseResult.ok(
            SentimentAnalysisOutput(
                report=report,
                saved_to_history=command.save_to_history and persistence_warning is None,
                persistence_warning=persistence_warning,
            )
        )

    def _persist_if_requested(
        self,
        command: SentimentAnalysisCommand,
        report: SentimentReport,
    ) -> str | None:
        if not command.save_to_history:
            return None

        try:
            self._sentiment_report_saver(
                command.supabase_client,
                command.user_id,
                report,
                command.generation_model,
            )
        except AnalysisPersistenceError as exc:
            return str(exc)
        return None

