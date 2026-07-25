from __future__ import annotations

from typing import Any

import pytest

from synapse_ai.clients.openai_client import create_openai_client
from synapse_ai.clients.supabase_client import create_supabase_client
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
