from __future__ import annotations

import asyncio

import backend.main as backend_main
import pytest
from backend.auth import AuthenticatedRequest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from synapse_ai.application.indexing import PrepareSemanticBaseOutput
from synapse_ai.application.result import UseCaseResult
from synapse_ai.config import (
    AppConfig,
    AppSettings,
    GoogleDriveSettings,
    OpenAISettings,
    SupabaseSettings,
)
from synapse_ai.models.user import AuthenticatedUser
from synapse_ai.services.google_drive_connection_service import GoogleDriveConnectionStatus
from synapse_ai.services.google_oauth_service import GoogleOAuthTokens


def _config() -> AppConfig:
    return AppConfig(
        supabase=SupabaseSettings(
            url="https://example.supabase.co",
            publishable_key="public-key",
        ),
        openai=OpenAISettings(api_key="sk-test", generation_model="gpt-test"),
        google_drive=GoogleDriveSettings(),
        app=AppSettings(),
    )


def _authenticated_request() -> AuthenticatedRequest:
    return AuthenticatedRequest(
        user=AuthenticatedUser(id="user-1", email="user@example.com"),
        client=object(),
        config=_config(),
    )


def _google_drive_authenticated_request(
    user_id: str = "user-1",
) -> AuthenticatedRequest:
    return AuthenticatedRequest(
        user=AuthenticatedUser(id=user_id, email="user@example.com"),
        client=object(),
        config=AppConfig(
            supabase=SupabaseSettings(
                url="https://example.supabase.co",
                publishable_key="public-key",
            ),
            openai=OpenAISettings(api_key="sk-test", generation_model="gpt-test"),
            google_drive=GoogleDriveSettings(
                client_id="google-client-id",
                client_secret="google-client-secret",
                redirect_uri="http://localhost:3000/upload",
            ),
            app=AppSettings(),
        ),
    )


def test_health_check() -> None:
    client = TestClient(backend_main.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_dashboard_stats_route_returns_contract(monkeypatch) -> None:
    backend_main.app.dependency_overrides[backend_main.require_authenticated_request] = (
        _authenticated_request
    )
    monkeypatch.setattr(backend_main, "list_user_documents", lambda *args: [])
    client = TestClient(backend_main.app)

    try:
        response = client.get("/api/dashboard/stats")
    finally:
        backend_main.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "base_ready": 0,
        "evidence_count": 0,
        "risk_count": 0,
        "pending_confirmation_count": 0,
    }


def test_document_routes_require_an_authenticated_session() -> None:
    client = TestClient(backend_main.app)

    response = client.get("/api/documents")

    assert response.status_code == 401


def test_integrations_returns_an_account_scoped_google_drive_status(monkeypatch) -> None:
    encryption_key = Fernet.generate_key().decode("utf-8")
    backend_main.app.dependency_overrides[backend_main.require_authenticated_request] = (
        _google_drive_authenticated_request
    )
    monkeypatch.setattr(backend_main, "connector_encryption_key", lambda: encryption_key)
    monkeypatch.setattr(
        backend_main,
        "google_drive_connection_status",
        lambda *_args: GoogleDriveConnectionStatus(
            connected=True,
            connected_at="2026-07-29T12:00:00+00:00",
        ),
    )
    client = TestClient(backend_main.app)

    try:
        response = client.get("/api/integrations")
    finally:
        backend_main.app.dependency_overrides.clear()

    assert response.status_code == 200
    integrations = {item["provider"]: item for item in response.json()}
    assert integrations["google_drive"]["connected"] is True
    assert integrations["slack"]["availability"] == "coming_soon"


def test_google_drive_authorization_and_completion_are_bound_to_the_account(monkeypatch) -> None:
    encryption_key = Fernet.generate_key().decode("utf-8")
    observed: dict[str, object] = {}
    backend_main.app.dependency_overrides[backend_main.require_authenticated_request] = (
        _google_drive_authenticated_request
    )
    monkeypatch.setattr(backend_main, "connector_encryption_key", lambda: encryption_key)
    monkeypatch.setattr(
        backend_main,
        "build_google_oauth_authorization_url",
        lambda *_args, **_kwargs: "https://accounts.google.test/authorize",
    )
    monkeypatch.setattr(
        backend_main,
        "exchange_google_oauth_code",
        lambda *_args, **_kwargs: GoogleOAuthTokens(
            access_token="access-token",
            refresh_token="refresh-token",
            token_type="Bearer",
            expires_in=3600,
        ),
    )
    monkeypatch.setattr(
        backend_main,
        "save_google_drive_connection",
        lambda *_args: observed.setdefault(
            "connection",
            GoogleDriveConnectionStatus(
                connected=True,
                connected_at="2026-07-29T12:00:00+00:00",
            ),
        ),
    )
    client = TestClient(backend_main.app)

    try:
        authorization = client.post("/api/integrations/google-drive/authorization")
        state = authorization.json()["state"]
        completion = client.post(
            "/api/integrations/google-drive/complete",
            json={
                "code": "authorization-code",
                "state": state,
                "code_verifier": "v" * 43,
            },
        )
    finally:
        backend_main.app.dependency_overrides.clear()

    assert authorization.status_code == 200
    assert authorization.json()["authorization_url"] == "https://accounts.google.test/authorize"
    assert completion.status_code == 200
    assert completion.json()["connected"] is True
    assert observed["connection"] is not None


