from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class DocumentStatus(StrEnum):
    PLANNED = "planned"
    RECEIVED = "received"
    EXTRACTED = "extracted"
    READY_FOR_PROCESSING = "ready_for_processing"
    FAILED = "failed"


@dataclass(frozen=True)
class Document:
    id: str
    user_id: str
    filename: str
    content_type: str | None
    size_bytes: int | None
    text_char_count: int
    metadata: dict[str, Any]
    status: DocumentStatus
    created_at: datetime
