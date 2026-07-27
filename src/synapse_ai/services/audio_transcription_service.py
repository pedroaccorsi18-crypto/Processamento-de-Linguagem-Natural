from __future__ import annotations

import logging
from io import BytesIO
from typing import Any

from synapse_ai.services.document_service import UploadedDocument

logger = logging.getLogger(__name__)


class AudioTranscriptionError(RuntimeError):
    """Raised when an uploaded audio file cannot be transcribed."""


def transcribe_audio(
    openai_client: Any,
    uploaded_document: UploadedDocument,
    model: str,
) -> str:
    try:
        response = openai_client.audio.transcriptions.create(
            model=model,
            file=(
                uploaded_document.filename,
                BytesIO(uploaded_document.content),
                uploaded_document.content_type,
            ),
            response_format="json",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Audio transcription failed: %s", exc.__class__.__name__)
        raise AudioTranscriptionError("Não foi possível transcrever o áudio enviado.") from exc

    transcription_text = _extract_transcription_text(response)
    if not transcription_text.strip():
        raise AudioTranscriptionError("A transcrição do áudio não retornou texto.")
    return transcription_text


def _extract_transcription_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        return str(response.get("text", "") or "")
    return str(getattr(response, "text", "") or "")
