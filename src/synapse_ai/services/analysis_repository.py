from __future__ import annotations

import logging
from typing import Any

from synapse_ai.services.agent_service import (
    MultiAgentReport,
    multi_agent_report_to_markdown,
    serialize_agent_outputs,
)
from synapse_ai.services.alert_service import (
    PreventiveAlertReport,
    preventive_alert_report_to_markdown,
    serialize_preventive_alerts,
)
from synapse_ai.services.analysis_service import (
    ActionPlan,
    RAGAnswer,
    action_plan_to_markdown,
    serialize_action_plan_items,
    serialize_sources,
)
from synapse_ai.services.comparison_service import (
    DocumentComparisonReport,
    document_comparison_to_markdown,
    serialize_comparison_issues,
)
from synapse_ai.services.intelligence_service import (
    IntelligenceSnapshot,
    intelligence_snapshot_to_markdown,
    serialize_intelligence_findings,
)
from synapse_ai.services.pattern_service import (
    HistoricalPatternReport,
    historical_pattern_report_to_markdown,
    serialize_historical_patterns,
)
from synapse_ai.services.sentiment_service import (
    SentimentReport,
    sentiment_report_to_markdown,
    serialize_sentiment_signals,
)

logger = logging.getLogger(__name__)


class AnalysisPersistenceError(RuntimeError):
    """Raised when an analysis result cannot be persisted."""


def save_analysis_result(
    client: Any,
    user_id: str,
    question: str,
    rag_answer: RAGAnswer,
    generation_model: str,
) -> dict[str, Any]:
    payload = {
        "user_id": user_id,
        "document_id": _first_document_id(rag_answer),
        "title": _build_title(question),
        "question": question.strip(),
        "answer": rag_answer.answer,
        "sources": serialize_sources(rag_answer.sources),
        "model": generation_model,
        "status": "ready",
        "metadata": {
            "source_count": len(rag_answer.sources),
            "source_filenames": sorted({source.filename for source in rag_answer.sources}),
        },
    }

    try:
        response = client.table("analyses").insert(payload).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Analysis persistence failed: %s", exc.__class__.__name__)
        raise AnalysisPersistenceError("Não foi possível salvar o histórico da análise.") from exc

    data = getattr(response, "data", None)
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    if isinstance(data, dict):
        return data
    return payload


def save_action_plan_result(
    client: Any,
    user_id: str,
    action_plan: ActionPlan,
    generation_model: str,
) -> dict[str, Any]:
    payload = {
        "user_id": user_id,
        "document_id": _first_source_document_id(action_plan.sources),
        "title": "Plano de ação gerado",
        "question": "Gerar plano de ação a partir dos documentos selecionados.",
        "answer": action_plan_to_markdown(action_plan),
        "sources": serialize_sources(action_plan.sources),
        "model": generation_model,
        "status": "ready",
        "metadata": {
            "artifact_type": "action_plan",
            "item_count": len(action_plan.items),
            "items": serialize_action_plan_items(action_plan.items),
            "source_count": len(action_plan.sources),
            "source_filenames": sorted({source.filename for source in action_plan.sources}),
        },
    }

    try:
        response = client.table("analyses").insert(payload).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Action plan persistence failed: %s", exc.__class__.__name__)
        raise AnalysisPersistenceError("Não foi possível salvar o plano de ação.") from exc

    data = getattr(response, "data", None)
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    if isinstance(data, dict):
        return data
    return payload


