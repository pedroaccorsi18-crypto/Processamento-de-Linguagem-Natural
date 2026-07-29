from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from synapse_ai.services.chunking_service import TextChunk

logger = logging.getLogger(__name__)


class ChunkPersistenceError(RuntimeError):
    """Raised when document chunks cannot be persisted."""


def replace_document_chunks(
    client: Any,
    user_id: str,
    document_id: str,
    filename: str,
    chunks: list[TextChunk],
    embeddings: list[list[float]],
    embedding_model: str,
) -> int:
    if len(chunks) != len(embeddings):
        raise ChunkPersistenceError("Chunks e embeddings precisam ter o mesmo tamanho.")
    if not chunks:
        return 0

    payloads = [
        {
            "user_id": user_id,
            "document_id": document_id,
            "chunk_index": chunk.index,
            "content": chunk.content,
            "content_char_count": chunk.char_count,
            "embedding": embedding,
            "embedding_model": embedding_model,
            "metadata": {"filename": filename, **(chunk.metadata or {})},
        }
        for chunk, embedding in zip(chunks, embeddings, strict=True)
    ]

    try:
        client.table("document_chunks").delete().eq("document_id", document_id).execute()
        response = client.table("document_chunks").insert(payloads).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Chunk persistence failed: %s", exc.__class__.__name__)
        raise ChunkPersistenceError("Não foi possível salvar os chunks do documento.") from exc

    data = getattr(response, "data", None)
    return len(data) if isinstance(data, list) else len(payloads)


def match_document_chunks(
    client: Any,
    user_id: str,
    query_embedding: list[float],
    document_ids: list[str] | None = None,
    limit: int = 5,
    similarity_threshold: float = 0.1,
) -> list[dict[str, Any]]:
    function_name = "match_document_chunks"
    params: dict[str, object] = {
        "match_user_id": user_id,
        "query_embedding": query_embedding,
        "match_count": limit,
        "similarity_threshold": similarity_threshold,
    }
    if document_ids:
        function_name = "match_document_chunks_in_documents"
        params["filter_document_ids"] = document_ids

    try:
        response = client.rpc(function_name, params).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Semantic search failed: %s", exc.__class__.__name__)
        return []

    data = getattr(response, "data", None)
    return data if isinstance(data, list) else []


def list_document_chunk_counts(
    client: Any,
    user_id: str,
    document_ids: list[str],
    embedding_model: str,
) -> dict[str, int]:
    if not document_ids:
        return {}

    try:
        response = (
            client.table("document_chunks")
            .select("document_id")
            .eq("user_id", user_id)
            .eq("embedding_model", embedding_model)
            .in_("document_id", document_ids)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Chunk count listing failed: %s", exc.__class__.__name__)
        return {}

    data = getattr(response, "data", None)
    if not isinstance(data, list):
        return {}

    counts: Counter[str] = Counter()
    for row in data:
        if not isinstance(row, dict):
            continue
        document_id = row.get("document_id")
        if isinstance(document_id, str) and document_id:
            counts[document_id] += 1
    return dict(counts)


def list_document_chunks_by_references(
    client: Any,
    user_id: str,
    references: list[tuple[str, int]],
) -> dict[tuple[str, int], dict[str, Any]]:
    document_ids = sorted({document_id for document_id, _chunk_index in references if document_id})
    if not document_ids:
        return {}

    try:
        response = (
            client.table("document_chunks")
            .select("document_id, chunk_index, content, content_char_count, embedding_model")
            .eq("user_id", user_id)
            .in_("document_id", document_ids)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Chunk reference listing failed: %s", exc.__class__.__name__)
        return {}

    wanted_references = set(references)
    data = getattr(response, "data", None)
    if not isinstance(data, list):
        return {}

    chunks: dict[tuple[str, int], dict[str, Any]] = {}
    for row in data:
        if not isinstance(row, dict):
            continue
        document_id = row.get("document_id")
        chunk_index = row.get("chunk_index")
        if not isinstance(document_id, str) or not isinstance(chunk_index, int):
            continue
        reference = (document_id, chunk_index)
        if reference in wanted_references:
            chunks[reference] = row
    return chunks
