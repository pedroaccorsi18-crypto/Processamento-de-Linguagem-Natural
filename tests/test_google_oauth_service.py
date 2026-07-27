from __future__ import annotations

import json
from typing import cast
from urllib.parse import parse_qs, urlparse
from urllib.request import Request

import pytest

from synapse_ai.services.google_oauth_service import (
    GOOGLE_DRIVE_READONLY_SCOPE,
    GOOGLE_OAUTH_AUTH_URL,
    GoogleOAuthError,
    GoogleOAuthTokens,
    build_google_oauth_authorization_url,
    build_pkce_code_challenge,
    consume_google_oauth_pending_authorization,
    exchange_google_oauth_code,
    refresh_google_oauth_access_token,
    store_google_oauth_pending_authorization,
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
    def __init__(self, payload: dict[str, object] | None = None) -> None:
        self.payload = payload or {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": GOOGLE_DRIVE_READONLY_SCOPE,
        }
        self.requests: list[Request] = []

    def __call__(self, request: Request) -> FakeResponse:
        self.requests.append(request)
        return FakeResponse(json.dumps(self.payload).encode())


def _request_body(request: Request) -> str:
    data = cast(bytes | None, request.data)
    return data.decode() if data else ""


def test_build_google_oauth_authorization_url() -> None:
    code_challenge = build_pkce_code_challenge("verifier-123")
    url = build_google_oauth_authorization_url(
        "client-id",
        "http://localhost:8501",
        "state-123",
        code_challenge=code_challenge,
    )

    parsed_url = urlparse(url)
    params = parse_qs(parsed_url.query)
    assert f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}" == GOOGLE_OAUTH_AUTH_URL
    assert params["client_id"] == ["client-id"]
    assert params["redirect_uri"] == ["http://localhost:8501"]
    assert params["scope"] == [GOOGLE_DRIVE_READONLY_SCOPE]
    assert params["access_type"] == ["offline"]
    assert params["include_granted_scopes"] == ["true"]
    assert params["prompt"] == ["consent"]
    assert params["state"] == ["state-123"]
    assert params["code_challenge"] == [code_challenge]
    assert params["code_challenge_method"] == ["S256"]


def test_build_google_oauth_authorization_url_requires_config() -> None:
    with pytest.raises(GoogleOAuthError):
        build_google_oauth_authorization_url("", "http://localhost:8501", "state")


def test_exchange_google_oauth_code_posts_authorization_code() -> None:
    opener = FakeOpener()

    tokens = exchange_google_oauth_code(
        "client-id",
        "client-secret",
        "http://localhost:8501",
        "auth-code",
        opener=opener,
    )

    assert tokens == GoogleOAuthTokens(
        access_token="access-token",
        token_type="Bearer",
        expires_in=3600,
        refresh_token="refresh-token",
        scope=GOOGLE_DRIVE_READONLY_SCOPE,
    )
    request = opener.requests[0]
    body = _request_body(request)
    params = parse_qs(body)
    assert params["grant_type"] == ["authorization_code"]
    assert params["code"] == ["auth-code"]
    assert params["client_id"] == ["client-id"]
    assert params["client_secret"] == ["client-secret"]


def test_exchange_google_oauth_code_supports_pkce_without_client_secret() -> None:
    opener = FakeOpener()

    tokens = exchange_google_oauth_code(
        "client-id",
        "",
        "http://localhost:8501",
        "auth-code",
        code_verifier="verifier-123",
        opener=opener,
    )

    assert tokens.access_token == "access-token"
    request = opener.requests[0]
    body = _request_body(request)
    params = parse_qs(body)
    assert params["client_id"] == ["client-id"]
    assert params["code_verifier"] == ["verifier-123"]
    assert "client_secret" not in params


def test_pending_authorization_can_be_consumed_once() -> None:
    store_google_oauth_pending_authorization("state-123", "verifier-123", now=100.0)

    pending_authorization = consume_google_oauth_pending_authorization("state-123", now=120.0)

    assert pending_authorization is not None
    assert pending_authorization.state == "state-123"
    assert pending_authorization.code_verifier == "verifier-123"
    assert consume_google_oauth_pending_authorization("state-123", now=121.0) is None


def test_pending_authorization_expires() -> None:
    store_google_oauth_pending_authorization("expired-state", "verifier-123", now=100.0)

    pending_authorization = consume_google_oauth_pending_authorization(
        "expired-state",
        now=701.0,
    )

    assert pending_authorization is None


def test_refresh_google_oauth_access_token_preserves_refresh_token() -> None:
    opener = FakeOpener({"access_token": "new-access-token", "token_type": "Bearer"})

    tokens = refresh_google_oauth_access_token(
        "client-id",
        "client-secret",
        "refresh-token",
        opener=opener,
    )

    assert tokens.access_token == "new-access-token"
    assert tokens.refresh_token == "refresh-token"
    body = _request_body(opener.requests[0])
    assert parse_qs(body)["grant_type"] == ["refresh_token"]


def test_refresh_google_oauth_access_token_supports_public_client() -> None:
    opener = FakeOpener({"access_token": "new-access-token", "token_type": "Bearer"})

    tokens = refresh_google_oauth_access_token(
        "client-id",
        "",
        "refresh-token",
        opener=opener,
    )

    assert tokens.access_token == "new-access-token"
    body = _request_body(opener.requests[0])
    params = parse_qs(body)
    assert params["client_id"] == ["client-id"]
    assert params["refresh_token"] == ["refresh-token"]
    assert "client_secret" not in params


def test_exchange_google_oauth_code_rejects_missing_access_token() -> None:
    with pytest.raises(GoogleOAuthError):
        exchange_google_oauth_code(
            "client-id",
            "client-secret",
            "http://localhost:8501",
            "auth-code",
            opener=FakeOpener({"token_type": "Bearer"}),
        )
