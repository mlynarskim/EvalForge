from __future__ import annotations

import math
from collections.abc import Awaitable, Callable
from typing import Any

from app.evaluators.base import BaseEvaluator, EvaluationContext, EvaluationOutcome

EmbeddingFunction = Callable[[list[str]], Awaitable[list[list[float]]]]


class SemanticSimilarityEvaluator(BaseEvaluator):
    key = "semantic_similarity"

    def __init__(self, embed: EmbeddingFunction) -> None:
        self.embed = embed

    async def evaluate(
        self, context: EvaluationContext, config: dict[str, Any]
    ) -> EvaluationOutcome:
        expected = context.expected_output
        if not isinstance(expected, str):
            return EvaluationOutcome(self.key, None, None, {"error": "Expected text is missing"})
        actual_vector, expected_vector = await self.embed([context.response, expected])
        dot = sum(a * b for a, b in zip(actual_vector, expected_vector, strict=True))
        norm_a = math.sqrt(sum(value * value for value in actual_vector))
        norm_b = math.sqrt(sum(value * value for value in expected_vector))
        score = dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
        threshold = float(config.get("threshold", 0.8))
        return EvaluationOutcome(self.key, score, score >= threshold, {"threshold": threshold})
