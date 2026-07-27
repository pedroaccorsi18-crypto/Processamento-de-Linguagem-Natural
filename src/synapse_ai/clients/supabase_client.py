from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from synapse_ai.config import AppConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthenticatedSupabaseConnection:
    client: Any
    access_token: str
    refresh_token: str | None


def create_supabase_client(
    config: AppConfig,
    client_factory: Callable[[str, str], Any] | None = None,
) -> Any:
    factory = client_factory or _default_factory()
    try:
        return factory(config.supabase.url, config.supabase.publishable_key)
    except Exception as exc:  # noqa: BLE001
        logger.error("Supabase client initialization failed: %s", exc.__class__.__name__)
        raise RuntimeError("Não foi possível inicializar o cliente Supabase.") from exc


def create_authenticated_supabase_client(
    config: AppConfig,
    access_token: str,
    refresh_token: str | None,
    client_factory: Callable[[str, str], Any] | None = None,
) -> Any:
    return create_authenticated_supabase_connection(
        config,
        access_token,
        refresh_token,
        client_factory,
    ).client


def create_authenticated_supabase_connection(
    config: AppConfig,
    access_token: str,
    refresh_token: str | None,
    client_factory: Callable[[str, str], Any] | None = None,
) -> AuthenticatedSupabaseConnection:
    client = create_supabase_client(config, client_factory)
    try:
        response = client.auth.set_session(access_token, refresh_token)
    except Exception as exc:  # noqa: BLE001
        if refresh_token is None:
            logger.warning("Supabase session restore failed: %s", exc.__class__.__name__)
            raise RuntimeError("Não conseguimos renovar sua autenticação nesta aba.") from exc
        try:
            response = client.auth.refresh_session(refresh_token)
        except Exception as refresh_exc:  # noqa: BLE001
            logger.warning(
                "Supabase session refresh failed: %s",
                refresh_exc.__class__.__name__,
            )
            raise RuntimeError("Não conseguimos renovar sua autenticação nesta aba.") from exc

    updated_access_token, updated_refresh_token = _extract_session_tokens(
        response,
        access_token,
        refresh_token,
    )
    return AuthenticatedSupabaseConnection(
        client=client,
        access_token=updated_access_token,
        refresh_token=updated_refresh_token,
    )


@lru_cache(maxsize=1)
def get_supabase_client(url: str, publishable_key: str) -> Any:
    return _default_factory()(url, publishable_key)


def _default_factory() -> Callable[[str, str], Any]:
    from supabase import create_client

    return create_client


def _extract_session_tokens(
    response: Any,
    fallback_access_token: str,
    fallback_refresh_token: str | None,
) -> tuple[str, str | None]:
    session = _get_value(response, "session")
    access_token = _get_value(session, "access_token") if session is not None else None
    refresh_token = _get_value(session, "refresh_token") if session is not None else None
    return (
        access_token if isinstance(access_token, str) and access_token else fallback_access_token,
        (
            refresh_token
            if isinstance(refresh_token, str) and refresh_token
            else fallback_refresh_token
        ),
    )


def _get_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)
