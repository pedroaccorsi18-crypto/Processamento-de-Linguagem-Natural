from __future__ import annotations

import streamlit as st

from synapse_ai.auth.session import clear_session, get_current_session_user
from synapse_ai.services.analysis_service import describe_planned_analysis_capabilities


def render_dashboard_page() -> None:
    user = get_current_session_user()
    st.title("Dashboard")
    if user is not None:
        st.caption(f"Usuário autenticado: {user.email}")

    if st.button("Sair"):
        clear_session()
        st.rerun()

    st.subheader("Status do projeto")
    st.success("Fase 2 — Data Layer em andamento.")
    st.write("Upload, extração textual, metadados e persistência inicial estão disponíveis.")

    st.subheader("Próximas capacidades")
    cols = st.columns(2)
    capabilities = describe_planned_analysis_capabilities()
    for index, capability in enumerate(capabilities):
        with cols[index % 2]:
            st.info(capability)
