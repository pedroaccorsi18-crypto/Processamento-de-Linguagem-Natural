from __future__ import annotations

import logging
from typing import Any

from synapse_ai.services.document_service import ParsedDocument, build_document_payload

logger = logging.getLogger(__name__)


class DocumentPersistenceError(RuntimeError):
    """Raised when a parsed document cannot be persisted."""


def save_parsed_document(
    client: Any,
    user_id: str,
    parsed_document: ParsedDocument,
    storage_bucket: str | None = None,
    storage_path: str | None = None,
) -> dict[str, Any]:
    payload = build_document_payload(user_id, parsed_document)
    if storage_bucket and storage_path:
        payload["storage_bucket"] = storage_bucket
        payload["storage_path"] = storage_path
    try:
        response = client.table("documents").insert(payload).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Document persistence failed: %s", exc.__class__.__name__)
        raise DocumentPersistenceError("Não foi possível salvar o documento.") from exc

    data = getattr(response, "data", None)
    if isinstance(data, list) and data:
        first_record = data[0]
        if isinstance(first_record, dict):
            return first_record
    if isinstance(data, dict):
        return data
    return payload


def list_user_documents(client: Any, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    try:
        response = (
            client.table("documents")
            .select(
                "id, user_id, filename, content_type, size_bytes, status, text_char_count, "
                "storage_bucket, storage_path, metadata, created_at"
            )
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Document listing failed: %s", exc.__class__.__name__)
        return []

    data = getattr(response, "data", None)
    return data if isinstance(data, list) else []


def get_user_document(client: Any, user_id: str, document_id: str) -> dict[str, Any] | None:
    """Return one document only when it belongs to the authenticated user."""
    try:
        response = (
            client.table("documents")
            .select(
                "id, user_id, filename, content_type, size_bytes, status, text_char_count, "
                "storage_bucket, storage_path, metadata, created_at"
            )
            .eq("id", document_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Document lookup failed: %s", exc.__class__.__name__)
        return None

    data = getattr(response, "data", None)
    return data if isinstance(data, dict) else None


def update_document_storage_location(
    client: Any,
    user_id: str,
    document_id: str,
    storage_bucket: str,
    storage_path: str,
) -> None:
    try:
        client.table("documents").update(
            {
                "storage_bucket": storage_bucket,
                "storage_path": storage_path,
            }
        ).eq("id", document_id).eq("user_id", user_id).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Document storage location update failed: %s", exc.__class__.__name__)
        raise DocumentPersistenceError(
            "O documento foi salvo, mas não foi possível registrar o arquivo original."
        ) from exc


def list_user_documents_for_processing(
    client: Any,
    user_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    try:
        response = (
            client.table("documents")
            .select(
                "id, user_id, filename, status, extracted_text, text_char_count, "
                "metadata, created_at"
            )
            .eq("user_id", user_id)
            .not_.is_("extracted_text", "null")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Processable document listing failed: %s", exc.__class__.__name__)
        return []

    data = getattr(response, "data", None)
    return data if isinstance(data, list) else []
