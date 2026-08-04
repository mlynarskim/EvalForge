from __future__ import annotations

import json
import math
import re
from contextlib import suppress
from typing import Any

from app.evaluators.base import BaseEvaluator, EvaluationContext, EvaluationOutcome


def _normalize_text(value: str, case_sensitive: bool, normalize_whitespace: bool) -> str:
    if normalize_whitespace:
        value = re.sub(r"\s+", " ", value).strip()
    if not case_sensitive:
        value = value.casefold()
    return value


class ExactMatchEvaluator(BaseEvaluator):
    key = "exact_match"

    async def evaluate(
        self, context: EvaluationContext, config: dict[str, Any]
    ) -> EvaluationOutcome:
        expected = context.expected_output
        actual: Any = context.response
        if isinstance(expected, (dict, list, bool, int, float)):
            with suppress(json.JSONDecodeError):
                actual = json.loads(context.response)
        tolerance = float(config.get("numeric_tolerance", 0.0))
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            passed = math.isclose(float(actual), float(expected), abs_tol=tolerance)
        elif isinstance(expected, str):
            expected = _normalize_text(
                expected,
                bool(config.get("case_sensitive", False)),
                bool(config.get("normalize_whitespace", True)),
            )
            actual = _normalize_text(
                str(actual),
                bool(config.get("case_sensitive", False)),
                bool(config.get("normalize_whitespace", True)),
            )
            passed = actual == expected
        else:
            passed = actual == expected
        return EvaluationOutcome(self.key, float(passed), passed, {"expected": expected})
