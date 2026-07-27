from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from synapse_ai.application.dashboard import (
    IntelligentExecutiveReportCommand,
    IntelligentExecutiveReportUseCase,
)
from synapse_ai.application.dashboard.intelligent_executive_report import (
    INTELLIGENT_EXECUTIVE_REPORT_QUERY,
    INTELLIGENT_EXECUTIVE_REPORT_SOURCE_LIMIT,
)
from synapse_ai.application.result import ResultSeverity
from synapse_ai.services.analysis_service import AnalysisGenerationError, SourceSnippet
from synapse_ai.services.chunk_repository import ChunkPersistenceError
from synapse_ai.services.embedding_service import EmbeddingGenerationError
from synapse_ai.services.report_service import (
    IntelligentExecutiveReport,
    ReportActionItem,
    ReportGenerationError,
)


class FakeSemanticRetriever:
    def __init__(
        self,
        *,
        sources: list[SourceSnippet] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.sources = sources if sources is not None else [_source()]
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def retrieve(
        self,
        *,
        supabase_client: Any,
        openai_client: Any,
        user_id: str,
        query: str,
        embedding_model: str,
        selected_document_ids: list[str] | None = None,
        limit: int = 5,
    ) -> list[SourceSnippet]:
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
        if self.error is not None:
            raise self.error
        return self.sources


class FakeReportGenerator:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.report = _report()
        self.calls: list[dict[str, Any]] = []

    def generate(
        self,
        client: Any,
        sources: list[SourceSnippet],
        documents: list[dict[str, Any]],
        analyses: list[dict[str, Any]],
        model: str,
        /,
    ) -> IntelligentExecutiveReport:
        self.calls.append(
            {
                "client": client,
                "sources": sources,
                "documents": documents,
                "analyses": analyses,
                "model": model,
            }
        )
        if self.error is not None:
            raise self.error
        return self.report


def test_intelligent_executive_report_use_case_succeeds() -> None:
    retriever = FakeSemanticRetriever()
    generator = FakeReportGenerator()

    result = _build_use_case(retriever, generator).execute(_command())

    assert result.success is True
    assert result.value is not None
    assert result.value.report is generator.report
    assert retriever.calls == [
        {
            "supabase_client": _SUPABASE_CLIENT,
            "openai_client": _OPENAI_CLIENT,
            "user_id": "user-1",
            "query": INTELLIGENT_EXECUTIVE_REPORT_QUERY,
            "embedding_model": "text-embedding-3-small",
            "selected_document_ids": ["doc-1"],
            "limit": INTELLIGENT_EXECUTIVE_REPORT_SOURCE_LIMIT,
        }
    ]
    assert generator.calls == [
        {
            "client": _OPENAI_CLIENT,
            "sources": retriever.sources,
            "documents": _DOCUMENTS,
            "analyses": _ANALYSES,
            "model": "gpt-4.1-mini",
        }
    ]


def test_intelligent_executive_report_use_case_returns_info_without_sources() -> None:
    retriever = FakeSemanticRetriever(sources=[])
    generator = FakeReportGenerator()

    result = _build_use_case(retriever, generator).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.INFO
    assert (
        result.message
        == "Nenhuma evidência relevante foi encontrada para compor o relatório."
    )
    assert generator.calls == []


def test_intelligent_executive_report_use_case_handles_embedding_errors() -> None:
    retriever = FakeSemanticRetriever(
        error=EmbeddingGenerationError("Não foi possível gerar embeddings.")
    )
    generator = FakeReportGenerator()

    result = _build_use_case(retriever, generator).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.ERROR
    assert result.message == "Não foi possível gerar embeddings."
    assert generator.calls == []


def test_intelligent_executive_report_use_case_handles_retrieval_errors() -> None:
    retriever = FakeSemanticRetriever(
        error=ChunkPersistenceError("Não foi possível consultar a base semântica.")
    )
    generator = FakeReportGenerator()

    result = _build_use_case(retriever, generator).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.ERROR
    assert result.message == "Não foi possível consultar a base semântica."
    assert generator.calls == []


def test_intelligent_executive_report_use_case_handles_generation_errors() -> None:
    retriever = FakeSemanticRetriever()
    generator = FakeReportGenerator(
        error=ReportGenerationError("Não foi possível gerar o relatório executivo com IA.")
    )

    result = _build_use_case(retriever, generator).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.ERROR
    assert result.message == "Não foi possível gerar o relatório executivo com IA."
    assert len(generator.calls) == 1


def test_intelligent_executive_report_use_case_handles_invalid_analysis_errors() -> None:
    retriever = FakeSemanticRetriever()
    generator = FakeReportGenerator(
        error=AnalysisGenerationError("A IA retornou o relatório em formato inesperado.")
    )

    result = _build_use_case(retriever, generator).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.ERROR
    assert result.message == "A IA retornou o relatório em formato inesperado."
    assert len(generator.calls) == 1


def test_intelligent_executive_report_use_case_validation_prevents_dependencies() -> None:
    retriever = FakeSemanticRetriever()
    generator = FakeReportGenerator()

    result = _build_use_case(retriever, generator).execute(_command(user_id=" "))

    assert result.success is False
    assert result.severity == ResultSeverity.INFO
    assert (
        result.message
        == "Não conseguimos confirmar sua conta nesta aba. Atualize a página para continuar."
    )
    assert retriever.calls == []
    assert generator.calls == []


def test_intelligent_executive_report_use_case_requires_prepared_documents() -> None:
    retriever = FakeSemanticRetriever()
    generator = FakeReportGenerator()

    result = _build_use_case(retriever, generator).execute(
        _command(prepared_document_ids=[])
    )

    assert result.success is False
    assert result.severity == ResultSeverity.INFO
    assert (
        result.message
        == "Prepare ao menos um documento para IA antes de gerar o relatório inteligente."
    )
    assert retriever.calls == []
    assert generator.calls == []


def _build_use_case(
    retriever: FakeSemanticRetriever,
    generator: FakeReportGenerator,
) -> IntelligentExecutiveReportUseCase:
    return IntelligentExecutiveReportUseCase(
        semantic_retriever=retriever,
        intelligent_executive_report_generator=generator.generate,
    )


def _command(
    *,
    user_id: str = "user-1",
    prepared_document_ids: list[str] | None = None,
) -> IntelligentExecutiveReportCommand:
    return IntelligentExecutiveReportCommand(
        supabase_client=_SUPABASE_CLIENT,
        openai_client=_OPENAI_CLIENT,
        user_id=user_id,
        documents=_DOCUMENTS,
        analyses=_ANALYSES,
        prepared_document_ids=prepared_document_ids
        if prepared_document_ids is not None
        else ["doc-1"],
        embedding_model="text-embedding-3-small",
        generation_model="gpt-4.1-mini",
    )


def _source() -> SourceSnippet:
    return SourceSnippet(
        document_id="doc-1",
        filename="ata.pdf",
        chunk_index=0,
        content="Decisão aprovada.",
        similarity=0.91,
    )


def _report() -> IntelligentExecutiveReport:
    return IntelligentExecutiveReport(
        generated_at=datetime(2026, 7, 27, tzinfo=UTC),
        title="Relatório Executivo",
        executive_summary="Síntese executiva.",
        key_findings=["Achado"],
        risks=["Risco"],
        recommendations=["Recomendação"],
        action_items=[
            ReportActionItem(
                task="Validar orçamento",
                responsible="Financeiro",
                deadline="30/07/2026",
                priority="Alta",
                risk="Atraso",
                evidence="Ata",
                sources="Fonte 1",
            )
        ],
        limitations=["Lacuna"],
        source_filenames=["ata.pdf"],
    )


_SUPABASE_CLIENT = object()
_OPENAI_CLIENT = object()
_DOCUMENTS: list[dict[str, Any]] = [{"id": "doc-1", "filename": "ata.pdf"}]
_ANALYSES: list[dict[str, Any]] = [{"id": "analysis-1"}]
