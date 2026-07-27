from __future__ import annotations

import json
import secrets
import time
from base64 import urlsafe_b64encode
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

GOOGLE_OAUTH_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
OAUTH_PENDING_AUTHORIZATION_TTL_SECONDS = 600


class GoogleOAuthError(RuntimeError):
    """Raised when Google OAuth cannot complete safely."""


@dataclass(frozen=True)
class GoogleOAuthTokens:
    access_token: str
    token_type: str
    expires_in: int | None = None
    refresh_token: str = ""
    scope: str = ""


@dataclass(frozen=True)
class GoogleOAuthPendingAuthorization:
    state: str
    code_verifier: str
    user_id: str = ""
    user_email: str = ""
    access_token: str = ""
    refresh_token: str = ""


_PENDING_AUTHORIZATIONS: dict[str, tuple[GoogleOAuthPendingAuthorization, float]] = {}


def generate_oauth_state() -> str:
    return secrets.token_urlsafe(32)


def generate_pkce_code_verifier() -> str:
    return secrets.token_urlsafe(64)


def build_pkce_code_challenge(code_verifier: str) -> str:
    if not code_verifier.strip():
        raise GoogleOAuthError("Não foi possível preparar a conexão com o Google Drive.")

    digest = sha256(code_verifier.encode("ascii")).digest()
    return urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def store_google_oauth_pending_authorization(
    state: str,
    code_verifier: str,
    *,
    user_id: str = "",
    user_email: str = "",
    access_token: str = "",
    refresh_token: str = "",
    now: float | None = None,
) -> None:
    if not state.strip() or not code_verifier.strip():
        raise GoogleOAuthError("Não foi possível preparar a conexão com o Google Drive.")

    current_time = time.monotonic() if now is None else now
    _cleanup_expired_pending_authorizations(current_time)
    _PENDING_AUTHORIZATIONS[state] = (
        GoogleOAuthPendingAuthorization(
            state=state,
            code_verifier=code_verifier,
            user_id=user_id,
            user_email=user_email,
            access_token=access_token,
            refresh_token=refresh_token,
        ),
        current_time,
    )


def consume_google_oauth_pending_authorization(
    state: str,
    *,
    now: float | None = None,
) -> GoogleOAuthPendingAuthorization | None:
    if not state.strip():
        return None

    current_time = time.monotonic() if now is None else now
    _cleanup_expired_pending_authorizations(current_time)
    pending = _PENDING_AUTHORIZATIONS.pop(state, None)
    if pending is None:
        return None
    pending_authorization, _created_at = pending
    return pending_authorization


def build_google_oauth_authorization_url(
    client_id: str,
    redirect_uri: str,
    state: str,
    *,
    scope: str = GOOGLE_DRIVE_READONLY_SCOPE,
    code_challenge: str = "",
) -> str:
    if not client_id.strip() or not redirect_uri.strip() or not state.strip():
        raise GoogleOAuthError("Configuração OAuth do Google Drive incompleta.")

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    if code_challenge.strip():
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"
    return f"{GOOGLE_OAUTH_AUTH_URL}?{urlencode(params)}"


def exchange_google_oauth_code(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
    *,
    code_verifier: str = "",
    opener: Callable[[Request], Any] = urlopen,
) -> GoogleOAuthTokens:
    if not all(value.strip() for value in (client_id, redirect_uri, code)):
        raise GoogleOAuthError("Não foi possível concluir a conexão com o Google Drive.")
    if not client_secret.strip() and not code_verifier.strip():
        raise GoogleOAuthError("Não foi possível concluir a conexão com o Google Drive.")

    payload_params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code": code,
        "grant_type": "authorization_code",
    }
    if client_secret.strip():
        payload_params["client_secret"] = client_secret
    if code_verifier.strip():
        payload_params["code_verifier"] = code_verifier
    payload = urlencode(payload_params).encode("utf-8")
    request = Request(
        GOOGLE_OAUTH_TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        response_payload = _read_json(request, opener)
    except GoogleOAuthError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise GoogleOAuthError("Não foi possível obter autorização do Google Drive.") from exc

    return _parse_token_response(response_payload)


def refresh_google_oauth_access_token(
    client_id: str,
    client_secret: str,
    refresh_token: str,
    *,
    opener: Callable[[Request], Any] = urlopen,
) -> GoogleOAuthTokens:
    if not all(value.strip() for value in (client_id, refresh_token)):
        raise GoogleOAuthError("Não foi possível renovar a conexão com o Google Drive.")

    payload_params = {
        "client_id": client_id,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    if client_secret.strip():
        payload_params["client_secret"] = client_secret
    payload = urlencode(payload_params).encode("utf-8")
    request = Request(
        GOOGLE_OAUTH_TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        response_payload = _read_json(request, opener)
    except GoogleOAuthError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise GoogleOAuthError("Não foi possível renovar a conexão com o Google Drive.") from exc

    return _parse_token_response(response_payload, fallback_refresh_token=refresh_token)


def _read_json(request: Request, opener: Callable[[Request], Any]) -> dict[str, Any]:
    try:
        with opener(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise GoogleOAuthError(_google_oauth_http_error_message(exc)) from exc
    if not isinstance(payload, dict):
        raise GoogleOAuthError("O Google retornou uma resposta OAuth inesperada.")
    return payload


def _google_oauth_http_error_message(exc: HTTPError) -> str:
    try:
        payload = json.loads(exc.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return "O Google recusou a autorização do Drive."

    error = str(payload.get("error", "") or "")
    description = str(payload.get("error_description", "") or "")
    if error and description:
        return f"O Google recusou a autorização do Drive: {error} - {description}"
    if error:
        return f"O Google recusou a autorização do Drive: {error}"
    return "O Google recusou a autorização do Drive."


def _parse_token_response(
    payload: dict[str, Any],
    *,
    fallback_refresh_token: str = "",
) -> GoogleOAuthTokens:
    access_token = str(payload.get("access_token", "") or "")
    token_type = str(payload.get("token_type", "") or "")
    if not access_token:
        raise GoogleOAuthError("O Google não retornou token de acesso.")

    raw_expires_in = payload.get("expires_in")
    expires_in = raw_expires_in if isinstance(raw_expires_in, int) else None
    return GoogleOAuthTokens(
        access_token=access_token,
        token_type=token_type,
        expires_in=expires_in,
        refresh_token=str(payload.get("refresh_token", "") or fallback_refresh_token),
        scope=str(payload.get("scope", "") or ""),
    )


def _cleanup_expired_pending_authorizations(now: float) -> None:
    expired_states = [
        state
        for state, (_pending_authorization, created_at) in _PENDING_AUTHORIZATIONS.items()
        if now - created_at > OAUTH_PENDING_AUTHORIZATION_TTL_SECONDS
    ]
    for state in expired_states:
        _PENDING_AUTHORIZATIONS.pop(state, None)
