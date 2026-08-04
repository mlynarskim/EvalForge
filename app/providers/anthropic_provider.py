from __future__ import annotations

import json
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


class AnthropicProvider(BaseModelProvider):
    key = "anthropic"
    default_base_url = "https://api.anthropic.com/v1"
    supported_parameters = {"temperature", "max_output_tokens", "top_p"}

    @property
    def api_base(self) -> str:
        return (self.base_url or self.default_base_url).rstrip("/")

    @property
    def headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key or "",
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    async def list_models(self) -> list[ModelInfo]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(f"{self.api_base}/models", headers=self.headers)
                response.raise_for_status()
            return [
                ModelInfo(item["id"], item.get("display_name", item["id"]))
                for item in response.json().get("data", [])
            ]
        except Exception as exc:
            raise self.normalize_error(exc) from exc

    def _payload(self, request: GenerateRequest, stream: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": request.model,
            "system": request.system_prompt,
            "messages": [{"role": "user", "content": request.user_prompt}],
            "max_tokens": request.max_output_tokens or 1024,
            "stream": stream,
        }
        for key in ("temperature", "top_p"):
            value = getattr(request, key)
            if value is not None:
                payload[key] = value
        return payload

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        try:
            async with httpx.AsyncClient(timeout=request.timeout) as client:
                response = await client.post(
                    f"{self.api_base}/messages",
                    headers=self.headers,
                    json=self._payload(request),
                )
                response.raise_for_status()
            data = response.json()
            text = "".join(block.get("text", "") for block in data.get("content", []))
            return GenerateResponse(
                text=text,
                usage=self.normalize_usage(data),
                raw=data,
                finish_reason=data.get("stop_reason"),
                provider_request_id=data.get("id"),
            )
        except Exception as exc:
            if isinstance(exc, ProviderError):
                raise
            raise self.normalize_error(exc) from exc

    async def stream(self, request: GenerateRequest) -> AsyncIterator[str]:
        try:
            async with httpx.AsyncClient(timeout=request.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.api_base}/messages",
                    headers=self.headers,
                    json=self._payload(request, True),
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data = json.loads(line[6:])
                        if data.get("type") == "content_block_delta":
                            text = data.get("delta", {}).get("text")
                            if text:
                                yield text
        except Exception as exc:
            raise self.normalize_error(exc) from exc

    def normalize_usage(self, response: dict[str, Any]) -> TokenUsage:
        usage = response.get("usage", {})
        return TokenUsage(
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cached_tokens=usage.get("cache_read_input_tokens", 0),
        )

    async def validate_credentials(self) -> bool:
        await self.list_models()
        return True
