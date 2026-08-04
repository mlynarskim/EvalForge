from __future__ import annotations

import csv
import io
import json

from app.schemas.dataset import TestCaseInput


class ImportService:
    """Parse bounded JSON and CSV datasets into validated test cases."""

    def parse_json(self, content: bytes) -> list[TestCaseInput]:
        data = json.loads(content)
        rows = data.get("test_cases", data) if isinstance(data, dict) else data
        if not isinstance(rows, list):
            raise ValueError("JSON input must contain an array of test cases")
        return [TestCaseInput.model_validate(row) for row in rows]

    def parse_csv(self, content: bytes) -> list[TestCaseInput]:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        cases = []
        for number, row in enumerate(reader, start=1):
            try:
                inputs = json.loads(row.get("inputs", "{}"))
                expected = (
                    json.loads(row["expected_output"]) if row.get("expected_output") else None
                )
                keywords = json.loads(row.get("expected_keywords", "[]"))
                metadata = json.loads(row.get("metadata", "{}"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in CSV row {number}") from exc
            cases.append(
                TestCaseInput(
                    name=row.get("name") or f"Case {number}",
                    inputs=inputs,
                    expected_output=expected,
                    expected_keywords=keywords,
                    reference_context=row.get("reference_context") or None,
                    metadata=metadata,
                    difficulty=row.get("difficulty") or "medium",
                )
            )
        return cases


import_service = ImportService()
