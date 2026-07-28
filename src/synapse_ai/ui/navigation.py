from __future__ import annotations

import streamlit as st

from synapse_ai.auth.session import clear_session, get_current_session_user


def public_navigation() -> str:
    st.sidebar.title("Synapse AI")
    pending_page = st.session_state.pop("pending_public_page", None)
    if pending_page in {"home", "login", "register"}:
        st.session_state["public_page"] = pending_page
    return st.sidebar.radio(
        "Navegação",
        options=("home", "login", "register"),
        format_func=_public_label,
        key="public_page",
    )


def private_navigation() -> str:
    st.sidebar.title("Synapse AI")
    user = get_current_session_user()
    if user is not None:
        st.sidebar.caption(f"Conta: {user.email}")
        if st.sidebar.button("Sair", key="sidebar-logout"):
            clear_session()
            st.rerun()

    pending_page = st.session_state.pop("pending_private_page", None)
    if pending_page in {"dashboard", "upload", "analysis", "intelligence", "audit", "copilot"}:
        st.session_state["private_page"] = pending_page
    return st.sidebar.radio(
        "Área autenticada",
        options=("dashboard", "upload", "analysis", "intelligence", "audit", "copilot"),
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
        "analysis": "Estúdio de IA",
        "intelligence": "Insights",
        "audit": "Evidências",
        "copilot": "Copiloto",
    }
    return labels[page]
