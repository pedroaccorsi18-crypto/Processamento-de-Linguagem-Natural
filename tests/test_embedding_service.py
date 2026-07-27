from __future__ import annotations

from types import SimpleNamespace

import pytest

from synapse_ai.services.embedding_service import EmbeddingGenerationError, generate_embeddings


class FakeEmbeddings:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: dict[str, object] = {}

    def create(self, *, model: str, input: list[str]) -> SimpleNamespace:  # noqa: A002
        if self.fail:
            raise RuntimeError("failed")
        self.calls = {"model": model, "input": input}
        return SimpleNamespace(
            data=[
                SimpleNamespace(index=1, embedding=[0.3, 0.4]),
                SimpleNamespace(index=0, embedding=[0.1, 0.2]),
            ]
        )


class FakeClient:
    def __init__(self, embeddings: FakeEmbeddings) -> None:
        self.embeddings = embeddings


def test_generate_embeddings_orders_by_response_index() -> None:
    embeddings_api = FakeEmbeddings()
    client = FakeClient(embeddings_api)

    embeddings = generate_embeddings(client, ["a", "b"], "text-embedding-3-small")

    assert embeddings == [[0.1, 0.2], [0.3, 0.4]]
    assert embeddings_api.calls["model"] == "text-embedding-3-small"


def test_generate_embeddings_wraps_api_errors() -> None:
    client = FakeClient(FakeEmbeddings(fail=True))

    with pytest.raises(EmbeddingGenerationError):
        generate_embeddings(client, ["a"], "text-embedding-3-small")
