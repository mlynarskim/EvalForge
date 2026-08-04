from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class EvaluationContext:
    response: str
    expected_output: Any | None = None
    expected_keywords: list[str] = field(default_factory=list)
    json_schema: dict[str, Any] | None = None
    reference_context: str | None = None
    inputs: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EvaluationOutcome:
    evaluator: str
    score: float | None
    passed: bool | None
    details: dict[str, Any] = field(default_factory=dict)
    is_automated_judge: bool = False


class BaseEvaluator(ABC):
    key: str

    @abstractmethod
    async def evaluate(
        self, context: EvaluationContext, config: dict[str, Any]
    ) -> EvaluationOutcome:
        raise NotImplementedError
