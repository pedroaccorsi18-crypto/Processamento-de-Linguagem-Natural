from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from synapse_ai.application.interfaces import ChunkMatcher, EmbeddingGenerator, SourceBuilder
from synapse_ai.services.analysis_service import SourceSnippet


@dataclass(frozen=True)
class SemanticRetriever:
    """Retrieves semantically relevant document sources for a query."""

    embedding_generator: EmbeddingGenerator
    chunk_matcher: ChunkMatcher
    source_builder: SourceBuilder

    def retrieve(
        self,
        *,
        supabase_client: Any,
        openai_client: Any,
        user_id: str,
        query: str,
        embedding_model: str,
        selected_document_ids: list[str],
        limit: int = 5,
    ) -> list[SourceSnippet]:
        query_embedding = self.embedding_generator(
            openai_client,
            [query],
            embedding_model,
        )[0]
        matches = self.chunk_matcher(
            supabase_client,
            user_id,
            query_embedding,
            document_ids=selected_document_ids,
            limit=limit,
        )
        return self.source_builder(matches)

