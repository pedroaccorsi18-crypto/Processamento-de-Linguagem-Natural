from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime

import altair as alt
import streamlit as st

from synapse_ai.application.dashboard import IntelligentExecutiveReportCommand
from synapse_ai.application.result import ResultSeverity, UseCaseResult
from synapse_ai.auth.session import (
    get_access_token,
    get_current_session_user,
    get_refresh_token,
    update_auth_tokens,
)
from synapse_ai.clients.supabase_client import create_authenticated_supabase_connection
from synapse_ai.config import AppConfig
from synapse_ai.services.analysis_service import (
    describe_planned_analysis_capabilities,
)
from synapse_ai.services.report_service import (
    build_executive_report,
    executive_report_to_markdown,
    executive_report_to_pdf,
    intelligent_report_to_markdown,
    intelligent_report_to_pdf,
)
from synapse_ai.ui.cache import (
    cached_document_chunk_counts,
    cached_recent_analyses,
    cached_user_documents,
    get_openai_client,
)
from synapse_ai.ui.dashboard_use_cases import build_intelligent_executive_report_use_case
from synapse_ai.ui.state import current_tenant_id
from synapse_ai.ui.theme import (
    render_callout,
    render_empty_state,
    render_kpi_card,
    render_page_header,
)


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


@dataclass(frozen=True)
class DashboardFilters:
    departments: list[str]
    risk_level: str


def render_dashboard_page(config: AppConfig) -> None:
    user = get_current_session_user()
    render_page_header(
        "Dashboard executivo",
        "Leitura consolidada da base documental, riscos, planos de ação e inteligência salva.",
        "Área autenticada",
    )

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

    tenant_id = current_tenant_id(user)
    documents = cached_user_documents(client, tenant_id, user.id, 50)
    chunk_counts = cached_document_chunk_counts(
        client,
        tenant_id,
        user.id,
        tuple(_document_ids(documents)),
        config.openai.embedding_model,
    )
    analyses = cached_recent_analyses(client, tenant_id, user.id, 50)
    summary = build_dashboard_summary(documents, chunk_counts, analyses)
    openai_client = get_openai_client(config)

    _render_dashboard_overview(summary)
    _render_dashboard_attention(summary, analyses)
    _render_next_best_steps(summary)
    _render_executive_report_downloads(
        client,
        openai_client,
        user.id,
        config,
        documents,
        chunk_counts,
        analyses,
    )


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


def _render_dashboard_filters(analyses: list[dict[str, object]]) -> DashboardFilters:
    with st.expander("Filtros executivos", expanded=False):
        st.caption(
            "Use os filtros para recortar as análises salvas por área detectada e nível "
            "de risco. A base documental e os registros originais permanecem intactos."
        )
        departments = _available_departments(analyses)
        filter_cols = st.columns(2)
        selected_department = filter_cols[0].selectbox(
            "Área de leitura",
            options=["Todas as áreas", *departments],
            help=(
                "Filtra as análises por área quando o Synapse identifica sinais textuais "
                "ou metadados de departamento."
            ),
        )
        risk_level = filter_cols[1].selectbox(
            "Nível de risco",
            options=["Todos", "Crítica", "Alta", "Média", "Baixa"],
            help="Filtra alertas e artefatos vinculados ao nível selecionado.",
        )
        filters = DashboardFilters(
            departments=departments
            if selected_department == "Todas as áreas"
            else [selected_department],
            risk_level=risk_level,
        )
        filtered_count = len(_filter_dashboard_analyses(analyses, filters))
        st.caption(
            f"Recorte atual: {filtered_count} de {len(analyses)} análise(s) salva(s)."
        )
    return filters


def _available_departments(analyses: list[dict[str, object]]) -> list[str]:
    discovered = {
        department
        for analysis in analyses
        if (department := _department_for_analysis(analysis))
    }
    return sorted(discovered) or ["Geral"]


