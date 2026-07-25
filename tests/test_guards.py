from __future__ import annotations

from synapse_ai.auth.guards import private_page_allowed, redirect_authenticated, require_auth
from synapse_ai.auth.session import initialize_session, set_auth_session
from synapse_ai.models.user import AuthenticatedUser


def test_require_auth_denies_anonymous_user() -> None:
    state: dict[str, object] = {}
    initialize_session(state)

    assert require_auth(state) is False
    assert private_page_allowed("upload", state) is False


def test_require_auth_allows_authenticated_user() -> None:
    state: dict[str, object] = {}
    initialize_session(state)
    set_auth_session(
        AuthenticatedUser(id="user-1", email="user@example.com"),
        "access",
        "refresh",
        state,
    )

    assert require_auth(state) is True
    assert private_page_allowed("analysis", state) is True
    assert redirect_authenticated("login", state) == "dashboard"
