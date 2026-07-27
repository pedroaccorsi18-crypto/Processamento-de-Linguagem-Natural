from __future__ import annotations

from typing import Any

import pytest

from synapse_ai.services.audio_transcription_service import (
    AudioTranscriptionError,
    transcribe_audio,
)
from synapse_ai.services.document_service import UploadedDocument


class FakeTranscriptions:
    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.response = response if response is not None else {"text": "Texto transcrito."}
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class FakeAudio:
    def __init__(self, transcriptions: FakeTranscriptions) -> None:
        self.transcriptions = transcriptions


class FakeOpenAIClient:
    def __init__(self, transcriptions: FakeTranscriptions) -> None:
        self.audio = FakeAudio(transcriptions)


def test_transcribe_audio_calls_openai_transcription_api() -> None:
    transcriptions = FakeTranscriptions({"text": "Reunião transcrita."})
    client = FakeOpenAIClient(transcriptions)

    text = transcribe_audio(client, _uploaded_audio(), "gpt-4o-mini-transcribe")

    assert text == "Reunião transcrita."
    assert len(transcriptions.calls) == 1
    call = transcriptions.calls[0]
    assert call["model"] == "gpt-4o-mini-transcribe"
    assert call["response_format"] == "json"
    assert call["file"][0] == "reuniao.mp3"
    assert call["file"][2] == "audio/mpeg"


def test_transcribe_audio_extracts_text_from_object_response() -> None:
    class Response:
        text = "Texto em objeto."

    text = transcribe_audio(
        FakeOpenAIClient(FakeTranscriptions(Response())),
        _uploaded_audio(),
        "whisper-1",
    )

    assert text == "Texto em objeto."


def test_transcribe_audio_wraps_api_errors() -> None:
    client = FakeOpenAIClient(FakeTranscriptions(error=RuntimeError("boom")))

    with pytest.raises(AudioTranscriptionError) as exc_info:
        transcribe_audio(client, _uploaded_audio(), "gpt-4o-mini-transcribe")

    assert str(exc_info.value) == "Não foi possível transcrever o áudio enviado."


def test_transcribe_audio_rejects_empty_transcription() -> None:
    client = FakeOpenAIClient(FakeTranscriptions({"text": "   "}))

    with pytest.raises(AudioTranscriptionError) as exc_info:
        transcribe_audio(client, _uploaded_audio(), "gpt-4o-mini-transcribe")

    assert str(exc_info.value) == "A transcrição do áudio não retornou texto."


def _uploaded_audio() -> UploadedDocument:
    return UploadedDocument(
        filename="reuniao.mp3",
        content_type="audio/mpeg",
        content=b"audio-content",
    )
