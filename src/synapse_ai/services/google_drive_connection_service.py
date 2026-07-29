"""Lifecycle of one encrypted Google Drive OAuth connection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from synapse_ai.services.google_drive_service import GoogleDriveCredentials
from synapse_ai.services.google_oauth_service import (
    GoogleOAuthError,
    GoogleOAuthTokens,
    refresh_google_oauth_access_token,
)
from synapse_ai.services.integration_connection_service import (
    IntegrationConnectionError,
    delete_integration_connection,
    get_integration_connection,
    save_integration_connection,
)
from synapse_ai.services.integration_crypto import (
    IntegrationCredentialError,
    decrypt_integration_credentials,
    encrypt_integration_credentials,
)

GOOGLE_DRIVE_PROVIDER = "google_drive"


class GoogleDriveConnectionError(RuntimeError):
    """Raised when a Google Drive connection is unavailable or expired."""


@dataclass(frozen=True)
class GoogleDriveConnectionStatus:
    connected: bool
    connected_at: str | None = None


def save_google_drive_connection(
    client: Any,
    user_id: str,
    tokens: GoogleOAuthTokens,
    encryption_key: str,
) -> GoogleDriveConnectionStatus:
    """Persist OAuth tokens encrypted at rest for exactly one Synapse account."""
    if not tokens.refresh_token.strip():
        raise GoogleDriveConnectionError(
            "O Google não concedeu acesso duradouro. Conecte a conta novamente "
            "e aprove o acesso solicitado."
        )

    expires_at = datetime.now(UTC) + timedelta(seconds=tokens.expires_in or 3600)
    encrypted_credentials = encrypt_integration_credentials(
        {
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "expires_at": expires_at.isoformat(),
        },
        encryption_key,
    )
    connection = save_integration_connection(
        client,
        user_id,
        GOOGLE_DRIVE_PROVIDER,
        encrypted_credentials,
        {"scope": tokens.scope, "token_type": tokens.token_type},
    )
    return GoogleDriveConnectionStatus(connected=True, connected_at=connection.updated_at)


def load_google_drive_credentials(
    client: Any,
    user_id: str,
    encryption_key: str,
    client_id: str,
    client_secret: str,
) -> GoogleDriveCredentials:
    """Recover or refresh an account-scoped Drive token before a provider request."""
    connection = get_integration_connection(client, user_id, GOOGLE_DRIVE_PROVIDER)
    if connection is None:
        raise GoogleDriveConnectionError(
            "Conecte uma conta Google Drive antes de importar arquivos."
        )

    payload = decrypt_integration_credentials(connection.encrypted_credentials, encryption_key)
    access_token = _required_string(payload, "access_token")
    refresh_token = _required_string(payload, "refresh_token")
    expires_at = _parse_expiration(payload.get("expires_at"))
    if expires_at > datetime.now(UTC) + timedelta(seconds=60):
        return GoogleDriveCredentials(access_token=access_token)

    try:
        refreshed_tokens = refresh_google_oauth_access_token(
            client_id,
            client_secret,
            refresh_token,
        )
    except GoogleOAuthError as exc:
        raise GoogleDriveConnectionError(
            "A conexão com o Google Drive expirou. Conecte a conta novamente."
        ) from exc

    save_google_drive_connection(client, user_id, refreshed_tokens, encryption_key)
    return GoogleDriveCredentials(access_token=refreshed_tokens.access_token)


def google_drive_connection_status(
    client: Any,
    user_id: str,
) -> GoogleDriveConnectionStatus:
    connection = get_integration_connection(client, user_id, GOOGLE_DRIVE_PROVIDER)
    return GoogleDriveConnectionStatus(
        connected=connection is not None,
        connected_at=connection.updated_at if connection is not None else None,
    )


def disconnect_google_drive(client: Any, user_id: str) -> None:
    delete_integration_connection(client, user_id, GOOGLE_DRIVE_PROVIDER)


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise GoogleDriveConnectionError(
            "A conexão com o Google Drive está incompleta. Conecte a conta novamente."
        )
    return value.strip()


def _parse_expiration(value: object) -> datetime:
    if not isinstance(value, str):
        return datetime.fromtimestamp(0, tz=UTC)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.fromtimestamp(0, tz=UTC)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


__all__ = [
    "GOOGLE_DRIVE_PROVIDER",
    "GoogleDriveConnectionError",
    "GoogleDriveConnectionStatus",
    "IntegrationConnectionError",
    "IntegrationCredentialError",
    "disconnect_google_drive",
    "google_drive_connection_status",
    "load_google_drive_credentials",
    "save_google_drive_connection",
]
