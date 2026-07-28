from __future__ import annotations

from typing import Any

import streamlit as st

from synapse_ai.config import AppConfig


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


def _assert_cache_scope(tenant_id: str, user_id: str) -> None:
    if not tenant_id or not user_id:
        raise RuntimeError("Escopo de usuário inválido para consulta em cache.")
