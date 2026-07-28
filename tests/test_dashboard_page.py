from __future__ import annotations

from synapse_ai.ui.dashboard_page import (
    DashboardFilters,
    DashboardSummary,
    _available_departments,
    _build_next_best_steps,
    _filter_dashboard_analyses,
    build_dashboard_summary,
)


def test_build_dashboard_summary_counts_documents_and_action_items() -> None:
    documents = [{"id": "doc-1"}, {"id": "doc-2"}]
    chunk_counts = {"doc-1": 2}
    analyses = [
        {"metadata": {"artifact_type": "analysis"}},
        {"metadata": {"artifact_type": "intelligence_snapshot", "findings": []}},
        {"metadata": {"artifact_type": "document_comparison", "issues": []}},
        {"metadata": {"artifact_type": "sentiment_report", "signals": []}},
        {
            "metadata": {
                "artifact_type": "preventive_alert_report",
                "alerts": [
                    {
                        "title": "Prazo crítico",
                        "severity": "Crítica",
                        "owner": "Financeiro",
                        "deadline": "30/07/2026",
                    }
                ],
            }
        },
        {
            "metadata": {
                "artifact_type": "historical_pattern_report",
                "patterns": [
                    {
                        "title": "Aprovação financeira recorrente",
                        "severity": "Alta",
                    }
                ],
            }
        },
        {
            "metadata": {
                "artifact_type": "multi_agent_report",
                "agent_outputs": [
                    {
                        "agent_name": "Agente de Riscos",
                        "findings": [
                            {
                                "title": "Aprovação pendente",
                                "category": "Risco",
                                "severity": "Alta",
                                "recommendation": "Escalar validação.",
                            }
                        ],
                    }
                ],
            }
        },
        {
            "metadata": {
                "artifact_type": "action_plan",
                "items": [
                    {
                        "task": "Validar orçamento",
                        "responsible": "Fernanda",
                        "deadline": "30/07/2026",
                        "priority": "Alta",
                        "risk": "Atraso no lançamento",
                    },
                    {
                        "task": "Confirmar responsável técnico",
                        "responsible": "",
                        "deadline": "A confirmar",
                        "priority": "Média",
                    },
                ],
            }
        },
    ]

    summary = build_dashboard_summary(documents, chunk_counts, analyses)

    assert summary.total_documents == 2
    assert summary.prepared_documents == 1
    assert summary.pending_documents == 1
    assert summary.saved_analyses == 8
    assert summary.intelligence_snapshots == 1
    assert summary.document_comparisons == 1
    assert summary.sentiment_reports == 1
    assert summary.preventive_alert_reports == 1
    assert summary.preventive_alerts == 1
    assert summary.critical_preventive_alerts == 1
    assert summary.historical_pattern_reports == 1
    assert summary.historical_patterns == 1
    assert summary.multi_agent_reports == 1
    assert summary.multi_agent_findings == 1
    assert summary.action_plans == 1
    assert summary.action_items == 2
    assert summary.high_priority_items == 1
    assert summary.items_to_confirm == 1


def test_build_dashboard_summary_handles_empty_state() -> None:
    summary = build_dashboard_summary([], {}, [])

    assert summary.total_documents == 0
    assert summary.prepared_documents == 0
    assert summary.pending_documents == 0
    assert summary.saved_analyses == 0
    assert summary.intelligence_snapshots == 0
    assert summary.document_comparisons == 0
    assert summary.sentiment_reports == 0
    assert summary.preventive_alert_reports == 0
    assert summary.preventive_alerts == 0
    assert summary.critical_preventive_alerts == 0
    assert summary.historical_pattern_reports == 0
    assert summary.historical_patterns == 0
    assert summary.multi_agent_reports == 0
    assert summary.multi_agent_findings == 0
    assert summary.action_plans == 0
    assert summary.action_items == 0
    assert summary.high_priority_items == 0
    assert summary.items_to_confirm == 0


def test_build_next_best_steps_guides_empty_dashboard() -> None:
    summary = DashboardSummary(
        total_documents=0,
        prepared_documents=0,
        pending_documents=0,
        saved_analyses=0,
        intelligence_snapshots=0,
        document_comparisons=0,
        sentiment_reports=0,
        preventive_alert_reports=0,
        preventive_alerts=0,
        critical_preventive_alerts=0,
        historical_pattern_reports=0,
        historical_patterns=0,
        multi_agent_reports=0,
        multi_agent_findings=0,
        action_plans=0,
        action_items=0,
        high_priority_items=0,
        items_to_confirm=0,
    )

    assert _build_next_best_steps(summary) == ["Envie o primeiro documento na aba Upload."]


def test_build_next_best_steps_prioritizes_readiness_and_risk() -> None:
    summary = DashboardSummary(
        total_documents=3,
        prepared_documents=1,
        pending_documents=2,
        saved_analyses=4,
        intelligence_snapshots=1,
        document_comparisons=1,
        sentiment_reports=0,
        preventive_alert_reports=1,
        preventive_alerts=3,
        critical_preventive_alerts=1,
        historical_pattern_reports=0,
        historical_patterns=0,
        multi_agent_reports=0,
        multi_agent_findings=0,
        action_plans=0,
        action_items=0,
        high_priority_items=0,
        items_to_confirm=0,
    )

    steps = _build_next_best_steps(summary)

    assert steps[0].startswith("Prepare 2 documento")
    assert steps[1].startswith("Revise 1 alerta")
    assert steps[2].startswith("Gere um plano de ação")


def test_available_departments_uses_detected_data_instead_of_fixed_options() -> None:
    analyses = [
        {"metadata": {"department": "Financeiro"}},
        {"answer": "O sistema de tecnologia precisa revisar o login."},
    ]

    departments = _available_departments(analyses)

    assert departments == ["Financeiro", "Tecnologia"]


def test_dashboard_filters_match_nested_multi_agent_findings() -> None:
    analyses = [
        {
            "answer": "Risco de segurança no login.",
            "metadata": {
                "artifact_type": "multi_agent_report",
                "agent_outputs": [
                    {
                        "agent_name": "Agente de Riscos",
                        "findings": [{"severity": "Alta", "title": "Revisão técnica"}],
                    }
                ],
            },
        },
        {
            "answer": "Plano financeiro sem severidade alta.",
            "metadata": {
                "artifact_type": "action_plan",
                "items": [{"priority": "Média", "task": "Validar orçamento"}],
            },
        },
    ]

    filtered = _filter_dashboard_analyses(
        analyses,
        DashboardFilters(departments=["Tecnologia", "Financeiro"], risk_level="Alta"),
    )

    assert filtered == [analyses[0]]


def test_dashboard_filters_normalize_risk_level_synonyms() -> None:
    analyses = [
        {
            "answer": "Clima de equipe em atenção.",
            "metadata": {"artifact_type": "sentiment_report", "risk_level": "Alto"},
        }
    ]

    filtered = _filter_dashboard_analyses(
        analyses,
        DashboardFilters(departments=["RH"], risk_level="Alta"),
    )

    assert filtered == analyses