def _filter_dashboard_analyses(
    analyses: list[dict[str, object]],
    filters: DashboardFilters,
) -> list[dict[str, object]]:
    selected_departments = set(filters.departments)
    filtered = [
        analysis
        for analysis in analyses
        if _department_for_analysis(analysis) in selected_departments
    ]
    if filters.risk_level == "Todos":
        return filtered
    return [
        analysis
        for analysis in filtered
        if _analysis_has_risk_level(analysis, filters.risk_level)
    ]


def _department_for_analysis(analysis: dict[str, object]) -> str:
    metadata = analysis.get("metadata")
    if isinstance(metadata, dict):
        explicit_department = metadata.get("department") or metadata.get("departamento")
        if isinstance(explicit_department, str) and explicit_department.strip():
            return explicit_department.strip()

    searchable_text = " ".join(
        str(value or "")
        for value in (
            analysis.get("title"),
            analysis.get("question"),
            analysis.get("answer"),
            metadata,
        )
    ).lower()
    department_keywords = {
        "Financeiro": ("financeiro", "orçamento", "budget", "custo", "custos"),
        "RH": ("rh", "pessoas", "colaborador", "equipe", "treinamento"),
        "Tecnologia": ("tecnologia", "sistema", "infra", "login", "segurança"),
        "Operações": ("operação", "operacional", "processo", "entrega", "prazo"),
        "Jurídico": ("jurídico", "contrato", "compliance", "fornecedor", "assinatura"),
    }
    for department, keywords in department_keywords.items():
        if any(keyword in searchable_text for keyword in keywords):
            return department
    return "Geral"


def _analysis_has_risk_level(analysis: dict[str, object], risk_level: str) -> bool:
    metadata = analysis.get("metadata")
    if not isinstance(metadata, dict):
        return False

    direct_values = (
        metadata.get("severity"),
        metadata.get("priority"),
        metadata.get("risk_level"),
    )
    if any(_normalize_filter_level(value) == risk_level for value in direct_values):
        return True

    for container in _severity_containers(metadata):
        if isinstance(container, list) and any(
            isinstance(item, dict)
            and _normalize_filter_level(
                item.get("severity") or item.get("priority") or item.get("risk_level")
            )
            == risk_level
            for item in container
        ):
            return True
    return False


def _severity_containers(metadata: dict[str, object]) -> tuple[object, ...]:
    containers: list[object] = [
        metadata.get("alerts"),
        metadata.get("patterns"),
        metadata.get("items"),
        metadata.get("issues"),
        metadata.get("findings"),
        metadata.get("signals"),
    ]
    raw_outputs = metadata.get("agent_outputs")
    if isinstance(raw_outputs, list):
        for raw_output in raw_outputs:
            if isinstance(raw_output, dict):
                containers.append(raw_output.get("findings"))
    return tuple(containers)


def _normalize_filter_level(value: object) -> str:
    if not isinstance(value, str):
        return ""
    clean_value = value.strip().casefold()
    level_map = {
        "critica": "Crítica",
        "crítica": "Crítica",
        "alta": "Alta",
        "alto": "Alta",
        "média": "Média",
        "media": "Média",
        "médio": "Média",
        "medio": "Média",
        "baixa": "Baixa",
        "baixo": "Baixa",
    }
    return level_map.get(clean_value, "")


def _render_dashboard_overview(summary: DashboardSummary) -> None:
    st.subheader("Leitura executiva")
    render_callout(
        "Como interpretar este painel",
        "O Dashboard resume maturidade da base, sinais de risco e próximos passos. Detalhes "
        "operacionais ficam em Base documental, Estúdio de IA, Insights e Evidências.",
    )

    metric_cols = st.columns(4)
    with metric_cols[0]:
        render_kpi_card(
            "Base pronta",
            f"{summary.prepared_documents} de {summary.total_documents}",
            "Documentos preparados para perguntas com IA.",
            tone="green" if summary.pending_documents == 0 else "amber",
        )
    with metric_cols[1]:
        render_kpi_card(
            "Evidências",
            summary.saved_analyses,
            "Perguntas, relatórios e evidências salvas.",
            tone="blue",
        )
    with metric_cols[2]:
        render_kpi_card(
            "Riscos",
            summary.preventive_alerts,
            "Alertas preventivos extraídos dos documentos.",
            tone="red" if summary.critical_preventive_alerts else "amber",
        )
    with metric_cols[3]:
        render_kpi_card(
            "A confirmar",
            summary.items_to_confirm,
            "Itens sem responsável, prazo ou evidência completa.",
            tone="amber" if summary.items_to_confirm else "green",
        )

    if summary.total_documents:
        st.progress(
            summary.prepared_documents / summary.total_documents,
            text=(
                "Preparação para IA: "
                f"{summary.prepared_documents} de {summary.total_documents} documento(s) "
                "pronto(s) para perguntas com fontes"
            ),
        )
    else:
        render_empty_state(
            "Seu ecossistema está silencioso.",
            "Conecte sua base documental para transformar arquivos dispersos em "
            "inteligência executiva, evidências e alertas acionáveis.",
            icon="IA",
        )


