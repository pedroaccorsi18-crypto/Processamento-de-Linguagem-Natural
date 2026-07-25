from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class AnalysisStatus(StrEnum):
    PLANNED = "planned"
    DRAFT = "draft"
    READY = "ready"


@dataclass(frozen=True)
class Analysis:
    id: str
    user_id: str
    document_id: str
    title: str
    status: AnalysisStatus
    created_at: datetime
