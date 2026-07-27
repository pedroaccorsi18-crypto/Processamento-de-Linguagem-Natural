from __future__ import annotations

import pytest

from synapse_ai.config import MissingConfigError, load_config


def fake_secrets() -> dict[str, dict[str, str]]:
    return {
        "supabase": {
            "url": "https://example.supabase.co",
            "publishable_key": "public-key",
        },
        "openai": {"api_key": "openai-key"},
    }


def test_load_config_from_injected_mapping() -> None:
    config = load_config(fake_secrets())

    assert config.supabase.url == "https://example.supabase.co"
    assert config.supabase.publishable_key == "public-key"
    assert config.openai.api_key == "openai-key"
    assert config.openai.embedding_model == "text-embedding-3-small"
    assert config.openai.generation_model == "gpt-5-mini"
    assert config.openai.transcription_model == "gpt-4o-mini-transcribe"
    assert config.google_drive.api_key == ""
    assert config.app.public_url == "http://localhost:8501"


def test_load_config_reads_public_app_url() -> None:
    secrets = fake_secrets()
    secrets["app"] = {"public_url": "https://synapse-ai-pnl.streamlit.app"}

    config = load_config(secrets)

    assert config.app.public_url == "https://synapse-ai-pnl.streamlit.app"


def test_load_config_reports_missing_setting_name_only() -> None:
    with pytest.raises(MissingConfigError) as exc_info:
        load_config({"supabase": {"url": "https://example.supabase.co"}, "openai": {}})

    assert exc_info.value.setting_name == "supabase.publishable_key"


def test_config_repr_does_not_include_secret_values() -> None:
    config = load_config(fake_secrets())

    rendered = repr(config)

    assert "public-key" not in rendered
    assert "openai-key" not in rendered