def _render_dashboard_charts(analyses: list[dict[str, object]]) -> None:
    st.subheader("Mapa de riscos")
    alerts = _extract_preventive_alerts(
        [analysis for analysis in analyses if _is_preventive_alert_report(analysis)]
    )
    if not alerts:
        render_empty_state(
            "Ainda não há riscos mapeados.",
            "Gere alertas preventivos no Estúdio de IA para visualizar severidade, "
            "recorrência e evolução do risco organizacional.",
            icon="!",
        )
        return

    severity_tab, timeline_tab = st.tabs(["Severidade", "Evolução no tempo"])
    with severity_tab:
        _render_alert_severity_donut(alerts)
    with timeline_tab:
        _render_risk_evolution_chart(analyses)


def _render_alert_severity_donut(alerts: list[dict[str, object]]) -> None:
    st.caption("Distribuição de alertas por nível de severidade")
    severity_counts = Counter(str(alert.get("severity") or "A confirmar") for alert in alerts)
    chart_data = [
        {"Severidade": severity, "Alertas": count}
        for severity, count in severity_counts.items()
    ]
    chart = (
        alt.Chart(alt.Data(values=chart_data))
        .mark_arc(innerRadius=58, outerRadius=92, cornerRadius=4)
        .encode(
            theta=alt.Theta("Alertas:Q"),
            color=alt.Color(
                "Severidade:N",
                scale=alt.Scale(
                    domain=["Crítica", "Alta", "Média", "Baixa", "A confirmar"],
                    range=["#e11d48", "#f97316", "#f59e0b", "#2563eb", "#94a3b8"],
                ),
                legend=alt.Legend(orient="bottom"),
            ),
            tooltip=["Severidade:N", "Alertas:Q"],
        )
        .properties(height=360)
    )
    st.altair_chart(chart, use_container_width=True)


def _render_risk_evolution_chart(analyses: list[dict[str, object]]) -> None:
    st.caption("Evolução de riscos mapeados no tempo")
    timeline = _risk_evolution_points(analyses)
    chart = (
        alt.Chart(alt.Data(values=timeline))
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("Período:N", sort=None, title="Período"),
            y=alt.Y("Riscos:Q", title="Riscos mapeados"),
            color=alt.Color("Nível:N", legend=alt.Legend(orient="bottom")),
            tooltip=["Período:N", "Nível:N", "Riscos:Q"],
        )
        .properties(height=360)
    )
    st.altair_chart(chart, use_container_width=True)


def _risk_evolution_points(analyses: list[dict[str, object]]) -> list[dict[str, object]]:
    counter: Counter[tuple[str, str]] = Counter()
    for analysis in analyses:
        if not _is_preventive_alert_report(analysis):
            continue
        period = _risk_period_label(analysis.get("created_at"))
        for alert in _extract_preventive_alerts([analysis]):
            counter[(period, str(alert.get("severity") or "A confirmar"))] += 1

    if not counter:
        return [{"Período": "Atual", "Nível": "A confirmar", "Riscos": 0}]
    return [
        {"Período": period, "Nível": severity, "Riscos": count}
        for (period, severity), count in sorted(counter.items())
    ]


def _risk_period_label(value: object) -> str:
    if not isinstance(value, str) or not value:
        return "Atual"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%d/%m")
    except ValueError:
        return "Atual"


