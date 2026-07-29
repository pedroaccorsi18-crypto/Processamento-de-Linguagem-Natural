from __future__ import annotations

import logging
from dataclasses import asdict, is_dataclass, replace
from typing import Any, Literal
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, HTTPException, Query, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel, Field

from backend.auth import AuthenticatedRequest, require_authenticated_request
from backend.settings import (
    backend_cors_origin_regex,
    backend_cors_origins,
    connector_encryption_key,
)
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
from synapse_ai.services.google_drive_connection_service import (
    GoogleDriveConnectionError,
    disconnect_google_drive,
    google_drive_connection_status,
    load_google_drive_credentials,
    save_google_drive_connection,
)
from synapse_ai.services.google_drive_service import (
    GoogleDriveConnectorError,
    GoogleDriveFile,
    download_google_drive_file,
    extract_google_drive_folder_id,
    list_google_drive_folder_files,
)
from synapse_ai.services.google_oauth_service import (
    GoogleOAuthError,
    build_google_oauth_authorization_url,
    build_pkce_code_challenge,
    exchange_google_oauth_code,
    generate_pkce_code_verifier,
)
from synapse_ai.services.integration_connection_service import IntegrationConnectionError
from synapse_ai.services.integration_crypto import (
    IntegrationCredentialError,
    decrypt_integration_credentials,
    encrypt_integration_credentials,
)
from synapse_ai.services.microsoft_connection_service import (
    MicrosoftConnectionError,
    disconnect_microsoft,
    load_microsoft_credentials,
    microsoft_connection_status,
    save_microsoft_connection,
)
from synapse_ai.services.microsoft_graph_service import (
    MicrosoftChannel,
    MicrosoftGraphConnectorError,
    MicrosoftTeam,
    SharePointDrive,
    SharePointFile,
    SharePointSite,
    download_microsoft_team_channel,
    download_sharepoint_file,
    list_microsoft_team_channels,
    list_microsoft_teams,
    list_sharepoint_drive_files,
    list_sharepoint_drives,
    list_sharepoint_sites,
)
from synapse_ai.services.microsoft_oauth_service import (
    MicrosoftOAuthError,
    build_microsoft_oauth_authorization_url,
    exchange_microsoft_oauth_code,
)
from synapse_ai.services.slack_connection_service import (
    SlackConnectionError,
    disconnect_slack,
    load_slack_credentials,
    save_slack_connection,
    slack_connection_status,
)
from synapse_ai.services.slack_oauth_service import (
    SlackOAuthError,
    build_slack_oauth_authorization_url,
    exchange_slack_oauth_code,
)
from synapse_ai.services.slack_service import (
    SlackConnectorError,
    SlackConversation,
    download_slack_conversation,
    list_slack_conversations,
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
IntegrationProvider = Literal["google_drive", "slack", "microsoft_teams", "sharepoint"]


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


class IntegrationStatusResponse(BaseModel):
    provider: IntegrationProvider
    label: str
    availability: Literal["available", "needs_configuration", "coming_soon"]
    connected: bool = False
    connected_at: str | None = None
    detail: str


class GoogleDriveAuthorizationResponse(BaseModel):
    authorization_url: str
    state: str
    code_verifier: str


class GoogleDriveOAuthCompletionRequest(BaseModel):
    code: str = Field(min_length=1, max_length=4096)
    state: str = Field(min_length=16, max_length=512)
    code_verifier: str = Field(min_length=43, max_length=256)


class GoogleDriveFolderRequest(BaseModel):
    folder_reference: str = Field(min_length=1, max_length=2048)


class GoogleDriveFileResponse(BaseModel):
    id: str
    name: str
    mime_type: str
    size_bytes: int | None = None
    web_view_link: str | None = None


class GoogleDriveImportRequest(GoogleDriveFolderRequest):
    file_ids: list[str] = Field(min_length=1, max_length=20)


class GoogleDriveImportFailure(BaseModel):
    filename: str
    detail: str


class GoogleDriveImportResponse(BaseModel):
    imported_documents: list[DocumentResponse] = Field(default_factory=list)
    failures: list[GoogleDriveImportFailure] = Field(default_factory=list)
    message: str


class OAuthAuthorizationResponse(BaseModel):
    authorization_url: str
    state: str


class OAuthCompletionRequest(BaseModel):
    code: str = Field(min_length=1, max_length=4096)
    state: str = Field(min_length=16, max_length=512)


class SlackConversationResponse(BaseModel):
    id: str
    name: str
    is_private: bool
    topic: str = ""


class SlackImportRequest(BaseModel):
    conversation_ids: list[str] = Field(min_length=1, max_length=10)
    message_limit: int = Field(default=100, ge=1, le=200)


class MicrosoftTeamResponse(BaseModel):
    id: str
    name: str
    description: str = ""


class MicrosoftChannelResponse(BaseModel):
    id: str
    name: str
    description: str = ""


class MicrosoftTeamChannelsRequest(BaseModel):
    team_id: str = Field(min_length=1, max_length=512)


class MicrosoftTeamsImportRequest(MicrosoftTeamChannelsRequest):
    channels: list[MicrosoftChannelResponse] = Field(min_length=1, max_length=10)
    message_limit: int = Field(default=100, ge=1, le=200)


class SharePointSiteResponse(BaseModel):
    id: str
    name: str
    web_url: str = ""


class SharePointDriveResponse(BaseModel):
    id: str
    name: str
    web_url: str = ""


class SharePointDrivesRequest(BaseModel):
    site_id: str = Field(min_length=1, max_length=1024)


class SharePointFilesRequest(BaseModel):
    drive_id: str = Field(min_length=1, max_length=1024)
    folder_id: str = Field(default="", max_length=1024)


class SharePointFileResponse(BaseModel):
    id: str
    name: str
    mime_type: str
    size_bytes: int | None = None
    web_url: str = ""
    is_folder: bool = False


class SharePointImportRequest(BaseModel):
    drive_id: str = Field(min_length=1, max_length=1024)
    files: list[SharePointFileResponse] = Field(min_length=1, max_length=20)


class ConnectorImportFailure(BaseModel):
    filename: str
    detail: str


class ConnectorImportResponse(BaseModel):
    imported_documents: list[DocumentResponse] = Field(default_factory=list)
    failures: list[ConnectorImportFailure] = Field(default_factory=list)
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


@app.get("/api/integrations", response_model=list[IntegrationStatusResponse])
async def get_integrations(
    request: AuthenticatedRequest = _authenticated_request,
) -> list[IntegrationStatusResponse]:
    """Describe connector availability without exposing provider credentials."""
    google_status = _google_drive_status(request)
    if google_status.availability == "available":
        try:
            connection = await run_in_threadpool(
                google_drive_connection_status,
                request.client,
                request.user.id,
            )
            google_status = google_status.model_copy(
                update={"connected": connection.connected, "connected_at": connection.connected_at}
            )
        except IntegrationConnectionError:
            google_status = google_status.model_copy(
                update={
                    "availability": "needs_configuration",
                    "detail": "A base segura de conexões ainda precisa ser preparada no servidor.",
                }
            )

    slack_status = _slack_status(request)
    microsoft_status = _microsoft_status(request)
    if slack_status.availability == "available":
        try:
            connection = await run_in_threadpool(
                slack_connection_status, request.client, request.user.id
            )
            slack_status = slack_status.model_copy(
                update={"connected": connection.connected, "connected_at": connection.connected_at}
            )
        except IntegrationConnectionError:
            slack_status = slack_status.model_copy(
                update={
                    "availability": "needs_configuration",
                    "detail": "A base segura de conexões ainda precisa ser preparada no servidor.",
                }
            )
    if microsoft_status.availability == "available":
        try:
            connection = await run_in_threadpool(
                microsoft_connection_status,
                request.client,
                request.user.id,
            )
            microsoft_status = microsoft_status.model_copy(
                update={"connected": connection.connected, "connected_at": connection.connected_at}
            )
        except IntegrationConnectionError:
            microsoft_status = microsoft_status.model_copy(
                update={
                    "availability": "needs_configuration",
                    "detail": "A base segura de conexões ainda precisa ser preparada no servidor.",
                }
            )

    return [
        google_status,
        slack_status,
        microsoft_status.model_copy(
            update={"provider": "microsoft_teams", "label": "Microsoft Teams"}
        ),
        microsoft_status.model_copy(update={"provider": "sharepoint", "label": "SharePoint"}),
    ]


@app.post(
    "/api/integrations/google-drive/authorization",
    response_model=GoogleDriveAuthorizationResponse,
)
async def begin_google_drive_authorization(
    request: AuthenticatedRequest = _authenticated_request,
) -> GoogleDriveAuthorizationResponse:
    """Create a PKCE authorization URL; the browser retains the ephemeral verifier."""
    _require_google_drive_configuration(request)
    state = _build_google_drive_oauth_state(request)
    code_verifier = generate_pkce_code_verifier()
    try:
        authorization_url = build_google_oauth_authorization_url(
            request.config.google_drive.client_id,
            request.config.google_drive.redirect_uri,
            state,
            code_challenge=build_pkce_code_challenge(code_verifier),
        )
    except GoogleOAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return GoogleDriveAuthorizationResponse(
        authorization_url=authorization_url,
        state=state,
        code_verifier=code_verifier,
    )


@app.post("/api/integrations/google-drive/complete", response_model=IntegrationStatusResponse)
async def complete_google_drive_authorization(
    payload: GoogleDriveOAuthCompletionRequest,
    request: AuthenticatedRequest = _authenticated_request,
) -> IntegrationStatusResponse:
    """Exchange a Google code then save encrypted credentials for the authenticated account."""
    _require_google_drive_configuration(request)
    try:
        _validate_google_drive_oauth_state(payload.state, request)
        tokens = await run_in_threadpool(
            exchange_google_oauth_code,
            request.config.google_drive.client_id,
            request.config.google_drive.client_secret,
            request.config.google_drive.redirect_uri,
            payload.code,
            code_verifier=payload.code_verifier,
        )
        connection = await run_in_threadpool(
            save_google_drive_connection,
            request.client,
            request.user.id,
            tokens,
            connector_encryption_key(),
        )
    except (
        GoogleOAuthError,
        GoogleDriveConnectionError,
        IntegrationConnectionError,
        IntegrationCredentialError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return IntegrationStatusResponse(
        provider="google_drive",
        label="Google Drive",
        availability="available",
        connected=connection.connected,
        connected_at=connection.connected_at,
        detail="Google Drive conectado com acesso somente leitura aos arquivos autorizados.",
    )


@app.delete("/api/integrations/google-drive", status_code=status.HTTP_204_NO_CONTENT)
async def remove_google_drive_connection(
    request: AuthenticatedRequest = _authenticated_request,
) -> None:
    try:
        await run_in_threadpool(disconnect_google_drive, request.client, request.user.id)
    except IntegrationConnectionError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@app.post(
    "/api/integrations/google-drive/files",
    response_model=list[GoogleDriveFileResponse],
)
async def list_google_drive_files(
    payload: GoogleDriveFolderRequest,
    request: AuthenticatedRequest = _authenticated_request,
) -> list[GoogleDriveFileResponse]:
    folder_id = _google_drive_folder_id(payload.folder_reference)
    credentials = await _load_google_drive_credentials(request)
    try:
        files = await run_in_threadpool(list_google_drive_folder_files, credentials, folder_id)
    except GoogleDriveConnectorError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return [_google_drive_file_response(file) for file in files]


@app.post(
    "/api/integrations/google-drive/import",
    response_model=GoogleDriveImportResponse,
)
async def import_google_drive_files(
    payload: GoogleDriveImportRequest,
    request: AuthenticatedRequest = _authenticated_request,
) -> GoogleDriveImportResponse:
    folder_id = _google_drive_folder_id(payload.folder_reference)
    credentials = await _load_google_drive_credentials(request)
    try:
        available_files = await run_in_threadpool(
            list_google_drive_folder_files,
            credentials,
            folder_id,
            page_size=50,
        )
    except GoogleDriveConnectorError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    files_by_id = {file.id: file for file in available_files}
    selected_ids = list(dict.fromkeys(file_id.strip() for file_id in payload.file_ids))
    selected_files = [files_by_id[file_id] for file_id in selected_ids if file_id in files_by_id]
    if len(selected_files) != len(selected_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Um ou mais arquivos não pertencem à pasta selecionada "
                "ou não estão mais disponíveis."
            ),
        )

    imported_documents: list[DocumentResponse] = []
    failures: list[GoogleDriveImportFailure] = []
    for drive_file in selected_files:
        try:
            downloaded_file = await run_in_threadpool(
                download_google_drive_file,
                credentials,
                drive_file,
            )
            document, _original_file_available = await _persist_uploaded_document(
                request,
                UploadedDocument(
                    filename=downloaded_file.filename,
                    content_type=downloaded_file.content_type,
                    content=downloaded_file.content,
                ),
                source_metadata={
                    "source_provider": "google_drive",
                    "source_file_id": drive_file.id,
                    "source_web_view_link": drive_file.web_view_link,
                },
            )
            imported_documents.append(document)
        except HTTPException as exc:
            failures.append(
                GoogleDriveImportFailure(filename=drive_file.name, detail=str(exc.detail))
            )
        except (
            DocumentProcessingError,
            DocumentPersistenceError,
            DocumentStorageError,
            GoogleDriveConnectorError,
        ) as exc:
            failures.append(GoogleDriveImportFailure(filename=drive_file.name, detail=str(exc)))

    message = (
        f"{len(imported_documents)} arquivo(s) importado(s) do Google Drive."
        if imported_documents
        else "Nenhum arquivo do Google Drive foi importado."
    )
    return GoogleDriveImportResponse(
        imported_documents=imported_documents,
        failures=failures,
        message=message,
    )


@app.post("/api/integrations/slack/authorization", response_model=OAuthAuthorizationResponse)
async def begin_slack_authorization(
    request: AuthenticatedRequest = _authenticated_request,
) -> OAuthAuthorizationResponse:
    """Start a Slack OAuth consent flow bound to the authenticated Synapse account."""
    _require_slack_configuration(request)
    state = _build_integration_oauth_state("slack", request)
    try:
        authorization_url = build_slack_oauth_authorization_url(
            request.config.slack.client_id,
            request.config.slack.redirect_uri,
            state,
        )
    except SlackOAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return OAuthAuthorizationResponse(authorization_url=authorization_url, state=state)


@app.post("/api/integrations/slack/complete", response_model=IntegrationStatusResponse)
async def complete_slack_authorization(
    payload: OAuthCompletionRequest,
    request: AuthenticatedRequest = _authenticated_request,
) -> IntegrationStatusResponse:
    _require_slack_configuration(request)
    try:
        _validate_integration_oauth_state("slack", payload.state, request)
        tokens = await run_in_threadpool(
            exchange_slack_oauth_code,
            request.config.slack.client_id,
            request.config.slack.client_secret,
            request.config.slack.redirect_uri,
            payload.code,
        )
        connection = await run_in_threadpool(
            save_slack_connection,
            request.client,
            request.user.id,
            tokens,
            connector_encryption_key(),
        )
    except (
        SlackOAuthError,
        SlackConnectionError,
        IntegrationConnectionError,
        IntegrationCredentialError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return IntegrationStatusResponse(
        provider="slack",
        label="Slack",
        availability="available",
        connected=connection.connected,
        connected_at=connection.connected_at,
        detail=(
            "Slack conectado com acesso somente leitura. Adicione o app Synapse AI "
            "somente aos canais que deseja importar."
        ),
    )


@app.delete("/api/integrations/slack", status_code=status.HTTP_204_NO_CONTENT)
async def remove_slack_connection(
    request: AuthenticatedRequest = _authenticated_request,
) -> None:
    try:
        await run_in_threadpool(disconnect_slack, request.client, request.user.id)
    except IntegrationConnectionError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@app.get("/api/integrations/slack/conversations", response_model=list[SlackConversationResponse])
async def get_slack_conversations(
    request: AuthenticatedRequest = _authenticated_request,
) -> list[SlackConversationResponse]:
    credentials = await _load_slack_credentials(request)
    try:
        conversations = await run_in_threadpool(list_slack_conversations, credentials)
    except SlackConnectorError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return [_slack_conversation_response(conversation) for conversation in conversations]


@app.post("/api/integrations/slack/import", response_model=ConnectorImportResponse)
async def import_slack_conversations(
    payload: SlackImportRequest,
    request: AuthenticatedRequest = _authenticated_request,
) -> ConnectorImportResponse:
    credentials = await _load_slack_credentials(request)
    try:
        available = await run_in_threadpool(list_slack_conversations, credentials)
    except SlackConnectorError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    conversations_by_id = {conversation.id: conversation for conversation in available}
    selected_ids = list(
        dict.fromkeys(conversation_id.strip() for conversation_id in payload.conversation_ids)
    )
    selected = [
        conversations_by_id[item_id] for item_id in selected_ids if item_id in conversations_by_id
    ]
    if len(selected) != len(selected_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Um ou mais canais não estão mais disponíveis para a conta conectada.",
        )

    imported_documents: list[DocumentResponse] = []
    failures: list[ConnectorImportFailure] = []
    for conversation in selected:
        try:
            downloaded = await run_in_threadpool(
                download_slack_conversation,
                credentials,
                conversation,
                message_limit=payload.message_limit,
            )
            document, _original_file_available = await _persist_uploaded_document(
                request,
                UploadedDocument(
                    filename=downloaded.filename,
                    content_type="application/json",
                    content=downloaded.content,
                ),
                source_metadata={
                    "source_provider": "slack",
                    "source_conversation_id": conversation.id,
                    "source_conversation_name": conversation.name,
                    "source_message_count": downloaded.message_count,
                },
            )
            imported_documents.append(document)
        except HTTPException as exc:
            failures.append(
                ConnectorImportFailure(filename=conversation.name, detail=str(exc.detail))
            )
        except (
            DocumentProcessingError,
            DocumentPersistenceError,
            DocumentStorageError,
            SlackConnectorError,
        ) as exc:
            failures.append(ConnectorImportFailure(filename=conversation.name, detail=str(exc)))
    return _connector_import_response("Slack", imported_documents, failures)


@app.post("/api/integrations/microsoft/authorization", response_model=OAuthAuthorizationResponse)
async def begin_microsoft_authorization(
    request: AuthenticatedRequest = _authenticated_request,
) -> OAuthAuthorizationResponse:
    """Start one Microsoft Graph connection used by Teams and SharePoint."""
    _require_microsoft_configuration(request)
    state = _build_integration_oauth_state("microsoft_graph", request)
    try:
        authorization_url = build_microsoft_oauth_authorization_url(
            request.config.microsoft.tenant_id,
            request.config.microsoft.client_id,
            request.config.microsoft.redirect_uri,
            state,
        )
    except MicrosoftOAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return OAuthAuthorizationResponse(authorization_url=authorization_url, state=state)


@app.post("/api/integrations/microsoft/complete", response_model=IntegrationStatusResponse)
async def complete_microsoft_authorization(
    payload: OAuthCompletionRequest,
    request: AuthenticatedRequest = _authenticated_request,
) -> IntegrationStatusResponse:
    _require_microsoft_configuration(request)
    try:
        _validate_integration_oauth_state("microsoft_graph", payload.state, request)
        tokens = await run_in_threadpool(
            exchange_microsoft_oauth_code,
            request.config.microsoft.tenant_id,
            request.config.microsoft.client_id,
            request.config.microsoft.client_secret,
            request.config.microsoft.redirect_uri,
            payload.code,
        )
        connection = await run_in_threadpool(
            save_microsoft_connection,
            request.client,
            request.user.id,
            tokens,
            connector_encryption_key(),
        )
    except (
        MicrosoftOAuthError,
        MicrosoftConnectionError,
        IntegrationConnectionError,
        IntegrationCredentialError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return IntegrationStatusResponse(
        provider="microsoft_teams",
        label="Microsoft 365",
        availability="available",
        connected=connection.connected,
        connected_at=connection.connected_at,
        detail=(
            "Microsoft 365 conectado com acesso somente leitura ao Teams e ao "
            "SharePoint autorizados."
        ),
    )


@app.delete("/api/integrations/microsoft", status_code=status.HTTP_204_NO_CONTENT)
async def remove_microsoft_connection(
    request: AuthenticatedRequest = _authenticated_request,
) -> None:
    try:
        await run_in_threadpool(disconnect_microsoft, request.client, request.user.id)
    except IntegrationConnectionError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@app.get("/api/integrations/microsoft/teams", response_model=list[MicrosoftTeamResponse])
async def get_microsoft_teams(
    request: AuthenticatedRequest = _authenticated_request,
) -> list[MicrosoftTeamResponse]:
    credentials = await _load_microsoft_credentials(request)
    try:
        teams = await run_in_threadpool(list_microsoft_teams, credentials)
    except MicrosoftGraphConnectorError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return [_microsoft_team_response(team) for team in teams]


@app.post(
    "/api/integrations/microsoft/teams/channels", response_model=list[MicrosoftChannelResponse]
)
async def get_microsoft_team_channels(
    payload: MicrosoftTeamChannelsRequest,
    request: AuthenticatedRequest = _authenticated_request,
) -> list[MicrosoftChannelResponse]:
    credentials = await _load_microsoft_credentials(request)
    try:
        channels = await run_in_threadpool(
            list_microsoft_team_channels, credentials, payload.team_id
        )
    except MicrosoftGraphConnectorError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return [_microsoft_channel_response(channel) for channel in channels]


@app.post("/api/integrations/microsoft/teams/import", response_model=ConnectorImportResponse)
async def import_microsoft_team_channels(
    payload: MicrosoftTeamsImportRequest,
    request: AuthenticatedRequest = _authenticated_request,
) -> ConnectorImportResponse:
    credentials = await _load_microsoft_credentials(request)
    imported_documents: list[DocumentResponse] = []
    failures: list[ConnectorImportFailure] = []
    for channel_payload in payload.channels:
        channel = MicrosoftChannel(
            id=channel_payload.id,
            name=channel_payload.name,
            description=channel_payload.description,
        )
        try:
            downloaded = await run_in_threadpool(
                download_microsoft_team_channel,
                credentials,
                payload.team_id,
                channel,
                message_limit=payload.message_limit,
            )
            document, _original_file_available = await _persist_uploaded_document(
                request,
                UploadedDocument(
                    filename=downloaded.filename,
                    content_type=downloaded.content_type,
                    content=downloaded.content,
                ),
                source_metadata={
                    "source_provider": "microsoft_teams",
                    "source_team_id": payload.team_id,
                    "source_channel_id": channel.id,
                    "source_channel_name": channel.name,
                },
            )
            imported_documents.append(document)
        except HTTPException as exc:
            failures.append(ConnectorImportFailure(filename=channel.name, detail=str(exc.detail)))
        except (
            DocumentProcessingError,
            DocumentPersistenceError,
            DocumentStorageError,
            MicrosoftGraphConnectorError,
        ) as exc:
            failures.append(ConnectorImportFailure(filename=channel.name, detail=str(exc)))
    return _connector_import_response("Microsoft Teams", imported_documents, failures)


@app.get(
    "/api/integrations/microsoft/sharepoint/sites", response_model=list[SharePointSiteResponse]
)
async def get_sharepoint_sites(
    request: AuthenticatedRequest = _authenticated_request,
) -> list[SharePointSiteResponse]:
    credentials = await _load_microsoft_credentials(request)
    try:
        sites = await run_in_threadpool(list_sharepoint_sites, credentials)
    except MicrosoftGraphConnectorError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return [_sharepoint_site_response(site) for site in sites]


@app.post(
    "/api/integrations/microsoft/sharepoint/drives", response_model=list[SharePointDriveResponse]
)
async def get_sharepoint_drives(
    payload: SharePointDrivesRequest,
    request: AuthenticatedRequest = _authenticated_request,
) -> list[SharePointDriveResponse]:
    credentials = await _load_microsoft_credentials(request)
    try:
        drives = await run_in_threadpool(list_sharepoint_drives, credentials, payload.site_id)
    except MicrosoftGraphConnectorError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return [_sharepoint_drive_response(drive) for drive in drives]


@app.post(
    "/api/integrations/microsoft/sharepoint/files", response_model=list[SharePointFileResponse]
)
async def get_sharepoint_files(
    payload: SharePointFilesRequest,
    request: AuthenticatedRequest = _authenticated_request,
) -> list[SharePointFileResponse]:
    credentials = await _load_microsoft_credentials(request)
    try:
        files = await run_in_threadpool(
            list_sharepoint_drive_files,
            credentials,
            payload.drive_id,
            folder_id=payload.folder_id,
        )
    except MicrosoftGraphConnectorError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return [_sharepoint_file_response(file) for file in files]


@app.post("/api/integrations/microsoft/sharepoint/import", response_model=ConnectorImportResponse)
async def import_sharepoint_files(
    payload: SharePointImportRequest,
    request: AuthenticatedRequest = _authenticated_request,
) -> ConnectorImportResponse:
    credentials = await _load_microsoft_credentials(request)
    imported_documents: list[DocumentResponse] = []
    failures: list[ConnectorImportFailure] = []
    for file_payload in payload.files:
        file = SharePointFile(
            id=file_payload.id,
            name=file_payload.name,
            mime_type=file_payload.mime_type,
            size_bytes=file_payload.size_bytes,
            web_url=file_payload.web_url,
            is_folder=file_payload.is_folder,
        )
        try:
            downloaded = await run_in_threadpool(
                download_sharepoint_file, credentials, payload.drive_id, file
            )
            document, _original_file_available = await _persist_uploaded_document(
                request,
                UploadedDocument(
                    filename=downloaded.filename,
                    content_type=downloaded.content_type,
                    content=downloaded.content,
                ),
                source_metadata={
                    "source_provider": "sharepoint",
                    "source_drive_id": payload.drive_id,
                    "source_file_id": file.id,
                    "source_web_view_link": file.web_url,
                },
            )
            imported_documents.append(document)
        except HTTPException as exc:
            failures.append(ConnectorImportFailure(filename=file.name, detail=str(exc.detail)))
        except (
            DocumentProcessingError,
            DocumentPersistenceError,
            DocumentStorageError,
            MicrosoftGraphConnectorError,
        ) as exc:
            failures.append(ConnectorImportFailure(filename=file.name, detail=str(exc)))
    return _connector_import_response("SharePoint", imported_documents, failures)


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
    document, original_file_available = await _persist_uploaded_document(request, upload)

    return DocumentUploadResponse(
        document=document,
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
        CopilotMessage(role=message.role, content=message.content) for message in payload.messages
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


def _slack_status(request: AuthenticatedRequest) -> IntegrationStatusResponse:
    if not _slack_is_configured(request):
        return IntegrationStatusResponse(
            provider="slack",
            label="Slack",
            availability="needs_configuration",
            detail="O Slack precisa concluir a configuração segura do servidor antes da conexão.",
        )
    return IntegrationStatusResponse(
        provider="slack",
        label="Slack",
        availability="available",
        detail=(
            "Conecte uma área de trabalho e adicione o app Synapse AI apenas aos canais "
            "que deseja importar."
        ),
    )


def _microsoft_status(request: AuthenticatedRequest) -> IntegrationStatusResponse:
    if not _microsoft_is_configured(request):
        return IntegrationStatusResponse(
            provider="microsoft_teams",
            label="Microsoft 365",
            availability="needs_configuration",
            detail=(
                "Teams e SharePoint precisam concluir o registro OAuth corporativo antes "
                "da conexão."
            ),
        )
    return IntegrationStatusResponse(
        provider="microsoft_teams",
        label="Microsoft 365",
        availability="available",
        detail=(
            "Conecte uma conta Microsoft 365 para importar conteúdo autorizado do Teams "
            "e SharePoint."
        ),
    )


def _slack_is_configured(request: AuthenticatedRequest) -> bool:
    settings = request.config.slack
    return bool(
        settings.client_id.strip()
        and settings.client_secret.strip()
        and settings.redirect_uri.strip()
        and connector_encryption_key()
    )


def _microsoft_is_configured(request: AuthenticatedRequest) -> bool:
    settings = request.config.microsoft
    return bool(
        settings.tenant_id.strip()
        and settings.client_id.strip()
        and settings.client_secret.strip()
        and settings.redirect_uri.strip()
        and connector_encryption_key()
    )


def _require_slack_configuration(request: AuthenticatedRequest) -> None:
    if not _slack_is_configured(request):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "O Slack ainda não foi configurado no servidor. Finalize as credenciais "
                "OAuth e o endereço de retorno."
            ),
        )


def _require_microsoft_configuration(request: AuthenticatedRequest) -> None:
    if not _microsoft_is_configured(request):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "O Microsoft 365 ainda não foi configurado no servidor. Finalize o registro OAuth, "
                "as permissões e o endereço de retorno."
            ),
        )


