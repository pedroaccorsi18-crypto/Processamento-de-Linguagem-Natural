from __future__ import annotations

import logging
from dataclasses import asdict, is_dataclass
from typing import Any, Literal
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, HTTPException, Query, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel, Field

from backend.auth import AuthenticatedRequest, require_authenticated_request
from backend.settings import backend_cors_origin_regex, backend_cors_origins
from synapse_ai.application.analysis import (
    ActionPlanCommand,
    AskQuestionCommand,
    DocumentComparisonCommand,
    HistoricalPatternsCommand,
    IntelligenceSnapshotCommand,
    MultiAgentReportCommand,
    PreventiveAlertsCommand,
    SentimentAnalysisCommand,
)
from synapse_ai.application.indexing import PrepareSemanticBaseCommand
from synapse_ai.application.result import ResultSeverity, UseCaseResult
from synapse_ai.application.studio_factory import (
    build_action_plan_use_case,
    build_ask_question_use_case,
    build_document_comparison_use_case,
    build_historical_patterns_use_case,
    build_intelligence_snapshot_use_case,
    build_multi_agent_report_use_case,
    build_prepare_semantic_base_use_case,
    build_preventive_alerts_use_case,
    build_sentiment_analysis_use_case,
)
from synapse_ai.services.analysis_repository import list_recent_analyses
from synapse_ai.services.audio_transcription_service import (
    AudioTranscriptionError,
    transcribe_audio,
)
from synapse_ai.services.chunk_repository import list_document_chunk_counts
from synapse_ai.services.document_repository import (
    DocumentPersistenceError,
    get_user_document,
    list_user_documents,
    list_user_documents_for_processing,
    save_parsed_document,
    update_document_storage_location,
)
from synapse_ai.services.document_service import (
    MAX_UPLOAD_SIZE_BYTES,
    DocumentProcessingError,
    ParsedDocument,
    UploadedDocument,
    is_audio_document,
    parse_transcribed_audio_document,
    parse_uploaded_document,
)
from synapse_ai.services.document_storage import (
    DocumentStorageError,
    download_original_document,
    upload_original_document,
)
from synapse_ai.ui.copilot_page import CopilotMessage, _generate_copilot_answer

logger = logging.getLogger(__name__)

StudioWorkflow = Literal[
    "ask",
    "action_plan",
    "intelligence_snapshot",
    "document_comparison",
    "sentiment_analysis",
    "preventive_alerts",
    "historical_patterns",
    "multi_agent",
]


class CopilotMessagePayload(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12000)


class CopilotRequest(BaseModel):
    prompt: str | None = Field(default=None, max_length=12000)
    messages: list[CopilotMessagePayload] = Field(default_factory=list)
    current_area: str = Field(default="API REST", max_length=120)
    context: str | None = Field(default=None, max_length=20000)
    model: str | None = Field(default=None, max_length=120)


class CopilotResponse(BaseModel):
    answer: str
    model: str


class DashboardStatsResponse(BaseModel):
    base_ready: int
    evidence_count: int
    risk_count: int
    pending_confirmation_count: int


class DocumentResponse(BaseModel):
    id: str
    filename: str
    content_type: str | None = None
    size_bytes: int | None = None
    status: str
    text_char_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    original_file_available: bool


class DocumentUploadResponse(BaseModel):
    document: DocumentResponse
    message: str


class StudioDocumentResponse(DocumentResponse):
    prepared_for_ai: bool
    indexed_chunk_count: int


class StudioScopeRequest(BaseModel):
    selected_document_ids: list[str] = Field(min_length=1, max_length=30)
    save_to_history: bool = True


class StudioAnalysisRequest(StudioScopeRequest):
    question: str | None = Field(default=None, max_length=12000)


class StudioPreparationResponse(BaseModel):
    indexed_chunks: int
    message: str


