from __future__ import annotations

from typing import Any

from synapse_ai.application.analysis import HistoricalPatternsCommand, HistoricalPatternsUseCase
from synapse_ai.application.analysis.historical_patterns import (
    HISTORICAL_ANALYSES_LIMIT,
    HISTORICAL_PATTERNS_QUERY,
    HISTORICAL_PATTERNS_SOURCE_LIMIT,
)
from synapse_ai.application.result import ResultSeverity
from synapse_ai.services.analysis_repository import AnalysisPersistenceError
from synapse_ai.services.analysis_service import AnalysisGenerationError, SourceSnippet
from synapse_ai.services.embedding_service import EmbeddingGenerationError
from synapse_ai.services.pattern_service import (
    HistoricalPattern,
    HistoricalPatternReport,
    PatternGenerationError,
)


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
        historical_analyses: list[dict[str, Any]] | None = None,
        sources: list[SourceSnippet] | None = None,
        retrieval_fail: bool = False,
        no_patterns: bool = False,
        insufficient_history: bool = False,
        analysis_generation_fail: bool = False,
        persistence_fail: bool = False,
    ) -> None:
        self.historical_analyses = historical_analyses if historical_analyses is not None else [
            _historical_record("1"),
            _historical_record("2"),
        ]
        self.retriever = FakeSemanticRetriever(sources=sources, fail=retrieval_fail)
        self.no_patterns = no_patterns
        self.insufficient_history = insufficient_history
        self.analysis_generation_fail = analysis_generation_fail
        self.persistence_fail = persistence_fail
        self.loader_calls: list[dict[str, Any]] = []
        self.generated_with_sources: list[SourceSnippet] | None = None
        self.generated_with_history: list[dict[str, Any]] | None = None
        self.generated_with_model: str | None = None
        self.saved = False
        self.events: list[str] = []

    def load_historical_analyses(
        self,
        _client: Any,
        user_id: str,
        /,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        self.events.append("load_history")
        self.loader_calls.append({"user_id": user_id, "limit": limit})
        return self.historical_analyses

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
        self.events.append("retrieve_sources")
        return self.retriever.retrieve(
            supabase_client=supabase_client,
            openai_client=openai_client,
            user_id=user_id,
            query=query,
            embedding_model=embedding_model,
            selected_document_ids=selected_document_ids,
            limit=limit,
        )

    def generate_historical_pattern_report(
        self,
        _client: Any,
        current_sources: list[SourceSnippet],
        historical_analyses: list[dict[str, Any]],
        model: str,
    ) -> HistoricalPatternReport:
        self.events.append("generate_report")
        if self.analysis_generation_fail:
            raise AnalysisGenerationError("Não foi possível gerar a resposta com IA.")
        if self.insufficient_history:
            raise PatternGenerationError(
                "Ainda não há histórico suficiente para reconhecer padrões recorrentes."
            )
        if self.no_patterns:
            raise PatternGenerationError(
                "A IA não encontrou padrões históricos claros para o escopo selecionado."
            )
        self.generated_with_sources = current_sources
        self.generated_with_history = historical_analyses
        self.generated_with_model = model
        return _report(current_sources)

    def save_historical_pattern_report(
        self,
        _client: Any,
        _user_id: str,
        _report: HistoricalPatternReport,
        _generation_model: str,
    ) -> dict[str, Any]:
        self.events.append("save_report")
        if self.persistence_fail:
            raise AnalysisPersistenceError("Não foi possível salvar os padrões históricos.")
        self.saved = True
        return {"id": "analysis-1"}


def test_historical_patterns_use_case_generates_report_successfully() -> None:
    deps = FakeDependencies()
    result = _build_use_case(deps).execute(_command(save_to_history=False))

    assert result.success is True
    assert result.value is not None
    assert result.value.report.patterns[0].title == "Aprovação financeira recorrente"
    assert result.value.saved_to_history is False
    assert result.value.persistence_warning is None
    assert deps.loader_calls == [{"user_id": "user-1", "limit": HISTORICAL_ANALYSES_LIMIT}]
    assert deps.retriever.calls[0]["query"] == HISTORICAL_PATTERNS_QUERY
    assert deps.retriever.calls[0]["limit"] == HISTORICAL_PATTERNS_SOURCE_LIMIT
    assert deps.retriever.calls[0]["selected_document_ids"] == ["doc-1"]
    assert deps.generated_with_sources == [_source()]
    assert deps.generated_with_history == [_historical_record("1"), _historical_record("2")]
    assert deps.generated_with_model == "gpt-5-mini"
    assert deps.events == ["load_history", "retrieve_sources", "generate_report"]


def test_historical_patterns_use_case_returns_info_when_sources_are_missing() -> None:
    deps = FakeDependencies(sources=[])
    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.INFO
    assert result.message == (
        "Nenhum trecho relevante foi encontrado. "
        "Atualize a base semântica antes de reconhecer padrões históricos."
    )
    assert deps.generated_with_sources is None
    assert deps.events == ["load_history", "retrieve_sources"]


def test_historical_patterns_use_case_returns_error_for_insufficient_history() -> None:
    deps = FakeDependencies(historical_analyses=[], insufficient_history=True)
    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.ERROR
    assert result.message == (
        "Ainda não há histórico suficiente para reconhecer padrões recorrentes."
    )
    assert deps.events == ["load_history", "retrieve_sources", "generate_report"]


def test_historical_patterns_use_case_returns_error_when_no_patterns_are_found() -> None:
    deps = FakeDependencies(no_patterns=True)
    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.ERROR
    assert result.message == (
        "A IA não encontrou padrões históricos claros para o escopo selecionado."
    )


def test_historical_patterns_use_case_returns_error_for_known_retrieval_errors() -> None:
    deps = FakeDependencies(retrieval_fail=True)
    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.ERROR
    assert result.message == "Não foi possível gerar embeddings."
    assert deps.generated_with_sources is None


def test_historical_patterns_use_case_returns_error_for_known_generation_errors() -> None:
    deps = FakeDependencies(analysis_generation_fail=True)
    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.ERROR
    assert result.message == "Não foi possível gerar a resposta com IA."


def test_historical_patterns_use_case_saves_when_requested() -> None:
    deps = FakeDependencies()
    result = _build_use_case(deps).execute(_command(save_to_history=True))

    assert result.success is True
    assert result.value is not None
    assert result.value.saved_to_history is True
    assert result.value.persistence_warning is None
    assert deps.saved is True
    assert deps.events == ["load_history", "retrieve_sources", "generate_report", "save_report"]


def test_historical_patterns_use_case_keeps_report_when_persistence_fails() -> None:
    deps = FakeDependencies(persistence_fail=True)
    result = _build_use_case(deps).execute(_command(save_to_history=True))

    assert result.success is True
    assert result.value is not None
    assert result.value.saved_to_history is False
    assert result.value.persistence_warning == "Não foi possível salvar os padrões históricos."
    assert result.value.report.patterns[0].title == "Aprovação financeira recorrente"


def _build_use_case(deps: FakeDependencies) -> HistoricalPatternsUseCase:
    return HistoricalPatternsUseCase(
        historical_analysis_loader=deps.load_historical_analyses,
        semantic_retriever=deps,
        historical_pattern_report_generator=deps.generate_historical_pattern_report,
        historical_pattern_report_saver=deps.save_historical_pattern_report,
    )


def _command(save_to_history: bool = False) -> HistoricalPatternsCommand:
    return HistoricalPatternsCommand(
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
        content="Orçamento pendente e reprogramação de prazo.",
        similarity=0.91,
    )


def _historical_record(identifier: str) -> dict[str, Any]:
    return {
        "id": f"analysis-{identifier}",
        "title": f"Registro {identifier}",
        "created_at": f"2026-07-2{identifier}T10:00:00",
        "metadata": {
            "artifact_type": "preventive_alert_report",
            "alerts": [{"title": "Aprovação financeira pendente"}],
        },
    }


def _report(sources: list[SourceSnippet]) -> HistoricalPatternReport:
    return HistoricalPatternReport(
        executive_summary="Há recorrência de risco financeiro.",
        historical_record_count=2,
        patterns=[
            HistoricalPattern(
                pattern_type="Orçamento",
                title="Aprovação financeira recorrente",
                recurrence="Aparece no escopo atual e no histórico recente.",
                severity="Alta",
                current_signal="Orçamento pendente.",
                historical_evidence="Alerta anterior citou aprovação financeira pendente.",
                interpretation="O gargalo financeiro voltou a aparecer.",
                recommendation="Criar validação financeira antecipada.",
                source_refs=["Fonte 1"],
                related_records=["Registro 1"],
            )
        ],
        sources=sources,
    )