def _build_integration_oauth_state(provider: str, request: AuthenticatedRequest) -> str:
    """Mint opaque state that binds a provider callback to exactly one Synapse account."""
    try:
        return encrypt_integration_credentials(
            {"provider": provider, "user_id": request.user.id},
            connector_encryption_key(),
        )
    except IntegrationCredentialError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível preparar a conexão corporativa segura.",
        ) from exc


def _validate_integration_oauth_state(
    provider: str,
    oauth_state: str,
    request: AuthenticatedRequest,
) -> None:
    try:
        state_payload = decrypt_integration_credentials(oauth_state, connector_encryption_key())
    except IntegrationCredentialError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O retorno corporativo não corresponde a uma conexão válida.",
        ) from exc
    if state_payload.get("provider") != provider or state_payload.get("user_id") != request.user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O retorno corporativo pertence a outra conta.",
        )


async def _load_slack_credentials(request: AuthenticatedRequest):
    _require_slack_configuration(request)
    try:
        return await run_in_threadpool(
            load_slack_credentials,
            request.client,
            request.user.id,
            connector_encryption_key(),
            request.config.slack.client_id,
            request.config.slack.client_secret,
        )
    except (SlackConnectionError, IntegrationConnectionError, IntegrationCredentialError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


async def _load_microsoft_credentials(request: AuthenticatedRequest):
    _require_microsoft_configuration(request)
    try:
        return await run_in_threadpool(
            load_microsoft_credentials,
            request.client,
            request.user.id,
            connector_encryption_key(),
            request.config.microsoft.tenant_id,
            request.config.microsoft.client_id,
            request.config.microsoft.client_secret,
        )
    except (
        MicrosoftConnectionError,
        IntegrationConnectionError,
        IntegrationCredentialError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


def _slack_conversation_response(conversation: SlackConversation) -> SlackConversationResponse:
    return SlackConversationResponse(
        id=conversation.id,
        name=conversation.name,
        is_private=conversation.is_private,
        topic=conversation.topic,
    )


def _microsoft_team_response(team: MicrosoftTeam) -> MicrosoftTeamResponse:
    return MicrosoftTeamResponse(id=team.id, name=team.name, description=team.description)


def _microsoft_channel_response(channel: MicrosoftChannel) -> MicrosoftChannelResponse:
    return MicrosoftChannelResponse(
        id=channel.id, name=channel.name, description=channel.description
    )


def _sharepoint_site_response(site: SharePointSite) -> SharePointSiteResponse:
    return SharePointSiteResponse(id=site.id, name=site.name, web_url=site.web_url)


def _sharepoint_drive_response(drive: SharePointDrive) -> SharePointDriveResponse:
    return SharePointDriveResponse(id=drive.id, name=drive.name, web_url=drive.web_url)


def _sharepoint_file_response(file: SharePointFile) -> SharePointFileResponse:
    return SharePointFileResponse(
        id=file.id,
        name=file.name,
        mime_type=file.mime_type,
        size_bytes=file.size_bytes,
        web_url=file.web_url,
        is_folder=file.is_folder,
    )


def _connector_import_response(
    provider_label: str,
    imported_documents: list[DocumentResponse],
    failures: list[ConnectorImportFailure],
) -> ConnectorImportResponse:
    message = (
        f"{len(imported_documents)} item(ns) importado(s) do {provider_label}."
        if imported_documents
        else f"Nenhum item do {provider_label} foi importado."
    )
    return ConnectorImportResponse(
        imported_documents=imported_documents,
        failures=failures,
        message=message,
    )


def _google_drive_status(request: AuthenticatedRequest) -> IntegrationStatusResponse:
    if not _google_drive_is_configured(request):
        return IntegrationStatusResponse(
            provider="google_drive",
            label="Google Drive",
            availability="needs_configuration",
            detail=(
                "O Google Drive precisa concluir a configuração segura do servidor "
                "antes da conexão."
            ),
        )
    return IntegrationStatusResponse(
        provider="google_drive",
        label="Google Drive",
        availability="available",
        detail="Conecte uma conta para buscar e importar arquivos de uma pasta autorizada.",
    )


def _google_drive_is_configured(request: AuthenticatedRequest) -> bool:
    settings = request.config.google_drive
    return bool(
        settings.client_id.strip()
        and settings.client_secret.strip()
        and settings.redirect_uri.strip()
        and connector_encryption_key()
    )


def _build_google_drive_oauth_state(request: AuthenticatedRequest) -> str:
    """Create an opaque OAuth state that cannot be reused by another Synapse account."""
    try:
        return encrypt_integration_credentials(
            {"provider": "google_drive", "user_id": request.user.id},
            connector_encryption_key(),
        )
    except IntegrationCredentialError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível preparar a conexão segura com o Google Drive.",
        ) from exc


def _validate_google_drive_oauth_state(
    oauth_state: str,
    request: AuthenticatedRequest,
) -> None:
    """Reject OAuth callbacks not minted for the account that is completing them."""
    try:
        state_payload = decrypt_integration_credentials(oauth_state, connector_encryption_key())
    except IntegrationCredentialError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O retorno do Google Drive não corresponde a uma conexão válida.",
        ) from exc

    if (
        state_payload.get("provider") != "google_drive"
        or state_payload.get("user_id") != request.user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O retorno do Google Drive pertence a outra conta.",
        )


