from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from synapse_ai.application.interfaces import (
    IntelligenceSnapshotGenerator,
    IntelligenceSnapshotSaver,
    SemanticSourceRetriever,
)
from synapse_ai.application.result import ResultSeverity, UseCaseResult
from synapse_ai.services.analysis_repository import AnalysisPersistenceError
from synapse_ai.services.analysis_service import AnalysisGenerationError
from synapse_ai.services.chunk_repository import ChunkPersistenceError
from synapse_ai.services.embedding_service import EmbeddingGenerationError
from synapse_ai.services.intelligence_service import (
    IntelligenceGenerationError,
    IntelligenceSnapshot,
)

INTELLIGENCE_SNAPSHOT_QUERY = (
    "decisões, riscos, inconsistências, pendências, prazos críticos, responsáveis, "
    "dependências e recomendações estratégicas"
)
INTELLIGENCE_SNAPSHOT_SOURCE_LIMIT = 10


@dataclass(frozen=True)
class IntelligenceSnapshotCommand:
    """Input data required to generate an organizational intelligence snapshot."""

    supabase_client: Any
    openai_client: Any
    user_id: str
    embedding_model: str
    generation_model: str
    save_to_history: bool
    selected_document_ids: list[str]


@dataclass(frozen=True)
class IntelligenceSnapshotOutput:
    """Successful output of the intelligence-snapshot use case."""

    snapshot: IntelligenceSnapshot
    saved_to_history: bool
    persistence_warning: str | None = None


class IntelligenceSnapshotUseCase:
    """Orchestrates semantic retrieval, intelligence generation and optional persistence."""

    def __init__(
        self,
        semantic_retriever: SemanticSourceRetriever,
        intelligence_snapshot_generator: IntelligenceSnapshotGenerator,
        intelligence_snapshot_saver: IntelligenceSnapshotSaver,
    ) -> None:
        self._semantic_retriever = semantic_retriever
        self._intelligence_snapshot_generator = intelligence_snapshot_generator
        self._intelligence_snapshot_saver = intelligence_snapshot_saver

    def execute(
        self,
        command: IntelligenceSnapshotCommand,
    ) -> UseCaseResult[IntelligenceSnapshotOutput]:
        try:
            sources = self._semantic_retriever.retrieve(
                supabase_client=command.supabase_client,
                openai_client=command.openai_client,
                user_id=command.user_id,
                query=INTELLIGENCE_SNAPSHOT_QUERY,
                embedding_model=command.embedding_model,
                selected_document_ids=command.selected_document_ids,
                limit=INTELLIGENCE_SNAPSHOT_SOURCE_LIMIT,
            )
            if not sources:
                return UseCaseResult.fail(
                    "Nenhum trecho relevante foi encontrado. "
                    "Atualize a base semântica antes de gerar inteligência organizacional.",
                    ResultSeverity.INFO,
                )

            snapshot = self._intelligence_snapshot_generator(
                command.openai_client,
                sources,
                command.generation_model,
            )
        except (
            AnalysisGenerationError,
            ChunkPersistenceError,
            EmbeddingGenerationError,
            IntelligenceGenerationError,
        ) as exc:
            return UseCaseResult.fail(str(exc), ResultSeverity.ERROR)

        persistence_warning = self._persist_if_requested(command, snapshot)
        return UseCaseResult.ok(
            IntelligenceSnapshotOutput(
                snapshot=snapshot,
                saved_to_history=command.save_to_history and persistence_warning is None,
                persistence_warning=persistence_warning,
            )
        )

    def _persist_if_requested(
        self,
        command: IntelligenceSnapshotCommand,
        snapshot: IntelligenceSnapshot,
    ) -> str | None:
        if not command.save_to_history:
            return None

        try:
            self._intelligence_snapshot_saver(
                command.supabase_client,
                command.user_id,
                snapshot,
                command.generation_model,
            )
        except AnalysisPersistenceError as exc:
            return str(exc)
        return None

