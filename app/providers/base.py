from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ModelInfo:
    model_id: str
    display_name: str
    family: str | None = None
    context_window: int | None = None
    max_output_tokens: int | None = None
    capabilities: set[str] = field(default_factory=set)


@dataclass(slots=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cached_tokens: int = 0


@dataclass(slots=True)
class GenerateRequest:
    model: str
    system_prompt: str
    user_prompt: str
    temperature: float | None = None
    max_output_tokens: int | None = None
    top_p: float | None = None
    seed: int | None = None
    response_format: str = "text"
    json_schema: dict[str, Any] | None = None
    timeout: float = 60.0


@dataclass(slots=True)
class GenerateResponse:
    text: str
    usage: TokenUsage
    raw: dict[str, Any]
    finish_reason: str | None = None
    provider_request_id: str | None = None


class ProviderError(RuntimeError):
    def __init__(self, category: str, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.category = category
        self.retryable = retryable


class BaseModelProvider(ABC):
    """Contract implemented by every external model provider adapter."""

    key: str
    supported_parameters: set[str] = {
        "temperature",
        "max_output_tokens",
        "top_p",
    }

    def __init__(self, api_key: str | None, base_url: str | None = None) -> None:
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        raise NotImplementedError

    @abstractmethod
    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        raise NotImplementedError

    @abstractmethod
    async def stream(self, request: GenerateRequest) -> AsyncIterator[str]:
        raise NotImplementedError
        yield ""

    @abstractmethod
    def normalize_usage(self, response: dict[str, Any]) -> TokenUsage:
        raise NotImplementedError

    def normalize_error(self, error: Exception) -> ProviderError:
        message = str(error).replace(self.api_key or "<never>", "[REDACTED]")
        lowered = message.lower()
        if "401" in lowered or "authentication" in lowered:
            return ProviderError("authentication", "Provider authentication failed")
        if "403" in lowered or "permission" in lowered:
            return ProviderError("permission", "Provider permission denied")
        if "429" in lowered or "rate limit" in lowered:
            return ProviderError("rate_limit", "Provider rate limit reached", retryable=True)
        if "timeout" in lowered:
            return ProviderError("timeout", "Provider request timed out", retryable=True)
        if "500" in lowered or "502" in lowered or "503" in lowered:
            return ProviderError(
                "provider_unavailable", "Provider is temporarily unavailable", True
            )
        return ProviderError("unknown", message[:500])

    @staticmethod
    def calculate_cost(usage: TokenUsage, pricing: dict[str, float | None]) -> float:
        input_price = pricing.get("input_price_per_million") or 0.0
        output_price = pricing.get("output_price_per_million") or 0.0
        cached_price = pricing.get("cached_input_price_per_million") or input_price
        billable_input = max(usage.input_tokens - usage.cached_tokens, 0)
        return (
            billable_input * input_price
            + usage.cached_tokens * cached_price
            + usage.output_tokens * output_price
        ) / 1_000_000

    @abstractmethod
    async def validate_credentials(self) -> bool:
        raise NotImplementedError

    def normalize_parameters(self, request: GenerateRequest) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for name in self.supported_parameters:
            value = getattr(request, name, None)
            if value is not None:
                values[name] = value
        return values
