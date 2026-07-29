"""Persistence for encrypted third-party connections scoped to one Synapse account."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


class IntegrationConnectionError(RuntimeError):
    """Raised when a provider connection cannot be stored or recovered."""


@dataclass(frozen=True)
class IntegrationConnection:
    provider: str
    encrypted_credentials: str
    metadata: dict[str, Any]
    created_at: str | None = None
    updated_at: str | None = None


def get_integration_connection(
    client: Any,
    user_id: str,
    provider: str,
) -> IntegrationConnection | None:
    """Return one connection only when it belongs to the authenticated account."""
    try:
        response = (
            client.table("integration_connections")
            .select("provider, encrypted_credentials, metadata, created_at, updated_at")
            .eq("user_id", user_id)
            .eq("provider", provider)
            .maybe_single()
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Integration connection lookup failed: %s", exc.__class__.__name__)
        raise IntegrationConnectionError(
            "Não foi possível consultar a conexão corporativa."
        ) from exc

    return _connection_from_data(getattr(response, "data", None))


def save_integration_connection(
    client: Any,
    user_id: str,
    provider: str,
    encrypted_credentials: str,
    metadata: dict[str, Any],
) -> IntegrationConnection:
    """Create or replace one encrypted connection without exposing credentials in metadata."""
    payload = {
        "user_id": user_id,
        "provider": provider,
        "encrypted_credentials": encrypted_credentials,
        "metadata": metadata,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    try:
        response = (
            client.table("integration_connections")
            .upsert(payload, on_conflict="user_id,provider")
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Integration connection persistence failed: %s", exc.__class__.__name__)
        raise IntegrationConnectionError("Não foi possível salvar a conexão corporativa.") from exc

    connection = _connection_from_data(getattr(response, "data", None))
    if connection is not None:
        return connection
    return IntegrationConnection(
        provider=provider,
        encrypted_credentials=encrypted_credentials,
        metadata=dict(metadata),
        updated_at=payload["updated_at"],
    )


def delete_integration_connection(client: Any, user_id: str, provider: str) -> None:
    """Remove a connection only from its owning account."""
    try:
        (
            client.table("integration_connections")
            .delete()
            .eq("user_id", user_id)
            .eq("provider", provider)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Integration connection deletion failed: %s", exc.__class__.__name__)
        raise IntegrationConnectionError(
            "Não foi possível desconectar a fonte corporativa."
        ) from exc


def _connection_from_data(data: object) -> IntegrationConnection | None:
    if isinstance(data, list):
        data = data[0] if data else None
    if not isinstance(data, dict):
        return None

    encrypted_credentials = data.get("encrypted_credentials")
    provider = data.get("provider")
    if not isinstance(provider, str) or not isinstance(encrypted_credentials, str):
        return None
    metadata = data.get("metadata")
    return IntegrationConnection(
        provider=provider,
        encrypted_credentials=encrypted_credentials,
        metadata=metadata if isinstance(metadata, dict) else {},
        created_at=data.get("created_at") if isinstance(data.get("created_at"), str) else None,
        updated_at=data.get("updated_at") if isinstance(data.get("updated_at"), str) else None,
    )
