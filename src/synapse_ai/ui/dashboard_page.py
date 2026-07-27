from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import streamlit as st

from synapse_ai.application.dashboard import IntelligentExecutiveReportCommand
from synapse_ai.application.result import ResultSeverity, UseCaseResult
from synapse_ai.auth.session import (
    clear_session,
    get_access_token,
    get_current_session_user,
    get_refresh_token,
    update_auth_tokens,
)
from synapse_ai.clients.openai_client import create_openai_client
from synapse_ai.clients.supabase_client import create_authenticated_supabase_connection
from synapse_ai.config import AppConfig
from synapse_ai.services.analysis_repository import list_recent_analyses
from synapse_ai.services.analysis_service import (
    describe_planned_analysis_capabilities,
)
from synapse_ai.services.chunk_repository import (
    list_document_chunk_counts,
)
from synapse_ai.services.document_repository import list_user_documents
from synapse_ai.services.report_service import (
    build_executive_report,
    executive_report_to_markdown,
    executive_report_to_pdf,
    intelligent_report_to_markdown,
    intelligent_report_to_pdf,
)
from synapse_ai.ui.dashboard_use_cases import build_intelligent_executive_report_use_case
from synapse_ai.ui.theme import render_page_header


@dataclass(frozen=True)
class DashboardSummary:
    total_documents: int
    prepared_documents: int
    pending_documents: int
    saved_analyses: int
    intelligence_snapshots: int
    document_comparisons: int
    sentiment_reports: int
    preventive_alert_reports: int
    preventive_alerts: int
    critical_preventive_alerts: int
    historical_pattern_reports: int
    historical_patterns: int
    multi_agent_reports: int
    multi_agent_findings: int
    action_plans: int
    action_items: int
    high_priority_items: int
    items_to_confirm: int


def render_dashboard_page(config: AppConfig) -> None:
    user = get_current_session_user()
    render_page_header(
        "Dashboard executivo",
        "Visão consolidada da base documental, alertas preventivos e trilha de inteligência salva.",
        "Área autenticada",
    )
    if user is not None:
        st.caption(f"Usuário autenticado: {user.email}")

    if st.button("Sair"):
        clear_session()
        st.rerun()

    if user is None:
        st.info("Não conseguimos confirmar sua conta nesta aba. Atualize a página para continuar.")
        return

    access_token = get_access_token()
    if access_token is None:
        st.info("Sua autenticação precisa ser renovada para consultar o painel.")
        return

    try:
        connection = create_authenticated_supabase_connection(
            config,
            access_token,
            get_refresh_token(),
        )
    except RuntimeError as exc:
        st.error(str(exc))
        return
    update_auth_tokens(connection.access_token, connection.refresh_token)
    client = connection.client

    documents = list_user_documents(client, user.id, limit=50)
    chunk_counts = list_document_chunk_counts(
        client,
        user.id,
        _document_ids(documents),
        config.openai.embedding_model,
    )
    analyses = list_recent_analyses(client, user.id, limit=50)
    summary = build_dashboard_summary(documents, chunk_counts, analyses)
    openai_client = create_openai_client(config)

    _render_summary_metrics(summary)
    _render_document_health(documents, chunk_counts)
    _render_preventive_alerts(analyses)
    _render_historical_patterns(analyses)
    _render_multi_agent_findings(analyses)
    _render_action_intelligence(analyses)
    _render_executive_report_downloads(
        client,
        openai_client,
        user.id,
        config,
        documents,
        chunk_counts,
        analyses,
    )
    _render_available_capabilities()


