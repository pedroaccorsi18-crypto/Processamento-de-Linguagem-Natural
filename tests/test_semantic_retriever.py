from __future__ import annotations

from typing import Any

import pytest

from synapse_ai.application.retrieval import SemanticRetriever
from synapse_ai.services.analysis_service import SourceSnippet
from synapse_ai.services.embedding_service import EmbeddingGenerationError


class FakeSemanticDependencies:
    def __init__(self, matches: list[dict[str, Any]] | None = None) -> None:
        self.matches = matches if matches is not None else [{"content": "Relevant chunk."}]
        self.embedding_calls: list[dict[str, Any]] = []
        self.matcher_calls: list[dict[str, Any]] = []
        self.builder_calls: list[list[dict[str, Any]]] = []

    def generate_embeddings(self, client: Any, texts: list[str], model: str) -> list[list[float]]:
        self.embedding_calls.append({"client": client, "texts": texts, "model": model})
        return [[0.1, 0.2, 0.3]]

    def match_chunks(
        self,
        client: Any,
        user_id: str,
        query_embedding: list[float],
        document_ids: list[str] | None = None,
        limit: int = 5,
        similarity_threshold: float = 0.1,
    ) -> list[dict[str, Any]]:
        self.matcher_calls.append(
            {
                "client": client,
                "user_id": user_id,
                "query_embedding": query_embedding,
                "document_ids": document_ids,
                "limit": limit,
                "similarity_threshold": similarity_threshold,
            }
        )
        return self.matches[:limit]

    def build_sources(self, matches: list[dict[str, Any]]) -> list[SourceSnippet]:
        self.builder_calls.append(matches)
        if not matches:
            return []
        return [
            SourceSnippet(
                document_id="doc-1",
                filename="documento.pdf",
                chunk_index=2,
                content="Relevant chunk.",
                similarity=0.88,
            )
        ]


class FailingEmbeddingDependencies(FakeSemanticDependencies):
    def generate_embeddings(
        self,
        _client: Any,
        _texts: list[str],
        _model: str,
    ) -> list[list[float]]:
        raise EmbeddingGenerationError("Nao foi possivel gerar embeddings.")


def test_semantic_retriever_generates_query_embedding() -> None:
    deps = FakeSemanticDependencies()

    _build_retriever(deps).retrieve(
        supabase_client=object(),
        openai_client="openai-client",
        user_id="user-1",
        query="Qual foi a decisao?",
        embedding_model="text-embedding-3-small",
        selected_document_ids=["doc-1"],
    )

    assert deps.embedding_calls == [
        {
            "client": "openai-client",
            "texts": ["Qual foi a decisao?"],
            "model": "text-embedding-3-small",
        }
    ]


def test_semantic_retriever_runs_vector_search_with_query_embedding() -> None:
    deps = FakeSemanticDependencies()
    supabase_client = object()

    _build_retriever(deps).retrieve(
        supabase_client=supabase_client,
        openai_client=object(),
        user_id="user-1",
        query="Pergunta",
        embedding_model="text-embedding-3-small",
        selected_document_ids=["doc-1", "doc-2"],
        limit=3,
    )

    assert deps.matcher_calls == [
        {
            "client": supabase_client,
            "user_id": "user-1",
            "query_embedding": [0.1, 0.2, 0.3],
            "document_ids": ["doc-1", "doc-2"],
            "limit": 3,
            "similarity_threshold": 0.1,
        }
    ]


def test_semantic_retriever_builds_source_snippets_from_matches() -> None:
    deps = FakeSemanticDependencies(matches=[{"content": "Relevant chunk.", "chunk_index": 2}])

    sources = _build_retriever(deps).retrieve(
        supabase_client=object(),
        openai_client=object(),
        user_id="user-1",
        query="Pergunta",
        embedding_model="text-embedding-3-small",
        selected_document_ids=["doc-1"],
    )

    assert deps.builder_calls == [[{"content": "Relevant chunk.", "chunk_index": 2}]]
    assert sources == [
        SourceSnippet(
            document_id="doc-1",
            filename="documento.pdf",
            chunk_index=2,
            content="Relevant chunk.",
            similarity=0.88,
        )
    ]


def test_semantic_retriever_returns_empty_sources_when_no_matches_exist() -> None:
    deps = FakeSemanticDependencies(matches=[])

    sources = _build_retriever(deps).retrieve(
        supabase_client=object(),
        openai_client=object(),
        user_id="user-1",
        query="Pergunta",
        embedding_model="text-embedding-3-small",
        selected_document_ids=["doc-1"],
    )

    assert sources == []
    assert deps.builder_calls == [[]]


def test_semantic_retriever_propagates_embedding_errors() -> None:
    deps = FailingEmbeddingDependencies()

    with pytest.raises(EmbeddingGenerationError):
        _build_retriever(deps).retrieve(
            supabase_client=object(),
            openai_client=object(),
            user_id="user-1",
            query="Pergunta",
            embedding_model="text-embedding-3-small",
            selected_document_ids=["doc-1"],
        )

    assert deps.matcher_calls == []
    assert deps.builder_calls == []


def _build_retriever(deps: FakeSemanticDependencies) -> SemanticRetriever:
    return SemanticRetriever(
        embedding_generator=deps.generate_embeddings,
        chunk_matcher=deps.match_chunks,
        source_builder=deps.build_sources,
    )
