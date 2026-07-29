from __future__ import annotations

from synapse_ai.application.analysis import (
    ActionPlanUseCase,
    AskQuestionUseCase,
    DocumentComparisonUseCase,
    HistoricalPatternsUseCase,
    IntelligenceSnapshotUseCase,
    MultiAgentReportUseCase,
    PreventiveAlertsUseCase,
    SentimentAnalysisUseCase,
)
from synapse_ai.application.indexing import PrepareSemanticBaseUseCase
from synapse_ai.application.retrieval import SemanticRetriever
from synapse_ai.services.agent_service import generate_multi_agent_report
from synapse_ai.services.alert_service import generate_preventive_alert_report
from synapse_ai.services.analysis_repository import (
    list_recent_analyses,
    save_action_plan_result,
    save_analysis_result,
    save_document_comparison_result,
    save_historical_pattern_report_result,
    save_intelligence_snapshot_result,
    save_multi_agent_report_result,
    save_preventive_alert_report_result,
    save_sentiment_report_result,
)
from synapse_ai.services.analysis_service import (
    build_source_snippets,
    generate_action_plan,
    generate_rag_answer,
)
from synapse_ai.services.chunk_repository import match_document_chunks, replace_document_chunks
from synapse_ai.services.chunking_service import split_text_into_chunks
from synapse_ai.services.comparison_service import generate_document_comparison
from synapse_ai.services.embedding_service import generate_embeddings
from synapse_ai.services.intelligence_service import generate_intelligence_snapshot
from synapse_ai.services.pattern_service import generate_historical_pattern_report
from synapse_ai.services.sentiment_service import generate_sentiment_report


def build_ask_question_use_case() -> AskQuestionUseCase:
    return AskQuestionUseCase(
        semantic_retriever=_build_semantic_retriever(),
        rag_answer_generator=generate_rag_answer,
        analysis_saver=save_analysis_result,
    )


def build_action_plan_use_case() -> ActionPlanUseCase:
    return ActionPlanUseCase(
        semantic_retriever=_build_semantic_retriever(),
        action_plan_generator=generate_action_plan,
        action_plan_saver=save_action_plan_result,
    )


def build_document_comparison_use_case() -> DocumentComparisonUseCase:
    return DocumentComparisonUseCase(
        semantic_retriever=_build_semantic_retriever(),
        document_comparison_generator=generate_document_comparison,
        document_comparison_saver=save_document_comparison_result,
    )


def build_intelligence_snapshot_use_case() -> IntelligenceSnapshotUseCase:
    return IntelligenceSnapshotUseCase(
        semantic_retriever=_build_semantic_retriever(),
        intelligence_snapshot_generator=generate_intelligence_snapshot,
        intelligence_snapshot_saver=save_intelligence_snapshot_result,
    )


def build_preventive_alerts_use_case() -> PreventiveAlertsUseCase:
    return PreventiveAlertsUseCase(
        semantic_retriever=_build_semantic_retriever(),
        preventive_alert_report_generator=generate_preventive_alert_report,
        preventive_alert_report_saver=save_preventive_alert_report_result,
    )


def build_historical_patterns_use_case() -> HistoricalPatternsUseCase:
    return HistoricalPatternsUseCase(
        historical_analysis_loader=list_recent_analyses,
        semantic_retriever=_build_semantic_retriever(),
        historical_pattern_report_generator=generate_historical_pattern_report,
        historical_pattern_report_saver=save_historical_pattern_report_result,
    )


def build_multi_agent_report_use_case() -> MultiAgentReportUseCase:
    return MultiAgentReportUseCase(
        historical_analysis_loader=list_recent_analyses,
        semantic_retriever=_build_semantic_retriever(),
        multi_agent_report_generator=generate_multi_agent_report,
        multi_agent_report_saver=save_multi_agent_report_result,
    )


def build_sentiment_analysis_use_case() -> SentimentAnalysisUseCase:
    return SentimentAnalysisUseCase(
        semantic_retriever=_build_semantic_retriever(),
        sentiment_report_generator=generate_sentiment_report,
        sentiment_report_saver=save_sentiment_report_result,
    )


def build_prepare_semantic_base_use_case() -> PrepareSemanticBaseUseCase:
    return PrepareSemanticBaseUseCase(
        text_chunker=split_text_into_chunks,
        embedding_generator=generate_embeddings,
        document_chunk_replacer=replace_document_chunks,
    )


def _build_semantic_retriever() -> SemanticRetriever:
    return SemanticRetriever(
        embedding_generator=generate_embeddings,
        chunk_matcher=match_document_chunks,
        source_builder=build_source_snippets,
    )
