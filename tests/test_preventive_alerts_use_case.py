from __future__ import annotations

from typing import Any

from synapse_ai.application.analysis import PreventiveAlertsCommand, PreventiveAlertsUseCase
from synapse_ai.application.analysis.preventive_alerts import (
    PREVENTIVE_ALERTS_QUERY,
    PREVENTIVE_ALERTS_SOURCE_LIMIT,
)
from synapse_ai.application.result import ResultSeverity
from synapse_ai.services.alert_service import (
    AlertGenerationError,
    PreventiveAlert,
    PreventiveAlertReport,
)
from synapse_ai.services.analysis_repository import AnalysisPersistenceError
from synapse_ai.services.analysis_service import AnalysisGenerationError, SourceSnippet
from synapse_ai.services.embedding_service import EmbeddingGenerationError


class FakeSemanticRetriever:
    def __init__(self, sources: list[SourceSnippet] | None = None, fail: bool = False) -> None:
        self.sources = sources if sources is not None else [_source()]
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    def retrieve(
        self,
        *,
        supabase_client: Any,
        openai_client: Any,
        user_id: str,
        query: str,
        embedding_model: str,
        selected_document_ids: list[str],
        limit: int = 5,
    ) -> list[SourceSnippet]:
        if self.fail:
            raise EmbeddingGenerationError("Não foi possível gerar embeddings.")
        self.calls.append(
            {
                "supabase_client": supabase_client,
                "openai_client": openai_client,
                "user_id": user_id,
                "query": query,
                "embedding_model": embedding_model,
                "selected_document_ids": selected_document_ids,
                "limit": limit,
            }
        )
        return self.sources


class FakeDependencies:
    def __init__(
        self,
        sources: list[SourceSnippet] | None = None,
        retrieval_fail: bool = False,
        generation_fail: bool = False,
        no_alerts: bool = False,
        analysis_generation_fail: bool = False,
        persistence_fail: bool = False,
    ) -> None:
        self.retriever = FakeSemanticRetriever(sources=sources, fail=retrieval_fail)
        self.generation_fail = generation_fail
        self.no_alerts = no_alerts
        self.analysis_generation_fail = analysis_generation_fail
        self.persistence_fail = persistence_fail
        self.generated_with_sources: list[SourceSnippet] | None = None
        self.generated_with_model: str | None = None
        self.saved = False

    def generate_preventive_alert_report(
        self,
        _client: Any,
        sources: list[SourceSnippet],
        model: str,
    ) -> PreventiveAlertReport:
        if self.analysis_generation_fail:
            raise AnalysisGenerationError("Não foi possível gerar a resposta com IA.")
        if self.no_alerts:
            raise AlertGenerationError(
                "A IA não encontrou alertas preventivos claros nos documentos selecionados."
            )
        if self.generation_fail:
            raise AlertGenerationError("Não foi possível gerar alertas preventivos.")
        self.generated_with_sources = sources
        self.generated_with_model = model
        return _report(sources)

    def save_preventive_alert_report(
        self,
        _client: Any,
        _user_id: str,
        _report: PreventiveAlertReport,
        _generation_model: str,
    ) -> dict[str, Any]:
        if self.persistence_fail:
            raise AnalysisPersistenceError("Não foi possível salvar os alertas preventivos.")
        self.saved = True
        return {"id": "analysis-1"}


def test_preventive_alerts_use_case_generates_report_successfully() -> None:
    deps = FakeDependencies()
    result = _build_use_case(deps).execute(_command(save_to_history=False))

    assert result.success is True
    assert result.value is not None
    assert result.value.report.alerts[0].title == "Prazo crítico para aprovação"
    assert result.value.saved_to_history is False
    assert result.value.persistence_warning is None
    assert deps.generated_with_sources == [_source()]
    assert deps.generated_with_model == "gpt-5-mini"
    assert deps.saved is False
    assert deps.retriever.calls[0]["query"] == PREVENTIVE_ALERTS_QUERY
    assert deps.retriever.calls[0]["limit"] == PREVENTIVE_ALERTS_SOURCE_LIMIT
    assert deps.retriever.calls[0]["selected_document_ids"] == ["doc-1"]


