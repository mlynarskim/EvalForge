from __future__ import annotations

from typing import Any

from app.evaluators.base import BaseEvaluator, EvaluationContext, EvaluationOutcome


class ContainsKeywordsEvaluator(BaseEvaluator):
    key = "contains_keywords"

    async def evaluate(
        self, context: EvaluationContext, config: dict[str, Any]
    ) -> EvaluationOutcome:
        response = context.response if config.get("case_sensitive") else context.response.casefold()
        keywords = context.expected_keywords or config.get("keywords", [])
        normalized = (
            keywords if config.get("case_sensitive") else [item.casefold() for item in keywords]
        )
        missing = [
            original
            for original, value in zip(keywords, normalized, strict=True)
            if value not in response
        ]
        score = (len(keywords) - len(missing)) / len(keywords) if keywords else 1.0
        threshold = float(config.get("threshold", 1.0))
        return EvaluationOutcome(self.key, score, score >= threshold, {"missing": missing})
