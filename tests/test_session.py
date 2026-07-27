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
    update_auth_tokens,
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
    assert state[USER_KEY] == {"id": "user-1", "email": "user@example.com"}
    assert get_current_session_user(state) == user
    assert get_access_token(state) == "access"
    assert get_refresh_token(state) == "refresh"

    clear_session(state)

    assert is_authenticated(state) is False
    assert get_current_session_user(state) is None
    assert get_access_token(state) is None
    assert get_refresh_token(state) is None


def test_get_current_session_user_restores_serialized_user() -> None:
    state: dict[str, object] = {
        AUTHENTICATED_KEY: True,
        USER_KEY: {"id": "user-1", "email": "user@example.com"},
        ACCESS_TOKEN_KEY: "access",
        REFRESH_TOKEN_KEY: "refresh",
    }

    assert get_current_session_user(state) == AuthenticatedUser(
        id="user-1",
        email="user@example.com",
    )
    assert is_authenticated(state) is True


def test_update_auth_tokens_keeps_current_user() -> None:
    state: dict[str, object] = {}
    user = AuthenticatedUser(id="user-1", email="user@example.com")

    initialize_session(state)
    set_auth_session(user, "old-access", "old-refresh", state)
    update_auth_tokens("new-access", "new-refresh", state)

    assert get_current_session_user(state) == user
    assert get_access_token(state) == "new-access"
    assert get_refresh_token(state) == "new-refresh"


def test_get_current_session_user_normalizes_legacy_user_object() -> None:
    class LegacyUser:
        id = "user-1"
        email = "user@example.com"

    state: dict[str, object] = {
        AUTHENTICATED_KEY: True,
        USER_KEY: LegacyUser(),
        ACCESS_TOKEN_KEY: "access",
        REFRESH_TOKEN_KEY: "refresh",
    }

    assert get_current_session_user(state) == AuthenticatedUser(
        id="user-1",
        email="user@example.com",
    )
    assert state[USER_KEY] == {"id": "user-1", "email": "user@example.com"}


def test_is_authenticated_requires_user_and_access_token() -> None:
    state_without_user = {
        AUTHENTICATED_KEY: True,
        USER_KEY: None,
        ACCESS_TOKEN_KEY: "access",
    }
    state_without_token = {
        AUTHENTICATED_KEY: True,
        USER_KEY: {"id": "user-1", "email": "user@example.com"},
        ACCESS_TOKEN_KEY: None,
    }

    assert is_authenticated(state_without_user) is False
    assert is_authenticated(state_without_token) is False
