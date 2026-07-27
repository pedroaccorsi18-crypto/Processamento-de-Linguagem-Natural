from __future__ import annotations

from typing import Any

from synapse_ai.application.analysis import DocumentComparisonCommand, DocumentComparisonUseCase
from synapse_ai.application.analysis.document_comparison import (
    DOCUMENT_COMPARISON_QUERY,
    DOCUMENT_COMPARISON_SOURCE_LIMIT,
)
from synapse_ai.application.result import ResultSeverity
from synapse_ai.services.analysis_repository import AnalysisPersistenceError
from synapse_ai.services.analysis_service import AnalysisGenerationError, SourceSnippet
from synapse_ai.services.comparison_service import (
    ComparisonGenerationError,
    DocumentComparisonIssue,
    DocumentComparisonReport,
)
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
        analysis_generation_fail: bool = False,
        persistence_fail: bool = False,
    ) -> None:
        self.retriever = FakeSemanticRetriever(sources=sources, fail=retrieval_fail)
        self.generation_fail = generation_fail
        self.analysis_generation_fail = analysis_generation_fail
        self.persistence_fail = persistence_fail
        self.generated_with_sources: list[SourceSnippet] | None = None
        self.saved = False

    def generate_document_comparison(
        self,
        _client: Any,
        sources: list[SourceSnippet],
        _model: str,
    ) -> DocumentComparisonReport:
        if self.analysis_generation_fail:
            raise AnalysisGenerationError("Não foi possível gerar a resposta com IA.")
        if self.generation_fail:
            raise ComparisonGenerationError("Não foi possível comparar os documentos selecionados.")
        self.generated_with_sources = sources
        return _report(sources)

    def save_document_comparison(
        self,
        _client: Any,
        _user_id: str,
        _report: DocumentComparisonReport,
        _generation_model: str,
    ) -> dict[str, Any]:
        if self.persistence_fail:
            raise AnalysisPersistenceError("Não foi possível salvar a comparação documental.")
        self.saved = True
        return {"id": "analysis-1"}


def test_document_comparison_use_case_generates_report_successfully() -> None:
    deps = FakeDependencies()
    result = _build_use_case(deps).execute(_command(save_to_history=False))

    assert result.success is True
    assert result.value is not None
    assert result.value.report.issues[0].title == "Datas divergentes"
    assert result.value.saved_to_history is False
    assert result.value.persistence_warning is None
    assert deps.generated_with_sources == [_source()]
    assert deps.saved is False
    assert deps.retriever.calls[0]["query"] == DOCUMENT_COMPARISON_QUERY
    assert deps.retriever.calls[0]["limit"] == DOCUMENT_COMPARISON_SOURCE_LIMIT
    assert deps.retriever.calls[0]["selected_document_ids"] == ["doc-1", "doc-2"]


def test_document_comparison_use_case_requires_two_documents() -> None:
    deps = FakeDependencies()
    result = _build_use_case(deps).execute(_command(selected_document_ids=["doc-1"]))

    assert result.success is False
    assert result.severity == ResultSeverity.WARNING
    assert result.message == (
        "Selecione pelo menos dois documentos para executar a comparação documental."
    )
    assert deps.retriever.calls == []
    assert deps.generated_with_sources is None


def test_document_comparison_use_case_returns_info_when_sources_are_missing() -> None:
    deps = FakeDependencies(sources=[])
    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.INFO
    assert result.message == (
        "Nenhum trecho relevante foi encontrado. "
        "Atualize a base semântica antes de comparar os documentos."
    )
    assert deps.generated_with_sources is None


def test_document_comparison_use_case_returns_error_for_known_retrieval_errors() -> None:
    deps = FakeDependencies(retrieval_fail=True)
    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.ERROR
    assert result.message == "Não foi possível gerar embeddings."
    assert deps.generated_with_sources is None


def test_document_comparison_use_case_returns_error_for_known_generation_errors() -> None:
    deps = FakeDependencies(generation_fail=True)
    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.ERROR
    assert result.message == "Não foi possível comparar os documentos selecionados."


def test_document_comparison_use_case_returns_error_for_known_analysis_errors() -> None:
    deps = FakeDependencies(analysis_generation_fail=True)
    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.ERROR
    assert result.message == "Não foi possível gerar a resposta com IA."


def test_document_comparison_use_case_saves_when_requested() -> None:
    deps = FakeDependencies()
    result = _build_use_case(deps).execute(_command(save_to_history=True))

    assert result.success is True
    assert result.value is not None
    assert result.value.saved_to_history is True
    assert result.value.persistence_warning is None
    assert deps.saved is True


def test_document_comparison_use_case_keeps_report_when_persistence_fails() -> None:
    deps = FakeDependencies(persistence_fail=True)
    result = _build_use_case(deps).execute(_command(save_to_history=True))

    assert result.success is True
    assert result.value is not None
    assert result.value.saved_to_history is False
    assert result.value.persistence_warning == "Não foi possível salvar a comparação documental."
    assert result.value.report.issues[0].title == "Datas divergentes"


def _build_use_case(deps: FakeDependencies) -> DocumentComparisonUseCase:
    return DocumentComparisonUseCase(
        semantic_retriever=deps.retriever,
        document_comparison_generator=deps.generate_document_comparison,
        document_comparison_saver=deps.save_document_comparison,
    )


def _command(
    save_to_history: bool = False,
    selected_document_ids: list[str] | None = None,
) -> DocumentComparisonCommand:
    return DocumentComparisonCommand(
        supabase_client=object(),
        openai_client=object(),
        user_id="user-1",
        embedding_model="text-embedding-3-small",
        generation_model="gpt-5-mini",
        save_to_history=save_to_history,
        selected_document_ids=selected_document_ids or ["doc-1", "doc-2"],
    )


def _source() -> SourceSnippet:
    return SourceSnippet(
        document_id="doc-1",
        filename="ata.pdf",
        chunk_index=0,
        content="A data informada diverge de outro documento.",
        similarity=0.91,
    )


def _report(sources: list[SourceSnippet]) -> DocumentComparisonReport:
    return DocumentComparisonReport(
        executive_summary="Há divergência de cronograma.",
        issues=[
            DocumentComparisonIssue(
                issue_type="Cronograma",
                title="Datas divergentes",
                description="Um documento cita 15/08 e outro 22/08.",
                severity="Alta",
                documents=["ata.pdf", "email.pdf"],
                impact="Comunicação inconsistente.",
                evidence="15/08 versus 22/08.",
                recommendation="Confirmar data oficial.",
                source_refs=["Fonte 1", "Fonte 2"],
            )
        ],
        sources=sources,
    )
