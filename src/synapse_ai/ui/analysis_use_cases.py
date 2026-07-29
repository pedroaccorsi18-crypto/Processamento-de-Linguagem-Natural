"""Compatibility wrappers for Streamlit while composition moves to Application."""

from __future__ import annotations

from synapse_ai.application.studio_factory import (
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

__all__ = [
    "build_action_plan_use_case",
    "build_ask_question_use_case",
    "build_document_comparison_use_case",
    "build_historical_patterns_use_case",
    "build_intelligence_snapshot_use_case",
    "build_multi_agent_report_use_case",
    "build_prepare_semantic_base_use_case",
    "build_preventive_alerts_use_case",
    "build_sentiment_analysis_use_case",
]
