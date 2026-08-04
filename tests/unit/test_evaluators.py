import pytest

from app.evaluators.base import EvaluationContext
from app.evaluators.contains_keywords import ContainsKeywordsEvaluator
from app.evaluators.exact_match import ExactMatchEvaluator
from app.evaluators.json_validator import JsonValidatorEvaluator, extract_json
from app.evaluators.schema_validator import SchemaValidatorEvaluator


@pytest.mark.asyncio
async def test_exact_match_normalizes_case_and_whitespace() -> None:
    outcome = await ExactMatchEvaluator().evaluate(
        EvaluationContext(response="  HELLO   world ", expected_output="hello world"), {}
    )
    assert outcome.passed is True
    assert outcome.score == 1.0


@pytest.mark.asyncio
async def test_exact_match_supports_numeric_tolerance() -> None:
    outcome = await ExactMatchEvaluator().evaluate(
        EvaluationContext(response="10.04", expected_output=10), {"numeric_tolerance": 0.05}
    )
    assert outcome.passed is True


def test_extract_json_detects_surrounding_text() -> None:
    parsed, error, surrounding = extract_json('Result: {"ok": true} done')
    assert parsed == {"ok": True}
    assert error is None
    assert surrounding is True


@pytest.mark.asyncio
async def test_json_validator_rejects_surrounding_text_by_default() -> None:
    outcome = await JsonValidatorEvaluator().evaluate(
        EvaluationContext(response='Result: {"ok": true}'), {}
    )
    assert outcome.passed is False
    assert outcome.details["surrounding_text"] is True


@pytest.mark.asyncio
async def test_schema_validator_returns_precise_paths() -> None:
    schema = {
        "type": "object",
        "required": ["priority"],
        "properties": {"priority": {"type": "string", "enum": ["high", "low"]}},
        "additionalProperties": False,
    }
    outcome = await SchemaValidatorEvaluator().evaluate(
        EvaluationContext(response='{"priority": 3, "extra": true}', json_schema=schema), {}
    )
    assert outcome.passed is False
    assert len(outcome.details["errors"]) == 3
    assert {item["validator"] for item in outcome.details["errors"]} == {
        "additionalProperties",
        "enum",
        "type",
    }


@pytest.mark.asyncio
async def test_keyword_score_is_partial() -> None:
    outcome = await ContainsKeywordsEvaluator().evaluate(
        EvaluationContext(
            response="A high priority complaint", expected_keywords=["high", "refund"]
        ),
        {"threshold": 0.5},
    )
    assert outcome.score == 0.5
    assert outcome.passed is True
    assert outcome.details["missing"] == ["refund"]
