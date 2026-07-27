from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from synapse_ai.services.document_service import UploadedDocument

logger = logging.getLogger(__name__)

DOCUMENT_STORAGE_BUCKET = "documents"


class DocumentStorageError(RuntimeError):
    """Raised when the original document file cannot be stored or retrieved."""


@dataclass(frozen=True)
class StoredDocumentFile:
    bucket: str
    path: str


def build_document_storage_path(user_id: str, document_id: str, filename: str) -> str:
    safe_filename = _safe_filename(filename)
    return f"{user_id}/{document_id}/{safe_filename}"


def upload_original_document(
    client: Any,
    user_id: str,
    document_id: str,
    upload: UploadedDocument,
    bucket: str = DOCUMENT_STORAGE_BUCKET,
) -> StoredDocumentFile:
    path = build_document_storage_path(user_id, document_id, upload.filename)
    try:
        client.storage.from_(bucket).upload(
            path,
            upload.content,
            {
                "content-type": upload.content_type,
                "cache-control": "3600",
                "upsert": "true",
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Original document upload failed: %s", exc.__class__.__name__)
        raise DocumentStorageError("Não foi possível armazenar o arquivo original.") from exc

    return StoredDocumentFile(bucket=bucket, path=path)


def download_original_document(
    client: Any,
    bucket: str,
    path: str,
) -> bytes:
    try:
        content = client.storage.from_(bucket).download(path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Original document download failed: %s", exc.__class__.__name__)
        raise DocumentStorageError("Não foi possível baixar o arquivo original.") from exc

    if not isinstance(content, bytes):
        raise DocumentStorageError("O arquivo original retornou em formato inesperado.")
    return content


def _safe_filename(filename: str) -> str:
    clean_filename = filename.strip().replace("\\", "/").split("/")[-1]
    safe_filename = re.sub(r"[^A-Za-z0-9._-]+", "_", clean_filename).strip("._")
    return safe_filename or "documento"