class StudioAnalysisResponse(BaseModel):
    workflow: StudioWorkflow
    message: str
    saved_to_history: bool
    persistence_warning: str | None = None
    result: dict[str, Any]


class StudioHistoryEntry(BaseModel):
    id: str
    title: str
    question: str
    answer: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    model: str | None = None
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    document_filename: str | None = None
    created_at: str | None = None


app = FastAPI(
    title="Synapse AI API",
    version="0.2.0",
    description="REST API for the Synapse AI SaaS migration.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=backend_cors_origins(),
    allow_origin_regex=backend_cors_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_authenticated_request = Depends(require_authenticated_request)
_uploaded_file = File(...)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/dashboard/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    request: AuthenticatedRequest = _authenticated_request,
) -> DashboardStatsResponse:
    documents = await run_in_threadpool(list_user_documents, request.client, request.user.id, 200)
    prepared_statuses = {"extracted", "ready_for_processing"}
    prepared_documents = sum(
        1 for document in documents if document.get("status") in prepared_statuses
    )
    return DashboardStatsResponse(
        base_ready=prepared_documents,
        evidence_count=0,
        risk_count=0,
        pending_confirmation_count=max(len(documents) - prepared_documents, 0),
    )


@app.get("/api/documents", response_model=list[DocumentResponse])
async def get_documents(
    request: AuthenticatedRequest = _authenticated_request,
) -> list[DocumentResponse]:
    documents = await run_in_threadpool(list_user_documents, request.client, request.user.id, 50)
    return [_document_response(document) for document in documents]


@app.get("/api/studio/documents", response_model=list[StudioDocumentResponse])
async def get_studio_documents(
    request: AuthenticatedRequest = _authenticated_request,
) -> list[StudioDocumentResponse]:
    """Return only processable documents belonging to the authenticated account."""
    documents = await run_in_threadpool(
        list_user_documents_for_processing,
        request.client,
        request.user.id,
        200,
    )
    document_ids = [str(document.get("id") or "") for document in documents]
    chunk_counts = await run_in_threadpool(
        list_document_chunk_counts,
        request.client,
        request.user.id,
        [document_id for document_id in document_ids if document_id],
        request.config.openai.embedding_model,
    )
    return [_studio_document_response(document, chunk_counts) for document in documents]


@app.get("/api/studio/history", response_model=list[StudioHistoryEntry])
async def get_studio_history(
    limit: int = Query(default=20, ge=1, le=50),
    request: AuthenticatedRequest = _authenticated_request,
) -> list[StudioHistoryEntry]:
    """Return the authenticated account's saved Studio analyses only."""
    analyses = await run_in_threadpool(
        list_recent_analyses,
        request.client,
        request.user.id,
        limit,
    )
    return [_studio_history_entry(analysis) for analysis in analyses]


@app.post("/api/studio/prepare", response_model=StudioPreparationResponse)
async def prepare_studio_documents(
    payload: StudioScopeRequest,
    request: AuthenticatedRequest = _authenticated_request,
) -> StudioPreparationResponse:
    documents = await _selected_studio_documents(request, payload.selected_document_ids)
    openai_client = OpenAI(api_key=request.config.openai.api_key)
    result = await run_in_threadpool(
        build_prepare_semantic_base_use_case().execute,
        PrepareSemanticBaseCommand(
            supabase_client=request.client,
            openai_client=openai_client,
            user_id=request.user.id,
            documents=documents,
            embedding_model=request.config.openai.embedding_model,
        ),
    )
    output = _require_studio_result(result)
    return StudioPreparationResponse(
        indexed_chunks=output.indexed_chunks,
        message=(
            f"Base semântica atualizada com {output.indexed_chunks} trecho(s). "
            "Você já pode gerar análises sobre este escopo."
        ),
    )


