"""Encrypted account-scoped lifecycle for Slack OAuth credentials."""

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
from synapse_ai.services.slack_oauth_service import (
    SlackOAuthError,
    SlackOAuthTokens,
    refresh_slack_oauth_access_token,
)

SLACK_PROVIDER = "slack"


class SlackConnectionError(RuntimeError):
    """Raised when the authenticated account has no usable Slack connection."""


@dataclass(frozen=True)
class SlackCredentials:
    access_token: str


@dataclass(frozen=True)
class SlackConnectionStatus:
    connected: bool
    connected_at: str | None = None


def save_slack_connection(
    client: Any,
    user_id: str,
    tokens: SlackOAuthTokens,
    encryption_key: str,
) -> SlackConnectionStatus:
    """Persist one Slack workspace connection encrypted at rest per Synapse account."""
    expires_at = _expiration_from_tokens(tokens)
    connection = save_integration_connection(
        client,
        user_id,
        SLACK_PROVIDER,
        encrypt_integration_credentials(
            {
                "access_token": tokens.access_token,
                "refresh_token": tokens.refresh_token,
                "expires_at": expires_at.isoformat() if expires_at else "",
            },
            encryption_key,
        ),
        {
            "scope": tokens.scope,
            "token_type": tokens.token_type,
            "workspace_id": tokens.team_id,
            "workspace_name": tokens.team_name,
        },
    )
    return SlackConnectionStatus(connected=True, connected_at=connection.updated_at)


def load_slack_credentials(
    client: Any,
    user_id: str,
    encryption_key: str,
    client_id: str,
    client_secret: str,
) -> SlackCredentials:
    """Recover a valid token, refreshing it only when Slack token rotation requires it."""
    connection = get_integration_connection(client, user_id, SLACK_PROVIDER)
    if connection is None:
        raise SlackConnectionError(
            "Conecte uma área de trabalho do Slack antes de importar conteúdo."
        )

    payload = decrypt_integration_credentials(connection.encrypted_credentials, encryption_key)
    access_token = _required_token(payload, "access_token")
    expires_at = _parse_expiration(payload.get("expires_at"))
    if expires_at is None or expires_at > datetime.now(UTC) + timedelta(seconds=60):
        return SlackCredentials(access_token=access_token)

    refresh_token = _required_token(payload, "refresh_token")
    try:
        refreshed = refresh_slack_oauth_access_token(client_id, client_secret, refresh_token)
    except SlackOAuthError as exc:
        raise SlackConnectionError(
            "A conexão com o Slack expirou. Conecte a área novamente."
        ) from exc
    save_slack_connection(client, user_id, refreshed, encryption_key)
    return SlackCredentials(access_token=refreshed.access_token)


def slack_connection_status(client: Any, user_id: str) -> SlackConnectionStatus:
    connection = get_integration_connection(client, user_id, SLACK_PROVIDER)
    return SlackConnectionStatus(
        connected=connection is not None,
        connected_at=connection.updated_at if connection is not None else None,
    )


def disconnect_slack(client: Any, user_id: str) -> None:
    delete_integration_connection(client, user_id, SLACK_PROVIDER)


def _expiration_from_tokens(tokens: SlackOAuthTokens) -> datetime | None:
    return (
        datetime.now(UTC) + timedelta(seconds=tokens.expires_in)
        if tokens.expires_in is not None
        else None
    )


def _required_token(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SlackConnectionError(
            "A conexão com o Slack está incompleta. Conecte a área novamente."
        )
    return value.strip()


def _parse_expiration(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.fromtimestamp(0, tz=UTC)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