def test_google_drive_oauth_rejects_a_callback_created_for_another_account(monkeypatch) -> None:
    encryption_key = Fernet.generate_key().decode("utf-8")
    backend_main.app.dependency_overrides[backend_main.require_authenticated_request] = (
        _google_drive_authenticated_request
    )
    monkeypatch.setattr(backend_main, "connector_encryption_key", lambda: encryption_key)
    state = backend_main._build_google_drive_oauth_state(_google_drive_authenticated_request())
    backend_main.app.dependency_overrides[backend_main.require_authenticated_request] = lambda: (
        _google_drive_authenticated_request("user-2")
    )
    client = TestClient(backend_main.app)

    try:
        response = client.post(
            "/api/integrations/google-drive/complete",
            json={
                "code": "authorization-code",
                "state": state,
                "code_verifier": "v" * 43,
            },
        )
    finally:
        backend_main.app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "O retorno do Google Drive pertence a outra conta."


def test_uploaded_document_rejects_content_above_the_limit() -> None:
    class LargeUpload:
        filename = "grande.txt"
        content_type = "text/plain"
        was_closed = False

        async def read(self, size: int) -> bytes:
            return b"a" * size

        async def close(self) -> None:
            self.was_closed = True

    upload = LargeUpload()

    try:
        asyncio.run(backend_main._read_uploaded_document(upload))
    except backend_main.HTTPException as exc:
        assert exc.status_code == 413
        assert exc.detail == "O arquivo excede o limite de 10 MB desta fase."
    else:
        raise AssertionError("O upload acima do limite deveria ser rejeitado.")

    assert upload.was_closed is True


def test_copilot_route_returns_json(monkeypatch) -> None:
    observed: dict[str, object] = {}

    def fake_generate_copilot_answer(*args, **kwargs) -> str:
        observed["args"] = args
        observed["kwargs"] = kwargs
        return "Resposta do Copiloto"

    backend_main.app.dependency_overrides[backend_main.require_authenticated_request] = (
        _authenticated_request
    )
    monkeypatch.setattr(backend_main, "OpenAI", lambda api_key: object())
    monkeypatch.setattr(
        backend_main,
        "_generate_copilot_answer",
        fake_generate_copilot_answer,
    )
    client = TestClient(backend_main.app)

    try:
        response = client.post(
            "/api/copilot",
            json={
                "prompt": "O que devo fazer agora?",
                "current_area": "Dashboard",
                "context": "Documentos recentes: nenhum.",
            },
        )
    finally:
        backend_main.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"answer": "Resposta do Copiloto", "model": "gpt-test"}
    kwargs = observed["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["api_key"] == "sk-test"
    assert kwargs["model"] == "gpt-test"
    assert kwargs["current_area"] == "Dashboard"


def test_studio_documents_returns_only_authenticated_documents(monkeypatch) -> None:
    backend_main.app.dependency_overrides[backend_main.require_authenticated_request] = (
        _authenticated_request
    )
    monkeypatch.setattr(
        backend_main,
        "list_user_documents_for_processing",
        lambda *args: [
            {
                "id": "document-1",
                "filename": "reuniao.pdf",
                "status": "extracted",
                "text_char_count": 1240,
                "metadata": {},
                "created_at": "2026-07-29T12:00:00Z",
            }
        ],
    )
    monkeypatch.setattr(
        backend_main,
        "list_document_chunk_counts",
        lambda *args: {"document-1": 3},
    )
    client = TestClient(backend_main.app)

    try:
        response = client.get("/api/studio/documents")
    finally:
        backend_main.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "document-1",
            "filename": "reuniao.pdf",
            "content_type": None,
            "size_bytes": None,
            "status": "extracted",
            "text_char_count": 1240,
            "metadata": {},
            "created_at": "2026-07-29T12:00:00Z",
            "original_file_available": False,
            "prepared_for_ai": True,
            "indexed_chunk_count": 3,
        }
    ]