def build_dashboard_summary(
    documents: list[dict[str, object]],
    chunk_counts: dict[str, int],
    analyses: list[dict[str, object]],
) -> DashboardSummary:
    prepared_documents = sum(
        1 for document in documents if _document_chunk_count(document, chunk_counts) > 0
    )
    action_plans = [analysis for analysis in analyses if _is_action_plan(analysis)]
    intelligence_snapshots = [
        analysis for analysis in analyses if _is_intelligence_snapshot(analysis)
    ]
    document_comparisons = [
        analysis for analysis in analyses if _is_document_comparison(analysis)
    ]
    sentiment_reports = [analysis for analysis in analyses if _is_sentiment_report(analysis)]
    preventive_alert_reports = [
        analysis for analysis in analyses if _is_preventive_alert_report(analysis)
    ]
    preventive_alerts = _extract_preventive_alerts(preventive_alert_reports)
    historical_pattern_reports = [
        analysis for analysis in analyses if _is_historical_pattern_report(analysis)
    ]
    historical_patterns = _extract_historical_patterns(historical_pattern_reports)
    multi_agent_reports = [analysis for analysis in analyses if _is_multi_agent_report(analysis)]
    multi_agent_findings = _extract_multi_agent_findings(multi_agent_reports)
    action_items = _extract_action_items(action_plans)
    return DashboardSummary(
        total_documents=len(documents),
        prepared_documents=prepared_documents,
        pending_documents=max(len(documents) - prepared_documents, 0),
        saved_analyses=len(analyses),
        intelligence_snapshots=len(intelligence_snapshots),
        document_comparisons=len(document_comparisons),
        sentiment_reports=len(sentiment_reports),
        preventive_alert_reports=len(preventive_alert_reports),
        preventive_alerts=len(preventive_alerts),
        critical_preventive_alerts=sum(
            1 for alert in preventive_alerts if alert.get("severity") == "Crítica"
        ),
        historical_pattern_reports=len(historical_pattern_reports),
        historical_patterns=len(historical_patterns),
        multi_agent_reports=len(multi_agent_reports),
        multi_agent_findings=len(multi_agent_findings),
        action_plans=len(action_plans),
        action_items=len(action_items),
        high_priority_items=sum(1 for item in action_items if item.get("priority") == "Alta"),
        items_to_confirm=sum(1 for item in action_items if _requires_confirmation(item)),
    )


def _render_summary_metrics(summary: DashboardSummary) -> None:
    st.subheader("Visão geral")
    first_row = st.columns(5)
    first_row[0].metric("Documentos", summary.total_documents)
    first_row[1].metric("Preparados para IA", summary.prepared_documents)
    first_row[2].metric("Análises salvas", summary.saved_analyses)
    first_row[3].metric("Inteligências salvas", summary.intelligence_snapshots)
    first_row[4].metric("Comparações", summary.document_comparisons)

    second_row = st.columns(6)
    second_row[0].metric("Pendentes de preparação", summary.pending_documents)
    second_row[1].metric("Alertas preventivos", summary.preventive_alerts)
    second_row[2].metric("Alertas críticos", summary.critical_preventive_alerts)
    second_row[3].metric("Multiagente", summary.multi_agent_reports)
    second_row[4].metric("Padrões históricos", summary.historical_patterns)
    second_row[5].metric("A confirmar", summary.items_to_confirm)

    if summary.total_documents:
        st.progress(
            summary.prepared_documents / summary.total_documents,
            text="Cobertura semântica da base documental",
        )


