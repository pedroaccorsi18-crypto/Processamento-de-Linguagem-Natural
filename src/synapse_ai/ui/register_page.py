from __future__ import annotations

import streamlit as st

from synapse_ai.auth.auth import register_user
from synapse_ai.clients.supabase_client import create_supabase_client
from synapse_ai.config import AppConfig
from synapse_ai.ui.theme import render_page_header
from synapse_ai.utils.validation import is_valid_email, passwords_match, validate_password


def render_register_page(config: AppConfig) -> None:
    render_page_header(
        "Cadastro",
        "Crie sua conta para acessar as capacidades de inteligência organizacional do Synapse AI.",
        "Novo acesso",
    )

    with st.form("register_form"):
        email = st.text_input("E-mail")
        password = st.text_input("Senha", type="password")
        confirmation = st.text_input("Confirmação de senha", type="password")
        submitted = st.form_submit_button("Cadastrar")

    if not submitted:
        return

    if not is_valid_email(email):
        st.warning("Informe um e-mail válido.")
        return
    if not validate_password(password):
        st.warning("A senha deve ter pelo menos 8 caracteres.")
        return
    if not passwords_match(password, confirmation):
        st.warning("A confirmação de senha não confere.")
        return

    client = create_supabase_client(config)
    result = register_user(client, email, password, config.app.public_url)
    if result.success:
        st.success(result.message)
    else:
        st.error(result.message)