@app.post("/api/studio/analyses/{workflow}", response_model=StudioAnalysisResponse)
async def run_studio_analysis(
    workflow: StudioWorkflow,
    payload: StudioAnalysisRequest,
    request: AuthenticatedRequest = _authenticated_request,
) -> StudioAnalysisResponse:
    """Run one real Application use case against the selected private document scope."""
    await _selected_studio_documents(request, payload.selected_document_ids)
    if workflow == "ask" and not (payload.question or "").strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Digite uma pergunta antes de consultar a base.",
        )
    result = await run_in_threadpool(
        _run_studio_workflow,
        workflow,
        request,
        payload,
    )
    output = _require_studio_result(result)
    serialized_output = _serialize_studio_output(output)
    return StudioAnalysisResponse(
        workflow=workflow,
        message=_studio_success_message(workflow),
        saved_to_history=bool(serialized_output.pop("saved_to_history", False)),
        persistence_warning=_optional_string(serialized_output.pop("persistence_warning", None)),
        result=serialized_output,
    )


async def _selected_studio_documents(
    request: AuthenticatedRequest,
    selected_document_ids: list[str],
) -> list[dict[str, Any]]:
    clean_ids = list(dict.fromkeys(document_id.strip() for document_id in selected_document_ids))
    if not clean_ids or any(not document_id for document_id in clean_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selecione pelo menos um documento válido para definir o escopo.",
        )

    available_documents = await run_in_threadpool(
        list_user_documents_for_processing,
        request.client,
        request.user.id,
        200,
    )
    documents_by_id = {
        str(document.get("id")): document
        for document in available_documents
        if str(document.get("id") or "")
    }
    missing_ids = [document_id for document_id in clean_ids if document_id not in documents_by_id]
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Um ou mais documentos do escopo não estão disponíveis para esta conta.",
        )
    return [documents_by_id[document_id] for document_id in clean_ids]


def _run_studio_workflow(
    workflow: StudioWorkflow,
    request: AuthenticatedRequest,
    payload: StudioAnalysisRequest,
) -> UseCaseResult[Any]:
    openai_client = OpenAI(api_key=request.config.openai.api_key)
    command_arguments = {
        "supabase_client": request.client,
        "openai_client": openai_client,
        "user_id": request.user.id,
        "embedding_model": request.config.openai.embedding_model,
        "generation_model": request.config.openai.generation_model,
        "save_to_history": payload.save_to_history,
        "selected_document_ids": payload.selected_document_ids,
    }

    try:
        if workflow == "ask":
            question = (payload.question or "").strip()
            return build_ask_question_use_case().execute(
                AskQuestionCommand(question=question, **command_arguments)
            )
        if workflow == "action_plan":
            return build_action_plan_use_case().execute(ActionPlanCommand(**command_arguments))
        if workflow == "intelligence_snapshot":
            return build_intelligence_snapshot_use_case().execute(
                IntelligenceSnapshotCommand(**command_arguments)
            )
        if workflow == "document_comparison":
            return build_document_comparison_use_case().execute(
                DocumentComparisonCommand(**command_arguments)
            )
        if workflow == "sentiment_analysis":
            return build_sentiment_analysis_use_case().execute(
                SentimentAnalysisCommand(**command_arguments)
            )
        if workflow == "preventive_alerts":
            return build_preventive_alerts_use_case().execute(
                PreventiveAlertsCommand(**command_arguments)
            )
        if workflow == "historical_patterns":
            return build_historical_patterns_use_case().execute(
                HistoricalPatternsCommand(**command_arguments)
            )
        return build_multi_agent_report_use_case().execute(
            MultiAgentReportCommand(**command_arguments)
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Studio workflow failed: %s", workflow)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Não foi possível concluir esta análise agora. Tente novamente em instantes.",
        ) from exc


