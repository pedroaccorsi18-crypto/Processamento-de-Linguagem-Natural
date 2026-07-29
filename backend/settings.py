from __future__ import annotations

import os
import tomllib
from copy import deepcopy
from pathlib import Path
from typing import Any

from synapse_ai.config import AppConfig, load_config

ROOT_DIR = Path(__file__).resolve().parents[1]
STREAMLIT_SECRETS_PATH = ROOT_DIR / ".streamlit" / "secrets.toml"


def load_backend_config() -> AppConfig:
    """Load API settings from environment variables or the existing Streamlit secrets."""
    source = _load_streamlit_secrets()
    _apply_environment_overrides(source)
    return load_config(source)


def backend_cors_origins() -> list[str]:
    """Return the explicitly configured browser origins allowed to call the API."""
    raw_origins = os.getenv("CORS_ORIGINS", "")
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


def backend_cors_origin_regex() -> str:
    """Allow the canonical Synapse deployment and its Vercel preview URLs."""
    configured_regex = os.getenv("CORS_ORIGIN_REGEX")
    if configured_regex and configured_regex.strip():
        return configured_regex.strip()
    return r"^https://processamento-de-linguagem-natural(?:-[a-z0-9]+)?\.vercel\.app$"


def connector_encryption_key() -> str:
    """Return the backend-only key used to encrypt provider credentials at rest."""
    return os.getenv("CONNECTOR_ENCRYPTION_KEY", "").strip()


def _load_streamlit_secrets() -> dict[str, Any]:
    if not STREAMLIT_SECRETS_PATH.exists():
        return {}

    with STREAMLIT_SECRETS_PATH.open("rb") as secrets_file:
        loaded = tomllib.load(secrets_file)
    return deepcopy(loaded)


def _apply_environment_overrides(source: dict[str, Any]) -> None:
    _set_nested_if_present(source, "supabase", "url", "SUPABASE_URL")
    _set_nested_if_present(source, "supabase", "publishable_key", "SUPABASE_PUBLISHABLE_KEY")
    _set_nested_if_present(source, "supabase", "publishable_key", "SUPABASE_ANON_KEY")
    _set_nested_if_present(source, "openai", "api_key", "OPENAI_API_KEY")
    _set_nested_if_present(source, "openai", "embedding_model", "OPENAI_EMBEDDING_MODEL")
    _set_nested_if_present(source, "openai", "generation_model", "OPENAI_GENERATION_MODEL")
    _set_nested_if_present(
        source,
        "openai",
        "transcription_model",
        "OPENAI_TRANSCRIPTION_MODEL",
    )
    _set_nested_if_present(source, "google_drive", "api_key", "GOOGLE_DRIVE_API_KEY")
    _set_nested_if_present(source, "google_drive", "client_id", "GOOGLE_DRIVE_CLIENT_ID")
    _set_nested_if_present(
        source,
        "google_drive",
        "client_secret",
        "GOOGLE_DRIVE_CLIENT_SECRET",
    )
    _set_nested_if_present(source, "google_drive", "redirect_uri", "GOOGLE_DRIVE_REDIRECT_URI")
    _set_nested_if_present(source, "slack", "client_id", "SLACK_CLIENT_ID")
    _set_nested_if_present(source, "slack", "client_secret", "SLACK_CLIENT_SECRET")
    _set_nested_if_present(source, "slack", "redirect_uri", "SLACK_REDIRECT_URI")
    _set_nested_if_present(source, "microsoft", "tenant_id", "MICROSOFT_TENANT_ID")
    _set_nested_if_present(source, "microsoft", "client_id", "MICROSOFT_CLIENT_ID")
    _set_nested_if_present(source, "microsoft", "client_secret", "MICROSOFT_CLIENT_SECRET")
    _set_nested_if_present(source, "microsoft", "redirect_uri", "MICROSOFT_REDIRECT_URI")
    _set_nested_if_present(source, "app", "public_url", "APP_PUBLIC_URL")


def _set_nested_if_present(
    source: dict[str, Any],
    section: str,
    key: str,
    environment_key: str,
) -> None:
    value = os.getenv(environment_key)
    if value is None or not value.strip():
        return
    section_value = source.setdefault(section, {})
    if isinstance(section_value, dict):
        section_value[key] = value.strip()
