"""OAuth 2.0 helpers for a least-privilege Slack workspace connection."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SLACK_OAUTH_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
SLACK_OAUTH_TOKEN_URL = "https://slack.com/api/oauth.v2.access"
SLACK_READ_SCOPES = (
    "channels:read",
    "channels:history",
    "groups:read",
    "groups:history",
    "files:read",
)


class SlackOAuthError(RuntimeError):
    """Raised when Slack does not authorize or renew a workspace connection."""


@dataclass(frozen=True)
class SlackOAuthTokens:
    access_token: str
    token_type: str
    scope: str = ""
    refresh_token: str = ""
    expires_in: int | None = None
    team_id: str = ""
    team_name: str = ""


def build_slack_oauth_authorization_url(
    client_id: str,
    redirect_uri: str,
    state: str,
    *,
    scopes: Iterable[str] = SLACK_READ_SCOPES,
) -> str:
    """Build the user-consent URL without embedding any user or token data."""
    requested_scopes = ",".join(scope.strip() for scope in scopes if scope.strip())
    if (
        not client_id.strip()
        or not redirect_uri.strip()
        or not state.strip()
        or not requested_scopes
    ):
        raise SlackOAuthError("Configuração OAuth do Slack incompleta.")

    parameters = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": requested_scopes,
        "state": state,
    }
    return f"{SLACK_OAUTH_AUTHORIZE_URL}?{urlencode(parameters)}"


def exchange_slack_oauth_code(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
    *,
    opener: Callable[[Request], Any] = urlopen,
) -> SlackOAuthTokens:
    """Exchange one Slack authorization code for workspace-scoped credentials."""
    if not all(value.strip() for value in (client_id, client_secret, redirect_uri, code)):
        raise SlackOAuthError("Não foi possível concluir a conexão com o Slack.")
    return _request_slack_tokens(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        },
        opener,
    )


def refresh_slack_oauth_access_token(
    client_id: str,
    client_secret: str,
    refresh_token: str,
    *,
    opener: Callable[[Request], Any] = urlopen,
) -> SlackOAuthTokens:
    """Refresh a rotating Slack token when token rotation is enabled by the workspace."""
    if not all(value.strip() for value in (client_id, client_secret, refresh_token)):
        raise SlackOAuthError("Não foi possível renovar a conexão com o Slack.")
    return _request_slack_tokens(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        opener,
    )


def _request_slack_tokens(
    parameters: dict[str, str],
    opener: Callable[[Request], Any],
) -> SlackOAuthTokens:
    request = Request(
        SLACK_OAUTH_TOKEN_URL,
        data=urlencode(parameters).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with opener(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise SlackOAuthError(_http_error_message(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise SlackOAuthError("Não foi possível obter autorização do Slack.") from exc

    if not isinstance(payload, dict):
        raise SlackOAuthError("O Slack retornou uma resposta OAuth inesperada.")
    if payload.get("ok") is not True:
        raise SlackOAuthError(_slack_error_message(payload))

    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token.strip():
        raise SlackOAuthError("O Slack não retornou um token de acesso.")
    team = payload.get("team")
    expires_in = payload.get("expires_in")
    return SlackOAuthTokens(
        access_token=access_token,
        token_type=str(payload.get("token_type") or "Bearer"),
        scope=str(payload.get("scope") or ""),
        refresh_token=str(payload.get("refresh_token") or ""),
        expires_in=expires_in if isinstance(expires_in, int) else None,
        team_id=str(team.get("id") or "") if isinstance(team, dict) else "",
        team_name=str(team.get("name") or "") if isinstance(team, dict) else "",
    )


def _http_error_message(exc: HTTPError) -> str:
    try:
        payload = json.loads(exc.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return "O Slack recusou a autorização da área de trabalho."
    return _slack_error_message(payload if isinstance(payload, dict) else {})


def _slack_error_message(payload: dict[str, Any]) -> str:
    error = str(payload.get("error") or "")
    return f"O Slack recusou a autorização: {error}." if error else "O Slack recusou a autorização."
