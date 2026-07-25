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
) -> dict[str, Any]:
    payload = build_document_payload(user_id, parsed_document)
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
            .select("id, filename, content_type, size_bytes, status, text_char_count, created_at")
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
