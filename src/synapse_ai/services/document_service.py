from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Protocol

from synapse_ai.models.document import DocumentStatus

logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024


class DocumentProcessingError(RuntimeError):
    """Raised when a document cannot be parsed safely."""


@dataclass(frozen=True)
class PlannedDocumentUpload:
    filename: str
    content_type: str
    size_bytes: int


@dataclass(frozen=True)
class UploadedDocument:
    filename: str
    content_type: str
    content: bytes


@dataclass(frozen=True)
class ParsedDocument:
    filename: str
    content_type: str
    size_bytes: int
    text: str
    status: DocumentStatus
    metadata: dict[str, object]


class UploadedFileLike(Protocol):
    name: str
    type: str
    size: int

    def getvalue(self) -> bytes:
        """Return uploaded file bytes."""
        ...


def describe_supported_document_formats() -> list[str]:
    return ["PDF", "DOCX", "TXT", "MD"]


def validate_planned_upload(upload: PlannedDocumentUpload) -> bool:
    return (
        upload.size_bytes > 0
        and bool(upload.filename.strip())
        and bool(upload.content_type.strip())
    )


def parse_streamlit_upload(uploaded_file: UploadedFileLike) -> ParsedDocument:
    content = uploaded_file.getvalue()
    return parse_uploaded_document(
        UploadedDocument(
            filename=uploaded_file.name,
            content_type=uploaded_file.type or "application/octet-stream",
            content=content,
        )
    )


def parse_uploaded_document(upload: UploadedDocument) -> ParsedDocument:
    extension = Path(upload.filename).suffix.lower()
    _validate_upload(upload, extension)

    parser = _parser_for_extension(extension)
    try:
        text, parser_metadata = parser(upload.content)
    except DocumentProcessingError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("Document parsing failed: %s", exc.__class__.__name__)
        raise DocumentProcessingError("Não foi possível extrair texto do arquivo enviado.") from exc

    normalized_text = _normalize_text(text)
    if not normalized_text:
        raise DocumentProcessingError("Nenhum texto foi encontrado no arquivo enviado.")

    metadata: dict[str, object] = {
        "file_extension": extension.removeprefix("."),
        "checksum_sha256": hashlib.sha256(upload.content).hexdigest(),
        "word_count": _word_count(normalized_text),
        "char_count": len(normalized_text),
        **parser_metadata,
    }

    return ParsedDocument(
        filename=upload.filename,
        content_type=upload.content_type,
        size_bytes=len(upload.content),
        text=normalized_text,
        status=DocumentStatus.EXTRACTED,
        metadata=metadata,
    )


def build_document_payload(user_id: str, parsed_document: ParsedDocument) -> dict[str, object]:
    return {
        "user_id": user_id,
        "filename": parsed_document.filename,
        "content_type": parsed_document.content_type,
        "size_bytes": parsed_document.size_bytes,
        "status": parsed_document.status.value,
        "extracted_text": parsed_document.text,
        "text_char_count": len(parsed_document.text),
        "metadata": parsed_document.metadata,
    }


def preview_text(text: str, limit: int = 1200) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _validate_upload(upload: UploadedDocument, extension: str) -> None:
    if not upload.filename.strip():
        raise DocumentProcessingError("O arquivo precisa ter um nome válido.")
    if not upload.content:
        raise DocumentProcessingError("O arquivo enviado está vazio.")
    if len(upload.content) > MAX_UPLOAD_SIZE_BYTES:
        raise DocumentProcessingError("O arquivo excede o limite de 10 MB desta fase.")
    if extension not in {".pdf", ".docx", ".txt", ".md"}:
        raise DocumentProcessingError("Formato ainda não suportado nesta fase.")


def _parser_for_extension(extension: str) -> Callable[[bytes], tuple[str, dict[str, object]]]:
    parsers: dict[str, Callable[[bytes], tuple[str, dict[str, object]]]] = {
        ".txt": _parse_plain_text,
        ".md": _parse_plain_text,
        ".pdf": _parse_pdf,
        ".docx": _parse_docx,
    }
    return parsers[extension]


def _parse_plain_text(content: bytes) -> tuple[str, dict[str, object]]:
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return content.decode(encoding), {"encoding": encoding}
        except UnicodeDecodeError:
            continue
    raise DocumentProcessingError("Não foi possível identificar a codificação do arquivo de texto.")


def _parse_pdf(content: bytes) -> tuple[str, dict[str, object]]:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(content))
    page_texts = [(page.extract_text() or "") for page in reader.pages]
    return "\n\n".join(page_texts), {"page_count": len(reader.pages)}


def _parse_docx(content: bytes) -> tuple[str, dict[str, object]]:
    from docx import Document as DocxDocument

    document = DocxDocument(BytesIO(content))
    paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    return "\n\n".join(paragraphs), {"paragraph_count": len(paragraphs)}


def _normalize_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").split("\n")).strip()


def _word_count(text: str) -> int:
    return len([word for word in text.split() if word.strip()])
