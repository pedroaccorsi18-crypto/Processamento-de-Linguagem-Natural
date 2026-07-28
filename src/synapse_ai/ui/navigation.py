from __future__ import annotations

import streamlit as st


def public_navigation() -> str:
    st.sidebar.title("Synapse AI")
    return st.sidebar.radio(
        "Navegação",
        options=("home", "login", "register"),
        format_func=_public_label,
        key="public_page",
    )


def private_navigation() -> str:
    st.sidebar.title("Synapse AI")
    pending_page = st.session_state.pop("pending_private_page", None)
    if pending_page in {"dashboard", "upload", "analysis", "intelligence", "audit"}:
        st.session_state["private_page"] = pending_page
    return st.sidebar.radio(
        "Área autenticada",
        options=("dashboard", "upload", "analysis", "intelligence", "audit"),
        format_func=_private_label,
        key="private_page",
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
        "upload": "Base documental",
        "analysis": "Análises",
        "intelligence": "Inteligência",
        "audit": "Evidências",
    }
    return labels[page]
