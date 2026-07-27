from __future__ import annotations

from typing import Any

import pytest

from synapse_ai.clients.openai_client import create_openai_client
from synapse_ai.clients.supabase_client import (
    create_authenticated_supabase_client,
    create_authenticated_supabase_connection,
    create_supabase_client,
)
from synapse_ai.config import load_config


def _config() -> Any:
    return load_config(
        {
            "supabase": {
                "url": "https://example.supabase.co",
                "publishable_key": "public-key",
            },
            "openai": {"api_key": "openai-key"},
        }
    )


def test_create_supabase_client_uses_project_url_and_publishable_key() -> None:
    calls: dict[str, str] = {}

    def fake_factory(url: str, key: str) -> object:
        calls["url"] = url
        calls["key"] = key
        return object()

    client = create_supabase_client(_config(), fake_factory)

    assert client is not None
    assert calls == {"url": "https://example.supabase.co", "key": "public-key"}


def test_create_supabase_client_wraps_errors() -> None:
    def failing_factory(_url: str, _key: str) -> object:
        raise ValueError("boom")

    with pytest.raises(RuntimeError):
        create_supabase_client(_config(), failing_factory)


def test_create_authenticated_supabase_client_restores_session() -> None:
    class FakeAuth:
        def __init__(self) -> None:
            self.session: tuple[str, str | None] | None = None

        def set_session(self, access_token: str, refresh_token: str | None) -> None:
            self.session = (access_token, refresh_token)

    class FakeClient:
        def __init__(self) -> None:
            self.auth = FakeAuth()

    fake_client = FakeClient()

    def fake_factory(_url: str, _key: str) -> FakeClient:
        return fake_client

    client = create_authenticated_supabase_client(_config(), "access", "refresh", fake_factory)

    assert client is fake_client
    assert client.auth.session == ("access", "refresh")


def test_create_authenticated_supabase_connection_returns_refreshed_tokens() -> None:
    class FakeAuth:
        def set_session(self, _access_token: str, _refresh_token: str | None) -> object:
            return {
                "session": {
                    "access_token": "fresh-access",
                    "refresh_token": "fresh-refresh",
                }
            }

    class FakeClient:
        def __init__(self) -> None:
            self.auth = FakeAuth()

    fake_client = FakeClient()

    def fake_factory(_url: str, _key: str) -> FakeClient:
        return fake_client

    connection = create_authenticated_supabase_connection(
        _config(),
        "old-access",
        "old-refresh",
        fake_factory,
    )

    assert connection.client is fake_client
    assert connection.access_token == "fresh-access"
    assert connection.refresh_token == "fresh-refresh"


def test_create_authenticated_supabase_connection_refreshes_when_restore_fails() -> None:
    class FakeAuth:
        def __init__(self) -> None:
            self.refreshed_with: str | None = None

        def set_session(self, _access_token: str, _refresh_token: str | None) -> object:
            raise RuntimeError("expired")

        def refresh_session(self, refresh_token: str) -> object:
            self.refreshed_with = refresh_token
            return {
                "session": {
                    "access_token": "renewed-access",
                    "refresh_token": "renewed-refresh",
                }
            }

    class FakeClient:
        def __init__(self) -> None:
            self.auth = FakeAuth()

    fake_client = FakeClient()

    def fake_factory(_url: str, _key: str) -> FakeClient:
        return fake_client

    connection = create_authenticated_supabase_connection(
        _config(),
        "old-access",
        "old-refresh",
        fake_factory,
    )

    assert fake_client.auth.refreshed_with == "old-refresh"
    assert connection.access_token == "renewed-access"
    assert connection.refresh_token == "renewed-refresh"


def test_create_openai_client_uses_api_key_without_calling_api() -> None:
    calls: dict[str, str] = {}

    class FakeOpenAI:
        def __init__(self, api_key: str) -> None:
            calls["api_key"] = api_key

    client = create_openai_client(_config(), FakeOpenAI)

    assert isinstance(client, FakeOpenAI)
    assert calls == {"api_key": "openai-key"}


def test_create_openai_client_wraps_errors() -> None:
    def failing_factory(api_key: str) -> object:
        raise ValueError(api_key)

    with pytest.raises(RuntimeError):
        create_openai_client(_config(), failing_factory)
