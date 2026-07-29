"""Read-only Microsoft Graph client for Teams channels and SharePoint files."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from synapse_ai.services.microsoft_connection_service import MicrosoftGraphCredentials

MICROSOFT_GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
logger = logging.getLogger(__name__)


class MicrosoftGraphConnectorError(RuntimeError):
    """Raised when Microsoft Graph content cannot be read by the delegated user token."""


@dataclass(frozen=True)
class MicrosoftTeam:
    id: str
    name: str
    description: str = ""


@dataclass(frozen=True)
class MicrosoftChannel:
    id: str
    name: str
    description: str = ""


@dataclass(frozen=True)
class SharePointSite:
    id: str
    name: str
    web_url: str = ""


@dataclass(frozen=True)
class SharePointDrive:
    id: str
    name: str
    web_url: str = ""


@dataclass(frozen=True)
class SharePointFile:
    id: str
    name: str
    mime_type: str
    size_bytes: int | None = None
    web_url: str = ""
    is_folder: bool = False


@dataclass(frozen=True)
class DownloadedMicrosoftContent:
    filename: str
    content_type: str
    content: bytes


def list_microsoft_teams(
    credentials: MicrosoftGraphCredentials,
    *,
    opener: Callable[[Request], Any] = urlopen,
) -> list[MicrosoftTeam]:
    payload = _request_json("/me/joinedTeams", credentials, opener)
    values = _value_list(payload, "equipes")
    return [
        MicrosoftTeam(
            id=str(item.get("id") or ""),
            name=str(item.get("displayName") or "Equipe sem nome"),
            description=str(item.get("description") or ""),
        )
        for item in values
        if str(item.get("id") or "")
    ]


def list_microsoft_team_channels(
    credentials: MicrosoftGraphCredentials,
    team_id: str,
    *,
    opener: Callable[[Request], Any] = urlopen,
) -> list[MicrosoftChannel]:
    payload = _request_json(f"/teams/{_segment(team_id)}/channels", credentials, opener)
    values = _value_list(payload, "canais")
    return [
        MicrosoftChannel(
            id=str(item.get("id") or ""),
            name=str(item.get("displayName") or "Canal sem nome"),
            description=str(item.get("description") or ""),
        )
        for item in values
        if str(item.get("id") or "")
    ]


def download_microsoft_team_channel(
    credentials: MicrosoftGraphCredentials,
    team_id: str,
    channel: MicrosoftChannel,
    *,
    opener: Callable[[Request], Any] = urlopen,
    message_limit: int = 100,
) -> DownloadedMicrosoftContent:
    """Package an authorized Teams channel history as a JSON document for ingestion."""
    payload = _request_json(
        f"/teams/{_segment(team_id)}/channels/{_segment(channel.id)}/messages"
        f"?{urlencode({'$top': str(message_limit)})}",
        credentials,
        opener,
    )
    messages = _value_list(payload, "mensagens")
    document = {
        "source": "microsoft_teams",
        "team_id": team_id,
        "channel": {"id": channel.id, "name": channel.name, "description": channel.description},
        "messages": messages,
    }
    return DownloadedMicrosoftContent(
        filename=f"teams-{_safe_filename_fragment(channel.name)}.json",
        content_type="application/json",
        content=json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8"),
    )


def list_sharepoint_sites(
    credentials: MicrosoftGraphCredentials,
    *,
    opener: Callable[[Request], Any] = urlopen,
) -> list[SharePointSite]:
    payload = _request_json(
        f"/sites?{urlencode({'search': '*', '$top': '50'})}", credentials, opener
    )
    values = _value_list(payload, "sites")
    return [
        SharePointSite(
            id=str(item.get("id") or ""),
            name=str(item.get("displayName") or item.get("name") or "Site sem nome"),
            web_url=str(item.get("webUrl") or ""),
        )
        for item in values
        if str(item.get("id") or "")
    ]


def list_sharepoint_drives(
    credentials: MicrosoftGraphCredentials,
    site_id: str,
    *,
    opener: Callable[[Request], Any] = urlopen,
) -> list[SharePointDrive]:
    payload = _request_json(f"/sites/{_segment(site_id)}/drives", credentials, opener)
    values = _value_list(payload, "bibliotecas")
    return [
        SharePointDrive(
            id=str(item.get("id") or ""),
            name=str(item.get("name") or "Biblioteca sem nome"),
            web_url=str(item.get("webUrl") or ""),
        )
        for item in values
        if str(item.get("id") or "")
    ]


def list_sharepoint_drive_files(
    credentials: MicrosoftGraphCredentials,
    drive_id: str,
    *,
    folder_id: str = "",
    opener: Callable[[Request], Any] = urlopen,
) -> list[SharePointFile]:
    """List only one library level so imports remain predictable and bounded."""
    resource = (
        f"/drives/{_segment(drive_id)}/items/{_segment(folder_id)}/children"
        if folder_id.strip()
        else f"/drives/{_segment(drive_id)}/root/children"
    )
    payload = _request_json(
        f"{resource}?{urlencode({'$select': 'id,name,size,webUrl,file,folder'})}",
        credentials,
        opener,
    )
    values = _value_list(payload, "arquivos")
    return [_sharepoint_file_from_payload(item) for item in values if isinstance(item, dict)]


def download_sharepoint_file(
    credentials: MicrosoftGraphCredentials,
    drive_id: str,
    file: SharePointFile,
    *,
    opener: Callable[[Request], Any] = urlopen,
) -> DownloadedMicrosoftContent:
    if file.is_folder:
        raise MicrosoftGraphConnectorError("Pastas devem ser abertas antes de importar arquivos.")
    request = Request(
        f"{MICROSOFT_GRAPH_BASE_URL}/drives/{_segment(drive_id)}/items/{_segment(file.id)}/content",
        headers={"Authorization": f"Bearer {credentials.access_token}"},
    )
    try:
        with opener(request) as response:
            content = response.read()
    except HTTPError as exc:
        logger.warning("SharePoint download failed: %s", exc.code)
        raise MicrosoftGraphConnectorError(
            f"Não foi possível baixar o arquivo {file.name}."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.warning("SharePoint download failed: %s", exc.__class__.__name__)
        raise MicrosoftGraphConnectorError(
            f"Não foi possível baixar o arquivo {file.name}."
        ) from exc
    return DownloadedMicrosoftContent(
        filename=file.name,
        content_type=file.mime_type or "application/octet-stream",
        content=content,
    )


def _request_json(
    resource: str,
    credentials: MicrosoftGraphCredentials,
    opener: Callable[[Request], Any],
) -> dict[str, Any]:
    request = Request(
        f"{MICROSOFT_GRAPH_BASE_URL}{resource}",
        headers={"Authorization": f"Bearer {credentials.access_token}"},
    )
    try:
        with opener(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        logger.warning("Microsoft Graph request failed: %s", exc.code)
        if exc.code in {401, 403}:
            raise MicrosoftGraphConnectorError(
                "A conta Microsoft não tem permissão para ler este conteúdo. "
                "Peça aprovação ao administrador."
            ) from exc
        raise MicrosoftGraphConnectorError(
            "Não foi possível ler o conteúdo autorizado da Microsoft."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.warning("Microsoft Graph request failed: %s", exc.__class__.__name__)
        raise MicrosoftGraphConnectorError(
            "Não foi possível ler o conteúdo autorizado da Microsoft."
        ) from exc
    if not isinstance(payload, dict):
        raise MicrosoftGraphConnectorError("A Microsoft retornou uma resposta inesperada.")
    return payload


def _value_list(payload: dict[str, Any], label: str) -> list[dict[str, Any]]:
    value = payload.get("value")
    if not isinstance(value, list):
        raise MicrosoftGraphConnectorError(
            f"A Microsoft retornou {label} em um formato inesperado."
        )
    return [item for item in value if isinstance(item, dict)]


def _sharepoint_file_from_payload(payload: dict[str, Any]) -> SharePointFile:
    file_metadata = payload.get("file")
    mime_type = "application/octet-stream"
    if isinstance(file_metadata, dict):
        mime_type = str(file_metadata.get("mimeType") or mime_type)
    size = payload.get("size")
    return SharePointFile(
        id=str(payload.get("id") or ""),
        name=str(payload.get("name") or "Arquivo sem nome"),
        mime_type=mime_type,
        size_bytes=size if isinstance(size, int) else None,
        web_url=str(payload.get("webUrl") or ""),
        is_folder=isinstance(payload.get("folder"), dict),
    )


def _segment(value: str) -> str:
    return quote(value.strip(), safe="")


def _safe_filename_fragment(value: str) -> str:
    cleaned = "".join(
        character if character.isalnum() or character in {"-", "_"} else "-" for character in value
    )
    return cleaned.strip("-") or "canal"
