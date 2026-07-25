from __future__ import annotations

import streamlit as st


def public_navigation() -> str:
    st.sidebar.title("Synapse AI")
    return st.sidebar.radio(
        "Navegação",
        options=("home", "login", "register"),
        format_func=_public_label,
    )


def private_navigation() -> str:
    st.sidebar.title("Synapse AI")
    return st.sidebar.radio(
        "Área autenticada",
        options=("dashboard", "upload", "analysis"),
        format_func=_private_label,
    )


def _public_label(page: str) -> str:
    labels = {
        "home": "Início",
        "login": "Entrar",
        "register": "Cadastro",
    }
    return labels[page]


def _private_label(page: str) -> str:
    labels = {
        "dashboard": "Dashboard",
        "upload": "Upload",
        "analysis": "Análises",
    }
    return labels[page]
