from __future__ import annotations

from typing import Any

from synapse_ai.application.analysis import MultiAgentReportCommand, MultiAgentReportUseCase
from synapse_ai.application.analysis.multi_agent_report import (
    MULTI_AGENT_HISTORY_LIMIT,
    MULTI_AGENT_REPORT_QUERY,
    MULTI_AGENT_REPORT_SOURCE_LIMIT,
)
from synapse_ai.application.result import ResultSeverity
from synapse_ai.services.agent_service import (
    AgentFinding,
    AgentOrchestrationError,
    AgentOutput,
    MultiAgentReport,
)
from synapse_ai.services.analysis_repository import AnalysisPersistenceError
from synapse_ai.services.analysis_service import AnalysisGenerationError, SourceSnippet
from synapse_ai.services.chunk_repository import ChunkPersistenceError
from synapse_ai.services.embedding_service import EmbeddingGenerationError


class FakeDependencies:
    def __init__(
        self,
        sources: list[SourceSnippet] | None = None,
        historical_analyses: list[dict[str, Any]] | None = None,
        history_returns_empty_after_failure: bool = False,
        retrieval_error: Exception | None = None,
        generation_error: Exception | None = None,
        persistence_error: Exception | None = None,
    ) -> None:
        self.sources = sources if sources is not None else [_source()]
        self.historical_analyses = historical_analyses if historical_analyses is not None else [
            _historical_record()
        ]
        self.history_returns_empty_after_failure = history_returns_empty_after_failure
        self.retrieval_error = retrieval_error
        self.generation_error = generation_error
        self.persistence_error = persistence_error
        self.events: list[str] = []
        self.loader_calls: list[dict[str, Any]] = []
        self.retriever_calls: list[dict[str, Any]] = []
        self.generator_calls: list[dict[str, Any]] = []
        self.saver_calls: list[dict[str, Any]] = []
        self.report = _report(self.sources)

    def load_historical_analyses(
        self,
        _client: Any,
        user_id: str,
        /,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        self.events.append("load_history")
        self.loader_calls.append({"user_id": user_id, "limit": limit})
        if self.history_returns_empty_after_failure:
            return []
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
        if self.retrieval_error is not None:
            raise self.retrieval_error
        self.retriever_calls.append(
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

    def generate_multi_agent_report(
        self,
        client: Any,
        sources: list[SourceSnippet],
        historical_analyses: list[dict[str, Any]],
        model: str,
        /,
    ) -> MultiAgentReport:
        self.events.append("generate_report")
        if self.generation_error is not None:
            raise self.generation_error
        self.generator_calls.append(
            {
                "client": client,
                "sources": sources,
                "historical_analyses": historical_analyses,
                "model": model,
            }
        )
        return self.report

    def save_multi_agent_report(
        self,
        client: Any,
        user_id: str,
        report: MultiAgentReport,
        generation_model: str,
        /,
    ) -> dict[str, Any]:
        self.events.append("save_report")
        if self.persistence_error is not None:
            raise self.persistence_error
        self.saver_calls.append(
            {
                "client": client,
                "user_id": user_id,
                "report": report,
                "generation_model": generation_model,
            }
        )
        return {"id": "analysis-1"}


def test_multi_agent_report_use_case_succeeds_with_sources_and_history() -> None:
    deps = FakeDependencies()

    result = _build_use_case(deps).execute(_command(save_to_history=False))

    assert result.success is True
    assert result.value is not None
    assert result.value.report is deps.report
    assert result.value.saved_to_history is False
    assert result.value.persistence_warning is None
    assert deps.loader_calls == [{"user_id": "user-1", "limit": MULTI_AGENT_HISTORY_LIMIT}]
    assert deps.retriever_calls[0]["query"] == MULTI_AGENT_REPORT_QUERY
    assert deps.retriever_calls[0]["limit"] == MULTI_AGENT_REPORT_SOURCE_LIMIT
    assert deps.retriever_calls[0]["selected_document_ids"] == ["doc-1", "doc-2"]
    assert deps.retriever_calls[0]["user_id"] == "user-1"
    assert deps.retriever_calls[0]["embedding_model"] == "text-embedding-3-small"
    assert deps.generator_calls[0] == {
        "client": _OPENAI_CLIENT,
        "sources": [_source()],
        "historical_analyses": [_historical_record()],
        "model": "gpt-5-mini",
    }
    assert deps.events == ["load_history", "retrieve_sources", "generate_report"]


def test_multi_agent_report_use_case_saves_when_requested() -> None:
    deps = FakeDependencies()

    result = _build_use_case(deps).execute(_command(save_to_history=True))

    assert result.success is True
    assert result.value is not None
    assert result.value.saved_to_history is True
    assert result.value.report is deps.report
    assert deps.saver_calls == [
        {
            "client": _SUPABASE_CLIENT,
            "user_id": "user-1",
            "report": deps.report,
            "generation_model": "gpt-5-mini",
        }
    ]
    assert deps.events == ["load_history", "retrieve_sources", "generate_report", "save_report"]


def test_multi_agent_report_use_case_history_failure_shape_continues_empty() -> None:
    deps = FakeDependencies(history_returns_empty_after_failure=True)

    result = _build_use_case(deps).execute(_command())

    assert result.success is True
    assert deps.generator_calls[0]["historical_analyses"] == []
    assert deps.events == ["load_history", "retrieve_sources", "generate_report"]


def test_multi_agent_report_use_case_returns_info_without_sources() -> None:
    deps = FakeDependencies(sources=[])

    result = _build_use_case(deps).execute(_command(save_to_history=True))

    assert result.success is False
    assert result.severity == ResultSeverity.INFO
    assert result.message == (
        "Nenhum trecho relevante foi encontrado. "
        "Atualize a base semântica antes de executar os agentes."
    )
    assert deps.generator_calls == []
    assert deps.saver_calls == []
    assert deps.events == ["load_history", "retrieve_sources"]


def test_multi_agent_report_use_case_returns_error_for_embedding_failure() -> None:
    deps = FakeDependencies(
        retrieval_error=EmbeddingGenerationError("Não foi possível gerar embeddings.")
    )

    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.ERROR
    assert result.message == "Não foi possível gerar embeddings."
    assert deps.events == ["load_history", "retrieve_sources"]


def test_multi_agent_report_use_case_returns_error_for_vector_search_failure() -> None:
    deps = FakeDependencies(
        retrieval_error=ChunkPersistenceError("Não foi possível buscar trechos.")
    )

    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.ERROR
    assert result.message == "Não foi possível buscar trechos."
    assert deps.events == ["load_history", "retrieve_sources"]


def test_multi_agent_report_use_case_preserves_agent_failure_message() -> None:
    deps = FakeDependencies(
        generation_error=AgentOrchestrationError(
            "Agente de Riscos não conseguiu concluir a análise."
        )
    )

    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.ERROR
    assert result.message == "Agente de Riscos não conseguiu concluir a análise."
    assert deps.saver_calls == []


def test_multi_agent_report_use_case_preserves_no_findings_message() -> None:
    deps = FakeDependencies(
        generation_error=AgentOrchestrationError(
            "Os agentes não encontraram achados claros neste escopo."
        )
    )

    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.message == "Os agentes não encontraram achados claros neste escopo."


def test_multi_agent_report_use_case_preserves_orchestrator_failure_message() -> None:
    deps = FakeDependencies(
        generation_error=AgentOrchestrationError(
            "O orquestrador multiagente não conseguiu consolidar."
        )
    )

    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.message == "O orquestrador multiagente não conseguiu consolidar."


def test_multi_agent_report_use_case_preserves_invalid_json_message() -> None:
    deps = FakeDependencies(
        generation_error=AgentOrchestrationError(
            "A IA retornou resposta multiagente inesperada."
        )
    )

    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.message == "A IA retornou resposta multiagente inesperada."


def test_multi_agent_report_use_case_returns_error_for_generation_failure() -> None:
    deps = FakeDependencies(
        generation_error=AnalysisGenerationError("Não foi possível gerar a resposta com IA.")
    )

    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.ERROR
    assert result.message == "Não foi possível gerar a resposta com IA."


def test_multi_agent_report_use_case_keeps_report_when_persistence_fails() -> None:
    deps = FakeDependencies(
        persistence_error=AnalysisPersistenceError(
            "Não foi possível salvar a orquestração multiagente."
        )
    )

    result = _build_use_case(deps).execute(_command(save_to_history=True))

    assert result.success is True
    assert result.value is not None
    assert result.value.report is deps.report
    assert result.value.saved_to_history is False
    assert (
        result.value.persistence_warning
        == "Não foi possível salvar a orquestração multiagente."
    )
    assert deps.events == ["load_history", "retrieve_sources", "generate_report", "save_report"]


def test_multi_agent_report_use_case_does_not_save_when_flag_is_disabled() -> None:
    deps = FakeDependencies()

    result = _build_use_case(deps).execute(_command(save_to_history=False))

    assert result.success is True
    assert result.value is not None
    assert result.value.saved_to_history is False
    assert deps.saver_calls == []


def test_multi_agent_report_use_case_validation_prevents_dependencies() -> None:
    deps = FakeDependencies()

    result = _build_use_case(deps).execute(_command(selected_document_ids=[]))

    assert result.success is False
    assert result.severity == ResultSeverity.WARNING
    assert result.message == "Selecione pelo menos um documento para definir o escopo da análise."
    assert deps.events == []


def test_multi_agent_report_use_case_retrieves_once_and_calls_generator_once() -> None:
    deps = FakeDependencies()

    result = _build_use_case(deps).execute(_command())

    assert result.success is True
    assert len(deps.retriever_calls) == 1
    assert len(deps.generator_calls) == 1


def _build_use_case(deps: FakeDependencies) -> MultiAgentReportUseCase:
    return MultiAgentReportUseCase(
        historical_analysis_loader=deps.load_historical_analyses,
        semantic_retriever=deps,
        multi_agent_report_generator=deps.generate_multi_agent_report,
        multi_agent_report_saver=deps.save_multi_agent_report,
    )


def _command(
    *,
    save_to_history: bool = False,
    selected_document_ids: list[str] | None = None,
) -> MultiAgentReportCommand:
    return MultiAgentReportCommand(
        supabase_client=_SUPABASE_CLIENT,
        openai_client=_OPENAI_CLIENT,
        user_id="user-1",
        embedding_model="text-embedding-3-small",
        generation_model="gpt-5-mini",
        save_to_history=save_to_history,
        selected_document_ids=(
            selected_document_ids if selected_document_ids is not None else ["doc-1", "doc-2"]
        ),
    )


def _source() -> SourceSnippet:
    return SourceSnippet(
        document_id="doc-1",
        filename="ata.pdf",
        chunk_index=0,
        content="Orçamento pendente e risco de atraso.",
        similarity=0.91,
    )


def _historical_record() -> dict[str, Any]:
    return {
        "id": "analysis-1",
        "title": "Alertas preventivos gerados",
        "metadata": {
            "artifact_type": "preventive_alert_report",
            "alerts": [{"title": "Aprovação financeira pendente"}],
        },
    }


def _report(sources: list[SourceSnippet]) -> MultiAgentReport:
    return MultiAgentReport(
        executive_summary="Há consenso multiagente sobre risco financeiro.",
        consensus=["Há risco de atraso por aprovação financeira."],
        conflicts=["Nenhum conflito relevante."],
        recommendations=["Priorizar validação financeira."],
        historical_record_count=1,
        agent_outputs=[
            AgentOutput(
                agent_id="risk_agent",
                agent_name="Agente de Riscos",
                mission="Identificar riscos operacionais.",
                summary="Há risco financeiro relevante.",
                confidence="Alta",
                findings=[
                    AgentFinding(
                        category="Risco",
                        title="Aprovação pendente",
                        severity="Alta",
                        evidence="O orçamento depende de aprovação.",
                        recommendation="Escalar validação financeira.",
                        source_refs=["Fonte 1"],
                    )
                ],
            )
        ],
        sources=sources,
    )


_SUPABASE_CLIENT = object()
_OPENAI_CLIENT = object()
