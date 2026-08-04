from __future__ import annotations

from app.providers.anthropic_provider import AnthropicProvider
from app.providers.base import BaseModelProvider
from app.providers.gemini_provider import GeminiProvider
from app.providers.mistral_provider import MistralProvider
from app.providers.ollama_provider import OllamaProvider
from app.providers.openai_provider import OpenAIProvider
from app.providers.openrouter_provider import OpenRouterProvider


class ProviderRegistry:
    """Extensible registry mapping provider keys to adapter implementations."""

    _providers: dict[str, type[BaseModelProvider]] = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "gemini": GeminiProvider,
        "mistral": MistralProvider,
        "openrouter": OpenRouterProvider,
        "ollama": OllamaProvider,
    }

    @classmethod
    def create(
        cls, key: str, api_key: str | None = None, base_url: str | None = None
    ) -> BaseModelProvider:
        provider_class = cls._providers.get(key)
        if not provider_class:
            raise KeyError(f"Unknown provider: {key}")
        return provider_class(api_key=api_key, base_url=base_url)

    @classmethod
    def available_keys(cls) -> tuple[str, ...]:
        return tuple(cls._providers)

    @classmethod
    def register(cls, key: str, provider_class: type[BaseModelProvider]) -> None:
        cls._providers[key] = provider_class
