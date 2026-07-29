from __future__ import annotations

import asyncio

import backend.main as backend_main
from backend.auth import AuthenticatedRequest
from fastapi.testclient import TestClient

from synapse_ai.config import (
    AppConfig,
    AppSettings,
    GoogleDriveSettings,
    OpenAISettings,
    SupabaseSettings,
)
from synapse_ai.models.user import AuthenticatedUser


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
