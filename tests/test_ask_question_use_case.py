from __future__ import annotations

from typing import Any

from synapse_ai.application.analysis import AskQuestionCommand, AskQuestionUseCase
from synapse_ai.application.result import ResultSeverity
from synapse_ai.services.analysis_repository import AnalysisPersistenceError
from synapse_ai.services.analysis_service import RAGAnswer, SourceSnippet


class FakeDependencies:
    def __init__(self, matches: list[dict[str, Any]] | None = None) -> None:
        self.matches = matches if matches is not None else [{"content": "Trecho relevante."}]
        self.saved = False
        self.embedding_calls: list[list[str]] = []
        self.matcher_document_ids: list[str] | None = None

    def generate_embeddings(self, _client: Any, texts: list[str], _model: str) -> list[list[float]]:
        self.embedding_calls.append(texts)
        return [[0.1, 0.2]]

    def match_chunks(
        self,
        _client: Any,
        _user_id: str,
        _query_embedding: list[float],
        document_ids: list[str] | None = None,
        limit: int = 5,
        similarity_threshold: float = 0.1,
    ) -> list[dict[str, Any]]:
        self.matcher_document_ids = document_ids
        return self.matches[:limit] if similarity_threshold else self.matches[:limit]

    def build_sources(self, matches: list[dict[str, Any]]) -> list[SourceSnippet]:
        if not matches:
            return []
        return [
            SourceSnippet(
                document_id="doc-1",
                filename="ata.pdf",
                chunk_index=0,
                content="Trecho relevante.",
                similarity=0.9,
            )
        ]

    def generate_answer(
        self,
        _client: Any,
        question: str,
        sources: list[SourceSnippet],
        _model: str,
    ) -> RAGAnswer:
        return RAGAnswer(answer=f"Resposta para: {question}", sources=sources)

    def save_analysis(
        self,
        _client: Any,
        _user_id: str,
        _question: str,
        _rag_answer: RAGAnswer,
        _generation_model: str,
    ) -> dict[str, Any]:
        self.saved = True
        return {"id": "analysis-1"}


class FailingSaver(FakeDependencies):
    def save_analysis(
        self,
        _client: Any,
        _user_id: str,
        _question: str,
        _rag_answer: RAGAnswer,
        _generation_model: str,
    ) -> dict[str, Any]:
        raise AnalysisPersistenceError("Não foi possível salvar o histórico da análise.")


def test_ask_question_use_case_requires_question() -> None:
    deps = FakeDependencies()
    result = _build_use_case(deps).execute(_command(question=" "))

    assert result.success is False
    assert result.severity == ResultSeverity.WARNING
    assert result.message == "Digite uma pergunta antes de consultar a base."
    assert deps.embedding_calls == []


def test_ask_question_use_case_returns_info_when_sources_are_missing() -> None:
    deps = FakeDependencies(matches=[])
    result = _build_use_case(deps).execute(_command())

    assert result.success is False
    assert result.severity == ResultSeverity.INFO
    assert result.message.startswith("Nenhum trecho relevante foi encontrado.")


def test_ask_question_use_case_generates_answer_without_saving() -> None:
    deps = FakeDependencies()
    result = _build_use_case(deps).execute(_command(save_to_history=False))

    assert result.success is True
    assert result.value is not None
    assert result.value.rag_answer.answer == "Resposta para: Qual foi a decisão?"
    assert result.value.saved_to_history is False
    assert result.value.persistence_warning is None
    assert deps.embedding_calls == [["Qual foi a decisão?"]]
    assert deps.matcher_document_ids == ["doc-1"]
    assert deps.saved is False


def test_ask_question_use_case_saves_when_requested() -> None:
    deps = FakeDependencies()
    result = _build_use_case(deps).execute(_command(save_to_history=True))

    assert result.success is True
    assert result.value is not None
    assert result.value.saved_to_history is True
    assert result.value.persistence_warning is None
    assert deps.saved is True


def test_ask_question_use_case_keeps_answer_when_persistence_fails() -> None:
    deps = FailingSaver()
    result = _build_use_case(deps).execute(_command(save_to_history=True))

    assert result.success is True
    assert result.value is not None
    assert result.value.saved_to_history is False
    assert result.value.persistence_warning == "Não foi possível salvar o histórico da análise."
    assert result.value.rag_answer.answer == "Resposta para: Qual foi a decisão?"


def _build_use_case(deps: FakeDependencies) -> AskQuestionUseCase:
    return AskQuestionUseCase(
        embedding_generator=deps.generate_embeddings,
        chunk_matcher=deps.match_chunks,
        source_builder=deps.build_sources,
        rag_answer_generator=deps.generate_answer,
        analysis_saver=deps.save_analysis,
    )


def _command(
    question: str = "Qual foi a decisão?",
    save_to_history: bool = False,
) -> AskQuestionCommand:
    return AskQuestionCommand(
        supabase_client=object(),
        openai_client=object(),
        user_id="user-1",
        question=question,
        embedding_model="text-embedding-3-small",
        generation_model="gpt-5-mini",
        save_to_history=save_to_history,
        selected_document_ids=["doc-1"],
    )
