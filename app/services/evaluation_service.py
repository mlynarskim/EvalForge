from __future__ import annotations

from typing import Any

from app.evaluators.base import BaseEvaluator, EvaluationContext, EvaluationOutcome
from app.evaluators.contains_keywords import ContainsKeywordsEvaluator
from app.evaluators.exact_match import ExactMatchEvaluator
from app.evaluators.json_validator import JsonValidatorEvaluator
from app.evaluators.schema_validator import SchemaValidatorEvaluator


class EvaluationService:
    """Run configured deterministic evaluators over a normalized response."""

    def __init__(self) -> None:
        evaluators: list[BaseEvaluator] = [
            ExactMatchEvaluator(),
            JsonValidatorEvaluator(),
            SchemaValidatorEvaluator(),
            ContainsKeywordsEvaluator(),
        ]
        self._evaluators = {evaluator.key: evaluator for evaluator in evaluators}

    def register(self, evaluator: BaseEvaluator) -> None:
        self._evaluators[evaluator.key] = evaluator

    async def evaluate(
        self, context: EvaluationContext, configuration: dict[str, dict[str, Any]]
    ) -> list[EvaluationOutcome]:
        outcomes = []
        for key, config in configuration.items():
            evaluator = self._evaluators.get(key)
            if evaluator:
                outcomes.append(await evaluator.evaluate(context, config or {}))
        return outcomes


evaluation_service = EvaluationService()
