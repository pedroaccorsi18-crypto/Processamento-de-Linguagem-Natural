from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.settings import load_backend_config
from synapse_ai.auth.auth import get_current_user
from synapse_ai.clients.supabase_client import (
    create_supabase_client,
    create_token_scoped_supabase_client,
)
from synapse_ai.config import AppConfig, MissingConfigError
from synapse_ai.models.user import AuthenticatedUser

_bearer_scheme = HTTPBearer(auto_error=False)
_bearer_credentials = Depends(_bearer_scheme)


@dataclass(frozen=True)
class AuthenticatedRequest:
    """Verified user and RLS-scoped Supabase client for one API request."""

    user: AuthenticatedUser
    client: Any
    config: AppConfig


def require_authenticated_request(
    credentials: HTTPAuthorizationCredentials | None = _bearer_credentials,
) -> AuthenticatedRequest:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sua sessão expirou. Entre novamente para continuar.",
        )

    try:
        config = load_backend_config()
    except MissingConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A configuração segura da plataforma está incompleta.",
        ) from exc

    verification_client = create_supabase_client(config)
    user = get_current_user(verification_client, credentials.credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sua sessão não pode ser validada. Entre novamente para continuar.",
        )

    return AuthenticatedRequest(
        user=user,
        client=create_token_scoped_supabase_client(config, credentials.credentials),
        config=config,
    )
