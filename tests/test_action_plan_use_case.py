from __future__ import annotations

from typing import Any

from synapse_ai.application.analysis import ActionPlanCommand, ActionPlanUseCase
from synapse_ai.application.analysis.action_plan import ACTION_PLAN_QUERY, ACTION_PLAN_SOURCE_LIMIT
from synapse_ai.application.result import ResultSeverity
from synapse_ai.services.analysis_repository import AnalysisPersistenceError
from synapse_ai.services.analysis_service import (
    ActionPlan,
    ActionPlanItem,
    AnalysisGenerationError,
    SourceSnippet,
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
        persistence_fail: bool = False,
    ) -> None:
        self.retriever = FakeSemanticRetriever(sources=sources, fail=retrieval_fail)
        self.generation_fail = generation_fail
        self.persistence_fail = persistence_fail
        self.generated_with_sources: list[SourceSnippet] | None = None
        self.saved = False

    def generate_action_plan(
        self,
        _client: Any,
        sources: list[SourceSnippet],
        _model: str,
    ) -> ActionPlan:
        if self.generation_fail:
            raise AnalysisGenerationError("Não foi possível gerar o plano de ação.")
        self.generated_with_sources = sources
        return ActionPlan(
            items=[
                ActionPlanItem(
                    task="Validar orçamento",
                    responsible="Financeiro",
                    deadline="30/07/2026",
                    priority="Alta",
                    risk="Atraso no lançamento",
                    evidence="Orçamento pendente.",
                    source_refs=["Fonte 1"],
                )
            ],
            sources=sources,
        )

    def save_action_plan(
        self,
        _client: Any,
        _user_id: str,
        _action_plan: ActionPlan,
        _generation_model: str,
    ) -> dict[str, Any]:
        if self.persistence_fail:
            raise AnalysisPersistenceError("Não foi possível salvar o plano de ação.")
        self.saved = True
        return {"id": "analysis-1"}


def test_action_plan_use_case_generates_plan_successfully() -> None:
    deps = FakeDependencies()
    result = _build_use_case(deps).execute(_command(save_to_history=False))

    assert result.success is True
    assert result.value is not None
    assert result.value.action_plan.items[0].task == "Validar orçamento"
    assert result.value.saved_to_history is False
    assert result.value.persistence_warning is None
    assert deps.generated_with_sources == [_source()]
    assert deps.saved is False
    assert deps.retriever.calls[0]["query"] == ACTION_PLAN_QUERY
    assert deps.retriever.calls[0]["limit"] == ACTION_PLAN_SOURCE_LIMIT


def test_action_plan_use_case_returns_info_when_sources_are_missing() -> None:
    deps = FakeDependencies(sources=[])
    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.INFO
    assert result.message == (
        "Nenhum trecho relevante foi encontrado. "
        "Atualize a base semântica antes de gerar o plano."
    )
    assert deps.generated_with_sources is None


def test_action_plan_use_case_returns_error_for_known_retrieval_errors() -> None:
    deps = FakeDependencies(retrieval_fail=True)
    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.ERROR
    assert result.message == "Não foi possível gerar embeddings."
    assert deps.generated_with_sources is None


def test_action_plan_use_case_returns_error_for_known_generation_errors() -> None:
    deps = FakeDependencies(generation_fail=True)
    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.ERROR
    assert result.message == "Não foi possível gerar o plano de ação."


def test_action_plan_use_case_saves_when_requested() -> None:
    deps = FakeDependencies()
    result = _build_use_case(deps).execute(_command(save_to_history=True))

    assert result.success is True
    assert result.value is not None
    assert result.value.saved_to_history is True
    assert result.value.persistence_warning is None
    assert deps.saved is True


def test_action_plan_use_case_keeps_plan_when_persistence_fails() -> None:
    deps = FakeDependencies(persistence_fail=True)
    result = _build_use_case(deps).execute(_command(save_to_history=True))

    assert result.success is True
    assert result.value is not None
    assert result.value.saved_to_history is False
    assert result.value.persistence_warning == "Não foi possível salvar o plano de ação."
    assert result.value.action_plan.items[0].task == "Validar orçamento"


def _build_use_case(deps: FakeDependencies) -> ActionPlanUseCase:
    return ActionPlanUseCase(
        semantic_retriever=deps.retriever,
        action_plan_generator=deps.generate_action_plan,
        action_plan_saver=deps.save_action_plan,
    )


def _command(save_to_history: bool = False) -> ActionPlanCommand:
    return ActionPlanCommand(
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
        content="Orçamento pendente.",
        similarity=0.91,
    )

