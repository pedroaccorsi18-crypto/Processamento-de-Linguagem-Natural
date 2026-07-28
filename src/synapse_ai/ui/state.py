from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

import streamlit as st

from synapse_ai.models.user import AuthenticatedUser

UI_STATE_VERSION_KEY = "synapse_ui_state_version"
ACTIVE_TENANT_KEY = "synapse_active_tenant_id"
SESSION_ANALYSIS_HISTORY_KEY = "synapse_session_analysis_history"
SESSION_PROCESSED_DOCUMENTS_KEY = "synapse_session_processed_documents"
SESSION_DOCUMENT_STATUS_KEY = "synapse_session_document_status"
WELCOME_TOUR_SHOWN_KEY = "synapse_welcome_tour_shown"
LAST_SCOPE_KEY = "synapse_last_analysis_scope"

UI_STATE_VERSION = "2026-07-28.1"


def initialize_ui_state(
    user: AuthenticatedUser | None = None,
    state: MutableMapping[str, Any] | None = None,
) -> None:
    """Initialize UI-only state without touching authentication or business data."""
    session = _state(state)
    session.setdefault(UI_STATE_VERSION_KEY, UI_STATE_VERSION)
    session.setdefault(SESSION_ANALYSIS_HISTORY_KEY, [])
    session.setdefault(SESSION_PROCESSED_DOCUMENTS_KEY, {})
    session.setdefault(SESSION_DOCUMENT_STATUS_KEY, {})
    session.setdefault(WELCOME_TOUR_SHOWN_KEY, False)
    session.setdefault(LAST_SCOPE_KEY, "Último documento enviado")
    if user is not None:
        session[ACTIVE_TENANT_KEY] = resolve_tenant_id(user)
    else:
        session.setdefault(ACTIVE_TENANT_KEY, "")


def resolve_tenant_id(user: AuthenticatedUser) -> str:
    """Resolve the tenant boundary used by UI cache keys.

    In a production B2B setup this value should come from an organization membership
    table or identity provider claim. For the academic MVP, the e-mail domain gives
    a deterministic tenant-like namespace while Supabase RLS still enforces user access.
    """
    _, _, domain = user.email.lower().partition("@")
    return domain or user.id


def current_tenant_id(
    user: AuthenticatedUser | None,
    state: MutableMapping[str, Any] | None = None,
) -> str:
    session = _state(state)
    if user is not None:
        tenant_id = resolve_tenant_id(user)
        session[ACTIVE_TENANT_KEY] = tenant_id
        return tenant_id
    tenant_id = session.get(ACTIVE_TENANT_KEY)
    return tenant_id if isinstance(tenant_id, str) else ""


def remember_processed_document(
    document_id: str,
    filename: str,
    *,
    state: MutableMapping[str, Any] | None = None,
) -> None:
    session = _state(state)
    documents = session.setdefault(SESSION_PROCESSED_DOCUMENTS_KEY, {})
    if isinstance(documents, dict):
        documents[document_id] = filename


def remember_document_status(
    document_id: str,
    status: str,
    *,
    state: MutableMapping[str, Any] | None = None,
) -> None:
    session = _state(state)
    statuses = session.setdefault(SESSION_DOCUMENT_STATUS_KEY, {})
    if isinstance(statuses, dict):
        statuses[document_id] = status


def remember_analysis_result(
    label: str,
    *,
    state: MutableMapping[str, Any] | None = None,
) -> None:
    session = _state(state)
    history = session.setdefault(SESSION_ANALYSIS_HISTORY_KEY, [])
    if isinstance(history, list):
        history.insert(0, label)
        del history[10:]


def render_welcome_tour(
    user: AuthenticatedUser | None,
    state: MutableMapping[str, Any] | None = None,
) -> None:
    """Show a lightweight first-session onboarding guide."""
    session = _state(state)
    if user is None or bool(session.get(WELCOME_TOUR_SHOWN_KEY)):
        return

    session[WELCOME_TOUR_SHOWN_KEY] = True
    st.toast(
        "Bem-vindo ao Synapse AI. Comece pela Base documental, prepare a IA e use Análises "
        "para gerar inteligência com fontes.",
    )


def _state(state: MutableMapping[str, Any] | None) -> MutableMapping[str, Any]:
    return state if state is not None else st.session_state
