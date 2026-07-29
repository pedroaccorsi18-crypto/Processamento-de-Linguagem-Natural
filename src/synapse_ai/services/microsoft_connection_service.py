"""Encrypted Microsoft Graph connection shared by Teams and SharePoint."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from synapse_ai.services.integration_connection_service import (
    delete_integration_connection,
    get_integration_connection,
    save_integration_connection,
)
from synapse_ai.services.integration_crypto import (
    decrypt_integration_credentials,
    encrypt_integration_credentials,
)
from synapse_ai.services.microsoft_oauth_service import (
    MicrosoftOAuthError,
    MicrosoftOAuthTokens,
    refresh_microsoft_oauth_access_token,
)

MICROSOFT_GRAPH_PROVIDER = "microsoft_graph"


class MicrosoftConnectionError(RuntimeError):
    """Raised when an account cannot use the shared Microsoft Graph connection."""


@dataclass(frozen=True)
class MicrosoftGraphCredentials:
    access_token: str


@dataclass(frozen=True)
class MicrosoftConnectionStatus:
    connected: bool
    connected_at: str | None = None


def save_microsoft_connection(
    client: Any,
    user_id: str,
    tokens: MicrosoftOAuthTokens,
    encryption_key: str,
) -> MicrosoftConnectionStatus:
    """Store Microsoft credentials once, encrypted and owned by one Synapse account."""
    expires_at = datetime.now(UTC) + timedelta(seconds=tokens.expires_in or 3600)
    connection = save_integration_connection(
        client,
        user_id,
        MICROSOFT_GRAPH_PROVIDER,
        encrypt_integration_credentials(
            {
                "access_token": tokens.access_token,
                "refresh_token": tokens.refresh_token,
                "expires_at": expires_at.isoformat(),
            },
            encryption_key,
        ),
        {"scope": tokens.scope, "token_type": tokens.token_type},
    )
    return MicrosoftConnectionStatus(connected=True, connected_at=connection.updated_at)


def load_microsoft_credentials(
    client: Any,
    user_id: str,
    encryption_key: str,
    tenant_id: str,
    client_id: str,
    client_secret: str,
) -> MicrosoftGraphCredentials:
    """Return a current token, refreshing it in the backend when needed."""
    connection = get_integration_connection(client, user_id, MICROSOFT_GRAPH_PROVIDER)
    if connection is None:
        raise MicrosoftConnectionError(
            "Conecte uma conta Microsoft 365 antes de importar conteúdo."
        )
    payload = decrypt_integration_credentials(connection.encrypted_credentials, encryption_key)
    access_token = _required_token(payload, "access_token")
    refresh_token = _required_token(payload, "refresh_token")
    expires_at = _parse_expiration(payload.get("expires_at"))
    if expires_at > datetime.now(UTC) + timedelta(seconds=60):
        return MicrosoftGraphCredentials(access_token=access_token)
    try:
        refreshed = refresh_microsoft_oauth_access_token(
            tenant_id,
            client_id,
            client_secret,
            refresh_token,
        )
    except MicrosoftOAuthError as exc:
        raise MicrosoftConnectionError(
            "A conexão Microsoft 365 expirou. Conecte a conta novamente."
        ) from exc
    save_microsoft_connection(client, user_id, refreshed, encryption_key)
    return MicrosoftGraphCredentials(access_token=refreshed.access_token)


def microsoft_connection_status(client: Any, user_id: str) -> MicrosoftConnectionStatus:
    connection = get_integration_connection(client, user_id, MICROSOFT_GRAPH_PROVIDER)
    return MicrosoftConnectionStatus(
        connected=connection is not None,
        connected_at=connection.updated_at if connection is not None else None,
    )


def disconnect_microsoft(client: Any, user_id: str) -> None:
    delete_integration_connection(client, user_id, MICROSOFT_GRAPH_PROVIDER)


def _required_token(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise MicrosoftConnectionError(
            "A conexão Microsoft 365 está incompleta. Conecte a conta novamente."
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
