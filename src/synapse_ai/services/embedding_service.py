from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class EmbeddingGenerationError(RuntimeError):
    """Raised when embeddings cannot be generated."""


def generate_embeddings(client: Any, texts: list[str], model: str) -> list[list[float]]:
    if not texts:
        return []

    try:
        response = client.embeddings.create(model=model, input=texts)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Embedding generation failed: %s", exc.__class__.__name__)
        raise EmbeddingGenerationError("Não foi possível gerar embeddings.") from exc

    embeddings_by_index: dict[int, list[float]] = {}
    for fallback_index, item in enumerate(getattr(response, "data", [])):
        index = _get_value(item, "index")
        embedding = _get_value(item, "embedding")
        if not isinstance(index, int):
            index = fallback_index
        if not _is_embedding(embedding):
            raise EmbeddingGenerationError("A resposta de embeddings veio em formato inesperado.")
        embeddings_by_index[index] = embedding

    if len(embeddings_by_index) != len(texts):
        raise EmbeddingGenerationError("A quantidade de embeddings retornada não confere.")

    return [embeddings_by_index[index] for index in range(len(texts))]


def _get_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _is_embedding(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, int | float) for item in value)
