from __future__ import annotations

import streamlit as st

from synapse_ai.ui.theme import render_callout, render_page_header


def render_home_page() -> None:
    render_page_header(
        "Synapse AI",
        "MVP acadêmico para organizar conhecimento institucional, preparar busca semântica "
        "e apoiar consultas sobre documentos organizacionais.",
        "Organizational Cognitive Intelligence Platform",
    )
    render_callout(
        "Plataforma operacional de inteligência documental",
        "A plataforma já processa arquivos, cria uma base semântica e responde perguntas "
        "com fontes recuperadas dos documentos enviados.",
    )
    col_login, col_register = st.columns(2)
    with col_login:
        st.info("Use o menu lateral para entrar na área privada.")
    with col_register:
        st.info("Novos usuários podem criar uma conta pelo cadastro.")
