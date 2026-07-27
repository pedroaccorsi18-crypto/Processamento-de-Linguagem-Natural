from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse
from urllib.request import Request

import pytest

from synapse_ai.services.google_drive_service import (
    GOOGLE_DOC_MIME_TYPE,
    GOOGLE_SHEET_MIME_TYPE,
    GoogleDriveConnectorError,
    GoogleDriveCredentials,
    GoogleDriveFile,
    download_google_drive_file,
    extract_google_drive_folder_id,
    list_google_drive_folder_files,
)


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


class FakeOpener:
    def __init__(self, responses: dict[str, bytes] | None = None) -> None:
        self.responses = responses or {}
        self.urls: list[str] = []
        self.requests: list[str | Request] = []

    def __call__(self, request: str | Request) -> FakeResponse:
        self.requests.append(request)
        url = request.full_url if isinstance(request, Request) else request
        self.urls.append(url)
        for marker, payload in self.responses.items():
            if marker in url:
                return FakeResponse(payload)
        raise RuntimeError("unexpected-url")


def test_extract_google_drive_folder_id_from_folder_url() -> None:
    folder_id = extract_google_drive_folder_id(
        "https://drive.google.com/drive/folders/folder-123?usp=sharing"
    )

    assert folder_id == "folder-123"


def test_extract_google_drive_folder_id_from_raw_id() -> None:
    assert extract_google_drive_folder_id("folder-123") == "folder-123"


def test_extract_google_drive_folder_id_rejects_invalid_url() -> None:
    with pytest.raises(GoogleDriveConnectorError):
        extract_google_drive_folder_id("https://drive.google.com/drive/my-drive")


def test_list_google_drive_folder_files_calls_drive_api() -> None:
    opener = FakeOpener(
        {
            "/files?": json.dumps(
                {
                    "files": [
                        {
                            "id": "file-1",
                            "name": "Ata.pdf",
                            "mimeType": "application/pdf",
                            "size": "123",
                            "webViewLink": "https://drive.google.com/file/d/file-1/view",
                        }
                    ]
                }
            ).encode()
        }
    )

    files = list_google_drive_folder_files("api-key", "folder-123", opener=opener)

    assert files == [
        GoogleDriveFile(
            id="file-1",
            name="Ata.pdf",
            mime_type="application/pdf",
            size_bytes=123,
            web_view_link="https://drive.google.com/file/d/file-1/view",
        )
    ]
    parsed_url = urlparse(opener.urls[0])
    params = parse_qs(parsed_url.query)
    assert params["key"] == ["api-key"]
    assert params["q"] == ["'folder-123' in parents and trashed = false"]
    assert params["supportsAllDrives"] == ["true"]


def test_download_google_drive_blob_file_uses_alt_media() -> None:
    opener = FakeOpener({"/files/file-1?": b"pdf-content"})

    downloaded = download_google_drive_file(
        "api-key",
        GoogleDriveFile("file-1", "Ata.pdf", "application/pdf"),
        opener=opener,
    )

    assert downloaded.filename == "Ata.pdf"
    assert downloaded.content_type == "application/pdf"
    assert downloaded.content == b"pdf-content"
    assert parse_qs(urlparse(opener.urls[0]).query)["alt"] == ["media"]


def test_download_google_workspace_document_uses_export_endpoint() -> None:
    opener = FakeOpener({"/export?": b"docx-content"})

    downloaded = download_google_drive_file(
        "api-key",
        GoogleDriveFile("file-2", "Ata", GOOGLE_DOC_MIME_TYPE),
        opener=opener,
    )

    assert downloaded.filename == "Ata.docx"
    assert (
        downloaded.content_type
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert downloaded.content == b"docx-content"
    assert "/files/file-2/export?" in opener.urls[0]


def test_download_google_workspace_sheet_uses_xlsx_export() -> None:
    opener = FakeOpener({"/export?": b"xlsx-content"})

    downloaded = download_google_drive_file(
        "api-key",
        GoogleDriveFile("file-3", "Tickets", GOOGLE_SHEET_MIME_TYPE),
        opener=opener,
    )

    assert downloaded.filename == "Tickets.xlsx"
    assert (
        downloaded.content_type
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def test_list_google_drive_folder_files_can_use_oauth_bearer_token() -> None:
    opener = FakeOpener({"/files?": json.dumps({"files": []}).encode()})

    files = list_google_drive_folder_files(
        GoogleDriveCredentials(access_token="access-token"),
        "folder-123",
        opener=opener,
    )

    assert files == []
    request = opener.requests[0]
    assert isinstance(request, Request)
    assert request.headers["Authorization"] == "Bearer access-token"
    assert "key=" not in request.full_url


def test_list_google_drive_folder_files_requires_api_key() -> None:
    with pytest.raises(GoogleDriveConnectorError):
        list_google_drive_folder_files("", "folder-123", opener=FakeOpener())


def test_download_google_drive_file_wraps_errors() -> None:
    with pytest.raises(GoogleDriveConnectorError) as exc_info:
        download_google_drive_file(
            "api-key",
            GoogleDriveFile("file-1", "Ata.pdf", "application/pdf"),
            opener=FakeOpener(),
        )

    assert str(exc_info.value) == "Não foi possível baixar o arquivo Ata.pdf."
