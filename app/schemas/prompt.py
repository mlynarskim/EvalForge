from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PromptCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    tags: list[str] = []
    system_prompt: str = ""
    user_template: str = Field(min_length=1, max_length=100_000)
    response_format: str = Field(default="text", pattern="^(text|json|json_schema)$")
    json_schema: dict[str, Any] | None = None


class PromptVersionCreate(BaseModel):
    system_prompt: str = ""
    user_template: str = Field(min_length=1, max_length=100_000)
    response_format: str = Field(default="text", pattern="^(text|json|json_schema)$")
    json_schema: dict[str, Any] | None = None
    change_note: str | None = None
