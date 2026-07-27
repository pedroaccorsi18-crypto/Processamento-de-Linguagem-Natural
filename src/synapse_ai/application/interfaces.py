from __future__ import annotations

from typing import Any, Protocol

from synapse_ai.services.agent_service import MultiAgentReport
from synapse_ai.services.alert_service import PreventiveAlertReport
from synapse_ai.services.analysis_service import ActionPlan, RAGAnswer, SourceSnippet
from synapse_ai.services.chunking_service import TextChunk
from synapse_ai.services.comparison_service import DocumentComparisonReport
from synapse_ai.services.intelligence_service import IntelligenceSnapshot
from synapse_ai.services.pattern_service import HistoricalPatternReport
from synapse_ai.services.report_service import IntelligentExecutiveReport
from synapse_ai.services.sentiment_service import SentimentReport


class EmbeddingGenerator(Protocol):
    """Generates vector embeddings for text inputs."""

    def __call__(self, client: Any, texts: list[str], model: str, /) -> list[list[float]]: ...


class ChunkMatcher(Protocol):
    """Finds semantically relevant document chunks."""

    def __call__(
        self,
        client: Any,
        user_id: str,
        query_embedding: list[float],
        /,
        document_ids: list[str] | None = None,
        limit: int = 5,
        similarity_threshold: float = 0.1,
    ) -> list[dict[str, Any]]: ...


class SourceBuilder(Protocol):
    """Builds source snippets from persistence-layer matches."""

    def __call__(self, matches: list[dict[str, Any]], /) -> list[SourceSnippet]: ...


class SemanticSourceRetriever(Protocol):
    """Retrieves semantically relevant source snippets for a query."""

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
    ) -> list[SourceSnippet]: ...


class RAGAnswerGenerator(Protocol):
    """Generates a grounded answer from a question and retrieved sources."""

    def __call__(
        self,
        client: Any,
        question: str,
        sources: list[SourceSnippet],
        model: str,
        /,
    ) -> RAGAnswer: ...


class AnalysisSaver(Protocol):
    """Persists a generated RAG analysis."""

    def __call__(
        self,
        client: Any,
        user_id: str,
        question: str,
        rag_answer: RAGAnswer,
        generation_model: str,
        /,
    ) -> dict[str, Any]: ...


class ActionPlanGenerator(Protocol):
    """Generates an action plan from retrieved sources."""

    def __call__(
        self,
        client: Any,
        sources: list[SourceSnippet],
        model: str,
        /,
    ) -> ActionPlan: ...


class ActionPlanSaver(Protocol):
    """Persists a generated action plan."""

    def __call__(
        self,
        client: Any,
        user_id: str,
        action_plan: ActionPlan,
        generation_model: str,
        /,
    ) -> dict[str, Any]: ...


class SentimentReportGenerator(Protocol):
    """Generates an organizational sentiment report from retrieved sources."""

    def __call__(
        self,
        client: Any,
        sources: list[SourceSnippet],
        model: str,
        /,
    ) -> SentimentReport: ...


class SentimentReportSaver(Protocol):
    """Persists a generated organizational sentiment report."""

    def __call__(
        self,
        client: Any,
        user_id: str,
        report: SentimentReport,
        generation_model: str,
        /,
    ) -> dict[str, Any]: ...


class DocumentComparisonGenerator(Protocol):
    """Generates a document comparison report from retrieved sources."""

    def __call__(
        self,
        client: Any,
        sources: list[SourceSnippet],
        model: str,
        /,
    ) -> DocumentComparisonReport: ...


class DocumentComparisonSaver(Protocol):
    """Persists a generated document comparison report."""

    def __call__(
        self,
        client: Any,
        user_id: str,
        report: DocumentComparisonReport,
        generation_model: str,
        /,
    ) -> dict[str, Any]: ...


class IntelligenceSnapshotGenerator(Protocol):
    """Generates an organizational intelligence snapshot from retrieved sources."""

    def __call__(
        self,
        client: Any,
        sources: list[SourceSnippet],
        model: str,
        /,
    ) -> IntelligenceSnapshot: ...


class IntelligenceSnapshotSaver(Protocol):
    """Persists a generated organizational intelligence snapshot."""

    def __call__(
        self,
        client: Any,
        user_id: str,
        snapshot: IntelligenceSnapshot,
        generation_model: str,
        /,
    ) -> dict[str, Any]: ...


class PreventiveAlertReportGenerator(Protocol):
    """Generates a preventive alert report from retrieved sources."""

    def __call__(
        self,
        client: Any,
        sources: list[SourceSnippet],
        model: str,
        /,
    ) -> PreventiveAlertReport: ...


class PreventiveAlertReportSaver(Protocol):
    """Persists a generated preventive alert report."""

    def __call__(
        self,
        client: Any,
        user_id: str,
        report: PreventiveAlertReport,
        generation_model: str,
        /,
    ) -> dict[str, Any]: ...


class HistoricalAnalysisLoader(Protocol):
    """Loads persisted analysis records used as historical memory."""

    def __call__(
        self,
        client: Any,
        user_id: str,
        /,
        limit: int = 10,
    ) -> list[dict[str, Any]]: ...


class HistoricalPatternReportGenerator(Protocol):
    """Generates a historical pattern report from current sources and saved analyses."""

    def __call__(
        self,
        client: Any,
        current_sources: list[SourceSnippet],
        historical_analyses: list[dict[str, Any]],
        model: str,
        /,
    ) -> HistoricalPatternReport: ...


class HistoricalPatternReportSaver(Protocol):
    """Persists a generated historical pattern report."""

    def __call__(
        self,
        client: Any,
        user_id: str,
        report: HistoricalPatternReport,
        generation_model: str,
        /,
    ) -> dict[str, Any]: ...


class MultiAgentReportGenerator(Protocol):
    """Generates a multi-agent report from retrieved sources and saved analyses."""

    def __call__(
        self,
        client: Any,
        sources: list[SourceSnippet],
        historical_analyses: list[dict[str, Any]],
        model: str,
        /,
    ) -> MultiAgentReport: ...


class MultiAgentReportSaver(Protocol):
    """Persists a generated multi-agent report."""

    def __call__(
        self,
        client: Any,
        user_id: str,
        report: MultiAgentReport,
        generation_model: str,
        /,
    ) -> dict[str, Any]: ...


class TextChunker(Protocol):
    """Splits extracted document text into chunks."""

    def __call__(self, text: str, /) -> list[TextChunk]: ...


class DocumentChunkReplacer(Protocol):
    """Replaces persisted chunks for a document."""

    def __call__(
        self,
        client: Any,
        user_id: str,
        document_id: str,
        filename: str,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
        embedding_model: str,
        /,
    ) -> int: ...


class IntelligentExecutiveReportGenerator(Protocol):
    """Generates an intelligent executive report from retrieved sources."""

    def __call__(
        self,
        client: Any,
        sources: list[SourceSnippet],
        documents: list[dict[str, Any]],
        analyses: list[dict[str, Any]],
        model: str,
        /,
    ) -> IntelligentExecutiveReport: ...