def _render_next_best_steps(summary: DashboardSummary) -> None:
    st.subheader("Próximo melhor passo")
    steps = "".join(f"<li>{step}</li>" for step in _build_next_best_steps(summary))
    st.markdown(f'<ol class="synapse-step-list">{steps}</ol>', unsafe_allow_html=True)


def _render_dashboard_attention(
    summary: DashboardSummary,
    analyses: list[dict[str, object]],
) -> None:
    st.subheader("Atenção executiva")
    critical_alerts = [
        alert
        for alert in _extract_preventive_alerts(
            [analysis for analysis in analyses if _is_preventive_alert_report(analysis)]
        )
        if alert.get("severity") == "Crítica"
    ]
    high_priority_items = [
        item for item in _extract_action_items(analyses) if item.get("priority") == "Alta"
    ]

    if not critical_alerts and not high_priority_items and summary.saved_analyses:
        st.success(
            "Nenhum item crítico consolidado no momento. Use Insights para explorar "
            "alertas, padrões e achados por perspectiva."
        )
        if st.button("Abrir Insights", key="cta-dashboard-intelligence", type="primary"):
            st.session_state["pending_private_page"] = "intelligence"
            st.rerun()
        return

    if not summary.saved_analyses:
        render_empty_state(
            "Ainda não há inteligência consolidada.",
            "Faça perguntas ou gere análises no Estúdio de IA para alimentar alertas, padrões, "
            "planos de ação e relatórios executivos.",
            icon="IA",
        )
        if st.button(
            "Ir para Estúdio de IA",
            key="cta-dashboard-analysis-empty",
            type="primary",
        ):
            st.session_state["pending_private_page"] = "analysis"
            st.rerun()
        return

    attention_cols = st.columns(2)
    with attention_cols[0]:
        render_kpi_card(
            "Alertas críticos",
            len(critical_alerts),
            "Riscos que exigem validação imediata.",
            tone="red" if critical_alerts else "green",
        )
    with attention_cols[1]:
        render_kpi_card(
            "Prioridade alta",
            len(high_priority_items),
            "Tarefas e decisões que precisam de acompanhamento.",
            tone="amber" if high_priority_items else "green",
        )
    if st.button("Investigar em Insights", key="cta-dashboard-intelligence-detail"):
        st.session_state["pending_private_page"] = "intelligence"
        st.rerun()


def _build_next_best_steps(summary: DashboardSummary) -> list[str]:
    if summary.total_documents == 0:
        return ["Envie o primeiro documento na aba Upload."]

    steps: list[str] = []
    if summary.pending_documents:
        steps.append(
            f"Prepare {summary.pending_documents} documento(s) para IA antes de fazer perguntas "
            "com fontes."
        )
    if summary.critical_preventive_alerts:
        steps.append(
            f"Revise {summary.critical_preventive_alerts} alerta(s) crítico(s) antes de "
            "tomar decisões executivas."
        )
    if summary.high_priority_items:
        steps.append(
            f"Acompanhe {summary.high_priority_items} item(ns) de alta prioridade nos planos "
            "de ação."
        )
    if summary.saved_analyses == 0:
        steps.append("Faça uma pergunta no Estúdio de IA para gerar as primeiras evidências.")
    elif summary.action_plans == 0:
        steps.append("Gere um plano de ação para transformar achados em tarefas acompanháveis.")
    if not steps:
        steps.append(
            "A base está preparada. Continue fazendo perguntas ou gere um relatório executivo."
        )
    return steps[:4]


