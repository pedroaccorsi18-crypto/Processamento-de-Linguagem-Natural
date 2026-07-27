from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, quote, urlencode, urlparse
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

GOOGLE_DRIVE_API_BASE_URL = "https://www.googleapis.com/drive/v3"
GOOGLE_DOC_MIME_TYPE = "application/vnd.google-apps.document"
GOOGLE_SHEET_MIME_TYPE = "application/vnd.google-apps.spreadsheet"
GOOGLE_SLIDE_MIME_TYPE = "application/vnd.google-apps.presentation"

EXPORT_TARGETS = {
    GOOGLE_DOC_MIME_TYPE: (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".docx",
    ),
    GOOGLE_SHEET_MIME_TYPE: (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
    GOOGLE_SLIDE_MIME_TYPE: (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pptx",
    ),
}


class GoogleDriveConnectorError(RuntimeError):
    """Raised when Google Drive content cannot be listed or downloaded."""


@dataclass(frozen=True)
class GoogleDriveFile:
    id: str
    name: str
    mime_type: str
    size_bytes: int | None = None
    web_view_link: str = ""


@dataclass(frozen=True)
class DownloadedGoogleDriveFile:
    filename: str
    content_type: str
    content: bytes
    source_file: GoogleDriveFile


@dataclass(frozen=True)
class GoogleDriveCredentials:
    api_key: str = ""
    access_token: str = ""


def extract_google_drive_folder_id(value: str) -> str:
    clean_value = value.strip()
    if not clean_value:
        raise GoogleDriveConnectorError("Informe o link ou ID da pasta do Google Drive.")

    parsed_url = urlparse(clean_value)
    if parsed_url.netloc:
        folder_match = re.search(r"/folders/([^/?#]+)", parsed_url.path)
        if folder_match:
            return folder_match.group(1)
        query_id = parse_qs(parsed_url.query).get("id", [""])[0]
        if query_id:
            return query_id
        raise GoogleDriveConnectorError("Não foi possível identificar a pasta do Google Drive.")

    return clean_value


def list_google_drive_folder_files(
    credentials: GoogleDriveCredentials | str,
    folder_id: str,
    *,
    opener: Callable[[str | Request], Any] = urlopen,
    page_size: int = 50,
) -> list[GoogleDriveFile]:
    google_credentials = _normalize_credentials(credentials)
    _validate_credentials(google_credentials)

    query = f"'{folder_id}' in parents and trashed = false"
    params = {
        "q": query,
        "fields": "files(id,name,mimeType,size,webViewLink)",
        "pageSize": str(page_size),
        "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true",
    }
    if google_credentials.api_key:
        params["key"] = google_credentials.api_key
    try:
        payload = _read_json(
            f"{GOOGLE_DRIVE_API_BASE_URL}/files?{urlencode(params)}",
            opener,
            google_credentials,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Google Drive listing failed: %s", exc.__class__.__name__)
        raise GoogleDriveConnectorError(
            "Não foi possível listar arquivos do Google Drive."
        ) from exc

    raw_files = payload.get("files", [])
    if not isinstance(raw_files, list):
        raise GoogleDriveConnectorError("O Google Drive retornou uma resposta inesperada.")

    return [_build_google_drive_file(file) for file in raw_files if isinstance(file, dict)]


def download_google_drive_file(
    credentials: GoogleDriveCredentials | str,
    drive_file: GoogleDriveFile,
    *,
    opener: Callable[[str | Request], Any] = urlopen,
) -> DownloadedGoogleDriveFile:
    google_credentials = _normalize_credentials(credentials)
    _validate_credentials(google_credentials)

    try:
        if drive_file.mime_type in EXPORT_TARGETS:
            content_type, extension = EXPORT_TARGETS[drive_file.mime_type]
            url = _export_url(google_credentials, drive_file.id, content_type)
            filename = _ensure_extension(drive_file.name, extension)
        else:
            content_type = drive_file.mime_type or "application/octet-stream"
            url = _download_url(google_credentials, drive_file.id)
            filename = drive_file.name
        content = _read_bytes(url, opener, google_credentials)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Google Drive download failed: %s", exc.__class__.__name__)
        raise GoogleDriveConnectorError(
            f"Não foi possível baixar o arquivo {drive_file.name}."
        ) from exc

    return DownloadedGoogleDriveFile(
        filename=filename,
        content_type=content_type,
        content=content,
        source_file=drive_file,
    )


def _build_google_drive_file(payload: dict[str, Any]) -> GoogleDriveFile:
    raw_size = payload.get("size")
    size_bytes = int(raw_size) if isinstance(raw_size, str) and raw_size.isdigit() else None
    return GoogleDriveFile(
        id=str(payload.get("id", "") or ""),
        name=str(payload.get("name", "") or "Arquivo sem nome"),
        mime_type=str(payload.get("mimeType", "") or "application/octet-stream"),
        size_bytes=size_bytes,
        web_view_link=str(payload.get("webViewLink", "") or ""),
    )


def _download_url(credentials: GoogleDriveCredentials, file_id: str) -> str:
    params = {"alt": "media", "supportsAllDrives": "true"}
    if credentials.api_key:
        params["key"] = credentials.api_key
    return f"{GOOGLE_DRIVE_API_BASE_URL}/files/{quote(file_id)}?{urlencode(params)}"


def _export_url(credentials: GoogleDriveCredentials, file_id: str, mime_type: str) -> str:
    params = {"mimeType": mime_type}
    if credentials.api_key:
        params["key"] = credentials.api_key
    return f"{GOOGLE_DRIVE_API_BASE_URL}/files/{quote(file_id)}/export?{urlencode(params)}"


def _read_json(
    url: str,
    opener: Callable[[str | Request], Any],
    credentials: GoogleDriveCredentials,
) -> dict[str, Any]:
    return json.loads(_read_bytes(url, opener, credentials).decode("utf-8"))


def _read_bytes(
    url: str,
    opener: Callable[[str | Request], Any],
    credentials: GoogleDriveCredentials,
) -> bytes:
    request: str | Request = url
    if credentials.access_token:
        request = Request(url, headers={"Authorization": f"Bearer {credentials.access_token}"})
    with opener(request) as response:
        return response.read()


def _ensure_extension(filename: str, extension: str) -> str:
    return filename if filename.lower().endswith(extension) else f"{filename}{extension}"


def _normalize_credentials(credentials: GoogleDriveCredentials | str) -> GoogleDriveCredentials:
    if isinstance(credentials, GoogleDriveCredentials):
        return credentials
    return GoogleDriveCredentials(api_key=credentials)


def _validate_credentials(credentials: GoogleDriveCredentials) -> None:
    if not credentials.api_key.strip() and not credentials.access_token.strip():
        raise GoogleDriveConnectorError(
            "Conecte uma conta Google Drive antes de importar arquivos."
        )
