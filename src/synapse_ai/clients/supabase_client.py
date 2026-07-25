from __future__ import annotations

import logging
from collections.abc import Callable
from functools import lru_cache
from typing import Any

from synapse_ai.config import AppConfig

logger = logging.getLogger(__name__)


def create_supabase_client(
    config: AppConfig,
    client_factory: Callable[[str, str], Any] | None = None,
) -> Any:
    factory = client_factory or _default_factory()
    try:
        return factory(config.supabase.url, config.supabase.publishable_key)
    except Exception as exc:  # noqa: BLE001
        logger.error("Supabase client initialization failed: %s", exc.__class__.__name__)
        raise RuntimeError("Não foi possível inicializar o cliente Supabase.") from exc


@lru_cache(maxsize=1)
def get_supabase_client(url: str, publishable_key: str) -> Any:
    return _default_factory()(url, publishable_key)


def _default_factory() -> Callable[[str, str], Any]:
    from supabase import create_client

    return create_client