def _require_studio_result(result: UseCaseResult[Any]) -> Any:
    if result.success and result.value is not None:
        return result.value

    status_code = {
        ResultSeverity.INFO: status.HTTP_409_CONFLICT,
        ResultSeverity.WARNING: status.HTTP_422_UNPROCESSABLE_ENTITY,
        ResultSeverity.ERROR: status.HTTP_502_BAD_GATEWAY,
    }.get(result.severity, status.HTTP_502_BAD_GATEWAY)
    raise HTTPException(
        status_code=status_code,
        detail=result.message or "A análise não foi concluída.",
    )


def _serialize_studio_output(output: Any) -> dict[str, Any]:
    serialized = jsonable_encoder(asdict(output) if is_dataclass(output) else output)
    if not isinstance(serialized, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A análise foi concluída, mas o resultado não pôde ser formatado.",
        )
    return serialized


def _studio_success_message(workflow: StudioWorkflow) -> str:
    messages = {
        "ask": "Resposta com fontes gerada para o escopo selecionado.",
        "action_plan": "Plano de ação gerado para o escopo selecionado.",
        "intelligence_snapshot": "Inteligência organizacional gerada com sucesso.",
        "document_comparison": "Comparação documental concluída com sucesso.",
        "sentiment_analysis": "Análise de sentimentos organizacionais concluída.",
        "preventive_alerts": "Alertas preventivos gerados com sucesso.",
        "historical_patterns": "Padrões históricos analisados com sucesso.",
        "multi_agent": "Orquestração multiagente concluída com sucesso.",
    }
    return messages[workflow]


@app.post(
    "/api/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_document(
    file: UploadFile = _uploaded_file,
    request: AuthenticatedRequest = _authenticated_request,
) -> DocumentUploadResponse:
    upload = await _read_uploaded_document(file)

    try:
        parsed_document = await run_in_threadpool(_parse_document, request, upload)
    except (DocumentProcessingError, AudioTranscriptionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    try:
        saved_document = await run_in_threadpool(
            save_parsed_document,
            request.client,
            request.user.id,
            parsed_document,
        )
    except DocumentPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    original_file_available = False
    document_id = saved_document.get("id")
    if isinstance(document_id, str) and document_id:
        try:
            stored_file = await run_in_threadpool(
                upload_original_document,
                request.client,
                request.user.id,
                document_id,
                upload,
            )
            await run_in_threadpool(
                update_document_storage_location,
                request.client,
                request.user.id,
                document_id,
                stored_file.bucket,
                stored_file.path,
            )
            saved_document["storage_bucket"] = stored_file.bucket
            saved_document["storage_path"] = stored_file.path
            original_file_available = True
        except (DocumentPersistenceError, DocumentStorageError):
            original_file_available = False

    return DocumentUploadResponse(
        document=_document_response(saved_document, original_file_available),
        message=(
            "Documento processado e salvo com download privado disponível."
            if original_file_available
            else (
                "Documento processado e salvo para análise. "
                "O arquivo original não ficou disponível."
            )
        ),
    )


@app.get("/api/documents/{document_id}/download")
async def download_document(
    document_id: str,
    request: AuthenticatedRequest = _authenticated_request,
) -> Response:
    document = await run_in_threadpool(
        get_user_document,
        request.client,
        request.user.id,
        document_id,
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento não encontrado.",
        )

    bucket = document.get("storage_bucket")
    path = document.get("storage_path")
    if not isinstance(bucket, str) or not isinstance(path, str) or not bucket or not path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="O arquivo original não está disponível para download.",
        )

    try:
        content = await run_in_threadpool(download_original_document, request.client, bucket, path)
    except DocumentStorageError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    filename = str(document.get("filename") or "documento")
    return Response(
        content=content,
        media_type=str(document.get("content_type") or "application/octet-stream"),
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@app.post("/api/copilot", response_model=CopilotResponse)
async def ask_copilot(
    payload: CopilotRequest,
    request: AuthenticatedRequest = _authenticated_request,
) -> CopilotResponse:
    messages = [
        CopilotMessage(role=message.role, content=message.content)
        for message in payload.messages
    ]
    if payload.prompt and payload.prompt.strip():
        messages.append(CopilotMessage(role="user", content=payload.prompt.strip()))
    if not messages:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Envie uma pergunta.")

    model = payload.model or request.config.openai.generation_model
    openai_client = OpenAI(api_key=request.config.openai.api_key)
    answer = await run_in_threadpool(
        _generate_copilot_answer,
        request.config,
        messages,
        api_key=request.config.openai.api_key,
        model=model,
        context_snapshot=payload.context or "Nenhum contexto documental enviado pela API.",
        current_area=payload.current_area,
        openai_client=openai_client,
    )
    return CopilotResponse(answer=answer, model=model)


def _parse_document(request: AuthenticatedRequest, upload: UploadedDocument) -> ParsedDocument:
    if not is_audio_document(upload.filename):
        return parse_uploaded_document(upload)

    transcription = transcribe_audio(
        OpenAI(api_key=request.config.openai.api_key),
        upload,
        request.config.openai.transcription_model,
    )
    return parse_transcribed_audio_document(
        upload,
        transcription,
        request.config.openai.transcription_model,
    )


async def _read_uploaded_document(file: UploadFile) -> UploadedDocument:
    """Lê somente o necessário para aplicar o limite documentado de upload."""
    content = await file.read(MAX_UPLOAD_SIZE_BYTES + 1)
    await file.close()
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="O arquivo excede o limite de 10 MB desta fase.",
        )
    return UploadedDocument(
        filename=file.filename or "documento",
        content_type=file.content_type or "application/octet-stream",
        content=content,
    )


