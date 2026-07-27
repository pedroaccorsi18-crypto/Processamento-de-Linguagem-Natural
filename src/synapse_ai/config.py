from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


class MissingConfigError(RuntimeError):
    """Raised when a required configuration key is missing."""

    def __init__(self, setting_name: str) -> None:
        self.setting_name = setting_name
        super().__init__(f"Missing required configuration: {setting_name}")


@dataclass(frozen=True)
class SupabaseSettings:
    url: str
    publishable_key: str = field(repr=False)


@dataclass(frozen=True)
class OpenAISettings:
    api_key: str = field(repr=False)
    embedding_model: str = "text-embedding-3-small"
    generation_model: str = "gpt-5-mini"
    transcription_model: str = "gpt-4o-mini-transcribe"


@dataclass(frozen=True)
class GoogleDriveSettings:
    api_key: str = field(default="", repr=False)
    client_id: str = field(default="", repr=False)
    client_secret: str = field(default="", repr=False)
    redirect_uri: str = "http://localhost:8501"


@dataclass(frozen=True)
class AppConfig:
    supabase: SupabaseSettings
    openai: OpenAISettings
    google_drive: GoogleDriveSettings


def load_config(secrets: Mapping[str, Any] | None = None) -> AppConfig:
    source = secrets if secrets is not None else _streamlit_secrets()
    return AppConfig(
        supabase=SupabaseSettings(
            url=_required(source, "supabase", "url"),
            publishable_key=_required(source, "supabase", "publishable_key"),
        ),
        openai=OpenAISettings(
            api_key=_required(source, "openai", "api_key"),
            embedding_model=_optional(
                source,
                "openai",
                "embedding_model",
                "text-embedding-3-small",
            ),
            generation_model=_optional(source, "openai", "generation_model", "gpt-5-mini"),
            transcription_model=_optional(
                source,
                "openai",
                "transcription_model",
                "gpt-4o-mini-transcribe",
            ),
        ),
        google_drive=GoogleDriveSettings(
            api_key=_optional(source, "google_drive", "api_key", ""),
            client_id=_optional(source, "google_drive", "client_id", ""),
            client_secret=_optional(source, "google_drive", "client_secret", ""),
            redirect_uri=_optional(
                source,
                "google_drive",
                "redirect_uri",
                "http://localhost:8501",
            ),
        ),
    )


def _streamlit_secrets() -> Mapping[str, Any]:
    import streamlit as st

    return st.secrets


def _required(source: Mapping[str, Any], section: str, key: str) -> str:
    setting_name = f"{section}.{key}"
    try:
        section_value = source[section]
        value = section_value[key]
    except KeyError as exc:
        raise MissingConfigError(setting_name) from exc
    except TypeError as exc:
        raise MissingConfigError(setting_name) from exc

    if not isinstance(value, str) or not value.strip():
        raise MissingConfigError(setting_name)
    return value.strip()


def _optional(
    source: Mapping[str, Any],
    section: str,
    key: str,
    default: str,
) -> str:
    try:
        section_value = source[section]
        value = section_value[key]
    except (KeyError, TypeError):
        return default

    return value.strip() if isinstance(value, str) and value.strip() else default
