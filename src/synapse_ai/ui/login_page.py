from __future__ import annotations

import streamlit as st

from synapse_ai.auth.auth import login_user
from synapse_ai.auth.session import set_auth_session
from synapse_ai.clients.supabase_client import create_supabase_client
from synapse_ai.config import AppConfig
from synapse_ai.ui.cache import invalidate_session_resources
from synapse_ai.ui.theme import render_page_header
from synapse_ai.utils.validation import is_valid_email


def render_login_page(config: AppConfig) -> None:
    render_page_header(
        "Entrar no Synapse",
        "Acesse sua área privada de inteligência organizacional.",
        "Acesso seguro",
    )

    _, center, _ = st.columns((0.2, 0.6, 0.2))
    with center:
        with st.form("login_form"):
            email = st.text_input("E-mail", placeholder="voce@empresa.com")
            password = st.text_input("Senha", type="password")
            submitted = st.form_submit_button(
                "Entrar com segurança",
                type="primary",
                use_container_width=True,
            )
        st.caption("Seu acesso isola documentos, análises e evidências por conta.")

    if not submitted:
        st.caption("Ainda não tem conta? Use a página de cadastro no menu lateral.")
        return

    if not is_valid_email(email) or not password:
        st.warning("Informe um e-mail válido e sua senha.")
        return

    client = create_supabase_client(config)
    result = login_user(client, email, password)
    if not result.success or result.user is None or result.access_token is None:
        st.error(result.message)
        return

    invalidate_session_resources()
    set_auth_session(result.user, result.access_token, result.refresh_token)
    st.success(result.message)
    st.rerun()
