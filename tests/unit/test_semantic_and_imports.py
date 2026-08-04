import json

import pytest

from app.evaluators.base import EvaluationContext
from app.evaluators.semantic_similarity import SemanticSimilarityEvaluator
from app.services.import_service import ImportService


@pytest.mark.asyncio
async def test_semantic_similarity_uses_injected_embeddings() -> None:
    async def embed(_: list[str]) -> list[list[float]]:
        return [[1.0, 0.0], [0.8, 0.6]]

    outcome = await SemanticSimilarityEvaluator(embed).evaluate(
        EvaluationContext(response="answer", expected_output="reference"),
        {"threshold": 0.75},
    )
    assert outcome.score == pytest.approx(0.8)
    assert outcome.passed is True


@pytest.mark.asyncio
async def test_semantic_similarity_requires_expected_text() -> None:
    async def embed(_: list[str]) -> list[list[float]]:
        raise AssertionError("Embedding must not run")

    outcome = await SemanticSimilarityEvaluator(embed).evaluate(
        EvaluationContext(response="answer", expected_output={"answer": True}), {}
    )
    assert outcome.score is None
    assert outcome.passed is None


def test_json_and_csv_imports_validate_structured_columns() -> None:
    service = ImportService()
    payload = [
        {
            "name": "Case",
            "inputs": {"input_text": "Hello"},
            "expected_output": {"category": "question"},
            "expected_keywords": ["question"],
            "metadata": {"source": "test"},
            "difficulty": "easy",
        }
    ]
    json_cases = service.parse_json(json.dumps(payload).encode())
    assert json_cases[0].inputs == {"input_text": "Hello"}
    csv_content = (
        b"name,inputs,expected_output,expected_keywords,metadata,difficulty\n"
        b'Case,"{""input_text"":""Hello""}","{""category"":""question""}",'
        b'"[""question""]","{""source"":""test""}",easy\n'
    )
    csv_cases = service.parse_csv(csv_content)
    assert csv_cases[0].expected_keywords == ["question"]
