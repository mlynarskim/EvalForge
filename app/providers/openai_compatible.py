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


class OpenAICompatibleProvider(BaseModelProvider):
    """Shared adapter for providers implementing the OpenAI chat API."""

    default_base_url = ""
    extra_headers: dict[str, str] = {}
    supported_parameters = BaseModelProvider.supported_parameters | {"seed"}

    @property
    def api_base(self) -> str:
        return (self.base_url or self.default_base_url).rstrip("/")

    @property
    def headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def list_models(self) -> list[ModelInfo]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(f"{self.api_base}/models", headers=self.headers)
                response.raise_for_status()
            return [
                ModelInfo(model_id=item["id"], display_name=item.get("name", item["id"]))
                for item in response.json().get("data", [])
                if item.get("id")
            ]
        except Exception as exc:
            raise self.normalize_error(exc) from exc

    def _payload(self, request: GenerateRequest, stream: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "stream": stream,
        }
        parameters = self.normalize_parameters(request)
        if "max_output_tokens" in parameters:
            parameters["max_tokens"] = parameters.pop("max_output_tokens")
        payload.update(parameters)
        if request.response_format == "json":
            payload["response_format"] = {"type": "json_object"}
        elif request.response_format == "json_schema" and request.json_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "evalforge_response", "schema": request.json_schema},
            }
        return payload

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        try:
            async with httpx.AsyncClient(timeout=request.timeout) as client:
                response = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers=self.headers,
                    json=self._payload(request),
                )
                response.raise_for_status()
            data = response.json()
            choice = data["choices"][0]
            content = choice.get("message", {}).get("content") or ""
            if isinstance(content, list):
                content = "".join(part.get("text", "") for part in content)
            return GenerateResponse(
                text=content,
                usage=self.normalize_usage(data),
                raw=data,
                finish_reason=choice.get("finish_reason"),
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
                    f"{self.api_base}/chat/completions",
                    headers=self.headers,
                    json=self._payload(request, stream=True),
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data: ") or line == "data: [DONE]":
                            continue
                        data = json.loads(line[6:])
                        text = data["choices"][0].get("delta", {}).get("content")
                        if text:
                            yield text
        except Exception as exc:
            raise self.normalize_error(exc) from exc

    def normalize_usage(self, response: dict[str, Any]) -> TokenUsage:
        usage = response.get("usage", {})
        details = usage.get("completion_tokens_details", {})
        input_details = usage.get("prompt_tokens_details", {})
        return TokenUsage(
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            reasoning_tokens=details.get("reasoning_tokens", 0),
            cached_tokens=input_details.get("cached_tokens", 0),
        )

    async def validate_credentials(self) -> bool:
        await self.list_models()
        return True