def _render_document_health(
    documents: list[dict[str, object]],
    chunk_counts: dict[str, int],
) -> None:
    st.subheader("Saúde da base documental")
    if not documents:
        st.info("Nenhum documento enviado ainda.")
        return

    rows = []
    for document in documents[:10]:
        chunk_count = _document_chunk_count(document, chunk_counts)
        rows.append(
            {
                "Documento": document.get("filename", "Documento sem nome"),
                "IA": f"Preparado ({chunk_count} trechos)"
                if chunk_count
                else "Pendente de preparação",
                "Caracteres": document.get("text_char_count", 0),
                "Enviado em": _format_created_at(document.get("created_at")),
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_action_intelligence(analyses: list[dict[str, object]]) -> None:
    st.subheader("Prioridades dos planos de ação")
    action_plans = [analysis for analysis in analyses if _is_action_plan(analysis)]
    action_items = _extract_action_items(action_plans)
    if not action_items:
        st.info(
            "Nenhum plano de ação salvo ainda. Gere um plano de ação na aba Análises "
            "para acompanhar tarefas, prazos, responsáveis e riscos."
        )
        return

    rows = [
        {
            "Tarefa": item.get("task", ""),
            "Responsável": item.get("responsible", ""),
            "Prazo": item.get("deadline", ""),
            "Prioridade": item.get("priority", ""),
            "Risco": item.get("risk", ""),
        }
        for item in action_items[:10]
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    high_priority = [item for item in action_items if item.get("priority") == "Alta"]
    to_confirm = [item for item in action_items if _requires_confirmation(item)]
    if high_priority:
        st.warning(
            _format_count_message(
                len(high_priority),
                "item de alta prioridade merece acompanhamento no plano de ação.",
                "itens de alta prioridade merecem acompanhamento no plano de ação.",
            )
        )
    if to_confirm:
        st.info(
            _format_count_message(
                len(to_confirm),
                "item ainda tem responsável, prazo ou risco a confirmar.",
                "itens ainda têm responsável, prazo ou risco a confirmar.",
            )
        )


def _render_preventive_alerts(analyses: list[dict[str, object]]) -> None:
    st.subheader("Alertas preventivos")
    alert_reports = [analysis for analysis in analyses if _is_preventive_alert_report(analysis)]
    alerts = _extract_preventive_alerts(alert_reports)
    if not alerts:
        st.info("Nenhum alerta preventivo salvo ainda.")
        return

    severity_order = {"Crítica": 0, "Alta": 1, "Média": 2, "Baixa": 3}
    rows = [
        {
            "Alerta": alert.get("title", ""),
            "Tipo": alert.get("alert_type", ""),
            "Severidade": alert.get("severity", ""),
            "Status": alert.get("status", ""),
            "Responsável": alert.get("owner", ""),
            "Prazo": alert.get("deadline", ""),
        }
        for alert in sorted(
            alerts,
            key=lambda item: severity_order.get(str(item.get("severity", "")), 4),
        )[:10]
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    critical_alerts = [alert for alert in alerts if alert.get("severity") == "Crítica"]
    high_alerts = [alert for alert in alerts if alert.get("severity") == "Alta"]
    if critical_alerts or high_alerts:
        st.caption(
            "Radar executivo gerado a partir dos alertas preventivos salvos. Esses avisos "
            "indicam pontos de atenção nos documentos analisados, não falhas da plataforma."
        )
    if critical_alerts:
        st.warning(
            _format_count_message(
                len(critical_alerts),
                "alerta crítico encontrado. Valide evidências, responsável e prazo antes "
                "de tomar uma decisão.",
                "alertas críticos encontrados. Valide evidências, responsáveis e prazos "
                "antes de tomar uma decisão.",
            )
        )
    if high_alerts:
        st.info(
            _format_count_message(
                len(high_alerts),
                "alerta de alta severidade encontrado. Acompanhe o desdobramento nas "
                "próximas análises.",
                "alertas de alta severidade encontrados. Acompanhe os desdobramentos nas "
                "próximas análises.",
            )
        )


def _render_historical_patterns(analyses: list[dict[str, object]]) -> None:
    st.subheader("Padrões históricos")
    pattern_reports = [
        analysis for analysis in analyses if _is_historical_pattern_report(analysis)
    ]
    patterns = _extract_historical_patterns(pattern_reports)
    if not patterns:
        st.info(
            "Nenhum padrão histórico salvo ainda. Gere uma análise de padrões históricos "
            "na aba Análises para identificar recorrências entre documentos."
        )
        return

    severity_order = {"Alta": 0, "Média": 1, "Baixa": 2}
    rows = [
        {
            "Padrão": pattern.get("title", ""),
            "Tipo": pattern.get("pattern_type", ""),
            "Severidade": pattern.get("severity", ""),
            "Recorrência": pattern.get("recurrence", ""),
            "Recomendação": pattern.get("recommendation", ""),
        }
        for pattern in sorted(
            patterns,
            key=lambda item: severity_order.get(str(item.get("severity", "")), 3),
        )[:10]
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    high_patterns = [pattern for pattern in patterns if pattern.get("severity") == "Alta"]
    if high_patterns:
        st.warning(
            _format_count_message(
                len(high_patterns),
                "padrão de alta severidade merece acompanhamento.",
                "padrões de alta severidade merecem acompanhamento.",
            )
        )


def _render_multi_agent_findings(analyses: list[dict[str, object]]) -> None:
    st.subheader("Orquestração multiagente")
    reports = [analysis for analysis in analyses if _is_multi_agent_report(analysis)]
    findings = _extract_multi_agent_findings(reports)
    if not findings:
        st.info(
            "Nenhuma orquestração multiagente salva ainda. Gere uma análise multiagente "
            "na aba Análises para comparar achados, riscos e recomendações por perspectiva."
        )
        return

    severity_order = {"Alta": 0, "Média": 1, "Baixa": 2}
    rows = [
        {
            "Agente": finding.get("agent_name", ""),
            "Achado": finding.get("title", ""),
            "Categoria": finding.get("category", ""),
            "Severidade": finding.get("severity", ""),
            "Recomendação": finding.get("recommendation", ""),
        }
        for finding in sorted(
            findings,
            key=lambda item: severity_order.get(str(item.get("severity", "")), 3),
        )[:10]
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_executive_report_downloads(
    supabase_client: object,
    openai_client: object,
    user_id: str,
    config: AppConfig,
    documents: list[dict[str, object]],
    chunk_counts: dict[str, int],
    analyses: list[dict[str, object]],
) -> None:
    st.subheader("Relatório executivo com IA")
    st.write(
        "Gere uma análise narrativa com achados, riscos, recomendações, plano de ação "
        "sugerido, fontes e lacunas de evidência."
    )
    prepared_document_ids = [
        document_id
        for document_id in _document_ids(documents)
        if chunk_counts.get(document_id, 0) > 0
    ]
    if not prepared_document_ids:
        st.info("Prepare ao menos um documento para IA antes de gerar o relatório inteligente.")
    elif st.button("Gerar relatório executivo com IA"):
        _generate_intelligent_report_downloads(
            supabase_client,
            openai_client,
            user_id,
            config,
            documents,
            analyses,
            prepared_document_ids,
        )

    with st.expander("Exportar painel atual"):
        st.caption(
            "Este export é um resumo operacional do Dashboard. Para análise executiva, use o "
            "botão de IA acima."
        )
        report = build_executive_report(documents, chunk_counts, analyses)
        download_cols = st.columns(2)
        download_cols[0].download_button(
            "Baixar painel Markdown",
            data=executive_report_to_markdown(report),
            file_name="painel_executivo_synapse.md",
            mime="text/markdown",
        )
        download_cols[1].download_button(
            "Baixar painel PDF",
            data=executive_report_to_pdf(report),
            file_name="painel_executivo_synapse.pdf",
            mime="application/pdf",
        )


def _generate_intelligent_report_downloads(
    supabase_client: object,
    openai_client: object,
    user_id: str,
    config: AppConfig,
    documents: list[dict[str, object]],
    analyses: list[dict[str, object]],
    prepared_document_ids: list[str],
) -> None:
    intelligent_report_use_case = build_intelligent_executive_report_use_case()
    with st.spinner("Gerando relatório executivo inteligente..."):
        result = intelligent_report_use_case.execute(
            IntelligentExecutiveReportCommand(
                supabase_client=supabase_client,
                openai_client=openai_client,
                user_id=user_id,
                documents=documents,
                analyses=analyses,
                prepared_document_ids=prepared_document_ids,
                embedding_model=config.openai.embedding_model,
                generation_model=config.openai.generation_model,
            )
        )
    if not result.success:
        _render_use_case_message(result)
        return

    output = result.value
    if output is None:
        return
    report = output.report

    st.success("Relatório executivo com IA gerado.")
    st.markdown("**Síntese executiva**")
    st.write(report.executive_summary)
    if report.key_findings:
        st.markdown("**Principais achados**")
        for item in report.key_findings:
            st.write(f"- {item}")
    download_cols = st.columns(2)
    download_cols[0].download_button(
        "Baixar relatório inteligente Markdown",
        data=intelligent_report_to_markdown(report),
        file_name="relatorio_executivo_inteligente_synapse.md",
        mime="text/markdown",
    )
    download_cols[1].download_button(
        "Baixar relatório inteligente PDF",
        data=intelligent_report_to_pdf(report),
        file_name="relatorio_executivo_inteligente_synapse.pdf",
        mime="application/pdf",
    )


def _render_use_case_message(result: UseCaseResult[object]) -> None:
    if result.severity == ResultSeverity.WARNING:
        st.warning(result.message)
    elif result.severity == ResultSeverity.ERROR:
        st.error(result.message)
    elif result.severity == ResultSeverity.SUCCESS:
        st.success(result.message)
    else:
        st.info(result.message)


def _render_available_capabilities() -> None:
    st.subheader("Capacidades disponíveis")
    cols = st.columns(2)
    capabilities = describe_planned_analysis_capabilities()
    for index, capability in enumerate(capabilities):
        with cols[index % 2]:
            st.info(capability)


def _format_count_message(count: int, singular: str, plural: str) -> str:
    message = singular if count == 1 else plural
    return f"{count} {message}"


def _extract_action_items(analyses: list[dict[str, object]]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for analysis in analyses:
        metadata = analysis.get("metadata")
        if not isinstance(metadata, dict):
            continue
        raw_items = metadata.get("items")
        if not isinstance(raw_items, list):
            continue
        for raw_item in raw_items:
            if isinstance(raw_item, dict):
                items.append(raw_item)
    return items


def _extract_preventive_alerts(analyses: list[dict[str, object]]) -> list[dict[str, object]]:
    alerts: list[dict[str, object]] = []
    for analysis in analyses:
        metadata = analysis.get("metadata")
        if not isinstance(metadata, dict):
            continue
        raw_alerts = metadata.get("alerts")
        if not isinstance(raw_alerts, list):
            continue
        for raw_alert in raw_alerts:
            if isinstance(raw_alert, dict):
                alerts.append(raw_alert)
    return alerts


def _extract_historical_patterns(analyses: list[dict[str, object]]) -> list[dict[str, object]]:
    patterns: list[dict[str, object]] = []
    for analysis in analyses:
        metadata = analysis.get("metadata")
        if not isinstance(metadata, dict):
            continue
        raw_patterns = metadata.get("patterns")
        if not isinstance(raw_patterns, list):
            continue
        for raw_pattern in raw_patterns:
            if isinstance(raw_pattern, dict):
                patterns.append(raw_pattern)
    return patterns


def _extract_multi_agent_findings(analyses: list[dict[str, object]]) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for analysis in analyses:
        metadata = analysis.get("metadata")
        if not isinstance(metadata, dict):
            continue
        raw_outputs = metadata.get("agent_outputs")
        if not isinstance(raw_outputs, list):
            continue
        for raw_output in raw_outputs:
            if not isinstance(raw_output, dict):
                continue
            agent_name = str(raw_output.get("agent_name") or "")
            raw_findings = raw_output.get("findings")
            if not isinstance(raw_findings, list):
                continue
            for raw_finding in raw_findings:
                if isinstance(raw_finding, dict):
                    finding = dict(raw_finding)
                    finding["agent_name"] = agent_name
                    findings.append(finding)
    return findings


def _is_action_plan(analysis: dict[str, object]) -> bool:
    metadata = analysis.get("metadata")
    return isinstance(metadata, dict) and metadata.get("artifact_type") == "action_plan"


def _is_intelligence_snapshot(analysis: dict[str, object]) -> bool:
    metadata = analysis.get("metadata")
    return isinstance(metadata, dict) and metadata.get("artifact_type") == "intelligence_snapshot"


def _is_document_comparison(analysis: dict[str, object]) -> bool:
    metadata = analysis.get("metadata")
    return isinstance(metadata, dict) and metadata.get("artifact_type") == "document_comparison"


def _is_sentiment_report(analysis: dict[str, object]) -> bool:
    metadata = analysis.get("metadata")
    return isinstance(metadata, dict) and metadata.get("artifact_type") == "sentiment_report"


def _is_preventive_alert_report(analysis: dict[str, object]) -> bool:
    metadata = analysis.get("metadata")
    return (
        isinstance(metadata, dict)
        and metadata.get("artifact_type") == "preventive_alert_report"
    )


def _is_historical_pattern_report(analysis: dict[str, object]) -> bool:
    metadata = analysis.get("metadata")
    return (
        isinstance(metadata, dict)
        and metadata.get("artifact_type") == "historical_pattern_report"
    )


def _is_multi_agent_report(analysis: dict[str, object]) -> bool:
    metadata = analysis.get("metadata")
    return isinstance(metadata, dict) and metadata.get("artifact_type") == "multi_agent_report"


def _requires_confirmation(item: dict[str, object]) -> bool:
    return (
        _is_confirmation_value(item.get("responsible"))
        or _is_confirmation_value(item.get("deadline"))
        or _is_confirmation_value(item.get("risk"))
    )


def _is_confirmation_value(value: object) -> bool:
    if not isinstance(value, str):
        return True
    clean_value = value.strip()
    return not clean_value or clean_value.casefold() == "a confirmar"


def _document_chunk_count(document: dict[str, object], chunk_counts: dict[str, int]) -> int:
    document_id = document.get("id")
    return chunk_counts.get(document_id, 0) if isinstance(document_id, str) else 0


def _document_ids(documents: list[dict[str, object]]) -> list[str]:
    return [str(document["id"]) for document in documents if isinstance(document.get("id"), str)]


def _format_created_at(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    normalized_value = value.replace("Z", "+00:00")
    try:
        created_at = datetime.fromisoformat(normalized_value)
    except ValueError:
        return value
    return created_at.strftime("%d/%m/%Y %H:%M")
