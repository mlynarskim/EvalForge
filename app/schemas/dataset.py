from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TestCaseInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    inputs: dict[str, Any]
    expected_output: Any | None = None
    expected_keywords: list[str] = []
    reference_context: str | None = None
    metadata: dict[str, Any] = {}
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    tags: list[str] = []
    test_cases: list[TestCaseInput] = Field(min_length=1)


class DatasetVersionCreate(BaseModel):
    change_note: str | None = None
    test_cases: list[TestCaseInput] = Field(min_length=1)