def save_intelligence_snapshot_result(
    client: Any,
    user_id: str,
    snapshot: IntelligenceSnapshot,
    generation_model: str,
) -> dict[str, Any]:
    payload = {
        "user_id": user_id,
        "document_id": _first_source_document_id(snapshot.sources),
        "title": "Inteligência organizacional gerada",
        "question": "Gerar inteligência estruturada a partir dos documentos selecionados.",
        "answer": intelligence_snapshot_to_markdown(snapshot),
        "sources": serialize_sources(snapshot.sources),
        "model": generation_model,
        "status": "ready",
        "metadata": {
            "artifact_type": "intelligence_snapshot",
            "finding_count": len(snapshot.findings),
            "findings": serialize_intelligence_findings(snapshot.findings),
            "source_count": len(snapshot.sources),
            "source_filenames": sorted({source.filename for source in snapshot.sources}),
        },
    }

    try:
        response = client.table("analyses").insert(payload).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Intelligence snapshot persistence failed: %s", exc.__class__.__name__)
        raise AnalysisPersistenceError(
            "Não foi possível salvar a inteligência organizacional."
        ) from exc

    data = getattr(response, "data", None)
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    if isinstance(data, dict):
        return data
    return payload


def save_document_comparison_result(
    client: Any,
    user_id: str,
    report: DocumentComparisonReport,
    generation_model: str,
) -> dict[str, Any]:
    payload = {
        "user_id": user_id,
        "document_id": _first_source_document_id(report.sources),
        "title": "Comparação documental gerada",
        "question": "Comparar documentos selecionados e detectar inconsistências.",
        "answer": document_comparison_to_markdown(report),
        "sources": serialize_sources(report.sources),
        "model": generation_model,
        "status": "ready",
        "metadata": {
            "artifact_type": "document_comparison",
            "issue_count": len(report.issues),
            "issues": serialize_comparison_issues(report.issues),
            "source_count": len(report.sources),
            "source_filenames": sorted({source.filename for source in report.sources}),
        },
    }

    try:
        response = client.table("analyses").insert(payload).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Document comparison persistence failed: %s", exc.__class__.__name__)
        raise AnalysisPersistenceError(
            "Não foi possível salvar a comparação documental."
        ) from exc

    data = getattr(response, "data", None)
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    if isinstance(data, dict):
        return data
    return payload


def save_sentiment_report_result(
    client: Any,
    user_id: str,
    report: SentimentReport,
    generation_model: str,
) -> dict[str, Any]:
    payload = {
        "user_id": user_id,
        "document_id": _first_source_document_id(report.sources),
        "title": "Sentimentos organizacionais gerados",
        "question": "Analisar sentimentos organizacionais nos documentos selecionados.",
        "answer": sentiment_report_to_markdown(report),
        "sources": serialize_sources(report.sources),
        "model": generation_model,
        "status": "ready",
        "metadata": {
            "artifact_type": "sentiment_report",
            "overall_sentiment": report.overall_sentiment,
            "risk_level": report.risk_level,
            "dominant_signals": report.dominant_signals,
            "signal_count": len(report.signals),
            "signals": serialize_sentiment_signals(report.signals),
            "source_count": len(report.sources),
            "source_filenames": sorted({source.filename for source in report.sources}),
        },
    }

    try:
        response = client.table("analyses").insert(payload).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Sentiment report persistence failed: %s", exc.__class__.__name__)
        raise AnalysisPersistenceError(
            "Não foi possível salvar a análise de sentimentos organizacionais."
        ) from exc

    data = getattr(response, "data", None)
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    if isinstance(data, dict):
        return data
    return payload


def save_preventive_alert_report_result(
    client: Any,
    user_id: str,
    report: PreventiveAlertReport,
    generation_model: str,
) -> dict[str, Any]:
    payload = {
        "user_id": user_id,
        "document_id": _first_source_document_id(report.sources),
        "title": "Alertas preventivos gerados",
        "question": "Gerar alertas preventivos a partir dos documentos selecionados.",
        "answer": preventive_alert_report_to_markdown(report),
        "sources": serialize_sources(report.sources),
        "model": generation_model,
        "status": "ready",
        "metadata": {
            "artifact_type": "preventive_alert_report",
            "alert_count": len(report.alerts),
            "critical_alert_count": sum(
                1 for alert in report.alerts if alert.severity == "Crítica"
            ),
            "high_alert_count": sum(1 for alert in report.alerts if alert.severity == "Alta"),
            "alerts": serialize_preventive_alerts(report.alerts),
            "source_count": len(report.sources),
            "source_filenames": sorted({source.filename for source in report.sources}),
        },
    }

    try:
        response = client.table("analyses").insert(payload).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Preventive alert persistence failed: %s", exc.__class__.__name__)
        raise AnalysisPersistenceError(
            "Não foi possível salvar os alertas preventivos."
        ) from exc

    data = getattr(response, "data", None)
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    if isinstance(data, dict):
        return data
    return payload