def _require_google_drive_configuration(request: AuthenticatedRequest) -> None:
    if not _google_drive_is_configured(request):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "O Google Drive ainda não foi configurado no servidor. "
                "Finalize as credenciais OAuth, o endereço de retorno e a chave de proteção."
            ),
        )


async def _load_google_drive_credentials(
    request: AuthenticatedRequest,
):
    _require_google_drive_configuration(request)
    try:
        return await run_in_threadpool(
            load_google_drive_credentials,
            request.client,
            request.user.id,
            connector_encryption_key(),
            request.config.google_drive.client_id,
            request.config.google_drive.client_secret,
        )
    except (
        GoogleDriveConnectionError,
        IntegrationConnectionError,
        IntegrationCredentialError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


def _google_drive_folder_id(folder_reference: str) -> str:
    try:
        return extract_google_drive_folder_id(folder_reference)
    except GoogleDriveConnectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


def _google_drive_file_response(file: GoogleDriveFile) -> GoogleDriveFileResponse:
    return GoogleDriveFileResponse(
        id=file.id,
        name=file.name,
        mime_type=file.mime_type,
        size_bytes=file.size_bytes,
        web_view_link=file.web_view_link or None,
    )


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


async def _persist_uploaded_document(
    request: AuthenticatedRequest,
    upload: UploadedDocument,
    *,
    source_metadata: dict[str, Any] | None = None,
) -> tuple[DocumentResponse, bool]:
    """Persist local or connector content through one identical extraction pipeline."""
    try:
        parsed_document = await run_in_threadpool(_parse_document, request, upload)
    except (DocumentProcessingError, AudioTranscriptionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if source_metadata:
        parsed_document = replace(
            parsed_document,
            metadata={**parsed_document.metadata, **source_metadata},
        )

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

    return _document_response(saved_document, original_file_available), original_file_available


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
