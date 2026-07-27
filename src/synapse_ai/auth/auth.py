from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from synapse_ai.models.user import AuthenticatedUser

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthResult:
    success: bool
    message: str
    user: AuthenticatedUser | None = None
    access_token: str | None = None
    refresh_token: str | None = None


def register_user(
    client: Any,
    email: str,
    password: str,
    email_redirect_to: str | None = None,
) -> AuthResult:
    payload: dict[str, object] = {"email": email, "password": password}
    if email_redirect_to:
        payload["options"] = {"email_redirect_to": email_redirect_to}

    try:
        response = client.auth.sign_up(payload)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Supabase sign-up failed: %s", exc.__class__.__name__)
        return AuthResult(
            False,
            "Não foi possível concluir o cadastro. Revise os dados e tente novamente.",
        )

    user = _extract_user(response)
    return AuthResult(
        success=True,
        message=(
            "Cadastro solicitado com sucesso. Confirme seu e-mail se essa etapa "
            "estiver habilitada."
        ),
        user=user,
    )


def login_user(client: Any, email: str, password: str) -> AuthResult:
    try:
        response = client.auth.sign_in_with_password({"email": email, "password": password})
    except Exception as exc:  # noqa: BLE001
        logger.warning("Supabase sign-in failed: %s", exc.__class__.__name__)
        return AuthResult(False, "E-mail ou senha inválidos.")

    user = _extract_user(response)
    access_token = _extract_nested_attr(response, "session", "access_token")
    refresh_token = _extract_nested_attr(response, "session", "refresh_token")
    if user is None or access_token is None:
        return AuthResult(False, "Não foi possível iniciar a sessão.")

    return AuthResult(
        success=True,
        message="Login realizado com sucesso.",
        user=user,
        access_token=access_token,
        refresh_token=refresh_token,
    )


def logout_user(client: Any) -> AuthResult:
    try:
        client.auth.sign_out()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Supabase sign-out failed: %s", exc.__class__.__name__)
        return AuthResult(False, "Não foi possível encerrar a sessão.")
    return AuthResult(True, "Sessão encerrada com sucesso.")


def get_current_user(client: Any, access_token: str | None = None) -> AuthenticatedUser | None:
    try:
        response = client.auth.get_user(access_token) if access_token else client.auth.get_user()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Supabase get-user failed: %s", exc.__class__.__name__)
        return None
    return _extract_user(response)


def restore_supabase_session(client: Any, access_token: str, refresh_token: str | None) -> bool:
    if not access_token or not refresh_token:
        return False
    try:
        client.auth.set_session(access_token, refresh_token)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Supabase session restore failed: %s", exc.__class__.__name__)
        return False
    return True


def _extract_user(response: Any) -> AuthenticatedUser | None:
    raw_user = _get_value(response, "user")
    if raw_user is None:
        return None

    user_id = _get_value(raw_user, "id") or _get_value(raw_user, "user_id")
    email = _get_value(raw_user, "email")
    if not isinstance(user_id, str) or not isinstance(email, str):
        return None
    return AuthenticatedUser(id=user_id, email=email)


def _extract_nested_attr(response: Any, parent: str, key: str) -> str | None:
    raw_parent = _get_value(response, parent)
    value = _get_value(raw_parent, key) if raw_parent is not None else None
    return value if isinstance(value, str) and value else None


def _get_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)
