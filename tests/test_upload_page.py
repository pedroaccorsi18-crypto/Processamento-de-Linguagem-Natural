from __future__ import annotations

from synapse_ai.config import (
    AppConfig,
    AppSettings,
    GoogleDriveSettings,
    OpenAISettings,
    SupabaseSettings,
)
from synapse_ai.services.document_service import UploadedDocument
from synapse_ai.ui.upload_page import _find_duplicate_document, _uploaded_document_cache_key


def _config(transcription_model: str = "gpt-4o-mini-transcribe") -> AppConfig:
    return AppConfig(
        supabase=SupabaseSettings(url="https://example.supabase.co", publishable_key="key"),
        openai=OpenAISettings(
            api_key="sk-test",
            transcription_model=transcription_model,
        ),
        google_drive=GoogleDriveSettings(),
        app=AppSettings(),
    )


def test_find_duplicate_document_matches_only_current_user() -> None:
    parsed_metadata = {"checksum_sha256": "same-checksum"}
    documents = [
        {
            "filename": "arquivo-de-outra-conta.pdf",
            "user_id": "user-2",
            "metadata": {"checksum_sha256": "same-checksum"},
        },
        {
            "filename": "arquivo-da-conta-atual.pdf",
            "user_id": "user-1",
            "metadata": {"checksum_sha256": "same-checksum"},
        },
    ]

    duplicate = _find_duplicate_document(parsed_metadata, documents, "user-1")

    assert duplicate is not None
    assert duplicate["filename"] == "arquivo-da-conta-atual.pdf"


def test_find_duplicate_document_ignores_other_users() -> None:
    parsed_metadata = {"checksum_sha256": "same-checksum"}
    documents = [
        {
            "filename": "arquivo-de-outra-conta.pdf",
            "user_id": "user-2",
            "metadata": {"checksum_sha256": "same-checksum"},
        }
    ]

    assert _find_duplicate_document(parsed_metadata, documents, "user-1") is None


def test_find_duplicate_document_ignores_records_without_user_id() -> None:
    parsed_metadata = {"checksum_sha256": "same-checksum"}
    documents = [
        {
            "filename": "registro-antigo-sem-dono.pdf",
            "metadata": {"checksum_sha256": "same-checksum"},
        }
    ]

    assert _find_duplicate_document(parsed_metadata, documents, "user-1") is None


def test_uploaded_document_cache_key_changes_with_content() -> None:
    first_key = _uploaded_document_cache_key(
        _config(),
        UploadedDocument(
            filename="arquivo.pdf",
            content_type="application/pdf",
            content=b"conteudo-a",
        ),
    )
    second_key = _uploaded_document_cache_key(
        _config(),
        UploadedDocument(
            filename="arquivo.pdf",
            content_type="application/pdf",
            content=b"conteudo-b",
        ),
    )

    assert first_key != second_key


def test_uploaded_document_cache_key_changes_with_transcription_model() -> None:
    uploaded_document = UploadedDocument(
        filename="audio.m4a",
        content_type="audio/mp4",
        content=b"audio",
    )

    assert _uploaded_document_cache_key(
        _config("gpt-4o-mini-transcribe"),
        uploaded_document,
    ) != _uploaded_document_cache_key(
        _config("outro-modelo"),
        uploaded_document,
    )
