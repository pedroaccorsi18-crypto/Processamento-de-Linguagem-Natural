from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_CHUNK_SIZE_CHARS = 1800
DEFAULT_CHUNK_OVERLAP_CHARS = 250


@dataclass(frozen=True)
class TextChunk:
    index: int
    content: str
    char_count: int
    metadata: dict[str, Any] | None = None


class ChunkingError(ValueError):
    """Raised when chunking parameters are invalid."""


def split_text_into_chunks(
    text: str,
    max_chars: int = DEFAULT_CHUNK_SIZE_CHARS,
    overlap_chars: int = DEFAULT_CHUNK_OVERLAP_CHARS,
) -> list[TextChunk]:
    if max_chars <= 0:
        raise ChunkingError("O tamanho do chunk precisa ser maior que zero.")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ChunkingError("A sobreposicao precisa ser menor que o tamanho do chunk.")

    normalized_text = _normalize_whitespace(text)
    if not normalized_text:
        return []

    chunks: list[TextChunk] = []
    start = 0
    while start < len(normalized_text):
        end = min(start + max_chars, len(normalized_text))
        if end < len(normalized_text):
            split_at = normalized_text.rfind(" ", start + max_chars // 2, end)
            if split_at > start:
                end = split_at

        content = normalized_text[start:end].strip()
        if content:
            chunks.append(TextChunk(index=len(chunks), content=content, char_count=len(content)))

        if end >= len(normalized_text):
            break
        next_start = max(0, end - overlap_chars)
        start = next_start if next_start > start else end

    return chunks


def _normalize_whitespace(text: str) -> str:
    lines = [line.strip() for line in text.replace("\r\n", "\n").split("\n")]
    paragraphs = [line for line in lines if line]
    return " ".join(paragraphs)