def test_studio_preparation_runs_the_application_use_case(monkeypatch) -> None:
    observed: dict[str, object] = {}

    class FakePreparationUseCase:
        def execute(self, command: object) -> UseCaseResult[PrepareSemanticBaseOutput]:
            observed["command"] = command
            return UseCaseResult.ok(PrepareSemanticBaseOutput(indexed_chunks=4))

    backend_main.app.dependency_overrides[backend_main.require_authenticated_request] = (
        _authenticated_request
    )
    monkeypatch.setattr(
        backend_main,
        "list_user_documents_for_processing",
        lambda *args: [
            {
                "id": "document-1",
                "filename": "reuniao.pdf",
                "extracted_text": "Conteúdo de teste",
            }
        ],
    )
    monkeypatch.setattr(backend_main, "OpenAI", lambda api_key: object())
    monkeypatch.setattr(
        backend_main,
        "build_prepare_semantic_base_use_case",
        lambda: FakePreparationUseCase(),
    )
    client = TestClient(backend_main.app)

    try:
        response = client.post(
            "/api/studio/prepare",
            json={"selected_document_ids": ["document-1"]},
        )
    finally:
        backend_main.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["indexed_chunks"] == 4
    assert observed["command"] is not None


@pytest.mark.parametrize(
    "workflow",
    [
        "ask",
        "action_plan",
        "intelligence_snapshot",
        "document_comparison",
        "sentiment_analysis",
        "preventive_alerts",
        "historical_patterns",
        "multi_agent",
    ],
)
def test_studio_analysis_routes_return_a_consistent_contract(
    monkeypatch,
    workflow: str,
) -> None:
    observed: dict[str, object] = {}

    def fake_workflow(
        next_workflow: str,
        request: object,
        payload: object,
    ) -> UseCaseResult[dict[str, object]]:
        observed["workflow"] = next_workflow
        observed["payload"] = payload
        return UseCaseResult.ok(
            {
                "saved_to_history": True,
                "persistence_warning": None,
                "summary": "Resultado de teste",
            }
        )

    backend_main.app.dependency_overrides[backend_main.require_authenticated_request] = (
        _authenticated_request
    )
    monkeypatch.setattr(
        backend_main,
        "list_user_documents_for_processing",
        lambda *args: [{"id": "document-1", "filename": "reuniao.pdf"}],
    )
    monkeypatch.setattr(backend_main, "_run_studio_workflow", fake_workflow)
    client = TestClient(backend_main.app)

    try:
        response = client.post(
            f"/api/studio/analyses/{workflow}",
            json={
                "selected_document_ids": ["document-1"],
                "question": "Quais são os riscos?" if workflow == "ask" else None,
            },
        )
    finally:
        backend_main.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["workflow"] == workflow
    assert response.json()["saved_to_history"] is True
    assert response.json()["result"] == {"summary": "Resultado de teste"}
    assert observed["workflow"] == workflow


def test_studio_analysis_rejects_documents_outside_the_authenticated_scope(monkeypatch) -> None:
    backend_main.app.dependency_overrides[backend_main.require_authenticated_request] = (
        _authenticated_request
    )
    monkeypatch.setattr(
        backend_main,
        "list_user_documents_for_processing",
        lambda *args: [{"id": "document-1", "filename": "reuniao.pdf"}],
    )
    client = TestClient(backend_main.app)

    try:
        response = client.post(
            "/api/studio/analyses/ask",
            json={
                "selected_document_ids": ["document-de-outra-conta"],
                "question": "Quais são os riscos?",
            },
        )
    finally:
        backend_main.app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Um ou mais documentos do escopo não estão disponíveis para esta conta."
    )


def test_studio_history_returns_saved_analyses_for_the_authenticated_scope(monkeypatch) -> None:
    backend_main.app.dependency_overrides[backend_main.require_authenticated_request] = (
        _authenticated_request
    )
    monkeypatch.setattr(
        backend_main,
        "list_recent_analyses",
        lambda *args: [
            {
                "id": "analysis-1",
                "title": "Riscos da reunião",
                "question": "Quais são os riscos?",
                "answer": "Há um prazo crítico.",
                "sources": [{"filename": "reuniao.pdf"}],
                "model": "gpt-test",
                "status": "ready",
                "metadata": {"artifact_type": "ask"},
                "documents": {"filename": "reuniao.pdf"},
                "created_at": "2026-07-29T12:00:00Z",
            }
        ],
    )
    client = TestClient(backend_main.app)

    try:
        response = client.get("/api/studio/history?limit=20")
    finally:
        backend_main.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["document_filename"] == "reuniao.pdf"
