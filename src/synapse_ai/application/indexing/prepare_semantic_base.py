from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from synapse_ai.application.interfaces import (
    DocumentChunkReplacer,
    EmbeddingGenerator,
    TextChunker,
)
from synapse_ai.application.result import ResultSeverity, UseCaseResult
from synapse_ai.services.chunk_repository import ChunkPersistenceError
from synapse_ai.services.chunking_service import TextChunk
from synapse_ai.services.embedding_service import EmbeddingGenerationError
from synapse_ai.services.ner_service import extract_named_entities


@dataclass(frozen=True)
class PrepareSemanticBaseCommand:
    """Input data required to prepare document chunks and embeddings."""

    supabase_client: Any
    openai_client: Any
    user_id: str
    documents: list[dict[str, Any]]
    embedding_model: str


@dataclass(frozen=True)
class PrepareSemanticBaseOutput:
    """Successful output of semantic-base preparation."""

    indexed_chunks: int


class PrepareSemanticBaseUseCase:
    """Orchestrates chunking, explicit NER, embedding generation and chunk replacement."""

    def __init__(
        self,
        text_chunker: TextChunker,
        embedding_generator: EmbeddingGenerator,
        document_chunk_replacer: DocumentChunkReplacer,
    ) -> None:
        self._text_chunker = text_chunker
        self._embedding_generator = embedding_generator
        self._document_chunk_replacer = document_chunk_replacer

    def execute(
        self,
        command: PrepareSemanticBaseCommand,
    ) -> UseCaseResult[PrepareSemanticBaseOutput]:
        validation_message = _validate_command(command)
        if validation_message:
            return UseCaseResult.fail(validation_message, ResultSeverity.WARNING)

        indexed_chunks = 0
        try:
            for document in command.documents:
                document_id = str(document.get("id") or "")
                filename = str(document.get("filename") or "Documento sem nome")
                extracted_text = document.get("extracted_text")
                if (
                    not document_id
                    or not isinstance(extracted_text, str)
                    or not extracted_text.strip()
                ):
                    continue

                chunks = _enrich_chunks_with_entities(self._text_chunker(extracted_text))
                embeddings = self._embedding_generator(
                    command.openai_client,
                    [chunk.content for chunk in chunks],
                    command.embedding_model,
                )
                indexed_chunks += self._document_chunk_replacer(
                    command.supabase_client,
                    command.user_id,
                    document_id,
                    filename,
                    chunks,
                    embeddings,
                    command.embedding_model,
                )
        except (ChunkPersistenceError, EmbeddingGenerationError) as exc:
            return UseCaseResult.fail(str(exc), ResultSeverity.ERROR)

        return UseCaseResult.ok(PrepareSemanticBaseOutput(indexed_chunks=indexed_chunks))


def _validate_command(command: PrepareSemanticBaseCommand) -> str:
    if not command.user_id.strip():
        return "Não conseguimos confirmar sua conta nesta aba. Atualize a página para continuar."
    return ""


def _enrich_chunks_with_entities(chunks: list[TextChunk]) -> list[TextChunk]:
    enriched_chunks: list[TextChunk] = []
    for chunk in chunks:
        entities = extract_named_entities(chunk.content)
        metadata = {**(chunk.metadata or {}), "entities": entities}
        metadata["entity_labels"] = sorted(
            {str(entity.get("label")) for entity in entities if entity.get("label")}
        )
        enriched_chunks.append(
            TextChunk(
                index=chunk.index,
                content=chunk.content,
                char_count=chunk.char_count,
                metadata=metadata,
            )
        )
    return enriched_chunks
