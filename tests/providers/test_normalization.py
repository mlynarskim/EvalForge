from app.providers.base import TokenUsage
from app.providers.openai_provider import OpenAIProvider


def test_openai_usage_normalization_includes_reasoning_and_cache() -> None:
    provider = OpenAIProvider("test-secret")
    usage = provider.normalize_usage(
        {
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "prompt_tokens_details": {"cached_tokens": 20},
                "completion_tokens_details": {"reasoning_tokens": 12},
            }
        }
    )
    assert usage == TokenUsage(100, 50, 12, 20)


def test_provider_error_is_categorized_and_secret_is_redacted() -> None:
    provider = OpenAIProvider("test-secret")
    error = provider.normalize_error(RuntimeError("429 rate limit for test-secret"))
    assert error.category == "rate_limit"
    assert error.retryable is True
    assert "test-secret" not in str(error)


def test_provider_cost_calculation_handles_cached_input() -> None:
    cost = OpenAIProvider.calculate_cost(
        TokenUsage(input_tokens=1_000, output_tokens=500, cached_tokens=200),
        {
            "input_price_per_million": 2,
            "output_price_per_million": 4,
            "cached_input_price_per_million": 1,
        },
    )
    assert cost == 0.0038
