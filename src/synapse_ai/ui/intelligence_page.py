from __future__ import annotations

import streamlit as st

from synapse_ai.auth.session import (
    get_access_token,
    get_current_session_user,
    get_refresh_token,
    update_auth_tokens,
)
from synapse_ai.clients.supabase_client import create_authenticated_supabase_connection
from synapse_ai.config import AppConfig
from synapse_ai.ui.cache import (
    cached_document_chunk_counts,
    cached_recent_analyses,
    cached_user_documents,
)
from synapse_ai.ui.dashboard_page import (
    DashboardSummary,
    _document_ids,
    _filter_dashboard_analyses,
    _render_action_intelligence,
    _render_available_capabilities,
    _render_dashboard_charts,
    _render_dashboard_filters,
    _render_historical_patterns,
    _render_intelligence_inventory,
    _render_multi_agent_findings,
    _render_preventive_alerts,
    build_dashboard_summary,
)
from synapse_ai.ui.state import current_tenant_id
from synapse_ai.ui.theme import render_callout, render_kpi_card, render_page_header


def render_intelligence_page(config: AppConfig) -> None:
    render_page_header(
        "Insights organizacionais",
        "Investigue riscos, planos, padrões e achados especializados sem misturar operação "
        "com análise executiva.",
        "Insights consolidados",
    )

    user = get_current_session_user()
    if user is None:
        st.info("Não conseguimos confirmar sua conta nesta aba. Atualize a página para continuar.")
        return

    access_token = get_access_token()
    if access_token is None:
        st.info("Sua autenticação precisa ser renovada para consultar inteligência.")
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
    filters = _render_dashboard_filters(analyses)
    filtered_analyses = _filter_dashboard_analyses(analyses, filters)
    summary = build_dashboard_summary(documents, chunk_counts, filtered_analyses)

    render_callout(
        "Leitura guiada",
        "Comece pelo mapa de riscos. Depois abra a aba específica para investigar alertas, "
        "planos de ação, padrões históricos ou agentes especializados.",
    )

    _render_insights_summary(summary)
    _render_dashboard_charts(filtered_analyses)

    risk_tab, plan_tab, pattern_tab, agent_tab, inventory_tab = st.tabs(
        ["Riscos", "Planos de ação", "Padrões", "Agentes", "Inventário"]
    )
    with risk_tab:
        _render_preventive_alerts(filtered_analyses)
    with plan_tab:
        _render_action_intelligence(filtered_analyses)
    with pattern_tab:
        _render_historical_patterns(filtered_analyses)
    with agent_tab:
        _render_multi_agent_findings(filtered_analyses)
    with inventory_tab:
        _render_intelligence_inventory(summary)

        with st.expander("Capacidades disponíveis", expanded=False):
            _render_available_capabilities()


def _render_insights_summary(summary: DashboardSummary) -> None:
    summary_cols = st.columns(4)
    with summary_cols[0]:
        render_kpi_card(
            "Alertas",
            summary.preventive_alerts,
            "Sinais preventivos detectados.",
            tone="red" if summary.critical_preventive_alerts else "amber",
        )
    with summary_cols[1]:
        render_kpi_card(
            "Críticos",
            summary.critical_preventive_alerts,
            "Exigem validação imediata.",
            tone="red" if summary.critical_preventive_alerts else "green",
        )
    with summary_cols[2]:
        render_kpi_card(
            "Planos",
            summary.action_plans,
            "Planos de ação salvos.",
            tone="blue",
        )
    with summary_cols[3]:
        render_kpi_card(
            "Achados",
            summary.multi_agent_findings + summary.historical_patterns,
            "Padrões e achados multiagente.",
            tone="green" if summary.multi_agent_findings or summary.historical_patterns else "blue",
        )
