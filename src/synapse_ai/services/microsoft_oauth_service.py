"""Microsoft identity platform OAuth helpers for Teams and SharePoint."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

MICROSOFT_LOGIN_BASE_URL = "https://login.microsoftonline.com"
MICROSOFT_GRAPH_READ_SCOPES = (
    "offline_access",
    "User.Read",
    "Files.Read.All",
    "Sites.Read.All",
    "Team.ReadBasic.All",
    "ChannelMessage.Read.All",
)


class MicrosoftOAuthError(RuntimeError):
    """Raised when Microsoft does not authorize or refresh a corporate connection."""


@dataclass(frozen=True)
class MicrosoftOAuthTokens:
    access_token: str
    token_type: str
    refresh_token: str = ""
    expires_in: int | None = None
    scope: str = ""


def build_microsoft_oauth_authorization_url(
    tenant_id: str,
    client_id: str,
    redirect_uri: str,
    state: str,
    *,
    scopes: Iterable[str] = MICROSOFT_GRAPH_READ_SCOPES,
) -> str:
    """Create one delegated OAuth authorization URL for the Microsoft 365 connection."""
    normalized_tenant = tenant_id.strip() or "organizations"
    requested_scopes = " ".join(scope.strip() for scope in scopes if scope.strip())
    if (
        not client_id.strip()
        or not redirect_uri.strip()
        or not state.strip()
        or not requested_scopes
    ):
        raise MicrosoftOAuthError("Configuração OAuth da Microsoft incompleta.")
    parameters = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "response_mode": "query",
        "scope": requested_scopes,
        "state": state,
        "prompt": "select_account",
    }
    return f"{_endpoint(normalized_tenant, 'authorize')}?{urlencode(parameters)}"


def exchange_microsoft_oauth_code(
    tenant_id: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
    *,
    opener: Callable[[Request], Any] = urlopen,
) -> MicrosoftOAuthTokens:
    """Exchange the browser authorization code on the backend only."""
    if not all(value.strip() for value in (client_id, client_secret, redirect_uri, code)):
        raise MicrosoftOAuthError("Não foi possível concluir a conexão Microsoft 365.")
    return _request_tokens(
        tenant_id,
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        opener,
    )


def refresh_microsoft_oauth_access_token(
    tenant_id: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    *,
    opener: Callable[[Request], Any] = urlopen,
) -> MicrosoftOAuthTokens:
    """Refresh a Microsoft delegated token without returning a secret to the browser."""
    if not all(value.strip() for value in (client_id, client_secret, refresh_token)):
        raise MicrosoftOAuthError("Não foi possível renovar a conexão Microsoft 365.")
    return _request_tokens(
        tenant_id,
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
            "scope": " ".join(MICROSOFT_GRAPH_READ_SCOPES),
        },
        opener,
    )


def _request_tokens(
    tenant_id: str,
    parameters: dict[str, str],
    opener: Callable[[Request], Any],
) -> MicrosoftOAuthTokens:
    request = Request(
        _endpoint(tenant_id.strip() or "organizations", "token"),
        data=urlencode(parameters).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with opener(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise MicrosoftOAuthError(_http_error_message(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise MicrosoftOAuthError("Não foi possível obter autorização Microsoft 365.") from exc

    if not isinstance(payload, dict):
        raise MicrosoftOAuthError("A Microsoft retornou uma resposta OAuth inesperada.")
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token.strip():
        raise MicrosoftOAuthError(_payload_error_message(payload))
    expires_in = payload.get("expires_in")
    return MicrosoftOAuthTokens(
        access_token=access_token,
        token_type=str(payload.get("token_type") or "Bearer"),
        refresh_token=str(payload.get("refresh_token") or ""),
        expires_in=expires_in if isinstance(expires_in, int) else None,
        scope=str(payload.get("scope") or ""),
    )


def _endpoint(tenant_id: str, action: str) -> str:
    return f"{MICROSOFT_LOGIN_BASE_URL}/{quote(tenant_id, safe='')}/oauth2/v2.0/{action}"


def _http_error_message(exc: HTTPError) -> str:
    try:
        payload = json.loads(exc.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return "A Microsoft recusou a autorização corporativa."
    return _payload_error_message(payload if isinstance(payload, dict) else {})


def _payload_error_message(payload: dict[str, Any]) -> str:
    error = str(payload.get("error") or "")
    description = str(payload.get("error_description") or "")
    if error == "consent_required":
        return "A organização Microsoft precisa conceder as permissões solicitadas ao Synapse."
    if error and description:
        return f"A Microsoft recusou a autorização: {error} - {description}"
    return (
        f"A Microsoft recusou a autorização: {error}"
        if error
        else "A Microsoft recusou a autorização."
    )
