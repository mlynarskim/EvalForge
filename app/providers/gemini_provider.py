from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.providers.base import (
    BaseModelProvider,
    GenerateRequest,
    GenerateResponse,
    ModelInfo,
    ProviderError,
    TokenUsage,
)


class GeminiProvider(BaseModelProvider):
    key = "gemini"
    default_base_url = "https://generativelanguage.googleapis.com/v1beta"
    supported_parameters = {"temperature", "max_output_tokens", "top_p"}

    @property
    def api_base(self) -> str:
        return (self.base_url or self.default_base_url).rstrip("/")

    async def list_models(self) -> list[ModelInfo]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(f"{self.api_base}/models", params={"key": self.api_key})
                response.raise_for_status()
            models = []
            for item in response.json().get("models", []):
                if "generateContent" not in item.get("supportedGenerationMethods", []):
                    continue
                model_id = item["name"].removeprefix("models/")
                models.append(
                    ModelInfo(
                        model_id=model_id,
                        display_name=item.get("displayName", model_id),
                        context_window=item.get("inputTokenLimit"),
                        max_output_tokens=item.get("outputTokenLimit"),
                    )
                )
            return models
        except Exception as exc:
            raise self.normalize_error(exc) from exc

    def _payload(self, request: GenerateRequest) -> dict[str, Any]:
        config: dict[str, Any] = {}
        names = {
            "temperature": "temperature",
            "top_p": "topP",
            "max_output_tokens": "maxOutputTokens",
        }
        for source, target in names.items():
            value = getattr(request, source)
            if value is not None:
                config[target] = value
        if request.response_format in {"json", "json_schema"}:
            config["responseMimeType"] = "application/json"
        if request.response_format == "json_schema" and request.json_schema:
            config["responseJsonSchema"] = request.json_schema
        return {
            "systemInstruction": {"parts": [{"text": request.system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": request.user_prompt}]}],
            "generationConfig": config,
        }

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        try:
            url = f"{self.api_base}/models/{request.model}:generateContent"
            async with httpx.AsyncClient(timeout=request.timeout) as client:
                response = await client.post(
                    url, params={"key": self.api_key}, json=self._payload(request)
                )
                response.raise_for_status()
            data = response.json()
            candidate = data["candidates"][0]
            text = "".join(
                part.get("text", "") for part in candidate.get("content", {}).get("parts", [])
            )
            return GenerateResponse(
                text=text,
                usage=self.normalize_usage(data),
                raw=data,
                finish_reason=candidate.get("finishReason"),
            )
        except Exception as exc:
            if isinstance(exc, ProviderError):
                raise
            raise self.normalize_error(exc) from exc

    async def stream(self, request: GenerateRequest) -> AsyncIterator[str]:
        response = await self.generate(request)
        yield response.text

    def normalize_usage(self, response: dict[str, Any]) -> TokenUsage:
        usage = response.get("usageMetadata", {})
        return TokenUsage(
            input_tokens=usage.get("promptTokenCount", 0),
            output_tokens=usage.get("candidatesTokenCount", 0),
            cached_tokens=usage.get("cachedContentTokenCount", 0),
            reasoning_tokens=usage.get("thoughtsTokenCount", 0),
        )

    async def validate_credentials(self) -> bool:
        await self.list_models()
        return True
