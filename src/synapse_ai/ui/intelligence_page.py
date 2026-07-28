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
from synapse_ai.ui.theme import render_callout, render_page_header


def render_intelligence_page(config: AppConfig) -> None:
    render_page_header(
        "Inteligência organizacional",
        "Explore alertas, padrões, planos de ação e achados especializados gerados a partir "
        "da base documental.",
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
        "Como usar esta área",
        "Use esta página para investigar o que já foi descoberto. Para gerar novas respostas, "
        "planos ou agentes, vá para Análises.",
    )
    _render_dashboard_charts(filtered_analyses)
    _render_preventive_alerts(filtered_analyses)
    _render_action_intelligence(filtered_analyses)
    _render_intelligence_inventory(summary)

    detail_cols = st.columns(2)
    with detail_cols[0]:
        _render_historical_patterns(filtered_analyses)
    with detail_cols[1]:
        _render_multi_agent_findings(filtered_analyses)

    with st.expander("Capacidades disponíveis", expanded=False):
        _render_available_capabilities()
