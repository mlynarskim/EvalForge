from __future__ import annotations

import json
from typing import Any

from app.evaluators.base import BaseEvaluator, EvaluationContext, EvaluationOutcome


def extract_json(text: str) -> tuple[Any | None, str | None, bool]:
    stripped = text.strip()
    try:
        return json.loads(stripped), None, False
    except json.JSONDecodeError as direct_error:
        decoder = json.JSONDecoder()
        candidates = [index for index, character in enumerate(stripped) if character in '[{"']
        for index in candidates:
            try:
                value, end = decoder.raw_decode(stripped[index:])
                trailing = stripped[index + end :].strip()
                surrounding_text = index > 0 or bool(trailing)
                return value, None, surrounding_text
            except json.JSONDecodeError:
                continue
        return None, str(direct_error), False


class JsonValidatorEvaluator(BaseEvaluator):
    key = "json_validator"

    async def evaluate(
        self, context: EvaluationContext, config: dict[str, Any]
    ) -> EvaluationOutcome:
        parsed, error, surrounding_text = extract_json(context.response)
        expected_root = config.get("root_type")
        root_matches = expected_root is None or type(parsed).__name__ == expected_root
        allow_surrounding = bool(config.get("allow_surrounding_text", False))
        passed = error is None and root_matches and (allow_surrounding or not surrounding_text)
        return EvaluationOutcome(
            self.key,
            float(passed),
            passed,
            {
                "parse_error": error,
                "surrounding_text": surrounding_text,
                "root_type": type(parsed).__name__ if parsed is not None else None,
            },
        )
