from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from synapse_ai.config import AppConfig

logger = logging.getLogger(__name__)


def create_openai_client(
    config: AppConfig,
    client_factory: Callable[..., Any] | None = None,
) -> Any:
    factory = client_factory or _default_factory()
    try:
        return factory(api_key=config.openai.api_key)
    except Exception as exc:  # noqa: BLE001
        logger.error("OpenAI client initialization failed: %s", exc.__class__.__name__)
        raise RuntimeError("Não foi possível inicializar o cliente OpenAI.") from exc


def test_openai_connectivity(client: Any) -> bool:
    try:
        client.models.list()
    except Exception as exc:  # noqa: BLE001
        logger.warning("OpenAI connectivity check failed: %s", exc.__class__.__name__)
        return False
    return True


def _default_factory() -> Callable[..., Any]:
    from openai import OpenAI

    return OpenAI
