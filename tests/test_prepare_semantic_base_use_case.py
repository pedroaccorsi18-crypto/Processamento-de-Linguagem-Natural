from __future__ import annotations

from typing import Any

from synapse_ai.application.indexing import (
    PrepareSemanticBaseCommand,
    PrepareSemanticBaseUseCase,
)
from synapse_ai.application.result import ResultSeverity
from synapse_ai.services.chunk_repository import ChunkPersistenceError
from synapse_ai.services.chunking_service import TextChunk
from synapse_ai.services.embedding_service import EmbeddingGenerationError


class FakeDependencies:
    def __init__(
        self,
        *,
        embedding_error: Exception | None = None,
        persistence_error: Exception | None = None,
    ) -> None:
        self.embedding_error = embedding_error
        self.persistence_error = persistence_error
        self.events: list[str] = []
        self.chunker_calls: list[str] = []
        self.embedding_calls: list[dict[str, Any]] = []
        self.replacer_calls: list[dict[str, Any]] = []

    def split_text_into_chunks(self, text: str, /) -> list[TextChunk]:
        self.events.append(f"chunk:{text}")
        self.chunker_calls.append(text)
        return [
            TextChunk(index=0, content=f"{text} - parte 1", char_count=len(text) + 9),
            TextChunk(index=1, content=f"{text} - parte 2", char_count=len(text) + 9),
        ]

    def generate_embeddings(
        self,
        client: Any,
        texts: list[str],
        model: str,
        /,
    ) -> list[list[float]]:
        self.events.append(f"embed:{','.join(texts)}")
        if self.embedding_error is not None:
            raise self.embedding_error
        self.embedding_calls.append({"client": client, "texts": texts, "model": model})
        return [[0.1, 0.2] for _ in texts]

    def replace_document_chunks(
        self,
        client: Any,
        user_id: str,
        document_id: str,
        filename: str,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
        embedding_model: str,
        /,
    ) -> int:
        self.events.append(f"persist:{document_id}")
        if self.persistence_error is not None:
            raise self.persistence_error
        self.replacer_calls.append(
            {
                "client": client,
                "user_id": user_id,
                "document_id": document_id,
                "filename": filename,
                "chunks": chunks,
                "embeddings": embeddings,
                "embedding_model": embedding_model,
            }
        )
        return len(chunks)


def test_prepare_semantic_base_use_case_succeeds_with_one_document() -> None:
    deps = FakeDependencies()

    result = _build_use_case(deps).execute(_command(documents=[_document("doc-1", "Ata")]))

    assert result.success is True
    assert result.value is not None
    assert result.value.indexed_chunks == 2
    assert deps.chunker_calls == ["Ata"]
    assert deps.embedding_calls[0]["texts"] == ["Ata - parte 1", "Ata - parte 2"]
    assert deps.embedding_calls[0]["model"] == "text-embedding-3-small"
    assert deps.replacer_calls[0]["document_id"] == "doc-1"
    assert deps.replacer_calls[0]["filename"] == "ata.pdf"
    assert deps.replacer_calls[0]["embedding_model"] == "text-embedding-3-small"
    assert deps.replacer_calls[0]["chunks"][0].metadata == {
        "entities": [],
        "entity_labels": [],
    }
    assert deps.events == [
        "chunk:Ata",
        "embed:Ata - parte 1,Ata - parte 2",
        "persist:doc-1",
    ]


def test_prepare_semantic_base_use_case_succeeds_with_multiple_documents() -> None:
    deps = FakeDependencies()

    result = _build_use_case(deps).execute(
        _command(documents=[_document("doc-1", "Ata"), _document("doc-2", "Contrato")])
    )

    assert result.success is True
    assert result.value is not None
    assert result.value.indexed_chunks == 4
    assert [call["document_id"] for call in deps.replacer_calls] == ["doc-1", "doc-2"]
    assert deps.events == [
        "chunk:Ata",
        "embed:Ata - parte 1,Ata - parte 2",
        "persist:doc-1",
        "chunk:Contrato",
        "embed:Contrato - parte 1,Contrato - parte 2",
        "persist:doc-2",
    ]


