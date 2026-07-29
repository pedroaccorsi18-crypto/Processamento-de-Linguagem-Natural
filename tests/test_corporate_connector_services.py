from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse

from cryptography.fernet import Fernet

from synapse_ai.services import microsoft_connection_service, slack_connection_service
from synapse_ai.services.integration_connection_service import IntegrationConnection
from synapse_ai.services.integration_crypto import decrypt_integration_credentials
from synapse_ai.services.microsoft_oauth_service import (
    MicrosoftOAuthTokens,
    build_microsoft_oauth_authorization_url,
    exchange_microsoft_oauth_code,
)
from synapse_ai.services.slack_oauth_service import (
    SlackOAuthTokens,
    build_slack_oauth_authorization_url,
    exchange_slack_oauth_code,
)
from synapse_ai.services.slack_service import (
    SlackConversation,
    download_slack_conversation,
    list_slack_conversations,
)


class _Response:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


class _Opener:
    def __init__(self, payloads: list[bytes]) -> None:
        self.payloads = iter(payloads)
        self.requests: list[Any] = []

    def __call__(self, request: Any) -> _Response:
        self.requests.append(request)
        return _Response(next(self.payloads))


def test_slack_authorization_uses_read_only_scopes_and_state() -> None:
    url = build_slack_oauth_authorization_url(
        "client-id",
        "https://app.example.com/upload",
        "opaque-state",
    )
    parameters = parse_qs(urlparse(url).query)

    assert parameters["state"] == ["opaque-state"]
    assert "channels:history" in parameters["scope"][0]
    assert "groups:history" in parameters["scope"][0]


def test_slack_exchange_and_channel_import_use_a_bearer_token() -> None:
    oauth_opener = _Opener(
        [
            b'{"ok": true, "access_token": "slack-token", "token_type": "bot", '
            b'"scope": "channels:read", "team": {"id": "T1", "name": "Synapse"}}'
        ]
    )
    tokens = exchange_slack_oauth_code(
        "client-id",
        "client-secret",
        "https://app.example.com/upload",
        "code",
        opener=oauth_opener,
    )
    connector_opener = _Opener(
        [
            b'{"ok": true, "channels": [{"id": "C1", "name": "estrategia", "is_private": false}]}',
            b'{"ok": true, "messages": [{"text": "Decis\\u00e3o registrada", "ts": "1.0"}]}',
        ]
    )
    credentials = slack_connection_service.SlackCredentials(access_token=tokens.access_token)

    conversations = list_slack_conversations(credentials, opener=connector_opener)
    downloaded = download_slack_conversation(
        credentials,
        conversations[0],
        opener=connector_opener,
    )

    assert conversations == [SlackConversation("C1", "estrategia", False)]
    assert b"Decis" in downloaded.content
    assert connector_opener.requests[0].headers["Authorization"] == "Bearer slack-token"


def test_slack_connection_is_encrypted_for_one_user(monkeypatch) -> None:
    encryption_key = Fernet.generate_key().decode("utf-8")
    saved: dict[str, object] = {}

    def fake_save(*args: object) -> IntegrationConnection:
        saved["encrypted_credentials"] = args[3]
        return IntegrationConnection(
            provider="slack",
            encrypted_credentials=str(args[3]),
            metadata={},
            updated_at="2026-07-29T12:00:00+00:00",
        )

    monkeypatch.setattr(slack_connection_service, "save_integration_connection", fake_save)
    slack_connection_service.save_slack_connection(
        object(),
        "user-1",
        SlackOAuthTokens(access_token="access-secret", token_type="Bearer"),
        encryption_key,
    )

    encrypted = str(saved["encrypted_credentials"])
    assert "access-secret" not in encrypted
    assert (
        decrypt_integration_credentials(encrypted, encryption_key)["access_token"]
        == "access-secret"
    )


def test_microsoft_authorization_and_connection_refresh_are_server_side(monkeypatch) -> None:
    url = build_microsoft_oauth_authorization_url(
        "organizations",
        "client-id",
        "https://app.example.com/upload",
        "opaque-state",
    )
    parameters = parse_qs(urlparse(url).query)
    assert parameters["state"] == ["opaque-state"]
    assert "offline_access" in parameters["scope"][0]
    assert "Sites.Read.All" in parameters["scope"][0]

    opener = _Opener(
        [
            b'{"access_token": "microsoft-token", "refresh_token": "refresh-token", '
            b'"token_type": "Bearer", "expires_in": 3600, "scope": "User.Read"}'
        ]
    )
    tokens = exchange_microsoft_oauth_code(
        "organizations",
        "client-id",
        "client-secret",
        "https://app.example.com/upload",
        "code",
        opener=opener,
    )
    assert tokens.access_token == "microsoft-token"

    encryption_key = Fernet.generate_key().decode("utf-8")
    expired_connection = IntegrationConnection(
        provider="microsoft_graph",
        encrypted_credentials=microsoft_connection_service.encrypt_integration_credentials(
            {
                "access_token": "expired-token",
                "refresh_token": "refresh-token",
                "expires_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
            },
            encryption_key,
        ),
        metadata={},
    )
    monkeypatch.setattr(
        microsoft_connection_service,
        "get_integration_connection",
        lambda *_args: expired_connection,
    )
    monkeypatch.setattr(
        microsoft_connection_service,
        "refresh_microsoft_oauth_access_token",
        lambda *_args: MicrosoftOAuthTokens(
            access_token="new-token",
            refresh_token="new-refresh-token",
            token_type="Bearer",
            expires_in=3600,
        ),
    )
    monkeypatch.setattr(
        microsoft_connection_service, "save_microsoft_connection", lambda *_args: None
    )

    credentials = microsoft_connection_service.load_microsoft_credentials(
        object(),
        "user-1",
        encryption_key,
        "organizations",
        "client-id",
        "client-secret",
    )
    assert credentials.access_token == "new-token"
