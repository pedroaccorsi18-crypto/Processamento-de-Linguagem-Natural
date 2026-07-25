from __future__ import annotations

from synapse_ai.models.document import DocumentStatus
from synapse_ai.services.document_service import (
    DocumentProcessingError,
    UploadedDocument,
    build_document_payload,
    parse_uploaded_document,
    preview_text,
)


def test_parse_text_document_extracts_text_and_metadata() -> None:
    parsed = parse_uploaded_document(
        UploadedDocument(
            filename="ata.txt",
            content_type="text/plain",
            content="Decisão aprovada pela diretoria.".encode(),
        )
    )

    assert parsed.status == DocumentStatus.EXTRACTED
    assert parsed.text == "Decisão aprovada pela diretoria."
    assert parsed.metadata["file_extension"] == "txt"
    assert parsed.metadata["word_count"] == 4
    assert "checksum_sha256" in parsed.metadata


def test_parse_markdown_document_normalizes_line_endings() -> None:
    parsed = parse_uploaded_document(
        UploadedDocument(
            filename="relatorio.md",
            content_type="text/markdown",
            content=b"# Titulo\r\n\r\nConteudo",
        )
    )

    assert parsed.text == "# Titulo\n\nConteudo"


def test_parse_rejects_unsupported_extension() -> None:
    try:
        parse_uploaded_document(
            UploadedDocument(
                filename="planilha.xlsx",
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                content=b"content",
            )
        )
    except DocumentProcessingError as exc:
        assert "Formato" in str(exc)
    else:
        raise AssertionError("Expected DocumentProcessingError")


def test_build_document_payload_contains_phase_2_fields() -> None:
    parsed = parse_uploaded_document(
        UploadedDocument(
            filename="ata.txt",
            content_type="text/plain",
            content=b"Texto extraido",
        )
    )

    payload = build_document_payload("user-1", parsed)

    assert payload["user_id"] == "user-1"
    assert payload["filename"] == "ata.txt"
    assert payload["status"] == "extracted"
    assert payload["extracted_text"] == "Texto extraido"
    assert payload["text_char_count"] == len("Texto extraido")
    assert isinstance(payload["metadata"], dict)


def test_preview_text_truncates_long_content() -> None:
    preview = preview_text("abcdef", limit=3)

    assert preview == "abc..."