def test_prepare_semantic_base_use_case_ignores_document_without_text() -> None:
    deps = FakeDependencies()

    result = _build_use_case(deps).execute(
        _command(documents=[_document("doc-1", ""), _document("doc-2", "Ata")])
    )

    assert result.success is True
    assert result.value is not None
    assert result.value.indexed_chunks == 2
    assert deps.chunker_calls == ["Ata"]


def test_prepare_semantic_base_use_case_handles_all_documents_without_text() -> None:
    deps = FakeDependencies()

    result = _build_use_case(deps).execute(
        _command(documents=[_document("doc-1", ""), {"id": "doc-2"}])
    )

    assert result.success is True
    assert result.value is not None
    assert result.value.indexed_chunks == 0
    assert deps.events == []


def test_prepare_semantic_base_use_case_returns_error_for_embedding_failure() -> None:
    deps = FakeDependencies(
        embedding_error=EmbeddingGenerationError("Não foi possível gerar embeddings.")
    )

    result = _build_use_case(deps).execute(_command(documents=[_document("doc-1", "Ata")]))

    assert result.success is False
    assert result.severity == ResultSeverity.ERROR
    assert result.message == "Não foi possível gerar embeddings."
    assert deps.replacer_calls == []


def test_prepare_semantic_base_use_case_returns_error_for_chunk_persistence_failure() -> None:
    deps = FakeDependencies(
        persistence_error=ChunkPersistenceError("Não foi possível salvar os chunks do documento.")
    )

    result = _build_use_case(deps).execute(_command(documents=[_document("doc-1", "Ata")]))

    assert result.success is False
    assert result.severity == ResultSeverity.ERROR
    assert result.message == "Não foi possível salvar os chunks do documento."
    assert deps.events == [
        "chunk:Ata",
        "embed:Ata - parte 1,Ata - parte 2",
        "persist:doc-1",
    ]


def test_prepare_semantic_base_use_case_preserves_partial_work_before_failure() -> None:
    deps = FakeDependencies(
        persistence_error=ChunkPersistenceError("Não foi possível salvar os chunks do documento.")
    )

    result = _build_use_case(deps).execute(
        _command(documents=[_document("doc-1", "Ata"), _document("doc-2", "Contrato")])
    )

    assert result.success is False
    assert deps.events == [
        "chunk:Ata",
        "embed:Ata - parte 1,Ata - parte 2",
        "persist:doc-1",
    ]


def test_prepare_semantic_base_use_case_validation_prevents_dependencies() -> None:
    deps = FakeDependencies()

    result = _build_use_case(deps).execute(_command(user_id=" "))

    assert result.success is False
    assert result.severity == ResultSeverity.WARNING
    assert (
        result.message
        == "Não conseguimos confirmar sua conta nesta aba. Atualize a página para continuar."
    )
    assert deps.events == []


def test_prepare_semantic_base_use_case_empty_documents_preserves_zero_result() -> None:
    deps = FakeDependencies()

    result = _build_use_case(deps).execute(_command(documents=[]))

    assert result.success is True
    assert result.value is not None
    assert result.value.indexed_chunks == 0
    assert deps.events == []


def _build_use_case(deps: FakeDependencies) -> PrepareSemanticBaseUseCase:
    return PrepareSemanticBaseUseCase(
        text_chunker=deps.split_text_into_chunks,
        embedding_generator=deps.generate_embeddings,
        document_chunk_replacer=deps.replace_document_chunks,
    )


def _command(
    *,
    user_id: str = "user-1",
    documents: list[dict[str, Any]] | None = None,
) -> PrepareSemanticBaseCommand:
    return PrepareSemanticBaseCommand(
        supabase_client=_SUPABASE_CLIENT,
        openai_client=_OPENAI_CLIENT,
        user_id=user_id,
        documents=documents if documents is not None else [_document("doc-1", "Ata")],
        embedding_model="text-embedding-3-small",
    )


def _document(document_id: str, text: str) -> dict[str, Any]:
    return {
        "id": document_id,
        "filename": f"{text.lower() or 'vazio'}.pdf",
        "extracted_text": text,
    }


_SUPABASE_CLIENT = object()
_OPENAI_CLIENT = object()
