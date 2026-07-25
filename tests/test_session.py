from __future__ import annotations

from synapse_ai.auth.session import (
    ACCESS_TOKEN_KEY,
    AUTHENTICATED_KEY,
    REFRESH_TOKEN_KEY,
    USER_KEY,
    clear_session,
    get_access_token,
    get_current_session_user,
    get_refresh_token,
    initialize_session,
    is_authenticated,
    set_auth_session,
)
from synapse_ai.models.user import AuthenticatedUser


def test_initialize_session_sets_defaults() -> None:
    state: dict[str, object] = {}

    initialize_session(state)

    assert state[AUTHENTICATED_KEY] is False
    assert state[USER_KEY] is None
    assert state[ACCESS_TOKEN_KEY] is None
    assert state[REFRESH_TOKEN_KEY] is None


def test_set_and_clear_session() -> None:
    state: dict[str, object] = {}
    user = AuthenticatedUser(id="user-1", email="user@example.com")

    initialize_session(state)
    set_auth_session(user, "access", "refresh", state)

    assert is_authenticated(state) is True
    assert get_current_session_user(state) == user
    assert get_access_token(state) == "access"
    assert get_refresh_token(state) == "refresh"

    clear_session(state)

    assert is_authenticated(state) is False
    assert get_current_session_user(state) is None
    assert get_access_token(state) is None
    assert get_refresh_token(state) is None
