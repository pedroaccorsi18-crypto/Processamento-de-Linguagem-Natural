from __future__ import annotations

from synapse_ai.ui.dashboard_page import build_dashboard_summary


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
    assert summary.saved_analyses == 7
    assert summary.intelligence_snapshots == 1
    assert summary.document_comparisons == 1
    assert summary.sentiment_reports == 1
    assert summary.preventive_alert_reports == 1
    assert summary.preventive_alerts == 1
    assert summary.critical_preventive_alerts == 1
    assert summary.historical_pattern_reports == 1
    assert summary.historical_patterns == 1
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
    assert summary.action_plans == 0
