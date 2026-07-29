from __future__ import annotations

import backend.main as backend_main
from fastapi.testclient import TestClient

from synapse_ai.config import (
    AppConfig,
    AppSettings,
    GoogleDriveSettings,
    OpenAISettings,
    SupabaseSettings,
)


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


def test_health_check() -> None:
    client = TestClient(backend_main.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_dashboard_stats_route_returns_contract() -> None:
    client = TestClient(backend_main.app)

    response = client.get("/api/dashboard/stats")

    assert response.status_code == 200
    assert response.json() == {
        "base_ready": 0,
        "evidence_count": 0,
        "risk_count": 0,
        "pending_confirmation_count": 0,
    }


def test_copilot_route_returns_json(monkeypatch) -> None:
    observed: dict[str, object] = {}

    def fake_generate_copilot_answer(*args, **kwargs) -> str:
        observed["args"] = args
        observed["kwargs"] = kwargs
        return "Resposta do Copiloto"

    monkeypatch.setattr(backend_main, "load_backend_config", _config)
    monkeypatch.setattr(backend_main, "OpenAI", lambda api_key: object())
    monkeypatch.setattr(
        backend_main,
        "_generate_copilot_answer",
        fake_generate_copilot_answer,
    )
    client = TestClient(backend_main.app)

    response = client.post(
        "/api/copilot",
        json={
            "prompt": "O que devo fazer agora?",
            "current_area": "Dashboard",
            "context": "Documentos recentes: nenhum.",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"answer": "Resposta do Copiloto", "model": "gpt-test"}
    kwargs = observed["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["api_key"] == "sk-test"
    assert kwargs["model"] == "gpt-test"
    assert kwargs["current_area"] == "Dashboard"
