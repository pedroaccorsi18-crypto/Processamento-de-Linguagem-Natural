from __future__ import annotations

from typing import Any

from synapse_ai.application.analysis import IntelligenceSnapshotCommand, IntelligenceSnapshotUseCase
from synapse_ai.application.analysis.intelligence_snapshot import (
    INTELLIGENCE_SNAPSHOT_QUERY,
    INTELLIGENCE_SNAPSHOT_SOURCE_LIMIT,
)
from synapse_ai.application.result import ResultSeverity
from synapse_ai.services.analysis_repository import AnalysisPersistenceError
from synapse_ai.services.analysis_service import AnalysisGenerationError, SourceSnippet
from synapse_ai.services.embedding_service import EmbeddingGenerationError
from synapse_ai.services.intelligence_service import (
    IntelligenceFinding,
    IntelligenceGenerationError,
    IntelligenceSnapshot,
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
        self.generated_with_model: str | None = None
        self.saved = False

    def generate_intelligence_snapshot(
        self,
        _client: Any,
        sources: list[SourceSnippet],
        model: str,
    ) -> IntelligenceSnapshot:
        if self.analysis_generation_fail:
            raise AnalysisGenerationError("Não foi possível gerar a resposta com IA.")
        if self.generation_fail:
            raise IntelligenceGenerationError(
                "Não foi possível gerar a inteligência organizacional."
            )
        self.generated_with_sources = sources
        self.generated_with_model = model
        return _snapshot(sources)

    def save_intelligence_snapshot(
        self,
        _client: Any,
        _user_id: str,
        _snapshot: IntelligenceSnapshot,
        _generation_model: str,
    ) -> dict[str, Any]:
        if self.persistence_fail:
            raise AnalysisPersistenceError("Não foi possível salvar a inteligência organizacional.")
        self.saved = True
        return {"id": "analysis-1"}


def test_intelligence_snapshot_use_case_generates_snapshot_successfully() -> None:
    deps = FakeDependencies()
    result = _build_use_case(deps).execute(_command(save_to_history=False))

    assert result.success is True
    assert result.value is not None
    assert result.value.snapshot.executive_summary == "Há risco financeiro relevante."
    assert result.value.snapshot.findings[0].title == "Aprovação pendente"
    assert result.value.saved_to_history is False
    assert result.value.persistence_warning is None
    assert deps.generated_with_sources == [_source()]
    assert deps.generated_with_model == "gpt-5-mini"
    assert deps.saved is False
    assert deps.retriever.calls[0]["query"] == INTELLIGENCE_SNAPSHOT_QUERY
    assert deps.retriever.calls[0]["limit"] == INTELLIGENCE_SNAPSHOT_SOURCE_LIMIT
    assert deps.retriever.calls[0]["selected_document_ids"] == ["doc-1"]


def test_intelligence_snapshot_use_case_returns_info_when_sources_are_missing() -> None:
    deps = FakeDependencies(sources=[])
    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.INFO
    assert result.message == (
        "Nenhum trecho relevante foi encontrado. "
        "Atualize a base semântica antes de gerar inteligência organizacional."
    )
    assert deps.generated_with_sources is None


def test_intelligence_snapshot_use_case_returns_error_for_known_retrieval_errors() -> None:
    deps = FakeDependencies(retrieval_fail=True)
    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.ERROR
    assert result.message == "Não foi possível gerar embeddings."
    assert deps.generated_with_sources is None


def test_intelligence_snapshot_use_case_returns_error_for_known_generation_errors() -> None:
    deps = FakeDependencies(generation_fail=True)
    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.ERROR
    assert result.message == "Não foi possível gerar a inteligência organizacional."


def test_intelligence_snapshot_use_case_returns_error_for_known_analysis_errors() -> None:
    deps = FakeDependencies(analysis_generation_fail=True)
    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.ERROR
    assert result.message == "Não foi possível gerar a resposta com IA."


def test_intelligence_snapshot_use_case_saves_when_requested() -> None:
    deps = FakeDependencies()
    result = _build_use_case(deps).execute(_command(save_to_history=True))

    assert result.success is True
    assert result.value is not None
    assert result.value.saved_to_history is True
    assert result.value.persistence_warning is None
    assert deps.saved is True


def test_intelligence_snapshot_use_case_keeps_snapshot_when_persistence_fails() -> None:
    deps = FakeDependencies(persistence_fail=True)
    result = _build_use_case(deps).execute(_command(save_to_history=True))

    assert result.success is True
    assert result.value is not None
    assert result.value.saved_to_history is False
    assert result.value.persistence_warning == (
        "Não foi possível salvar a inteligência organizacional."
    )
    assert result.value.snapshot.findings[0].title == "Aprovação pendente"


def _build_use_case(deps: FakeDependencies) -> IntelligenceSnapshotUseCase:
    return IntelligenceSnapshotUseCase(
        semantic_retriever=deps.retriever,
        intelligence_snapshot_generator=deps.generate_intelligence_snapshot,
        intelligence_snapshot_saver=deps.save_intelligence_snapshot,
    )


def _command(save_to_history: bool = False) -> IntelligenceSnapshotCommand:
    return IntelligenceSnapshotCommand(
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
        content="A aprovação financeira está pendente.",
        similarity=0.91,
    )


def _snapshot(sources: list[SourceSnippet]) -> IntelligenceSnapshot:
    return IntelligenceSnapshot(
        executive_summary="Há risco financeiro relevante.",
        findings=[
            IntelligenceFinding(
                category="Risco",
                title="Aprovação pendente",
                description="O cronograma depende de aprovação financeira.",
                severity="Alta",
                responsible="Financeiro",
                deadline="30/07/2026",
                evidence="Orçamento pendente.",
                recommendation="Antecipar validação financeira.",
                source_refs=["Fonte 1"],
            )
        ],
        sources=sources,
    )
