from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

from synapse_ai.auth.session import is_authenticated


def require_auth(state: MutableMapping[str, Any] | None = None) -> bool:
    return is_authenticated(state)


def redirect_authenticated(default_page: str, state: MutableMapping[str, Any] | None = None) -> str:
    return "dashboard" if is_authenticated(state) else default_page


def private_page_allowed(page: str, state: MutableMapping[str, Any] | None = None) -> bool:
    private_pages = {"dashboard", "upload", "analysis"}
    return page not in private_pages or is_authenticated(state)
