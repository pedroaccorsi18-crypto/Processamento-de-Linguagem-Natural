from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet

from synapse_ai.services import google_drive_connection_service as connection_service
from synapse_ai.services.google_oauth_service import GoogleOAuthTokens
from synapse_ai.services.integration_connection_service import IntegrationConnection
from synapse_ai.services.integration_crypto import encrypt_integration_credentials


def test_save_google_drive_connection_encrypts_tokens_before_persisting(monkeypatch) -> None:
    encryption_key = Fernet.generate_key().decode("utf-8")
    saved: dict[str, object] = {}

    def fake_save(*args: object) -> IntegrationConnection:
        saved["args"] = args
        return IntegrationConnection(
            provider="google_drive",
            encrypted_credentials=str(args[3]),
            metadata=dict(args[4]),
            updated_at="2026-07-29T12:00:00+00:00",
        )

    monkeypatch.setattr(connection_service, "save_integration_connection", fake_save)

    status = connection_service.save_google_drive_connection(
        object(),
        "user-1",
        GoogleOAuthTokens(
            access_token="access-secret",
            refresh_token="refresh-secret",
            token_type="Bearer",
            expires_in=3600,
            scope="drive.readonly",
        ),
        encryption_key,
    )

    encrypted_credentials = str(saved["args"][3])
    assert "access-secret" not in encrypted_credentials
    assert status.connected is True
    assert status.connected_at == "2026-07-29T12:00:00+00:00"


def test_load_google_drive_credentials_refreshes_an_expired_connection(monkeypatch) -> None:
    encryption_key = Fernet.generate_key().decode("utf-8")
    encrypted_credentials = encrypt_integration_credentials(
        {
            "access_token": "expired-access-token",
            "refresh_token": "refresh-token",
            "expires_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
        },
        encryption_key,
    )
    connection = IntegrationConnection(
        provider="google_drive",
        encrypted_credentials=encrypted_credentials,
        metadata={},
    )
    observed: dict[str, object] = {}

    monkeypatch.setattr(
        connection_service,
        "get_integration_connection",
        lambda *_args: connection,
    )
    monkeypatch.setattr(
        connection_service,
        "refresh_google_oauth_access_token",
        lambda *_args: GoogleOAuthTokens(
            access_token="refreshed-access-token",
            refresh_token="refresh-token",
            token_type="Bearer",
            expires_in=3600,
        ),
    )
    monkeypatch.setattr(
        connection_service,
        "save_google_drive_connection",
        lambda *_args: observed.setdefault("persisted", True),
    )

    credentials = connection_service.load_google_drive_credentials(
        object(),
        "user-1",
        encryption_key,
        "client-id",
        "client-secret",
    )

    assert credentials.access_token == "refreshed-access-token"
    assert observed["persisted"] is True


def test_load_google_drive_credentials_requires_an_account_connection(monkeypatch) -> None:
    monkeypatch.setattr(
        connection_service,
        "get_integration_connection",
        lambda *_args: None,
    )

    with pytest.raises(connection_service.GoogleDriveConnectionError):
        connection_service.load_google_drive_credentials(
            object(),
            "user-1",
            Fernet.generate_key().decode("utf-8"),
            "client-id",
            "client-secret",
        )
