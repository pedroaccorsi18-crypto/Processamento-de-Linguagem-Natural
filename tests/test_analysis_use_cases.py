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
from synapse_ai.ui.analysis_use_cases import (
    build_action_plan_use_case,
    build_ask_question_use_case,
    build_document_comparison_use_case,
    build_historical_patterns_use_case,
    build_intelligence_snapshot_use_case,
    build_multi_agent_report_use_case,
    build_prepare_semantic_base_use_case,
    build_preventive_alerts_use_case,
    build_sentiment_analysis_use_case,
)


def test_analysis_use_case_builders_return_expected_use_cases() -> None:
    assert isinstance(build_ask_question_use_case(), AskQuestionUseCase)
    assert isinstance(build_action_plan_use_case(), ActionPlanUseCase)
    assert isinstance(build_document_comparison_use_case(), DocumentComparisonUseCase)
    assert isinstance(build_intelligence_snapshot_use_case(), IntelligenceSnapshotUseCase)
    assert isinstance(build_preventive_alerts_use_case(), PreventiveAlertsUseCase)
    assert isinstance(build_historical_patterns_use_case(), HistoricalPatternsUseCase)
    assert isinstance(build_multi_agent_report_use_case(), MultiAgentReportUseCase)
    assert isinstance(build_sentiment_analysis_use_case(), SentimentAnalysisUseCase)
    assert isinstance(build_prepare_semantic_base_use_case(), PrepareSemanticBaseUseCase)
