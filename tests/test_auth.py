from __future__ import annotations

from types import SimpleNamespace

from synapse_ai.auth.auth import get_current_user, login_user, logout_user, register_user


class FakeAuth:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.signed_out = False
        self.sign_up_payload: dict[str, object] | None = None

    def sign_up(self, payload: dict[str, object]) -> SimpleNamespace:
        if self.fail:
            raise RuntimeError("failed")
        self.sign_up_payload = payload
        return SimpleNamespace(user=SimpleNamespace(id="user-1", email="user@example.com"))

    def sign_in_with_password(self, _payload: dict[str, str]) -> SimpleNamespace:
        if self.fail:
            raise RuntimeError("failed")
        return SimpleNamespace(
            user=SimpleNamespace(id="user-1", email="user@example.com"),
            session=SimpleNamespace(access_token="access", refresh_token="refresh"),
        )

    def sign_out(self) -> None:
        if self.fail:
            raise RuntimeError("failed")
        self.signed_out = True

    def get_user(self, _access_token: str | None = None) -> SimpleNamespace:
        if self.fail:
            raise RuntimeError("failed")
        return SimpleNamespace(user=SimpleNamespace(id="user-1", email="user@example.com"))


class FakeClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.auth = FakeAuth(fail=fail)


def test_register_user_success() -> None:
    result = register_user(FakeClient(), "user@example.com", "password123")

    assert result.success is True
    assert result.user is not None
    assert result.user.email == "user@example.com"


def test_register_user_sends_email_redirect_when_available() -> None:
    client = FakeClient()

    result = register_user(
        client,
        "user@example.com",
        "password123",
        "https://synapse-ai-pnl.streamlit.app",
    )

    assert result.success is True
    assert client.auth.sign_up_payload == {
        "email": "user@example.com",
        "password": "password123",
        "options": {"email_redirect_to": "https://synapse-ai-pnl.streamlit.app"},
    }


def test_register_user_failure() -> None:
    result = register_user(FakeClient(fail=True), "user@example.com", "password123")

    assert result.success is False


def test_login_user_success() -> None:
    result = login_user(FakeClient(), "user@example.com", "password123")

    assert result.success is True
    assert result.access_token == "access"
    assert result.refresh_token == "refresh"


def test_login_user_failure() -> None:
    result = login_user(FakeClient(fail=True), "user@example.com", "password123")

    assert result.success is False


def test_logout_user_success() -> None:
    client = FakeClient()

    result = logout_user(client)

    assert result.success is True
    assert client.auth.signed_out is True


def test_get_current_user() -> None:
    user = get_current_user(FakeClient(), "access")

    assert user is not None
    assert user.id == "user-1"
