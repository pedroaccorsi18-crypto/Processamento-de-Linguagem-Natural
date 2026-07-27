from __future__ import annotations

from synapse_ai.application.dashboard import IntelligentExecutiveReportUseCase
from synapse_ai.application.retrieval import SemanticRetriever
from synapse_ai.services.analysis_service import build_source_snippets
from synapse_ai.services.chunk_repository import match_document_chunks
from synapse_ai.services.embedding_service import generate_embeddings
from synapse_ai.services.report_service import generate_intelligent_executive_report


def build_intelligent_executive_report_use_case() -> IntelligentExecutiveReportUseCase:
    return IntelligentExecutiveReportUseCase(
        semantic_retriever=_build_semantic_retriever(),
        intelligent_executive_report_generator=generate_intelligent_executive_report,
    )


def _build_semantic_retriever() -> SemanticRetriever:
    return SemanticRetriever(
        embedding_generator=generate_embeddings,
        chunk_matcher=match_document_chunks,
        source_builder=build_source_snippets,
    )
