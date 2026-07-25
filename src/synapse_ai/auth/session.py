from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

from synapse_ai.models.user import AuthenticatedUser

AUTHENTICATED_KEY = "synapse_authenticated"
USER_KEY = "synapse_user"
ACCESS_TOKEN_KEY = "synapse_access_token"
REFRESH_TOKEN_KEY = "synapse_refresh_token"


def initialize_session(state: MutableMapping[str, Any] | None = None) -> None:
    session = _state(state)
    session.setdefault(AUTHENTICATED_KEY, False)
    session.setdefault(USER_KEY, None)
    session.setdefault(ACCESS_TOKEN_KEY, None)
    session.setdefault(REFRESH_TOKEN_KEY, None)


def is_authenticated(state: MutableMapping[str, Any] | None = None) -> bool:
    session = _state(state)
    return bool(session.get(AUTHENTICATED_KEY))


def get_current_session_user(
    state: MutableMapping[str, Any] | None = None,
) -> AuthenticatedUser | None:
    session = _state(state)
    user = session.get(USER_KEY)
    return user if isinstance(user, AuthenticatedUser) else None


def get_access_token(state: MutableMapping[str, Any] | None = None) -> str | None:
    token = _state(state).get(ACCESS_TOKEN_KEY)
    return token if isinstance(token, str) else None


def get_refresh_token(state: MutableMapping[str, Any] | None = None) -> str | None:
    token = _state(state).get(REFRESH_TOKEN_KEY)
    return token if isinstance(token, str) else None


def set_auth_session(
    user: AuthenticatedUser,
    access_token: str,
    refresh_token: str | None,
    state: MutableMapping[str, Any] | None = None,
) -> None:
    session = _state(state)
    session[AUTHENTICATED_KEY] = True
    session[USER_KEY] = user
    session[ACCESS_TOKEN_KEY] = access_token
    session[REFRESH_TOKEN_KEY] = refresh_token


def clear_session(state: MutableMapping[str, Any] | None = None) -> None:
    session = _state(state)
    session[AUTHENTICATED_KEY] = False
    session[USER_KEY] = None
    session[ACCESS_TOKEN_KEY] = None
    session[REFRESH_TOKEN_KEY] = None


def restore_session(
    user: AuthenticatedUser,
    access_token: str,
    refresh_token: str | None,
    state: MutableMapping[str, Any] | None = None,
) -> None:
    set_auth_session(user, access_token, refresh_token, state)


def _state(state: MutableMapping[str, Any] | None) -> MutableMapping[str, Any]:
    if state is not None:
        return state

    import streamlit as st

    return st.session_state
