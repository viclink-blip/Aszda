"""The list of provider adapters ASZDA knows about.

To add a provider: write an adapter (see base.py), then add it to _default_adapters().
"""

from __future__ import annotations

from app.providers.anthropic_text import AnthropicTextAdapter
from app.providers.base import ProviderAdapter
from app.providers.openai_speech import OpenAISpeechAdapter
from app.providers.runway_video import RunwayVideoAdapter


def _default_adapters() -> dict[str, ProviderAdapter]:
    adapters: list[ProviderAdapter] = [AnthropicTextAdapter(), OpenAISpeechAdapter(), RunwayVideoAdapter()]
    return {a.name: a for a in adapters}


_registry: dict[str, ProviderAdapter] = _default_adapters()


def all_adapters() -> list[ProviderAdapter]:
    return list(_registry.values())


def get_adapter(name: str) -> ProviderAdapter | None:
    return _registry.get(name)


def register(adapter: ProviderAdapter) -> None:
    """Used by tests to add a fake provider."""
    _registry[adapter.name] = adapter


def reset() -> None:
    global _registry
    _registry = _default_adapters()
