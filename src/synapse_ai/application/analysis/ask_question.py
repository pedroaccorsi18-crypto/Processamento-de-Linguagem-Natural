from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from synapse_ai.application.interfaces import (
    AnalysisSaver,
    ChunkMatcher,
    EmbeddingGenerator,
    RAGAnswerGenerator,
    SemanticSourceRetriever,
    SourceBuilder,
)
from synapse_ai.application.result import ResultSeverity, UseCaseResult
from synapse_ai.application.retrieval import SemanticRetriever
from synapse_ai.services.analysis_repository import AnalysisPersistenceError
from synapse_ai.services.analysis_service import AnalysisGenerationError, RAGAnswer
from synapse_ai.services.chunk_repository import ChunkPersistenceError
from synapse_ai.services.embedding_service import EmbeddingGenerationError


@dataclass(frozen=True)
class AskQuestionCommand:
    """Input data required to answer a user question with RAG."""

    supabase_client: Any
    openai_client: Any
    user_id: str
    question: str
    embedding_model: str
    generation_model: str
    save_to_history: bool
    selected_document_ids: list[str]
    source_limit: int = 5


@dataclass(frozen=True)
class AskQuestionOutput:
    """Successful output of the question-answering use case."""

    question: str
    rag_answer: RAGAnswer
    saved_to_history: bool
    persistence_warning: str | None = None


class AskQuestionUseCase:
    """Orchestrates semantic retrieval, RAG generation and optional persistence."""

    def __init__(
        self,
        rag_answer_generator: RAGAnswerGenerator,
        analysis_saver: AnalysisSaver,
        semantic_retriever: SemanticSourceRetriever | None = None,
        embedding_generator: EmbeddingGenerator | None = None,
        chunk_matcher: ChunkMatcher | None = None,
        source_builder: SourceBuilder | None = None,
    ) -> None:
        self._semantic_retriever = semantic_retriever or _build_compatible_semantic_retriever(
            embedding_generator,
            chunk_matcher,
            source_builder,
        )
        self._rag_answer_generator = rag_answer_generator
        self._analysis_saver = analysis_saver

    def execute(self, command: AskQuestionCommand) -> UseCaseResult[AskQuestionOutput]:
        clean_question = command.question.strip()
        if not clean_question:
            return UseCaseResult.fail(
                "Digite uma pergunta antes de consultar a base.",
                ResultSeverity.WARNING,
            )

        try:
            sources = self._semantic_retriever.retrieve(
                supabase_client=command.supabase_client,
                openai_client=command.openai_client,
                user_id=command.user_id,
                query=clean_question,
                embedding_model=command.embedding_model,
                selected_document_ids=command.selected_document_ids,
                limit=command.source_limit,
            )
            if not sources:
                return UseCaseResult.fail(
                    "Nenhum trecho relevante foi encontrado. "
                    "Atualize a base semântica antes de perguntar sobre este escopo.",
                    ResultSeverity.INFO,
                )

            rag_answer = self._rag_answer_generator(
                command.openai_client,
                clean_question,
                sources,
                command.generation_model,
            )
        except (AnalysisGenerationError, ChunkPersistenceError, EmbeddingGenerationError) as exc:
            return UseCaseResult.fail(str(exc), ResultSeverity.ERROR)

        persistence_warning = self._persist_if_requested(command, clean_question, rag_answer)
        return UseCaseResult.ok(
            AskQuestionOutput(
                question=clean_question,
                rag_answer=rag_answer,
                saved_to_history=command.save_to_history and persistence_warning is None,
                persistence_warning=persistence_warning,
            )
        )

    def _persist_if_requested(
        self,
        command: AskQuestionCommand,
        clean_question: str,
        rag_answer: RAGAnswer,
    ) -> str | None:
        if not command.save_to_history:
            return None

        try:
            self._analysis_saver(
                command.supabase_client,
                command.user_id,
                clean_question,
                rag_answer,
                command.generation_model,
            )
        except AnalysisPersistenceError as exc:
            return str(exc)
        return None


def _build_compatible_semantic_retriever(
    embedding_generator: EmbeddingGenerator | None,
    chunk_matcher: ChunkMatcher | None,
    source_builder: SourceBuilder | None,
) -> SemanticRetriever:
    if embedding_generator is None or chunk_matcher is None or source_builder is None:
        raise TypeError(
            "AskQuestionUseCase requires semantic_retriever or the legacy retrieval dependencies."
        )
    return SemanticRetriever(
        embedding_generator=embedding_generator,
        chunk_matcher=chunk_matcher,
        source_builder=source_builder,
    )
