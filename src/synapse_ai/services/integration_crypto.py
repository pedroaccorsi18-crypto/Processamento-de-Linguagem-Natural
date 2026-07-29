"""Backend-only encryption helpers for third-party connector credentials."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


class IntegrationCredentialError(RuntimeError):
    """Raised when connector credentials cannot be encrypted or recovered safely."""


def encrypt_integration_credentials(payload: Mapping[str, Any], encryption_key: str) -> str:
    """Serialize and encrypt a provider payload with the backend-only Fernet key."""
    cipher = _cipher(encryption_key)
    try:
        serialized = json.dumps(
            dict(payload),
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise IntegrationCredentialError(
            "As credenciais da conexão não puderam ser protegidas."
        ) from exc
    return cipher.encrypt(serialized).decode("utf-8")


def decrypt_integration_credentials(encrypted_payload: str, encryption_key: str) -> dict[str, Any]:
    """Decrypt a connector payload without ever logging token values."""
    cipher = _cipher(encryption_key)
    try:
        payload = json.loads(cipher.decrypt(encrypted_payload.encode("utf-8")).decode("utf-8"))
    except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IntegrationCredentialError("Não foi possível recuperar a conexão protegida.") from exc
    if not isinstance(payload, dict):
        raise IntegrationCredentialError("A conexão protegida retornou um formato inesperado.")
    return payload


def _cipher(encryption_key: str) -> Fernet:
    if not encryption_key.strip():
        raise IntegrationCredentialError(
            "A conexão corporativa ainda não recebeu a chave de proteção do servidor."
        )
    try:
        return Fernet(encryption_key.encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise IntegrationCredentialError(
            "A chave de proteção das conexões corporativas é inválida."
        ) from exc
