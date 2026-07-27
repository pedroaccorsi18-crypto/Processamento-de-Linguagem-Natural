from __future__ import annotations

import pytest

from synapse_ai.services.chunking_service import ChunkingError, split_text_into_chunks


def test_split_text_into_chunks_preserves_order_and_overlap() -> None:
    chunks = split_text_into_chunks("alpha beta gamma delta epsilon", max_chars=16, overlap_chars=5)

    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))
    assert chunks[0].content == "alpha beta"
    assert "gamma" in chunks[1].content


def test_split_text_into_chunks_ignores_blank_text() -> None:
    assert split_text_into_chunks("  \n\n  ") == []


def test_split_text_into_chunks_rejects_invalid_overlap() -> None:
    with pytest.raises(ChunkingError):
        split_text_into_chunks("texto", max_chars=10, overlap_chars=10)