def test_preventive_alerts_use_case_returns_info_when_sources_are_missing() -> None:
    deps = FakeDependencies(sources=[])
    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.INFO
    assert result.message == (
        "Nenhum trecho relevante foi encontrado. "
        "Atualize a base semântica antes de gerar alertas preventivos."
    )
    assert deps.generated_with_sources is None


def test_preventive_alerts_use_case_returns_error_for_known_retrieval_errors() -> None:
    deps = FakeDependencies(retrieval_fail=True)
    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.ERROR
    assert result.message == "Não foi possível gerar embeddings."
    assert deps.generated_with_sources is None


def test_preventive_alerts_use_case_returns_error_when_no_alerts_are_found() -> None:
    deps = FakeDependencies(no_alerts=True)
    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.ERROR
    assert result.message == (
        "A IA não encontrou alertas preventivos claros nos documentos selecionados."
    )


def test_preventive_alerts_use_case_returns_error_for_known_generation_errors() -> None:
    deps = FakeDependencies(generation_fail=True)
    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.ERROR
    assert result.message == "Não foi possível gerar alertas preventivos."


def test_preventive_alerts_use_case_returns_error_for_known_analysis_errors() -> None:
    deps = FakeDependencies(analysis_generation_fail=True)
    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.ERROR
    assert result.message == "Não foi possível gerar a resposta com IA."


def test_preventive_alerts_use_case_saves_when_requested() -> None:
    deps = FakeDependencies()
    result = _build_use_case(deps).execute(_command(save_to_history=True))

    assert result.success is True
    assert result.value is not None
    assert result.value.saved_to_history is True
    assert result.value.persistence_warning is None
    assert deps.saved is True


def test_preventive_alerts_use_case_keeps_report_when_persistence_fails() -> None:
    deps = FakeDependencies(persistence_fail=True)
    result = _build_use_case(deps).execute(_command(save_to_history=True))

    assert result.success is True
    assert result.value is not None
    assert result.value.saved_to_history is False
    assert result.value.persistence_warning == "Não foi possível salvar os alertas preventivos."
    assert result.value.report.alerts[0].title == "Prazo crítico para aprovação"


def _build_use_case(deps: FakeDependencies) -> PreventiveAlertsUseCase:
    return PreventiveAlertsUseCase(
        semantic_retriever=deps.retriever,
        preventive_alert_report_generator=deps.generate_preventive_alert_report,
        preventive_alert_report_saver=deps.save_preventive_alert_report,
    )


def _command(save_to_history: bool = False) -> PreventiveAlertsCommand:
    return PreventiveAlertsCommand(
        supabase_client=object(),
        openai_client=object(),
        user_id="user-1",
        embedding_model="text-embedding-3-small",
        generation_model="gpt-5-mini",
        save_to_history=save_to_history,
        selected_document_ids=["doc-1"],
    )


def _source() -> SourceSnippet:
    return SourceSnippet(
        document_id="doc-1",
        filename="ata.pdf",
        chunk_index=0,
        content="A aprovação financeira está pendente e próxima do prazo limite.",
        similarity=0.91,
    )


def _report(sources: list[SourceSnippet]) -> PreventiveAlertReport:
    return PreventiveAlertReport(
        executive_summary="Há risco preventivo por prazo crítico.",
        alerts=[
            PreventiveAlert(
                alert_type="Prazo",
                title="Prazo crítico para aprovação",
                severity="Crítica",
                status="Aberto",
                trigger="Aprovação pendente próxima do limite.",
                evidence="Aprovação exigida até 30/07/2026.",
                impact="Risco de atraso no lançamento.",
                recommendation="Escalar validação com Financeiro.",
                owner="Financeiro",
                deadline="30/07/2026",
                source_refs=["Fonte 1"],
            )
        ],
        sources=sources,
    )

