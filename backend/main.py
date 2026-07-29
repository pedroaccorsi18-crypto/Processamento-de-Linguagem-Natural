from __future__ import annotations

from typing import Any, Literal
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, HTTPException, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel, Field

from backend.auth import AuthenticatedRequest, require_authenticated_request
from backend.settings import backend_cors_origin_regex, backend_cors_origins
from synapse_ai.services.audio_transcription_service import (
    AudioTranscriptionError,
    transcribe_audio,
)
from synapse_ai.services.document_repository import (
    DocumentPersistenceError,
    get_user_document,
    list_user_documents,
    save_parsed_document,
    update_document_storage_location,
)
from synapse_ai.services.document_service import (
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


@app.post(
    "/api/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_document(
    file: UploadFile = _uploaded_file,
    request: AuthenticatedRequest = _authenticated_request,
) -> DocumentUploadResponse:
    upload = UploadedDocument(
        filename=file.filename or "documento",
        content_type=file.content_type or "application/octet-stream",
        content=await file.read(),
    )
    await file.close()

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
            "Documento processado e salvo com download privado disponivel."
            if original_file_available
            else (
                "Documento processado e salvo para analise. "
                "O arquivo original nao ficou disponivel."
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
            detail="Documento nao encontrado.",
        )

    bucket = document.get("storage_bucket")
    path = document.get("storage_path")
    if not isinstance(bucket, str) or not isinstance(path, str) or not bucket or not path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="O arquivo original nao esta disponivel para download.",
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


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None