def _render_document_health(
    documents: list[dict[str, object]],
    chunk_counts: dict[str, int],
) -> None:
    st.subheader("Saúde da base documental")
    st.caption(
        "Mostra quais arquivos já podem ser usados nas perguntas com IA e quais ainda "
        "precisam de preparação semântica."
    )
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
    with st.expander("Ver documentos e status de IA", expanded=True):
        st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_action_intelligence(analyses: list[dict[str, object]]) -> None:
    st.subheader("Prioridades dos planos de ação")
    st.caption(
        "Consolida tarefas, responsáveis, prazos e riscos extraídos dos planos de ação salvos."
    )
    action_plans = [analysis for analysis in analyses if _is_action_plan(analysis)]
    action_items = _extract_action_items(action_plans)
    if not action_items:
        st.info(
            "Nenhum plano de ação salvo ainda. Gere um plano de ação no Estúdio de IA "
            "para acompanhar tarefas, prazos, responsáveis e riscos."
        )
        _render_analysis_cta(
            "Ir para plano de ação",
            "action_plan",
            "cta-dashboard-action-plan",
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
    with st.expander("Ver tarefas priorizadas", expanded=False):
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


def _render_intelligence_inventory(summary: DashboardSummary) -> None:
    st.subheader("Inventário de inteligência")
    st.caption(
        "Resumo dos tipos de análise já acumulados. Esses números ajudam a entender a trilha "
        "de evidências existente, mas não indicam erro quando estão zerados."
    )
    inventory_cols = st.columns(4)
    inventory_cols[0].metric("Comparações", summary.document_comparisons)
    inventory_cols[1].metric("Relatórios", summary.intelligence_snapshots)
    inventory_cols[2].metric("Padrões", summary.historical_patterns)
    inventory_cols[3].metric("Multiagente", summary.multi_agent_reports)


def _render_preventive_alerts(analyses: list[dict[str, object]]) -> None:
    st.subheader("Alertas preventivos")
    st.caption(
        "Sinais de atenção identificados em análises salvas. Eles apontam riscos de negócio, "
        "não falhas técnicas da plataforma."
    )
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
    with st.expander("Ver alertas detectados", expanded=False):
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
    st.caption(
        "Recorrências detectadas quando você salva análises voltadas a padrões históricos."
    )
    pattern_reports = [
        analysis for analysis in analyses if _is_historical_pattern_report(analysis)
    ]
    patterns = _extract_historical_patterns(pattern_reports)
    if not patterns:
        st.info(
            "Nenhum padrão histórico salvo ainda. Gere uma análise de padrões históricos "
            "no Estúdio de IA para identificar recorrências entre documentos."
        )
        _render_analysis_cta(
            "Ir para padrões históricos",
            "historical_patterns",
            "cta-dashboard-historical-patterns",
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
    with st.expander("Ver recorrências detectadas", expanded=False):
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
    st.caption(
        "Achados gerados por perspectivas especializadas, como riscos, processos e decisões."
    )
    reports = [analysis for analysis in analyses if _is_multi_agent_report(analysis)]
    findings = _extract_multi_agent_findings(reports)
    if not findings:
        st.info(
            "Nenhuma orquestração multiagente salva ainda. Gere uma análise multiagente "
            "no Estúdio de IA para comparar achados, riscos e recomendações por perspectiva."
        )
        _render_analysis_cta(
            "Ir para orquestração multiagente",
            "multi_agent",
            "cta-dashboard-multi-agent",
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
    with st.expander("Ver achados por agente", expanded=False):
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
    elif st.button("Gerar relatório executivo com IA", type="primary"):
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
            "Exportar painel Markdown",
            data=executive_report_to_markdown(report),
            file_name="painel_executivo_synapse.md",
            mime="text/markdown",
        )
        download_cols[1].download_button(
            "Exportar painel PDF",
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
    st.toast("Relatório executivo pronto para download.")
    st.markdown("**Síntese executiva**")
    st.write(report.executive_summary)
    if report.key_findings:
        st.markdown("**Principais achados**")
        for item in report.key_findings:
            st.write(f"- {item}")
    download_cols = st.columns(2)
    download_cols[0].download_button(
        "Exportar relatório inteligente Markdown",
        data=intelligent_report_to_markdown(report),
        file_name="relatorio_executivo_inteligente_synapse.md",
        mime="text/markdown",
    )
    download_cols[1].download_button(
        "Exportar relatório inteligente PDF",
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


def _render_analysis_cta(label: str, focus: str, key: str) -> None:
    if st.button(label, key=key, type="primary"):
        st.session_state["analysis_focus"] = focus
        st.session_state["pending_private_page"] = "analysis"
        st.rerun()


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
