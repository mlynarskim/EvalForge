from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from app.evaluators.base import BaseEvaluator, EvaluationContext, EvaluationOutcome
from app.evaluators.json_validator import extract_json


class SchemaValidatorEvaluator(BaseEvaluator):
    key = "schema_validator"

    async def evaluate(
        self, context: EvaluationContext, config: dict[str, Any]
    ) -> EvaluationOutcome:
        schema = context.json_schema or config.get("schema")
        if not schema:
            return EvaluationOutcome(self.key, None, None, {"error": "JSON Schema is missing"})
        parsed, parse_error, _ = extract_json(context.response)
        if parse_error:
            return EvaluationOutcome(
                self.key, 0.0, False, {"errors": [{"message": parse_error, "path": []}]}
            )
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        errors = sorted(validator.iter_errors(parsed), key=lambda item: list(item.path))
        details = [
            {
                "message": error.message,
                "path": list(error.absolute_path),
                "validator": error.validator,
            }
            for error in errors
        ]
        passed = not details
        return EvaluationOutcome(self.key, float(passed), passed, {"errors": details})
