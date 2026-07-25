from __future__ import annotations

import streamlit as st

from synapse_ai.auth.session import initialize_session, is_authenticated
from synapse_ai.config import MissingConfigError, load_config
from synapse_ai.ui.analysis_page import render_analysis_page
from synapse_ai.ui.dashboard_page import render_dashboard_page
from synapse_ai.ui.home_page import render_home_page
from synapse_ai.ui.login_page import render_login_page
from synapse_ai.ui.navigation import private_navigation, public_navigation
from synapse_ai.ui.register_page import render_register_page
from synapse_ai.ui.upload_page import render_upload_page
from synapse_ai.utils.logging_utils import configure_logging


def main() -> None:
    st.set_page_config(
        page_title="Synapse AI",
        page_icon="🧠",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    configure_logging()
    initialize_session()

    try:
        config = load_config()
    except MissingConfigError as exc:
        st.error(f"Configuração ausente: {exc.setting_name}")
        st.info("Revise o arquivo local .streamlit/secrets.toml antes de iniciar o app.")
        st.stop()

    if is_authenticated():
        selected_page = private_navigation()
        if selected_page == "dashboard":
            render_dashboard_page()
        elif selected_page == "upload":
            render_upload_page(config)
        elif selected_page == "analysis":
            render_analysis_page()
        return

    selected_page = public_navigation()
    if selected_page == "login":
        render_login_page(config)
    elif selected_page == "register":
        render_register_page(config)
    else:
        render_home_page()


if __name__ == "__main__":
    main()
