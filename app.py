from __future__ import annotations

import streamlit as st

from synapse_ai.auth.session import get_current_session_user, initialize_session, is_authenticated
from synapse_ai.config import MissingConfigError, load_config
from synapse_ai.ui.navigation import private_navigation, public_navigation
from synapse_ai.ui.state import initialize_ui_state, render_welcome_tour
from synapse_ai.ui.theme import apply_synapse_theme
from synapse_ai.utils.logging_utils import configure_logging


def main() -> None:
    st.set_page_config(
        page_title="Synapse AI",
        page_icon="🧠",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    configure_logging()
    apply_synapse_theme()
    initialize_session()
    initialize_ui_state()

    try:
        config = load_config()
    except MissingConfigError as exc:
        st.error(f"Configuração ausente: {exc.setting_name}")
        st.info("Revise o arquivo local .streamlit/secrets.toml antes de iniciar o app.")
        st.stop()

    if is_authenticated():
        from synapse_ai.ui.copilot_page import (
            render_copilot,
            render_copilot_context_panel,
            render_copilot_sidebar,
        )

        user = get_current_session_user()
        initialize_ui_state(user)
        render_welcome_tour(user)
        selected_page = private_navigation()
        if selected_page != "copilot":
            render_copilot_sidebar(config, selected_page)
        if selected_page == "dashboard":
            from synapse_ai.ui.dashboard_page import render_dashboard_page

            render_dashboard_page(config)
        elif selected_page == "upload":
            from synapse_ai.ui.upload_page import render_upload_page

            render_upload_page(config)
        elif selected_page == "analysis":
            from synapse_ai.ui.analysis_page import render_analysis_page

            render_analysis_page(config)
        elif selected_page == "intelligence":
            from synapse_ai.ui.intelligence_page import render_intelligence_page

            render_intelligence_page(config)
        elif selected_page == "audit":
            from synapse_ai.ui.audit_page import render_audit_page

            render_audit_page(config)
        elif selected_page == "copilot":
            render_copilot(config)
        if selected_page != "copilot":
            render_copilot_context_panel(config, selected_page)
        return

    from synapse_ai.ui.upload_page import (
        has_google_drive_oauth_return,
        render_google_drive_oauth_return_without_session,
        render_upload_page,
        restore_google_drive_oauth_synapse_session,
    )

    if has_google_drive_oauth_return():
        if restore_google_drive_oauth_synapse_session():
            render_upload_page(config)
            return
        render_google_drive_oauth_return_without_session(config)
        return

    selected_page = public_navigation()
    if selected_page == "login":
        from synapse_ai.ui.login_page import render_login_page

        render_login_page(config)
    elif selected_page == "register":
        from synapse_ai.ui.register_page import render_register_page

        render_register_page(config)
    else:
        from synapse_ai.ui.home_page import render_home_page

        render_home_page()


if __name__ == "__main__":
    main()
