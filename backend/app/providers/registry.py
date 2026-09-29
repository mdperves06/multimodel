from functools import lru_cache

from app.config import get_settings
from app.providers.base import ProviderAdapter
from app.providers.mock import MockAdapter
from app.providers.openai import OpenAIAdapter


class UnknownProviderError(KeyError):
    pass


@lru_cache
def get_registry() -> dict[str, ProviderAdapter]:
    """Add future providers here (one line each)."""
    settings = get_settings()
    adapters: list[ProviderAdapter] = [OpenAIAdapter(base_url=settings.openai_base_url)]
    if settings.enable_mock_provider and not settings.is_production:
        adapters.append(MockAdapter())
    return {a.slug: a for a in adapters}


def get_adapter(slug: str) -> ProviderAdapter:
    try:
        return get_registry()[slug]
    except KeyError:
        raise UnknownProviderError(slug) from None


def register_adapter(adapter: ProviderAdapter) -> None:
    """Replace/add an adapter at runtime (used by tests to inject transports)."""
    get_registry()[adapter.slug] = adapter


def reset_registry() -> None:
    get_registry.cache_clear()