def _document_response(
    document: dict[str, Any],
    original_file_available: bool | None = None,
) -> DocumentResponse:
    metadata = document.get("metadata")
    return DocumentResponse(
        id=str(document.get("id") or ""),
        filename=str(document.get("filename") or "Documento sem nome"),
        content_type=_optional_string(document.get("content_type")),
        size_bytes=_optional_int(document.get("size_bytes")),
        status=str(document.get("status") or "unknown"),
        text_char_count=_optional_int(document.get("text_char_count")) or 0,
        metadata=metadata if isinstance(metadata, dict) else {},
        created_at=_optional_string(document.get("created_at")),
        original_file_available=(
            original_file_available
            if original_file_available is not None
            else bool(document.get("storage_bucket") and document.get("storage_path"))
        ),
    )


def _studio_document_response(
    document: dict[str, Any],
    chunk_counts: dict[str, int],
) -> StudioDocumentResponse:
    document_id = str(document.get("id") or "")
    indexed_chunk_count = chunk_counts.get(document_id, 0)
    return StudioDocumentResponse(
        **_document_response(document).model_dump(),
        prepared_for_ai=indexed_chunk_count > 0,
        indexed_chunk_count=indexed_chunk_count,
    )


def _studio_history_entry(analysis: dict[str, Any]) -> StudioHistoryEntry:
    sources = analysis.get("sources")
    metadata = analysis.get("metadata")
    return StudioHistoryEntry(
        id=str(analysis.get("id") or ""),
        title=str(analysis.get("title") or "Análise sem título"),
        question=str(analysis.get("question") or ""),
        answer=str(analysis.get("answer") or ""),
        sources=[source for source in sources if isinstance(source, dict)]
        if isinstance(sources, list)
        else [],
        model=_optional_string(analysis.get("model")),
        status=str(analysis.get("status") or "ready"),
        metadata=metadata if isinstance(metadata, dict) else {},
        document_filename=_analysis_document_filename(analysis.get("documents")),
        created_at=_optional_string(analysis.get("created_at")),
    )


def _analysis_document_filename(value: object) -> str | None:
    if isinstance(value, dict):
        return _optional_string(value.get("filename"))
    if isinstance(value, list):
        for document in value:
            if isinstance(document, dict):
                filename = _optional_string(document.get("filename"))
                if filename:
                    return filename
    return None


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None