def save_historical_pattern_report_result(
    client: Any,
    user_id: str,
    report: HistoricalPatternReport,
    generation_model: str,
) -> dict[str, Any]:
    payload = {
        "user_id": user_id,
        "document_id": _first_source_document_id(report.sources),
        "title": "Padrões históricos reconhecidos",
        "question": "Reconhecer padrões históricos a partir do escopo documental atual.",
        "answer": historical_pattern_report_to_markdown(report),
        "sources": serialize_sources(report.sources),
        "model": generation_model,
        "status": "ready",
        "metadata": {
            "artifact_type": "historical_pattern_report",
            "pattern_count": len(report.patterns),
            "historical_record_count": report.historical_record_count,
            "patterns": serialize_historical_patterns(report.patterns),
            "source_count": len(report.sources),
            "source_filenames": sorted({source.filename for source in report.sources}),
        },
    }

    try:
        response = client.table("analyses").insert(payload).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Historical pattern persistence failed: %s", exc.__class__.__name__)
        raise AnalysisPersistenceError(
            "Não foi possível salvar os padrões históricos."
        ) from exc

    data = getattr(response, "data", None)
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    if isinstance(data, dict):
        return data
    return payload


def save_multi_agent_report_result(
    client: Any,
    user_id: str,
    report: MultiAgentReport,
    generation_model: str,
) -> dict[str, Any]:
    agent_outputs = serialize_agent_outputs(report.agent_outputs)
    payload = {
        "user_id": user_id,
        "document_id": _first_source_document_id(report.sources),
        "title": "Orquestração multiagente gerada",
        "question": "Executar agentes especializados sobre o escopo documental atual.",
        "answer": multi_agent_report_to_markdown(report),
        "sources": serialize_sources(report.sources),
        "model": generation_model,
        "status": "ready",
        "metadata": {
            "artifact_type": "multi_agent_report",
            "agent_count": len(report.agent_outputs),
            "finding_count": sum(len(output.findings) for output in report.agent_outputs),
            "historical_record_count": report.historical_record_count,
            "consensus": report.consensus,
            "conflicts": report.conflicts,
            "recommendations": report.recommendations,
            "agent_outputs": agent_outputs,
            "source_count": len(report.sources),
            "source_filenames": sorted({source.filename for source in report.sources}),
        },
    }

    try:
        response = client.table("analyses").insert(payload).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Multi-agent report persistence failed: %s", exc.__class__.__name__)
        raise AnalysisPersistenceError(
            "Não foi possível salvar a orquestração multiagente."
        ) from exc

    data = getattr(response, "data", None)
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    if isinstance(data, dict):
        return data
    return payload


def list_recent_analyses(client: Any, user_id: str, limit: int = 10) -> list[dict[str, Any]]:
    try:
        response = (
            client.table("analyses")
            .select(
                "id, title, question, answer, sources, model, metadata, status, created_at, "
                "documents(filename)"
            )
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Analysis history listing failed: %s", exc.__class__.__name__)
        return []

    data = getattr(response, "data", None)
    return data if isinstance(data, list) else []


def _first_document_id(rag_answer: RAGAnswer) -> str | None:
    return _first_source_document_id(rag_answer.sources)


def _first_source_document_id(sources: list[object]) -> str | None:
    if not sources:
        return None
    document_id = getattr(sources[0], "document_id", "")
    return document_id or None


def _build_title(question: str) -> str:
    clean_question = " ".join(question.split())
    if len(clean_question) <= 80:
        return clean_question
    return f"{clean_question[:77].rstrip()}..."
