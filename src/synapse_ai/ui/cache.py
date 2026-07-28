from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import Any

import streamlit as st

from synapse_ai.clients.supabase_client import (
    AuthenticatedSupabaseConnection,
    create_authenticated_supabase_connection,
)
from synapse_ai.config import AppConfig

AUTHENTICATED_SUPABASE_CONNECTION_KEY = "synapse_authenticated_supabase_connection"
AUTHENTICATED_SUPABASE_CONNECTION_TTL_SECONDS = 600


@st.cache_resource(show_spinner=False)
def get_cached_openai_client(api_key: str) -> Any:
    """Cache the OpenAI client resource without caching LLM responses."""
    from openai import OpenAI

    return OpenAI(api_key=api_key)


def get_openai_client(config: AppConfig) -> Any:
    """Return a cached OpenAI client configured for the current deployment."""
    try:
        return get_cached_openai_client(config.openai.api_key)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Não foi possível inicializar o cliente OpenAI.") from exc


@dataclass
class LazyOpenAIClient:
    """Initialize the OpenAI client only when an AI action actually runs."""

    config: AppConfig
    _client: Any = field(default=None, init=False, repr=False)

    def __getattr__(self, name: str) -> Any:
        if self._client is None:
            self._client = get_openai_client(self.config)
        return getattr(self._client, name)


def lazy_openai_client(config: AppConfig) -> Any:
    """Return a lazy proxy that preserves the public OpenAI client contract."""
    return LazyOpenAIClient(config)


def get_session_supabase_connection(
    config: AppConfig,
    access_token: str,
    refresh_token: str | None,
) -> AuthenticatedSupabaseConnection:
    """Reuse an authenticated Supabase client inside the current Streamlit session."""
    cache_identity = _supabase_connection_identity(config, access_token, refresh_token)
    cached_entry = st.session_state.get(AUTHENTICATED_SUPABASE_CONNECTION_KEY)
    if (
        isinstance(cached_entry, dict)
        and cached_entry.get("identity") == cache_identity
        and _is_fresh_session_resource(cached_entry.get("created_at"))
    ):
        connection = cached_entry.get("connection")
        if isinstance(connection, AuthenticatedSupabaseConnection):
            return connection

    connection = create_authenticated_supabase_connection(config, access_token, refresh_token)
    st.session_state[AUTHENTICATED_SUPABASE_CONNECTION_KEY] = {
        "identity": _supabase_connection_identity(
            config,
            connection.access_token,
            connection.refresh_token,
        ),
        "connection": connection,
        "created_at": monotonic(),
    }
    return connection


@st.cache_data(ttl=45, show_spinner=False)
def cached_user_documents(
    _client: object,
    tenant_id: str,
    user_id: str,
    limit: int,
) -> list[dict[str, object]]:
    """Load user documents with cache scoped by tenant and user."""
    from synapse_ai.services.document_repository import list_user_documents

    _assert_cache_scope(tenant_id, user_id)
    return list_user_documents(_client, user_id, limit=limit)


@st.cache_data(ttl=45, show_spinner=False)
def cached_user_documents_for_processing(
    _client: object,
    tenant_id: str,
    user_id: str,
) -> list[dict[str, object]]:
    """Load processable documents with cache scoped by tenant and user."""
    from synapse_ai.services.document_repository import list_user_documents_for_processing

    _assert_cache_scope(tenant_id, user_id)
    return list_user_documents_for_processing(_client, user_id)


@st.cache_data(ttl=45, show_spinner=False)
def cached_recent_analyses(
    _client: object,
    tenant_id: str,
    user_id: str,
    limit: int,
) -> list[dict[str, object]]:
    """Load recent analyses with cache scoped by tenant and user."""
    from synapse_ai.services.analysis_repository import list_recent_analyses

    _assert_cache_scope(tenant_id, user_id)
    return list_recent_analyses(_client, user_id, limit=limit)


@st.cache_data(ttl=45, show_spinner=False)
def cached_document_chunk_counts(
    _client: object,
    tenant_id: str,
    user_id: str,
    document_ids: tuple[str, ...],
    embedding_model: str,
) -> dict[str, int]:
    """Load semantic readiness counts without sharing cache across tenants."""
    from synapse_ai.services.chunk_repository import list_document_chunk_counts

    _assert_cache_scope(tenant_id, user_id)
    return list_document_chunk_counts(
        _client,
        user_id,
        list(document_ids),
        embedding_model,
    )


@st.cache_data(ttl=45, show_spinner=False)
def cached_document_chunks_by_references(
    _client: object,
    tenant_id: str,
    user_id: str,
    references: tuple[tuple[str, int], ...],
) -> dict[tuple[str, int], dict[str, object]]:
    """Load source chunks for audit exports with tenant-aware cache keys."""
    from synapse_ai.services.chunk_repository import list_document_chunks_by_references

    _assert_cache_scope(tenant_id, user_id)
    return list_document_chunks_by_references(_client, user_id, list(references))


def invalidate_data_cache() -> None:
    """Clear cached table/document data after writes or semantic indexing."""
    st.cache_data.clear()


def invalidate_session_resources() -> None:
    """Clear session-scoped clients after auth changes."""
    st.session_state.pop(AUTHENTICATED_SUPABASE_CONNECTION_KEY, None)


def _assert_cache_scope(tenant_id: str, user_id: str) -> None:
    if not tenant_id or not user_id:
        raise RuntimeError("Escopo de usuário inválido para consulta em cache.")


def _is_fresh_session_resource(created_at: object) -> bool:
    return (
        isinstance(created_at, (int, float))
        and monotonic() - float(created_at) <= AUTHENTICATED_SUPABASE_CONNECTION_TTL_SECONDS
    )


def _supabase_connection_identity(
    config: AppConfig,
    access_token: str,
    refresh_token: str | None,
) -> tuple[str, str, str, str]:
    return (
        config.supabase.url,
        config.supabase.publishable_key,
        access_token,
        refresh_token or "",
    )
