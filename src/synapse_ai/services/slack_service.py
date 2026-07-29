"""Read-only Slack Web API client used to import authorized channel history."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from synapse_ai.services.slack_connection_service import SlackCredentials

SLACK_API_BASE_URL = "https://slack.com/api"
logger = logging.getLogger(__name__)


class SlackConnectorError(RuntimeError):
    """Raised when Slack content cannot be read by the authorized workspace token."""


@dataclass(frozen=True)
class SlackConversation:
    id: str
    name: str
    is_private: bool
    topic: str = ""


@dataclass(frozen=True)
class DownloadedSlackConversation:
    filename: str
    content: bytes
    conversation: SlackConversation
    message_count: int


def list_slack_conversations(
    credentials: SlackCredentials,
    *,
    opener: Callable[[Request], Any] = urlopen,
    limit: int = 100,
) -> list[SlackConversation]:
    """List only public and private channels visible to the connected Slack user."""
    payload = _request_json(
        "conversations.list",
        credentials,
        {
            "types": "public_channel,private_channel",
            "exclude_archived": "true",
            "limit": str(limit),
        },
        opener,
    )
    channels = payload.get("channels")
    if not isinstance(channels, list):
        raise SlackConnectorError("O Slack retornou canais em um formato inesperado.")
    conversations = [
        _conversation_from_payload(channel) for channel in channels if isinstance(channel, dict)
    ]
    return [conversation for conversation in conversations if conversation.id]


def download_slack_conversation(
    credentials: SlackCredentials,
    conversation: SlackConversation,
    *,
    opener: Callable[[Request], Any] = urlopen,
    message_limit: int = 100,
) -> DownloadedSlackConversation:
    """Download the visible portion of one channel as a JSON document for the common pipeline."""
    if not conversation.id.strip():
        raise SlackConnectorError("Selecione um canal válido do Slack.")
    payload = _request_json(
        "conversations.history",
        credentials,
        {"channel": conversation.id, "limit": str(message_limit)},
        opener,
    )
    messages = payload.get("messages")
    if not isinstance(messages, list):
        raise SlackConnectorError("O Slack retornou mensagens em um formato inesperado.")

    document = {
        "source": "slack",
        "channel": {
            "id": conversation.id,
            "name": conversation.name,
            "private": conversation.is_private,
            "topic": conversation.topic,
        },
        "messages": [message for message in messages if isinstance(message, dict)],
    }
    return DownloadedSlackConversation(
        filename=f"slack-{_safe_filename_fragment(conversation.name)}.json",
        content=json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8"),
        conversation=conversation,
        message_count=len(document["messages"]),
    )


def _request_json(
    method: str,
    credentials: SlackCredentials,
    parameters: dict[str, str],
    opener: Callable[[Request], Any],
) -> dict[str, Any]:
    url = f"{SLACK_API_BASE_URL}/{method}?{urlencode(parameters)}"
    request = Request(url, headers={"Authorization": f"Bearer {credentials.access_token}"})
    try:
        with opener(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        logger.warning("Slack request failed: %s", exc.code)
        raise SlackConnectorError("Não foi possível ler o conteúdo autorizado do Slack.") from exc
    except Exception as exc:  # noqa: BLE001
        logger.warning("Slack request failed: %s", exc.__class__.__name__)
        raise SlackConnectorError("Não foi possível ler o conteúdo autorizado do Slack.") from exc

    if not isinstance(payload, dict):
        raise SlackConnectorError("O Slack retornou uma resposta inesperada.")
    if payload.get("ok") is not True:
        error = str(payload.get("error") or "")
        if error in {"missing_scope", "not_authed", "token_revoked", "invalid_auth"}:
            raise SlackConnectorError(
                "A conexão do Slack não tem as permissões necessárias ou expirou. "
                "Conecte novamente."
            )
        raise SlackConnectorError("O Slack recusou a leitura deste conteúdo autorizado.")
    return payload


def _conversation_from_payload(payload: dict[str, Any]) -> SlackConversation:
    topic = payload.get("topic")
    return SlackConversation(
        id=str(payload.get("id") or ""),
        name=str(payload.get("name") or "Canal sem nome"),
        is_private=bool(payload.get("is_private")),
        topic=str(topic.get("value") or "") if isinstance(topic, dict) else "",
    )


def _safe_filename_fragment(value: str) -> str:
    cleaned = "".join(
        character if character.isalnum() or character in {"-", "_"} else "-" for character in value
    )
    return cleaned.strip("-") or "canal"
