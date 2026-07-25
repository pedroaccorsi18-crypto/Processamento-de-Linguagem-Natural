from __future__ import annotations

import streamlit as st


def render_home_page() -> None:
    st.title("Synapse AI")
    st.subheader("Organizational Cognitive Intelligence Platform")
    st.write(
        "MVP acadêmico para organizar conhecimento institucional, preparar busca semântica "
        "e apoiar consultas futuras sobre documentos organizacionais."
    )
    st.info(
        "Esta fase entrega a fundação técnica. O pipeline completo de PLN virá "
        "nas próximas fases."
    )
    col_login, col_register = st.columns(2)
    with col_login:
        st.caption("Use o menu lateral para entrar.")
    with col_register:
        st.caption("Novos usuários podem criar uma conta pelo cadastro.")
