from __future__ import annotations

import streamlit as st

from synapse_ai.services.analysis_service import analysis_pipeline_available


def render_analysis_page() -> None:
    st.title("Análises")
    st.write("Espaço reservado para consultas, sínteses e rastreabilidade das fontes.")
    st.warning("RAG, embeddings e sínteses com IA serão implementados na Fase 3.")
    if not analysis_pipeline_available():
        st.info("Na Fase 2, o foco é upload, extração textual, metadados e persistência.")
