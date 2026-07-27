from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from synapse_ai.application.interfaces import (
    PreventiveAlertReportGenerator,
    PreventiveAlertReportSaver,
    SemanticSourceRetriever,
)
from synapse_ai.application.result import ResultSeverity, UseCaseResult
from synapse_ai.services.alert_service import AlertGenerationError, PreventiveAlertReport
from synapse_ai.services.analysis_repository import AnalysisPersistenceError
from synapse_ai.services.analysis_service import AnalysisGenerationError
from synapse_ai.services.chunk_repository import ChunkPersistenceError
from synapse_ai.services.embedding_service import EmbeddingGenerationError

PREVENTIVE_ALERTS_QUERY = (
    "alertas preventivos, prazo crítico, risco alto, orçamento pendente, responsável ausente, "
    "decisão conflitante, mudança de cronograma, dependência externa, comunicação crítica "
    "e lacuna de evidência"
)
PREVENTIVE_ALERTS_SOURCE_LIMIT = 12


@dataclass(frozen=True)
class PreventiveAlertsCommand:
    """Input data required to generate preventive alerts."""

    supabase_client: Any
    openai_client: Any
    user_id: str
    embedding_model: str
    generation_model: str
    save_to_history: bool
    selected_document_ids: list[str]


@dataclass(frozen=True)
class PreventiveAlertsOutput:
    """Successful output of the preventive-alerts use case."""

    report: PreventiveAlertReport
    saved_to_history: bool
    persistence_warning: str | None = None


class PreventiveAlertsUseCase:
    """Orchestrates semantic retrieval, preventive-alert generation and optional persistence."""

    def __init__(
        self,
        semantic_retriever: SemanticSourceRetriever,
        preventive_alert_report_generator: PreventiveAlertReportGenerator,
        preventive_alert_report_saver: PreventiveAlertReportSaver,
    ) -> None:
        self._semantic_retriever = semantic_retriever
        self._preventive_alert_report_generator = preventive_alert_report_generator
        self._preventive_alert_report_saver = preventive_alert_report_saver

    def execute(self, command: PreventiveAlertsCommand) -> UseCaseResult[PreventiveAlertsOutput]:
        try:
            sources = self._semantic_retriever.retrieve(
                supabase_client=command.supabase_client,
                openai_client=command.openai_client,
                user_id=command.user_id,
                query=PREVENTIVE_ALERTS_QUERY,
                embedding_model=command.embedding_model,
                selected_document_ids=command.selected_document_ids,
                limit=PREVENTIVE_ALERTS_SOURCE_LIMIT,
            )
            if not sources:
                return UseCaseResult.fail(
                    "Nenhum trecho relevante foi encontrado. "
                    "Atualize a base semântica antes de gerar alertas preventivos.",
                    ResultSeverity.INFO,
                )

            report = self._preventive_alert_report_generator(
                command.openai_client,
                sources,
                command.generation_model,
            )
        except (
            AlertGenerationError,
            AnalysisGenerationError,
            ChunkPersistenceError,
            EmbeddingGenerationError,
        ) as exc:
            return UseCaseResult.fail(str(exc), ResultSeverity.ERROR)

        persistence_warning = self._persist_if_requested(command, report)
        return UseCaseResult.ok(
            PreventiveAlertsOutput(
                report=report,
                saved_to_history=command.save_to_history and persistence_warning is None,
                persistence_warning=persistence_warning,
            )
        )

    def _persist_if_requested(
        self,
        command: PreventiveAlertsCommand,
        report: PreventiveAlertReport,
    ) -> str | None:
        if not command.save_to_history:
            return None

        try:
            self._preventive_alert_report_saver(
                command.supabase_client,
                command.user_id,
                report,
                command.generation_model,
            )
        except AnalysisPersistenceError as exc:
            return str(exc)
        return None

