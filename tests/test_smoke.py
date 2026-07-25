from __future__ import annotations

import importlib


def test_main_modules_import() -> None:
    modules = [
        "synapse_ai.config",
        "synapse_ai.auth.auth",
        "synapse_ai.auth.session",
        "synapse_ai.auth.guards",
        "synapse_ai.clients.supabase_client",
        "synapse_ai.clients.openai_client",
        "synapse_ai.services.document_service",
        "synapse_ai.services.document_repository",
        "synapse_ai.services.analysis_service",
        "synapse_ai.ui.home_page",
        "synapse_ai.ui.login_page",
        "synapse_ai.ui.register_page",
        "synapse_ai.ui.dashboard_page",
        "synapse_ai.ui.upload_page",
        "synapse_ai.ui.analysis_page",
    ]

    for module in modules:
        importlib.import_module(module)
